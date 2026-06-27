from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from montage_backend.jobs.import_queue import ImportJobQueue
from montage_backend.logging import get_logger
from montage_backend.media.ffmpeg_runner import ProcessingContext
from montage_backend.metadata.extractor import MetadataExtractor
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.media import ImportStatus, MediaProcessingError, ProcessingStatus
from montage_backend.models.domain.metadata import (
    AICacheMetadata,
    AudioMetadata,
    MetadataError,
    MetadataFeatureKey,
    MetadataFeatureNotFoundError,
    MetadataFeatureRecord,
    MediaMetadataSummary,
    UpsertMetadataFeatureRequest,
    VisualMetadata,
)
from montage_backend.repositories.metadata_repo import MetadataRepository
from montage_backend.services.project_service import ProjectService

logger = get_logger(__name__)


class MetadataService:
    def __init__(
        self,
        project_service: ProjectService,
        extractor: MetadataExtractor | None = None,
        worker_count: int = 1,
    ) -> None:
        self._project_service = project_service
        self._extractor = extractor or MetadataExtractor()
        self._repo = MetadataRepository()
        self._queue = ImportJobQueue(max_workers=worker_count)
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._get_media_item: Callable[[str, str], Awaitable[object]] | None = None
        self._update_media_status: Callable[[str, str, ProcessingStatus], Awaitable[None]] | None = None

    @property
    def queue(self) -> ImportJobQueue:
        return self._queue

    def wire_media_hooks(
        self,
        *,
        get_media_item: Callable[[str, str], Awaitable[object]],
        update_media_status: Callable[[str, str, ProcessingStatus], Awaitable[None]],
    ) -> None:
        self._get_media_item = get_media_item
        self._update_media_status = update_media_status

    async def enqueue_analysis(self, project_id: str, media_id: str) -> None:
        if media_id in self._tasks and not self._tasks[media_id].done():
            return

        async def run_job() -> None:
            await self._queue.run(self._analyze_media(project_id, media_id))

        self._tasks[media_id] = asyncio.create_task(run_job())

    async def analyze_now(self, project_id: str, media_id: str) -> MediaMetadataSummary:
        await self._analyze_media(project_id, media_id)
        return await self.get_metadata(project_id, media_id)

    async def get_metadata(self, project_id: str, media_id: str) -> MediaMetadataSummary:
        media = await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            records = await self._repo.list_for_media(session, media_id)
        summary = self._build_summary(media_id, records)

        if (
            media.import_status == ImportStatus.READY
            and summary.status == ProcessingStatus.PENDING
        ):
            await self.enqueue_analysis(project_id, media_id)

        return summary

    async def get_feature(
        self,
        project_id: str,
        media_id: str,
        feature_key: MetadataFeatureKey,
    ) -> MetadataFeatureRecord:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            record = await self._repo.get_feature(session, media_id, feature_key)
        if record is None:
            raise MetadataFeatureNotFoundError(
                f"Metadata feature not found: {feature_key.value}",
            )
        return record

    async def upsert_feature(
        self,
        project_id: str,
        media_id: str,
        feature_key: MetadataFeatureKey,
        request: UpsertMetadataFeatureRequest,
    ) -> MetadataFeatureRecord:
        media = await self._ensure_media_exists(project_id, media_id)
        video = Path(media.file_path)
        fingerprint = self._extractor.fingerprint(video) if video.is_file() else None
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            record = await self._repo.upsert_feature(
                session,
                media_id=media_id,
                feature_key=feature_key,
                status=request.status,
                payload=request.payload,
                source_fingerprint=fingerprint,
                confidence=request.confidence,
                reasoning=request.reasoning,
            )
        await self._sync_media_status(project_id, media_id)
        return record

    async def invalidate_metadata(self, project_id: str, media_id: str) -> None:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._repo.delete_for_media(session, media_id)
        await self._set_media_status(project_id, media_id, ProcessingStatus.PENDING)

    async def _analyze_media(self, project_id: str, media_id: str) -> None:
        if self._get_media_item is None:
            raise MetadataError("Metadata service is not wired to media service")

        media = await self._get_media_item(project_id, media_id)
        if media.import_status != ImportStatus.READY:
            return

        video = Path(media.file_path)
        if not video.is_file():
            raise MediaProcessingError(f"Video file missing for metadata analysis: {video}")

        fingerprint = self._extractor.fingerprint(video)
        _, session_factory = await self._project_session(project_id)

        async with session_factory() as session:
            existing = await self._repo.list_for_media(session, media_id)
            if existing and any(
                record.source_fingerprint and record.source_fingerprint != fingerprint
                for record in existing
            ):
                await self._repo.delete_for_media(session, media_id)

        await self._set_media_status(project_id, media_id, ProcessingStatus.PROCESSING)
        ctx = ProcessingContext()

        scenes_path = None
        waveform_path = None
        if media.cache_paths is not None:
            scenes_path = Path(media.cache_paths.scenes_cache_path)
            waveform_path = Path(media.cache_paths.waveform_path)

        try:
            visual = await self._extractor.extract_visual(
                video,
                ctx=ctx,
                scenes_cache_path=scenes_path,
            )
            audio = await self._extractor.extract_audio(
                video,
                ctx=ctx,
                waveform_path=waveform_path,
                duration_ms=media.duration_ms,
            )
            ai_cache = self._extractor.empty_ai_cache()

            async with session_factory() as session:
                await self._repo.upsert_feature(
                    session,
                    media_id=media_id,
                    feature_key=MetadataFeatureKey.VISUAL,
                    status=ProcessingStatus.READY,
                    payload=visual.model_dump(),
                    source_fingerprint=fingerprint,
                    confidence=0.85,
                    reasoning="Derived from FFmpeg scene, signalstats, and frame sampling.",
                )
                await self._repo.upsert_feature(
                    session,
                    media_id=media_id,
                    feature_key=MetadataFeatureKey.AUDIO,
                    status=ProcessingStatus.READY,
                    payload=audio.model_dump(),
                    source_fingerprint=fingerprint,
                    confidence=0.8,
                    reasoning="Derived from FFmpeg volumedetect, silencedetect, and waveform peaks.",
                )
                await self._repo.upsert_feature(
                    session,
                    media_id=media_id,
                    feature_key=MetadataFeatureKey.AI_CACHE,
                    status=ProcessingStatus.READY,
                    payload=ai_cache.model_dump(),
                    source_fingerprint=fingerprint,
                    confidence=None,
                    reasoning="Reserved for M3 AI analysis modules.",
                )

            await self._set_media_status(project_id, media_id, ProcessingStatus.READY)
            logger.info("metadata_analysis_complete", media_id=media_id, project_id=project_id)
        except Exception as exc:
            await self._set_media_status(project_id, media_id, ProcessingStatus.ERROR)
            logger.error("metadata_analysis_failed", media_id=media_id, error=str(exc))
        finally:
            self._tasks.pop(media_id, None)

    async def _project_session(self, project_id: str):
        project = await self._project_service.get_project(project_id)
        session_factory = await self._project_service._ensure_project_db(Path(project.root_path))
        return project, session_factory

    async def _ensure_media_exists(self, project_id: str, media_id: str):
        if self._get_media_item is None:
            raise MetadataError("Metadata service is not wired to media service")
        media = await self._get_media_item(project_id, media_id)
        if media.project_id != project_id:
            raise MetadataFeatureNotFoundError(f"Media item not found: {media_id}")
        return media

    async def _set_media_status(
        self,
        project_id: str,
        media_id: str,
        status: ProcessingStatus,
    ) -> None:
        if self._update_media_status is not None:
            await self._update_media_status(project_id, media_id, status)

    async def _sync_media_status(self, project_id: str, media_id: str) -> None:
        summary = await self.get_metadata(project_id, media_id)
        await self._set_media_status(project_id, media_id, summary.status)

    def _build_summary(
        self,
        media_id: str,
        records: list[MetadataFeatureRecord],
    ) -> MediaMetadataSummary:
        visual = None
        audio = None
        ai_cache = None
        fingerprint = None
        for record in records:
            fingerprint = record.source_fingerprint or fingerprint
            if record.feature_key == MetadataFeatureKey.VISUAL:
                visual = VisualMetadata.model_validate(record.payload)
            elif record.feature_key == MetadataFeatureKey.AUDIO:
                audio = AudioMetadata.model_validate(record.payload)
            elif record.feature_key == MetadataFeatureKey.AI_CACHE:
                ai_cache = AICacheMetadata.model_validate(record.payload)

        status = self._aggregate_status(records)
        return MediaMetadataSummary(
            media_id=media_id,
            status=status,
            source_fingerprint=fingerprint,
            visual=visual,
            audio=audio,
            ai_cache=ai_cache,
            features=records,
        )

    @staticmethod
    def _aggregate_status(records: list[MetadataFeatureRecord]) -> ProcessingStatus:
        if not records:
            return ProcessingStatus.PENDING
        statuses = {record.status for record in records}
        if ProcessingStatus.ERROR in statuses:
            return ProcessingStatus.ERROR
        if ProcessingStatus.PROCESSING in statuses:
            return ProcessingStatus.PROCESSING
        if all(status == ProcessingStatus.READY for status in statuses):
            return ProcessingStatus.READY
        return ProcessingStatus.PENDING
