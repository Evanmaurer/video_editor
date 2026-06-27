from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from montage_backend.logging import get_logger
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.media import (
    MediaProcessingError,
    ProcessingCancelledError,
    ProcessingPausedError,
)
from montage_backend.models.domain.render import (
    RenderError,
    RenderJobDetail,
    RenderJobNotFoundError,
    RenderJobStatus,
    RenderJobSummary,
    RenderLogResponse,
    RenderPresetInfo,
    StartRenderRequest,
)
from montage_backend.models.domain.timeline import TimelineDocument
from montage_backend.render.encoder import detect_hardware_encoders
from montage_backend.render.graph_builder import (
    build_ffmpeg_command,
    collect_export_segments,
    command_preview,
    export_duration_ms,
)
from montage_backend.render.presets import get_preset, list_preset_infos, resolve_video_encoder
from montage_backend.services.media_service import MediaService
from montage_backend.services.project_service import ProjectService
from montage_backend.services.timeline_service import TimelineService
from montage_backend.ws.hub import ws_hub

logger = get_logger(__name__)

MAX_LOG_LINES = 10_000


@dataclass
class RenderJobRecord:
    id: str
    project_id: str
    timeline_id: str
    preset_id: str
    status: RenderJobStatus
    progress: float = 0.0
    output_path: str | None = None
    output_name: str | None = None
    error_message: str | None = None
    eta_seconds: float | None = None
    elapsed_seconds: float = 0.0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    ffmpeg_command: str | None = None
    hardware_encoding: bool = False
    use_hardware_encoding: bool = True
    resume_from_ms: int = 0
    total_duration_ms: int = 0
    current_run_duration_ms: int = 0
    current_run_progress: float = 0.0
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    _started_at: float | None = None
    _run_task: asyncio.Task[None] | None = None


