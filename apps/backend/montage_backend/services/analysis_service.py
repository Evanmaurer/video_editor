from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from montage_backend.analysis.base import AnalysisModuleId, AnalysisRunContext, Analyzer
from montage_backend.analysis.modules.albion import AlbionAnalyzer
from montage_backend.analysis.modules.audio import AudioAnalyzer
from montage_backend.analysis.modules.motion import MotionAnalyzer
from montage_backend.analysis.modules.embedding import EmbeddingAnalyzer
from montage_backend.analysis.modules.object import ObjectAnalyzer
from montage_backend.analysis.modules.ocr import OcrAnalyzer
from montage_backend.analysis.modules.scene import SceneAnalyzer
from montage_backend.analysis.clip_analysis_aggregation import (
    build_clip_analysis_record,
    build_clip_analysis_summary,
    build_project_analysis_overview,
)
from montage_backend.analysis.registry import AnalyzerRegistry, default_registry
from montage_backend.jobs.analysis_queue import AnalysisJobQueue, AnalysisQueueItem
from montage_backend.logging import get_logger
from montage_backend.media.cache import source_fingerprint
from montage_backend.analysis.albion.albion_analysis import AlbionAnalysisResult
from montage_backend.analysis.albion.ability.albion_ability_analysis import AlbionAbilityAnalysisResult
from montage_backend.analysis.albion.ocr.albion_ocr_analysis import AlbionOcrAnalysisResult
from montage_backend.analysis.albion.ui.albion_ui_analysis import AlbionUiAnalysisResult
from montage_backend.analysis.audio_analysis import AudioAnalysisResult
from montage_backend.analysis.motion_analysis import MotionAnalysisResult
from montage_backend.analysis.embedding.engine import resolve_embedding_engine
from montage_backend.analysis.embedding_analysis import (
    EmbeddingAnalysisResult,
    EmbeddingMatch,
    EmbeddingScopeType,
    SemanticSearchRequest,
    SemanticSearchResponse,
    cache_payload_from_result,
)
from montage_backend.analysis.object_analysis import ObjectAnalysisResult
from montage_backend.analysis.ocr_analysis import OcrAnalysisResult
from montage_backend.models.domain.analysis import (
    AnalysisCancelledError,
    AnalysisJobRecord,
    AnalysisModuleCacheRecord,
    AnalysisModuleInfo,
    AnalysisPausedError,
    AnalysisQueueStatus,
    AnalysisRetryLimitError,
    RunAnalysisRequest,
    SceneAnalysisResult,
    new_analysis_job,
)
from montage_backend.models.domain.clip_analysis import (
    ClipAnalysisRecord,
    ClipAnalysisSummary,
    ProjectAnalysisOverview,
)
from montage_backend.models.domain.media import ImportStatus, MediaItem, MediaNotFoundError, ProcessingStatus
from montage_backend.models.domain.metadata import MediaMetadataSummary, MetadataFeatureKey
from montage_backend.repositories.clip_analysis_repo import ClipAnalysisRepository
from montage_backend.repositories.embedding_repo import EmbeddingRepository
from montage_backend.repositories.analysis_repo import AnalysisRepository
from montage_backend.repositories.metadata_repo import MetadataRepository
from montage_backend.services.project_service import ProjectService
from montage_backend.ws.hub import ws_hub

logger = get_logger(__name__)


def build_default_registry() -> AnalyzerRegistry:
    registry = AnalyzerRegistry()
    registry.register(SceneAnalyzer())
    registry.register(MotionAnalyzer())
    registry.register(AudioAnalyzer())
    registry.register(OcrAnalyzer())
    registry.register(ObjectAnalyzer())
    registry.register(EmbeddingAnalyzer())
    registry.register(AlbionAnalyzer())
    return registry


