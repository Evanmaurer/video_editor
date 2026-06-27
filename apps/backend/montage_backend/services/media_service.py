from __future__ import annotations

import asyncio
from pathlib import Path

from montage_backend.jobs.import_queue import ImportJobQueue
from montage_backend.logging import get_logger
from montage_backend.media.cache import build_cache_paths, invalidate_cache
from montage_backend.media.ffmpeg_runner import ProcessingContext
from montage_backend.media.hash import compute_sha256_async
from montage_backend.media.paths import expand_import_paths
from montage_backend.media.processor import MediaProcessor
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.media import (
    ImportMediaResponse,
    ImportMediaResult,
    ImportStatus,
    MediaItem,
    MediaListQuery,
    MediaNotFoundError,
    MediaProcessingError,
    MediaRole,
    MediaType,
    ProcessingCancelledError,
    ProcessingStatus,
    StorageMode,
    UpdateMediaRequest,
    new_media_item,
)
from montage_backend.repositories.media_repo import (
    MediaRepository,
    link_or_copy_source,
)
from montage_backend.services.project_service import ProjectService

logger = get_logger(__name__)


class MediaService:
    def __init__(
        self,
        project_service: ProjectService,
        processor: MediaProcessor | None = None,
        worker_count: int = 2,
    ) -> None:
        self._project_service = project_service
        self._processor = processor or MediaProcessor()
        self._repo = MediaRepository()
        self._queue = ImportJobQueue(max_workers=worker_count)
        self._active_contexts: dict[str, ProcessingContext] = {}
        self._import_tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def processor(self) -> MediaProcessor:
        return self._processor

    @property
    def queue(self) -> ImportJobQueue:
        return self._queue

    def set_worker_count(self, worker_count: int) -> None:
        self._queue.set_max_workers(worker_count)

    async def import_files(
        self,
        project_id: str,
        paths: list[str],
        role: MediaRole = MediaRole.CLIP,
        storage_mode: StorageMode = StorageMode.COPY,
        *,
        wait: bool = False,
    ) -> ImportMediaResponse:
        project = await self._project_service.get_project(project_id)
        project_root = Path(project.root_path)
        session_factory = await self._project_service._ensure_project_db(project_root)

        imported: list[ImportMediaResult] = []
        skipped: list[str] = []
        duplicates: list[ImportMediaResult] = []
        pending_tasks: list[asyncio.Task[None]] = []

        sources = expand_import_paths(paths)
        if not sources:
            return ImportMediaResponse(imported=[], skipped=paths, duplicates=[])

        for source in sources:
            file_hash = await compute_sha256_async(source)

            async with session_factory() as session:
                existing_hash = await self._repo.get_by_sha256(session, project_id, file_hash)

            if existing_hash is not None and existing_hash.import_status != ImportStatus.ERROR:
                duplicates.append(
                    ImportMediaResult(
                        media_id=existing_hash.id,
                        file_name=source.name,
                        status=ImportStatus.DUPLICATE,
                        sha256_hash=file_hash,
                    ),
                )
                continue

            media_id, media, task = await self._start_import(
                project_id=project_id,
                project_root=project_root,
                session_factory=session_factory,
                source=source,
                role=role,
                storage_mode=storage_mode,
                file_hash=file_hash,
            )
            pending_tasks.append(task)

            imported.append(
                ImportMediaResult(
                    media_id=media_id,
                    file_name=media.file_name,
                    status=ImportStatus.PROCESSING,
                    sha256_hash=file_hash,
                ),
            )

        if wait and pending_tasks:
            await asyncio.gather(*pending_tasks)
            for idx, result in enumerate(imported):
                async with session_factory() as session:
                    final = await self._repo.get_by_id(session, result.media_id)
                if final:
                    result.status = final.import_status
                    result.error = final.error_message

        return ImportMediaResponse(imported=imported, skipped=skipped, duplicates=duplicates)

    async def _start_import(
        self,
        *,
        project_id: str,
        project_root: Path,
        session_factory,
        source: Path,
        role: MediaRole,
        storage_mode: StorageMode,
        file_hash: str,
    ) -> tuple[str, MediaItem, asyncio.Task[None]]:
        suffix = source.suffix.lower() or ".mp4"
        media = new_media_item(
            project_id=project_id,
            file_path=source,
            role=role,
            media_type=MediaType.VIDEO,
            storage_mode=storage_mode,
            source_path=str(source),
            sha256_hash=file_hash,
        )
        cache_paths = build_cache_paths(project_root, media.id, suffix)
        original_dest = Path(cache_paths.original_path)
        processing_path = link_or_copy_source(
            source,
            original_dest,
            storage_mode=storage_mode,
        )
        media.file_path = str(processing_path)
        media.import_status = ImportStatus.PROCESSING
        media.proxy_status = ProcessingStatus.PROCESSING
        media.waveform_status = ProcessingStatus.PROCESSING
        media.scene_status = ProcessingStatus.PROCESSING

        async with session_factory() as session:
            await self._repo.create(session, media)

        ctx = ProcessingContext()
        self._active_contexts[media.id] = ctx

        async def run_job() -> None:
            await self._queue.run(
                self._run_import(project_root, media.id, session_factory, ctx),
            )

        task = asyncio.create_task(run_job())
        self._import_tasks[media.id] = task
        return media.id, media, task

    async def cancel_import(self, media_id: str) -> None:
        ctx = self._active_contexts.get(media_id)
        if ctx is not None:
            ctx.cancel_event.set()
            self._processor.runner.cancel_all()
        task = self._import_tasks.get(media_id)
        if task is not None:
            await task

    async def get_media_item(self, project_id: str, media_id: str) -> MediaItem:
        project = await self._project_service.get_project(project_id)
        session_factory = await self._project_service._ensure_project_db(Path(project.root_path))
        async with session_factory() as session:
            media = await self._repo.get_by_id(session, media_id)
            if media is None or media.project_id != project_id:
                raise MediaNotFoundError(f"Media item not found: {media_id}")
            return media

    async def list_media(
        self,
        project_id: str,
        query: MediaListQuery | None = None,
    ) -> list[MediaItem]:
        project = await self._project_service.get_project(project_id)
        session_factory = await self._project_service._ensure_project_db(Path(project.root_path))
        async with session_factory() as session:
            return await self._repo.list_by_project(session, project_id, query)

    async def update_media(
        self,
        project_id: str,
        media_id: str,
        updates: UpdateMediaRequest,
    ) -> MediaItem:
        media = await self.get_media_item(project_id, media_id)
        if updates.tags is not None:
            media.tags = sorted({tag.strip() for tag in updates.tags if tag.strip()})
        if updates.is_favorite is not None:
            media.is_favorite = updates.is_favorite
        media.updated_at = utc_now_iso()

        project = await self._project_service.get_project(project_id)
        session_factory = await self._project_service._ensure_project_db(Path(project.root_path))
        async with session_factory() as session:
            return await self._repo.update(session, media)

    async def delete_media(self, project_id: str, media_id: str) -> None:
        project = await self._project_service.get_project(project_id)
        project_root = Path(project.root_path)
        media = await self.get_media_item(project_id, media_id)

        await self.cancel_import(media_id)
        invalidate_cache(project_root, media_id)

        session_factory = await self._project_service._ensure_project_db(project_root)
        async with session_factory() as session:
            await self._repo.delete(session, media_id)

        logger.info("media_deleted", media_id=media_id, file_name=media.file_name)

    async def _run_import(
        self,
        project_root: Path,
        media_id: str,
        session_factory,
        ctx: ProcessingContext,
    ) -> None:
        try:
            async with session_factory() as session:
                media = await self._repo.get_by_id(session, media_id)
                if media is None:
                    return

            video = Path(media.file_path)
            if not video.is_file():
                raise MediaProcessingError(f"Video file missing: {video}")

            async def on_progress(operation: str, progress: float, message: str) -> None:
                status_map = {
                    "proxy": "proxy_status",
                    "waveform": "waveform_status",
                    "detect_scenes": "scene_status",
                }
                field = status_map.get(operation)
                if field:
                    async with session_factory() as session:
                        current = await self._repo.get_by_id(session, media_id)
                        if current is None:
                            return
                        setattr(current, field, ProcessingStatus.PROCESSING)
                        current.updated_at = utc_now_iso()
                        await self._repo.update(session, current)

            ctx.on_progress = on_progress

            manifest = await self._processor.process_import(
                video,
                project_root,
                media_id,
                ctx=ctx,
            )
            probe = manifest.probe
            media.duration_ms = probe.duration_ms
            media.width = probe.width
            media.height = probe.height
            media.frame_rate = probe.frame_rate
            media.codec = probe.codec
            media.frame_count = probe.frame_count
            media.audio_sample_rate = probe.audio_sample_rate
            media.bitrate = probe.bitrate
            media.file_size_bytes = probe.file_size_bytes
            media.proxy_path = manifest.paths.proxy_path
            media.thumbnail_path = manifest.paths.thumbnail_poster_path
            media.waveform_path = manifest.paths.waveform_path
            media.cache_paths = manifest.paths
            media.import_status = ImportStatus.READY
            media.proxy_status = ProcessingStatus.READY
            media.waveform_status = ProcessingStatus.READY
            media.scene_status = ProcessingStatus.READY
            media.error_message = None
            media.updated_at = utc_now_iso()

            async with session_factory() as session:
                await self._repo.update(session, media)

            logger.info("media_import_complete", media_id=media_id)
        except ProcessingCancelledError:
            await self._mark_error(
                session_factory,
                media_id,
                ImportStatus.CANCELLED,
                "Cancelled",
                ProcessingStatus.ERROR,
            )
        except MediaProcessingError as exc:
            await self._mark_error(
                session_factory,
                media_id,
                ImportStatus.ERROR,
                exc.message,
                ProcessingStatus.ERROR,
            )
            logger.error("media_import_failed", media_id=media_id, error=exc.message)
        except Exception as exc:
            await self._mark_error(
                session_factory,
                media_id,
                ImportStatus.ERROR,
                str(exc),
                ProcessingStatus.ERROR,
            )
            logger.error("media_import_failed", media_id=media_id, error=str(exc))
        finally:
            self._active_contexts.pop(media_id, None)
            self._import_tasks.pop(media_id, None)

    async def _mark_error(
        self,
        session_factory,
        media_id: str,
        status: ImportStatus,
        message: str,
        processing_status: ProcessingStatus,
    ) -> None:
        async with session_factory() as session:
            media = await self._repo.get_by_id(session, media_id)
            if media is None:
                return
            media.import_status = status
            media.error_message = message
            media.proxy_status = processing_status
            media.waveform_status = processing_status
            media.scene_status = processing_status
            media.updated_at = utc_now_iso()
            await self._repo.update(session, media)

    async def invalidate_if_source_changed(
        self,
        project_root: Path,
        media_id: str,
        source: Path,
    ) -> bool:
        from montage_backend.media.cache import is_cache_valid, load_manifest

        paths = build_cache_paths(project_root, media_id, source.suffix.lower() or ".mp4")
        manifest = load_manifest(Path(paths.manifest_path))
        if manifest is None:
            return True
        if is_cache_valid(manifest, source):
            return False
        invalidate_cache(project_root, media_id)
        return True
