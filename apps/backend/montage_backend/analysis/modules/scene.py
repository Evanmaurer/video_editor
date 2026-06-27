from __future__ import annotations

from pathlib import Path

from montage_backend.analysis.base import AnalysisModuleId, AnalysisOutput, AnalysisRunContext, Analyzer
from montage_backend.analysis.scene_detection import build_scene_analysis_result
from montage_backend.media.ffmpeg_runner import FFmpegRunner, ProcessingContext
from montage_backend.media.processor import MediaProcessor


class SceneAnalyzer(Analyzer):
    module_id = AnalysisModuleId.SCENE
    version = "scene-analyzer-v1.0"

    SCENE_THRESHOLD = 0.05
    BLACK_MIN_DURATION = 0.08
    BLACK_PIXEL_THRESHOLD = 0.10
    FREEZE_NOISE_DB = -60
    FREEZE_MIN_DURATION = 0.5

    def __init__(
        self,
        processor: MediaProcessor | None = None,
        runner: FFmpegRunner | None = None,
    ) -> None:
        self._processor = processor or MediaProcessor()
        self._runner = runner or self._processor.runner

    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
        return f"{self.module_id.value}:{self.version}:{source_fingerprint}:fps={fps_part}"

    async def analyze(
        self,
        ctx: AnalysisRunContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
        frame_count: int | None,
    ) -> AnalysisOutput:
        video = Path(video_path)
        processing_ctx = self._build_processing_context(ctx)

        await ctx.report(0.0, "Probing video")
        ctx.check_cancelled()
        probe = await self._processor.probe(video, ctx=processing_ctx)
        resolved_duration_ms = duration_ms if duration_ms is not None else probe.duration_ms
        resolved_frame_rate = frame_rate if frame_rate is not None else probe.frame_rate
        resolved_frame_count = frame_count if frame_count is not None else probe.frame_count
        duration_s = resolved_duration_ms / 1000.0

        fingerprint = ctx.source_fingerprint
        cache_key = self.cache_key(fingerprint, frame_rate=resolved_frame_rate)

        await ctx.report(0.1, "Detecting scene changes")
        scene_stderr = await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-i",
                str(video),
                "-filter:v",
                f"select='gt(scene,{self.SCENE_THRESHOLD})',showinfo",
                "-f",
                "null",
                "-",
            ],
            ctx=processing_ctx,
            operation="scene_detect",
            duration_seconds=duration_s,
        )
        ctx.check_cancelled()

        await ctx.report(0.45, "Detecting black frames")
        black_stderr = await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-i",
                str(video),
                "-vf",
                (
                    f"blackdetect=d={self.BLACK_MIN_DURATION}:"
                    f"pix_th={self.BLACK_PIXEL_THRESHOLD}"
                ),
                "-f",
                "null",
                "-",
            ],
            ctx=processing_ctx,
            operation="black_detect",
            duration_seconds=duration_s,
        )
        ctx.check_cancelled()

        await ctx.report(0.75, "Detecting freeze frames")
        freeze_stderr = await self._runner.run(
            [
                self._runner.ffmpeg_bin,
                "-i",
                str(video),
                "-vf",
                (
                    f"freezedetect=n={self.FREEZE_NOISE_DB}dB:"
                    f"d={self.FREEZE_MIN_DURATION}"
                ),
                "-f",
                "null",
                "-",
            ],
            ctx=processing_ctx,
            operation="freeze_detect",
            duration_seconds=duration_s,
        )

        result = build_scene_analysis_result(
            analyzer_version=self.version,
            cache_key=cache_key,
            frame_rate=resolved_frame_rate,
            frame_count=resolved_frame_count,
            duration_ms=resolved_duration_ms,
            scene_stderr=scene_stderr,
            black_stderr=black_stderr,
            freeze_stderr=freeze_stderr,
        )

        await ctx.report(1.0, f"Found {len(result.segments)} scenes")
        avg_confidence = (
            sum(segment.confidence for segment in result.segments) / len(result.segments)
            if result.segments
            else 1.0
        )
        return AnalysisOutput(
            module_id=self.module_id.value,
            analyzer_version=self.version,
            cache_key=cache_key,
            payload=result.model_dump(),
            confidence=avg_confidence,
            reasoning=f"Detected {len(result.events)} boundary events",
        )

    def _build_processing_context(self, ctx: AnalysisRunContext) -> ProcessingContext:
        processing_ctx = ProcessingContext()

        async def on_progress(_operation: str, progress: float, message: str) -> None:
            if ctx.cancel_requested:
                processing_ctx.cancel_event.set()
            ctx.check_cancelled()
            await ctx.report(progress, message)

        processing_ctx.on_progress = on_progress
        return processing_ctx