class AnalysisService:
    MODULE_DESCRIPTIONS: dict[str, str] = {
        AnalysisModuleId.SCENE.value: "Scene boundaries, cuts, fades, black frames, and freeze frames",
        AnalysisModuleId.MOTION.value: "Motion intensity, camera movement, shake, and per-window motion scores",
        AnalysisModuleId.AUDIO.value: "Loudness, peaks, silence, beats, tempo, dynamic range, music and voice probability",
        AnalysisModuleId.OCR.value: "On-screen text: HUD, combat, player names, guild tags, chat, damage numbers",
        AnalysisModuleId.OBJECT.value: "Characters, mounts, spell effects, party frames, UI panels, health bars, minimap",
        AnalysisModuleId.EMBEDDING.value: "Semantic embeddings for clips, scenes, and keyframes with vector search",
        AnalysisModuleId.ALBION.value: "Albion Online gameplay intelligence: UI, combat, abilities, and highlight events",
    }
    MODULE_PRIORITIES: dict[str, int] = {
        AnalysisModuleId.SCENE.value: 100,
        AnalysisModuleId.MOTION.value: 50,
        AnalysisModuleId.AUDIO.value: 50,
        AnalysisModuleId.OCR.value: 50,
        AnalysisModuleId.OBJECT.value: 50,
        AnalysisModuleId.EMBEDDING.value: 10,
        AnalysisModuleId.ALBION.value: 5,
    }
    ALBION_DEPENDENCY_MODULES = (
        AnalysisModuleId.SCENE,
        AnalysisModuleId.MOTION,
        AnalysisModuleId.AUDIO,
        AnalysisModuleId.OCR,
        AnalysisModuleId.OBJECT,
    )

    def __init__(
        self,
        project_service: ProjectService,
        registry: AnalyzerRegistry | None = None,
        worker_count: int = 2,
    ) -> None:
        self._project_service = project_service
        self._registry = registry or build_default_registry()
        self._repo = AnalysisRepository()
        self._metadata_repo = MetadataRepository()
        self._embedding_repo = EmbeddingRepository()
        self._clip_analysis_repo = ClipAnalysisRepository()
        self._worker_count = max(1, worker_count)
        self._job_queue = AnalysisJobQueue(self._worker_count, self._execute_queued_job)
        self._contexts: dict[str, AnalysisRunContext] = {}
        self._get_media_item: Callable[[str, str], Awaitable[object]] | None = None

    @property
    def registry(self) -> AnalyzerRegistry:
        return self._registry

    @property
    def queue(self) -> AnalysisJobQueue:
        return self._job_queue

    def wire_media_hooks(
        self,
        *,
        get_media_item: Callable[[str, str], Awaitable[object]],
    ) -> None:
        self._get_media_item = get_media_item

    def list_modules(self) -> list[AnalysisModuleInfo]:
        modules: list[AnalysisModuleInfo] = []
        for module_id in self._registry.list_modules():
            analyzer = self._registry.get(module_id)
            modules.append(
                AnalysisModuleInfo(
                    module_id=module_id,
                    version=analyzer.version,
                    description=self.MODULE_DESCRIPTIONS.get(module_id, ""),
                ),
            )
        return modules

    async def enqueue_module(
        self,
        project_id: str,
        media_id: str,
        module_id: AnalysisModuleId | str,
        *,
        force: bool = False,
        priority: int | None = None,
    ) -> AnalysisJobRecord:
        module_key = module_id.value if isinstance(module_id, AnalysisModuleId) else module_id
        task_key = self._task_key(media_id, module_key)
        if self._job_queue.is_queued_or_running(task_key):
            return await self._get_or_create_job(project_id, media_id, module_key)

        job_priority = priority if priority is not None else self.MODULE_PRIORITIES.get(module_key, 0)
        job = await self._get_or_create_job(
            project_id,
            media_id,
            module_key,
            priority=job_priority,
        )
        self._job_queue.ensure_started()
        await self._job_queue.enqueue(
            project_id=project_id,
            media_id=media_id,
            module_id=module_key,
            job_id=job.id,
            priority=job_priority,
            created_at=job.created_at,
            force=force,
        )
        return job

    async def enqueue_default_modules(self, project_id: str, media_id: str) -> None:
        project = await self._project_service.get_project(project_id)
        for module_id in AnalysisModuleId:
            if module_id == AnalysisModuleId.ALBION and project.target_game != "albion":
                continue
            await self.enqueue_module(
                project_id,
                media_id,
                module_id,
                priority=self.MODULE_PRIORITIES.get(module_id.value, 0),
            )

    async def list_jobs(self, project_id: str, *, limit: int = 100) -> list[AnalysisJobRecord]:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._repo.list_jobs_for_project(session, project_id, limit=limit)

    async def get_queue_status(self, project_id: str) -> AnalysisQueueStatus:
        return AnalysisQueueStatus(
            project_id=project_id,
            paused=self._job_queue.is_project_paused(project_id),
            pending_count=self._job_queue.pending_count,
            in_flight_count=self._job_queue.in_flight_count,
            max_workers=self._job_queue.max_workers,
            active_workers=self._job_queue.active_workers,
        )

    async def pause_project_queue(self, project_id: str) -> AnalysisQueueStatus:
        self._job_queue.pause_project(project_id)
        for key, context in list(self._contexts.items()):
            if context.project_id == project_id:
                context.pause()
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            jobs = await self._repo.list_jobs_for_project(session, project_id, limit=200)
            for job in jobs:
                if job.status == ProcessingStatus.PROCESSING:
                    await self._repo.update_job(
                        session,
                        job.id,
                        status=ProcessingStatus.PAUSED,
                        message="Paused by user",
                    )
        return await self.get_queue_status(project_id)

    async def resume_project_queue(self, project_id: str) -> AnalysisQueueStatus:
        self._job_queue.resume_project(project_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            jobs = await self._repo.list_jobs_for_project(session, project_id, limit=200)
            for job in jobs:
                if job.status == ProcessingStatus.PAUSED:
                    await self._repo.update_job(
                        session,
                        job.id,
                        status=ProcessingStatus.PENDING,
                        message="Resumed",
                    )
                    await self.enqueue_module(
                        project_id,
                        job.media_id,
                        job.module_id,
                        priority=job.priority,
                    )
        return await self.get_queue_status(project_id)

    async def pause_job(self, project_id: str, job_id: str) -> AnalysisJobRecord:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            job = await self._repo.get_job(session, job_id)
            if job is None:
                raise MediaNotFoundError(f"Analysis job not found: {job_id}")
            context = self._contexts.get(self._task_key(job.media_id, job.module_id))
            if context is not None:
                context.pause()
            updated = await self._repo.update_job(
                session,
                job_id,
                status=ProcessingStatus.PAUSED,
                message="Paused by user",
            )
        assert updated is not None
        return updated

    async def resume_job(self, project_id: str, job_id: str) -> AnalysisJobRecord:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            job = await self._repo.get_job(session, job_id)
            if job is None:
                raise MediaNotFoundError(f"Analysis job not found: {job_id}")
            if job.status != ProcessingStatus.PAUSED:
                return job
            await self._repo.update_job(
                session,
                job_id,
                status=ProcessingStatus.PENDING,
                message="Resumed",
            )
        await self.enqueue_module(project_id, job.media_id, job.module_id, priority=job.priority)
        async with session_factory() as session:
            updated = await self._repo.get_job(session, job_id)
        assert updated is not None
        return updated

    async def retry_job(self, project_id: str, job_id: str, *, force: bool = True) -> AnalysisJobRecord:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            job = await self._repo.get_job(session, job_id)
            if job is None:
                raise MediaNotFoundError(f"Analysis job not found: {job_id}")
            if job.retry_count >= job.max_retries:
                raise AnalysisRetryLimitError(
                    f"Maximum retries reached ({job.max_retries}) for job {job_id}",
                )
            updated = await self._repo.update_job(
                session,
                job_id,
                status=ProcessingStatus.PENDING,
                progress=0.0,
                message="Retry scheduled",
                error_message=None,
                retry_count=job.retry_count + 1,
            )
        assert updated is not None
        await self.enqueue_module(
            project_id,
            updated.media_id,
            updated.module_id,
            force=force,
            priority=updated.priority + 1,
        )
        return updated

    async def _execute_queued_job(self, item: AnalysisQueueItem) -> None:
        await self._run_module(
            item.project_id,
            item.media_id,
            item.module_id,
            force=item.force,
            job_id=item.job_id,
        )

    async def get_module_cache(
        self,
        project_id: str,
        media_id: str,
        module_id: AnalysisModuleId | str,
    ) -> AnalysisModuleCacheRecord | None:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        module_key = module_id.value if isinstance(module_id, AnalysisModuleId) else module_id
        async with session_factory() as session:
            cache = await self._repo.get_cache(session, media_id, module_key)

        if cache is None or cache.status != ProcessingStatus.READY:
            media = await self._ensure_media_exists(project_id, media_id)
            if media.import_status == ImportStatus.READY:
                await self.enqueue_module(project_id, media_id, module_key)
        return cache

    async def get_scene_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> SceneAnalysisResult | None:
        cache = await self.get_module_cache(project_id, media_id, AnalysisModuleId.SCENE)
        if cache is None or cache.status != ProcessingStatus.READY:
            return None
        return SceneAnalysisResult.model_validate(cache.payload)

    async def get_motion_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> MotionAnalysisResult | None:
        cache = await self.get_module_cache(project_id, media_id, AnalysisModuleId.MOTION)
        if cache is None or cache.status != ProcessingStatus.READY:
            return None
        return MotionAnalysisResult.model_validate(cache.payload)

    async def get_audio_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> AudioAnalysisResult | None:
        cache = await self.get_module_cache(project_id, media_id, AnalysisModuleId.AUDIO)
        if cache is None or cache.status != ProcessingStatus.READY:
            return None
        return AudioAnalysisResult.model_validate(cache.payload)

    async def get_ocr_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> OcrAnalysisResult | None:
        cache = await self.get_module_cache(project_id, media_id, AnalysisModuleId.OCR)
        if cache is None or cache.status != ProcessingStatus.READY:
            return None
        return OcrAnalysisResult.model_validate(cache.payload)

    async def get_object_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> ObjectAnalysisResult | None:
        cache = await self.get_module_cache(project_id, media_id, AnalysisModuleId.OBJECT)
        if cache is None or cache.status != ProcessingStatus.READY:
            return None
        return ObjectAnalysisResult.model_validate(cache.payload)

    async def get_embedding_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> EmbeddingAnalysisResult | None:
        cache = await self.get_module_cache(project_id, media_id, AnalysisModuleId.EMBEDDING)
        if cache is None or cache.status != ProcessingStatus.READY:
            return None
        return EmbeddingAnalysisResult.model_validate(cache.payload)

    async def get_albion_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> AlbionAnalysisResult | None:
        cache = await self.get_module_cache(project_id, media_id, AnalysisModuleId.ALBION)
        if cache is None or cache.status != ProcessingStatus.READY:
            return None
        return AlbionAnalysisResult.model_validate(cache.payload)

    async def get_albion_ocr_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> AlbionOcrAnalysisResult | None:
        albion = await self.get_albion_analysis(project_id, media_id)
        if albion is None:
            return None
        ocr_result = albion.detector_results.get("ocr")
        if ocr_result is None or not ocr_result.payload:
            return None
        return AlbionOcrAnalysisResult.model_validate(ocr_result.payload)

    async def get_albion_ui_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> AlbionUiAnalysisResult | None:
        albion = await self.get_albion_analysis(project_id, media_id)
        if albion is None:
            return None
        ui_result = albion.detector_results.get("ui")
        if ui_result is None or not ui_result.payload:
            return None
        return AlbionUiAnalysisResult.model_validate(ui_result.payload)

    async def get_albion_ability_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> AlbionAbilityAnalysisResult | None:
        albion = await self.get_albion_analysis(project_id, media_id)
        if albion is None:
            return None
        ability_result = albion.detector_results.get("ability")
        if ability_result is None or not ability_result.payload:
            return None
        return AlbionAbilityAnalysisResult.model_validate(ability_result.payload)

    async def get_clip_analysis(
        self,
        project_id: str,
        media_id: str,
        *,
        refresh_snapshot: bool = True,
    ) -> ClipAnalysisRecord:
        media = await self._ensure_media_exists(project_id, media_id)
        record = await self._build_clip_analysis_record(project_id, media)
        if refresh_snapshot:
            await self._persist_clip_analysis_snapshot(project_id, record.summary)
        return record

    async def get_clip_analysis_summary(
        self,
        project_id: str,
        media_id: str,
        *,
        refresh: bool = False,
    ) -> ClipAnalysisSummary:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            cached = await self._clip_analysis_repo.get_for_media(session, media_id)
        if cached is not None and not refresh:
            return cached
        record = await self.get_clip_analysis(project_id, media_id, refresh_snapshot=True)
        return record.summary

    async def get_project_analysis_overview(
        self,
        project_id: str,
    ) -> ProjectAnalysisOverview:
        from montage_backend.repositories.media_repo import MediaRepository

        _, session_factory = await self._project_session(project_id)
        media_repo = MediaRepository()
        async with session_factory() as session:
            media_items = await media_repo.list_by_project(session, project_id)
            snapshot_summaries = await self._clip_analysis_repo.list_for_project(session, project_id)

        snapshot_by_media = {summary.media_id: summary for summary in snapshot_summaries}
        summaries: list[ClipAnalysisSummary] = []

        for media in media_items:
            if media.id in snapshot_by_media:
                summaries.append(snapshot_by_media[media.id])
                continue
            record = await self._build_clip_analysis_record(project_id, media)
            summaries.append(record.summary)
            await self._persist_clip_analysis_snapshot(project_id, record.summary)

        return build_project_analysis_overview(project_id, summaries)

    async def refresh_clip_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> ClipAnalysisSummary:
        record = await self.get_clip_analysis(project_id, media_id, refresh_snapshot=True)
        return record.summary

    async def invalidate_all_analysis(
        self,
        project_id: str,
        media_id: str,
    ) -> None:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._repo.invalidate_cache(session, media_id, None)
            await self._embedding_repo.delete_for_media(session, media_id)
            await self._clip_analysis_repo.delete_for_media(session, media_id)

    async def semantic_search(
        self,
        project_id: str,
        request: SemanticSearchRequest,
    ) -> SemanticSearchResponse:
        engine = resolve_embedding_engine()
        query_vector = await asyncio.to_thread(engine.embed_text, request.query)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            matches = await self._embedding_repo.search_similar(
                session,
                project_id,
                query_vector,
                scope_type=request.scope_type,
                top_k=request.top_k,
            )
        return SemanticSearchResponse(
            query=request.query,
            model_id=engine.model_id,
            matches=matches,
        )

    async def find_similar_clips(
        self,
        project_id: str,
        media_id: str,
        *,
        top_k: int = 10,
    ) -> list[EmbeddingMatch]:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            clip = await self._embedding_repo.get_clip_embedding(session, media_id)
            if clip is None:
                return []
            return await self._embedding_repo.search_similar(
                session,
                project_id,
                clip.vector,
                scope_type=EmbeddingScopeType.CLIP,
                top_k=top_k,
                exclude_media_id=media_id,
            )

    async def find_similar_scenes(
        self,
        project_id: str,
        media_id: str,
        scope_id: str,
        *,
        top_k: int = 10,
    ) -> list[EmbeddingMatch]:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            scene = await self._embedding_repo.get_scene_embedding(session, media_id, scope_id)
            if scene is None:
                return []
            matches = await self._embedding_repo.search_similar(
                session,
                project_id,
                scene.vector,
                scope_type=EmbeddingScopeType.SCENE,
                top_k=top_k + 1,
            )
            return [
                match
                for match in matches
                if not (match.media_id == media_id and match.scope_id == scope_id)
            ][:top_k]

    async def find_duplicate_clips(
        self,
        project_id: str,
        media_id: str,
        *,
        threshold: float = 0.95,
    ) -> list[EmbeddingMatch]:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._embedding_repo.find_duplicates(
                session,
                project_id,
                media_id,
                threshold=threshold,
            )

    async def get_job(
        self,
        project_id: str,
        media_id: str,
        module_id: AnalysisModuleId | str,
    ) -> AnalysisJobRecord | None:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        module_key = module_id.value if isinstance(module_id, AnalysisModuleId) else module_id
        async with session_factory() as session:
            return await self._repo.get_active_job(session, media_id, module_key)

    async def cancel_module(
        self,
        project_id: str,
        media_id: str,
        module_id: AnalysisModuleId | str,
    ) -> None:
        await self._ensure_media_exists(project_id, media_id)
        key = self._task_key(media_id, module_id)
        context = self._contexts.get(key)
        if context is not None:
            context.cancel()
        module_key = module_id.value if isinstance(module_id, AnalysisModuleId) else module_id
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            job = await self._repo.get_active_job(session, media_id, module_key)
            if job is not None:
                await self._repo.update_job(
                    session,
                    job.id,
                    status=ProcessingStatus.ERROR,
                    message="Cancelled by user",
                )

    async def invalidate_module(
        self,
        project_id: str,
        media_id: str,
        module_id: AnalysisModuleId | str | None = None,
    ) -> None:
        await self._ensure_media_exists(project_id, media_id)
        _, session_factory = await self._project_session(project_id)
        module_key = None
        if module_id is not None:
            module_key = module_id.value if isinstance(module_id, AnalysisModuleId) else module_id
        async with session_factory() as session:
            await self._repo.invalidate_cache(session, media_id, module_key)
        await self._refresh_clip_analysis_snapshot(project_id, media_id)

    async def _run_module(
        self,
        project_id: str,
        media_id: str,
        module_id: AnalysisModuleId | str,
        *,
        force: bool = False,
        job_id: str | None = None,
    ) -> None:
        module_key = module_id.value if isinstance(module_id, AnalysisModuleId) else module_id
        analyzer = self._registry.get(module_key)
        media = await self._ensure_media_exists(project_id, media_id)
        video = Path(media.file_path)
        if not video.is_file():
            logger.warning("analysis_skipped_missing_file", media_id=media_id, module_id=module_key)
            return

        fingerprint = source_fingerprint(video)
        frame_rate = media.frame_rate
        _, session_factory = await self._project_session(project_id)

        if not force:
            async with session_factory() as session:
                cached = await self._repo.get_cache(session, media_id, module_key)
            if cached is not None and cached.status == ProcessingStatus.READY:
                if analyzer.is_cache_valid(
                    cached.analyzer_version,
                    cached.cache_key,
                    fingerprint,
                    frame_rate=frame_rate,
                ):
                    logger.info("analysis_cache_hit", media_id=media_id, module_id=module_key)
                    if job_id is not None:
                        async with session_factory() as session:
                            await self._repo.update_job(
                                session,
                                job_id,
                                status=ProcessingStatus.READY,
                                progress=1.0,
                                message="Cache hit",
                            )
                    return

        if job_id is not None:
            job = await self._load_job(session_factory, job_id)
        else:
            job = await self._get_or_create_job(project_id, media_id, module_key)
        task_key = self._task_key(media_id, module_key)
        ctx = AnalysisRunContext(
            project_id=project_id,
            media_id=media_id,
            source_fingerprint=fingerprint,
            gpu_enabled=True,
        )
        ctx.bind_progress(lambda progress: self._on_progress(project_id, media_id, module_key, job.id, progress))
        self._contexts[task_key] = ctx

        if module_key == AnalysisModuleId.EMBEDDING.value:
            async with session_factory() as session:
                scene_cache = await self._repo.get_cache(session, media_id, AnalysisModuleId.SCENE.value)
            if scene_cache is not None and scene_cache.status == ProcessingStatus.READY:
                segments = scene_cache.payload.get("segments", [])
                ctx.extras["scene_segments"] = segments

        if module_key == AnalysisModuleId.ALBION.value:
            async with session_factory() as session:
                for sibling in self.ALBION_DEPENDENCY_MODULES:
                    sibling_cache = await self._repo.get_cache(session, media_id, sibling.value)
                    if sibling_cache is not None and sibling_cache.status == ProcessingStatus.READY:
                        ctx.extras[f"{sibling.value}_analysis"] = sibling_cache.payload
                albion_cache = await self._repo.get_cache(session, media_id, module_key)
                if albion_cache is not None and albion_cache.payload:
                    ctx.extras["prior_albion_payload"] = albion_cache.payload
                    ctx.extras["detector_caches"] = albion_cache.payload.get("detector_caches", {})
                    ctx.extras["detector_results"] = albion_cache.payload.get("detector_results", {})

        async with session_factory() as session:
            await self._repo.update_job(
                session,
                job.id,
                status=ProcessingStatus.PROCESSING,
                progress=0.0,
                message="Starting analysis",
            )
            await self._repo.upsert_cache(
                session,
                media_id=media_id,
                module_id=module_key,
                analyzer_version=analyzer.version,
                cache_key=analyzer.cache_key(fingerprint, frame_rate=frame_rate),
                status=ProcessingStatus.PROCESSING,
                payload={},
                source_fingerprint=fingerprint,
            )

        try:
            output = await analyzer.analyze(
                ctx,
                video_path=str(video),
                duration_ms=media.duration_ms,
                frame_rate=frame_rate,
                frame_count=None,
            )
            cache_payload = output.payload
            if module_key == AnalysisModuleId.EMBEDDING.value:
                cache_payload = await self._persist_embedding_output(
                    project_id,
                    media_id,
                    fingerprint,
                    output.payload,
                    session_factory,
                )
            async with session_factory() as session:
                cache = await self._repo.upsert_cache(
                    session,
                    media_id=media_id,
                    module_id=module_key,
                    analyzer_version=output.analyzer_version,
                    cache_key=output.cache_key,
                    status=ProcessingStatus.READY,
                    payload=cache_payload,
                    source_fingerprint=fingerprint,
                    confidence=output.confidence,
                    reasoning=output.reasoning,
                )
                await self._repo.update_job(
                    session,
                    job.id,
                    status=ProcessingStatus.READY,
                    progress=1.0,
                    message="Analysis complete",
                    cache_id=cache.id,
                )
            await self._broadcast_progress(
                project_id,
                media_id,
                module_key,
                job.id,
                progress=1.0,
                message="Analysis complete",
                status=ProcessingStatus.READY,
            )
            await self._refresh_clip_analysis_snapshot(project_id, media_id)
        except AnalysisPausedError:
            async with session_factory() as session:
                await self._repo.update_job(
                    session,
                    job.id,
                    status=ProcessingStatus.PAUSED,
                    message="Paused",
                )
        except AnalysisCancelledError:
            async with session_factory() as session:
                await self._repo.update_job(
                    session,
                    job.id,
                    status=ProcessingStatus.ERROR,
                    message="Cancelled by user",
                )
                await self._repo.upsert_cache(
                    session,
                    media_id=media_id,
                    module_id=module_key,
                    analyzer_version=analyzer.version,
                    cache_key=analyzer.cache_key(fingerprint, frame_rate=frame_rate),
                    status=ProcessingStatus.ERROR,
                    payload={},
                    source_fingerprint=fingerprint,
                    reasoning="Cancelled",
                )
        except Exception as exc:
            logger.exception("analysis_failed", media_id=media_id, module_id=module_key)
            async with session_factory() as session:
                await self._repo.update_job(
                    session,
                    job.id,
                    status=ProcessingStatus.ERROR,
                    error_message=str(exc),
                    message="Analysis failed",
                )
                await self._repo.upsert_cache(
                    session,
                    media_id=media_id,
                    module_id=module_key,
                    analyzer_version=analyzer.version,
                    cache_key=analyzer.cache_key(fingerprint, frame_rate=frame_rate),
                    status=ProcessingStatus.ERROR,
                    payload={"error": str(exc)},
                    source_fingerprint=fingerprint,
                )
            await self._broadcast_progress(
                project_id,
                media_id,
                module_key,
                job.id,
                progress=0.0,
                message=str(exc),
                status=ProcessingStatus.ERROR,
            )
            await self._refresh_clip_analysis_snapshot(project_id, media_id)
        finally:
            self._contexts.pop(task_key, None)

    async def _get_or_create_job(
        self,
        project_id: str,
        media_id: str,
        module_id: str,
        *,
        priority: int = 0,
    ) -> AnalysisJobRecord:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            existing = await self._repo.get_active_job(session, media_id, module_id)
            if existing is not None:
                return existing
            job = new_analysis_job(
                project_id=project_id,
                media_id=media_id,
                module_id=module_id,
                priority=priority,
            )
            return await self._repo.create_job(session, job, priority=priority)

    async def _load_job(self, session_factory, job_id: str) -> AnalysisJobRecord:
        async with session_factory() as session:
            job = await self._repo.get_job(session, job_id)
            if job is None:
                raise MediaNotFoundError(f"Analysis job not found: {job_id}")
            return job

    async def _on_progress(
        self,
        project_id: str,
        media_id: str,
        module_id: str,
        job_id: str,
        progress: object,
    ) -> None:
        from montage_backend.analysis.base import AnalysisProgress

        if not isinstance(progress, AnalysisProgress):
            return
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._repo.update_job(
                session,
                job_id,
                status=ProcessingStatus.PROCESSING,
                progress=progress.progress,
                message=progress.message,
            )
        await self._broadcast_progress(
            project_id,
            media_id,
            module_id,
            job_id,
            progress=progress.progress,
            message=progress.message,
            status=ProcessingStatus.PROCESSING,
        )

    async def _broadcast_progress(
        self,
        project_id: str,
        media_id: str,
        module_id: str,
        job_id: str,
        *,
        progress: float,
        message: str,
        status: ProcessingStatus,
    ) -> None:
        await ws_hub.broadcast(
            {
                "type": "analysis.progress",
                "project_id": project_id,
                "media_id": media_id,
                "module_id": module_id,
                "job_id": job_id,
                "progress": progress,
                "message": message,
                "status": status.value,
            },
        )

    async def _persist_embedding_output(
        self,
        project_id: str,
        media_id: str,
        fingerprint: str,
        payload: dict,
        session_factory,
    ) -> dict:
        result = EmbeddingAnalysisResult.model_validate(payload)
        async with session_factory() as session:
            await self._embedding_repo.upsert_records(
                session,
                project_id=project_id,
                media_id=media_id,
                model_id=result.summary.model_id,
                source_fingerprint=fingerprint,
                records=result.embeddings,
            )
        return cache_payload_from_result(result)

    async def _build_clip_analysis_record(
        self,
        project_id: str,
        media: MediaItem,
    ) -> ClipAnalysisRecord:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            metadata_records = await self._metadata_repo.list_for_media(session, media.id)
            caches = await self._repo.list_caches_for_media(session, media.id)
            embedding_vector_count = await self._embedding_repo.count_for_media(session, media.id)
            existing_snapshot = await self._clip_analysis_repo.get_for_media(session, media.id)

        metadata = self._build_metadata_summary(media.id, metadata_records)
        fingerprint = metadata.source_fingerprint
        if fingerprint is None and caches:
            fingerprint = next((cache.source_fingerprint for cache in caches if cache.source_fingerprint), None)

        created_at = existing_snapshot.created_at if existing_snapshot else None
        return build_clip_analysis_record(
            project_id=project_id,
            media=media,
            metadata=metadata,
            caches=caches,
            embedding_vector_count=embedding_vector_count,
            source_fingerprint=fingerprint,
            created_at=created_at,
        )

    async def _refresh_clip_analysis_snapshot(self, project_id: str, media_id: str) -> None:
        media = await self._ensure_media_exists(project_id, media_id)
        record = await self._build_clip_analysis_record(project_id, media)
        await self._persist_clip_analysis_snapshot(project_id, record.summary)

    async def _persist_clip_analysis_snapshot(
        self,
        project_id: str,
        summary: ClipAnalysisSummary,
    ) -> None:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._clip_analysis_repo.upsert_summary(
                session,
                project_id=project_id,
                summary=summary,
            )

    @staticmethod
    def _build_metadata_summary(
        media_id: str,
        records: list,
    ) -> MediaMetadataSummary | None:
        if not records:
            return None

        from montage_backend.models.domain.metadata import (
            AICacheMetadata,
            AudioMetadata,
            VisualMetadata,
        )
        from montage_backend.services.metadata_service import MetadataService

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

        status = MetadataService._aggregate_status(records)
        return MediaMetadataSummary(
            media_id=media_id,
            status=status,
            source_fingerprint=fingerprint,
            visual=visual,
            audio=audio,
            ai_cache=ai_cache,
            features=records,
        )

    async def _ensure_media_exists(self, project_id: str, media_id: str):
        if self._get_media_item is None:
            raise RuntimeError("AnalysisService media hooks not wired")
        media = await self._get_media_item(project_id, media_id)
        if media is None:
            raise MediaNotFoundError(f"Media not found: {media_id}")
        return media

    async def _project_session(self, project_id: str):
        project = await self._project_service.get_project(project_id)
        session_factory = await self._project_service._ensure_project_db(Path(project.root_path))
        return project, session_factory

    @staticmethod
    def _task_key(media_id: str, module_id: AnalysisModuleId | str) -> str:
        module_key = module_id.value if isinstance(module_id, AnalysisModuleId) else module_id
        return f"{media_id}:{module_key}"