class RenderService:
    def __init__(
        self,
        project_service: ProjectService,
        timeline_service: TimelineService,
        media_service: MediaService,
        runner: FFmpegRunner,
    ) -> None:
        self._project_service = project_service
        self._timeline_service = timeline_service
        self._media_service = media_service
        self._runner = runner
        self._jobs: dict[str, RenderJobRecord] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._hw_encoders: set[str] | None = None
        self._active_job_id: str | None = None

    async def _ensure_hw_encoders(self) -> set[str]:
        if self._hw_encoders is None:
            self._hw_encoders = await detect_hardware_encoders(self._runner.ffmpeg_bin)
        return self._hw_encoders

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    async def list_presets(self) -> list[RenderPresetInfo]:
        hw = await self._ensure_hw_encoders()
        return list_preset_infos(hw)

    async def start_render(
        self,
        project_id: str,
        request: StartRenderRequest,
    ) -> RenderJobSummary:
        try:
            preset = get_preset(request.preset_id)
        except KeyError as exc:
            raise RenderError(f"Unknown export preset: {request.preset_id}") from exc

        if request.timeline_id:
            timeline = await self._timeline_service.get_timeline(project_id, request.timeline_id)
        else:
            timeline = await self._timeline_service.get_or_create_active(project_id)

        video_segments, _ = collect_export_segments(timeline)
        if not video_segments:
            raise RenderError("Timeline has no video clips to export")

        project = await self._project_service.get_project(project_id)
        exports_dir = Path(project.root_path) / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)

        output_name = request.output_name or f"export_{timeline.name.replace(' ', '_')}_{preset.id}.mp4"
        if not output_name.endswith(".mp4"):
            output_name = f"{output_name}.mp4"
        output_path = str(exports_dir / output_name)

        job_id = new_uuid()
        job = RenderJobRecord(
            id=job_id,
            project_id=project_id,
            timeline_id=timeline.id,
            preset_id=preset.id,
            status=RenderJobStatus.QUEUED,
            output_path=output_path,
            output_name=output_name,
            use_hardware_encoding=request.use_hardware_encoding,
            total_duration_ms=export_duration_ms(timeline),
        )
        self._jobs[job_id] = job
        self._ensure_worker()
        await self._queue.put(job_id)
        await self._broadcast_job(job)
        return self._to_summary(job)

    async def list_jobs(self, project_id: str) -> list[RenderJobSummary]:
        return [
            self._to_summary(job)
            for job in self._jobs.values()
            if job.project_id == project_id
        ]

    async def get_job(self, project_id: str, job_id: str) -> RenderJobDetail:
        job = self._get_job(project_id, job_id)
        return self._to_detail(job)

    async def get_logs(self, project_id: str, job_id: str) -> RenderLogResponse:
        job = self._get_job(project_id, job_id)
        lines = list(job.logs)
        return RenderLogResponse(job_id=job.id, lines=lines, total_lines=len(lines))

    async def pause_job(self, project_id: str, job_id: str) -> RenderJobSummary:
        job = self._get_job(project_id, job_id)
        if job.status != RenderJobStatus.RUNNING:
            raise RenderError("Only running export jobs can be paused")
        job.pause_event.set()
        return self._to_summary(job)

    async def resume_job(self, project_id: str, job_id: str) -> RenderJobSummary:
        job = self._get_job(project_id, job_id)
        if job.status != RenderJobStatus.PAUSED:
            raise RenderError("Only paused export jobs can be resumed")
        job.status = RenderJobStatus.QUEUED
        job.pause_event = asyncio.Event()
        job.cancel_event = asyncio.Event()
        job.updated_at = utc_now_iso()
        await self._queue.put(job.id)
        await self._broadcast_job(job)
        return self._to_summary(job)

    async def cancel_job(self, project_id: str, job_id: str) -> RenderJobSummary:
        job = self._get_job(project_id, job_id)
        if job.status in {RenderJobStatus.COMPLETED, RenderJobStatus.CANCELLED}:
            return self._to_summary(job)
        job.cancel_event.set()
        if job.status == RenderJobStatus.RUNNING:
            self._runner.cancel_all()
        elif job.status == RenderJobStatus.QUEUED:
            job.status = RenderJobStatus.CANCELLED
            job.updated_at = utc_now_iso()
            await self._broadcast_job(job)
        return self._to_summary(job)

    async def shutdown(self) -> None:
        for job in self._jobs.values():
            if job.status in {RenderJobStatus.RUNNING, RenderJobStatus.QUEUED}:
                job.cancel_event.set()
        self._runner.cancel_all()
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def _get_job(self, project_id: str, job_id: str) -> RenderJobRecord:
        job = self._jobs.get(job_id)
        if job is None or job.project_id != project_id:
            raise RenderJobNotFoundError(f"Render job not found: {job_id}")
        return job

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = self._jobs.get(job_id)
            if job is None:
                continue
            if job.cancel_event.is_set():
                job.status = RenderJobStatus.CANCELLED
                job.updated_at = utc_now_iso()
                await self._broadcast_job(job)
                continue
            if job.status == RenderJobStatus.COMPLETED:
                continue
            self._active_job_id = job_id
            try:
                await self._execute_job(job)
            except Exception:
                logger.exception("render_worker_failed", job_id=job_id)
            finally:
                self._active_job_id = None

    async def _execute_job(self, job: RenderJobRecord) -> None:
        job.status = RenderJobStatus.RUNNING
        job.pause_event = asyncio.Event()
        job._started_at = time.monotonic()
        job.updated_at = utc_now_iso()
        await self._broadcast_job(job)

        try:
            timeline = await self._timeline_service.get_timeline(job.project_id, job.timeline_id)
            preset = get_preset(job.preset_id)
            hw = await self._ensure_hw_encoders()
            encoder_name, encoder_opts = resolve_video_encoder(
                preset,
                hw,
                use_hardware=job.use_hardware_encoding,
            )
            job.hardware_encoding = encoder_name not in {preset.video_codec}

            media_paths = await self._resolve_media_paths(job.project_id, timeline, job.resume_from_ms)
            video_segments, audio_segments = collect_export_segments(
                timeline,
                resume_from_ms=job.resume_from_ms,
            )
            if not video_segments:
                raise RenderError("Nothing left to export at current resume position")

            output_path = job.output_path
            assert output_path is not None
            args, run_duration_s = build_ffmpeg_command(
                ffmpeg_bin=self._runner.ffmpeg_bin,
                preset=preset,
                video_segments=video_segments,
                audio_segments=audio_segments,
                media_paths=media_paths,
                output_path=output_path,
                video_encoder=encoder_name,
                encoder_options=encoder_opts,
            )
            job.ffmpeg_command = command_preview(args)
            job.logs.append(f"[montage] starting export preset={preset.id} encoder={encoder_name}")
            job.logs.append(job.ffmpeg_command)

            job.current_run_duration_ms = max(int(run_duration_s * 1000), 1)
            job.current_run_progress = 0.0

            async def on_progress(_operation: str, progress: float, message: str) -> None:
                run_fraction = min(max(progress, 0.0), 1.0)
                job.current_run_progress = run_fraction
                exported_ms = job.resume_from_ms + int(run_fraction * job.current_run_duration_ms)
                job.progress = min(exported_ms / max(job.total_duration_ms, 1), 0.999)
                if job._started_at is not None:
                    elapsed = time.monotonic() - job._started_at
                    job.elapsed_seconds = elapsed
                    if job.progress > 0.01:
                        job.eta_seconds = max(elapsed / job.progress - elapsed, 0.0)
                job.updated_at = utc_now_iso()
                await self._broadcast_job(job, message=message)

            async def on_log_line(line: str) -> None:
                job.logs.append(line)

            ctx = ProcessingContext(
                cancel_event=job.cancel_event,
                pause_event=job.pause_event,
                on_progress=on_progress,
                on_log_line=on_log_line,
            )

            await self._runner.run(
                args,
                ctx=ctx,
                operation="render",
                duration_seconds=run_duration_s,
            )

            job.progress = 1.0
            job.status = RenderJobStatus.COMPLETED
            job.eta_seconds = 0.0
            job.error_message = None
            job.updated_at = utc_now_iso()
            job.logs.append("[montage] export completed")
            await self._broadcast_job(job)

        except ProcessingPausedError:
            job.resume_from_ms += int(job.current_run_progress * job.current_run_duration_ms)
            job.progress = job.resume_from_ms / max(job.total_duration_ms, 1)
            job.status = RenderJobStatus.PAUSED
            job.updated_at = utc_now_iso()
            job.logs.append("[montage] export paused")
            await self._broadcast_job(job)

        except ProcessingCancelledError:
            job.status = RenderJobStatus.CANCELLED
            job.updated_at = utc_now_iso()
            job.logs.append("[montage] export cancelled")
            await self._broadcast_job(job)

        except (MediaProcessingError, RenderError) as exc:
            job.status = RenderJobStatus.FAILED
            job.error_message = exc.message
            job.updated_at = utc_now_iso()
            job.logs.append(f"[montage] export failed: {exc.message}")
            await self._broadcast_job(job)

    async def _resolve_media_paths(
        self,
        project_id: str,
        timeline: TimelineDocument,
        resume_from_ms: int,
    ) -> dict[str, str]:
        video_segments, audio_segments = collect_export_segments(
            timeline,
            resume_from_ms=resume_from_ms,
        )
        media_ids: set[str] = set()
        for segment in [*video_segments, *audio_segments]:
            if hasattr(segment, "media_item_id"):
                media_ids.add(segment.media_item_id)

        paths: dict[str, str] = {}
        for media_id in media_ids:
            media = await self._media_service.get_media_item(project_id, media_id)
            path = Path(media.file_path)
            if not path.is_file():
                raise RenderError(f"Media file missing for export: {path}")
            paths[media_id] = str(path)
        return paths

    async def _broadcast_job(self, job: RenderJobRecord, *, message: str | None = None) -> None:
        event = {
            "type": "render.progress",
            "job_id": job.id,
            "project_id": job.project_id,
            "status": job.status.value,
            "progress": job.progress,
            "eta_seconds": job.eta_seconds,
            "elapsed_seconds": job.elapsed_seconds,
            "output_path": job.output_path,
            "error_message": job.error_message,
            "message": message,
        }
        await ws_hub.broadcast(event)

    def _to_summary(self, job: RenderJobRecord) -> RenderJobSummary:
        return RenderJobSummary(
            id=job.id,
            project_id=job.project_id,
            timeline_id=job.timeline_id,
            preset_id=job.preset_id,
            status=job.status,
            progress=job.progress,
            output_path=job.output_path,
            error_message=job.error_message,
            eta_seconds=job.eta_seconds,
            elapsed_seconds=job.elapsed_seconds,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    def _to_detail(self, job: RenderJobRecord) -> RenderJobDetail:
        summary = self._to_summary(job)
        return RenderJobDetail(
            **summary.model_dump(),
            ffmpeg_command=job.ffmpeg_command,
            hardware_encoding=job.hardware_encoding,
            log_tail=list(job.logs)[-200:],
        )
