from __future__ import annotations

from montage_backend.analysis.albion.albion_analysis import AlbionAnalysisResult
from montage_backend.analysis.audio_analysis import AudioAnalysisResult
from montage_backend.analysis.base import AnalysisModuleId
from montage_backend.analysis.embedding_analysis import EmbeddingAnalysisResult
from montage_backend.analysis.motion_analysis import MotionAnalysisResult
from montage_backend.analysis.object_analysis import ObjectAnalysisResult
from montage_backend.analysis.ocr_analysis import OcrAnalysisResult
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.analysis import AnalysisModuleCacheRecord, SceneAnalysisResult
from montage_backend.models.domain.clip_analysis import (
    CLIP_ANALYSIS_SCHEMA_VERSION,
    AnalysisModuleStatusEntry,
    ClipAnalysisRecord,
    ClipAnalysisSummary,
    ClipAnalysisVersions,
    ClipAssetSnapshot,
    ClipProcessingSnapshot,
    ClipVideoSnapshot,
    ProjectAnalysisOverview,
)
from montage_backend.models.domain.media import ImportStatus, MediaItem, ProcessingStatus
from montage_backend.models.domain.metadata import MediaMetadataSummary

DEFAULT_MODULE_IDS = [module.value for module in AnalysisModuleId]


def module_status_from_cache(cache: AnalysisModuleCacheRecord | None) -> AnalysisModuleStatusEntry:
    if cache is None:
        return AnalysisModuleStatusEntry(
            module_id="unknown",
            status=ProcessingStatus.PENDING,
        )
    return AnalysisModuleStatusEntry(
        module_id=cache.module_id,
        status=cache.status,
        analyzer_version=cache.analyzer_version,
        cache_key=cache.cache_key,
        confidence=cache.confidence,
        updated_at=cache.updated_at,
    )


def build_module_status_map(
    caches: list[AnalysisModuleCacheRecord],
) -> dict[str, AnalysisModuleStatusEntry]:
    by_id = {cache.module_id: module_status_from_cache(cache) for cache in caches}
    return {
        module_id: by_id.get(
            module_id,
            AnalysisModuleStatusEntry(module_id=module_id, status=ProcessingStatus.PENDING),
        )
        for module_id in DEFAULT_MODULE_IDS
    }


def aggregate_overall_status(
    *,
    import_status: ImportStatus,
    module_statuses: dict[str, AnalysisModuleStatusEntry],
    metadata_status: ProcessingStatus,
) -> ProcessingStatus:
    if import_status != ImportStatus.READY:
        return ProcessingStatus.PENDING

    statuses = [entry.status for entry in module_statuses.values()]
    statuses.append(metadata_status)

    if ProcessingStatus.ERROR in statuses:
        return ProcessingStatus.ERROR
    if ProcessingStatus.PROCESSING in statuses or ProcessingStatus.PAUSED in statuses:
        return ProcessingStatus.PROCESSING
    ready_modules = sum(1 for status in statuses if status == ProcessingStatus.READY)
    if ready_modules == len(statuses):
        return ProcessingStatus.READY
    if ready_modules > 0:
        return ProcessingStatus.PROCESSING
    return ProcessingStatus.PENDING


def compute_readiness(module_statuses: dict[str, AnalysisModuleStatusEntry]) -> tuple[float, int, int]:
    total = len(module_statuses)
    ready = sum(1 for entry in module_statuses.values() if entry.status == ProcessingStatus.READY)
    if total == 0:
        return 0.0, 0, 0
    return ready / total, ready, total


def _parse_module_result(
    module_id: str,
    cache: AnalysisModuleCacheRecord | None,
):
    if cache is None or cache.status != ProcessingStatus.READY:
        return None
    parsers = {
        AnalysisModuleId.SCENE.value: SceneAnalysisResult.model_validate,
        AnalysisModuleId.MOTION.value: MotionAnalysisResult.model_validate,
        AnalysisModuleId.AUDIO.value: AudioAnalysisResult.model_validate,
        AnalysisModuleId.OCR.value: OcrAnalysisResult.model_validate,
        AnalysisModuleId.OBJECT.value: ObjectAnalysisResult.model_validate,
        AnalysisModuleId.EMBEDDING.value: EmbeddingAnalysisResult.model_validate,
        AnalysisModuleId.ALBION.value: AlbionAnalysisResult.model_validate,
    }
    parser = parsers.get(module_id)
    if parser is None:
        return None
    try:
        return parser(cache.payload)
    except Exception:
        return None


def build_processing_snapshot(media: MediaItem) -> ClipProcessingSnapshot:
    return ClipProcessingSnapshot(
        import_status=media.import_status,
        proxy_status=media.proxy_status,
        waveform_status=media.waveform_status,
        scene_cache_status=media.scene_status,
        metadata_status=media.metadata_status,
    )


def build_asset_snapshot(media: MediaItem) -> ClipAssetSnapshot:
    cache_paths = media.cache_paths
    return ClipAssetSnapshot(
        proxy_path=media.proxy_path or (cache_paths.proxy_path if cache_paths else None),
        thumbnail_path=media.thumbnail_path or (cache_paths.thumbnail_poster_path if cache_paths else None),
        waveform_path=media.waveform_path or (cache_paths.waveform_path if cache_paths else None),
        thumbnail_strip_path=cache_paths.thumbnail_strip_path if cache_paths else None,
    )


def build_video_snapshot(media: MediaItem) -> ClipVideoSnapshot:
    return ClipVideoSnapshot(
        duration_ms=media.duration_ms,
        width=media.width,
        height=media.height,
        frame_rate=media.frame_rate,
        codec=media.codec,
        frame_count=media.frame_count,
        file_size_bytes=media.file_size_bytes,
    )


def build_versions(
    *,
    module_statuses: dict[str, AnalysisModuleStatusEntry],
    metadata: MediaMetadataSummary | None,
) -> ClipAnalysisVersions:
    module_versions = {
        module_id: entry.analyzer_version
        for module_id, entry in module_statuses.items()
        if entry.analyzer_version
    }
    metadata_schema = None
    if metadata is not None and metadata.features:
        metadata_schema = metadata.features[0].schema_version
    return ClipAnalysisVersions(
        schema_version=CLIP_ANALYSIS_SCHEMA_VERSION,
        metadata_schema_version=metadata_schema,
        module_versions=module_versions,
    )


def build_clip_analysis_summary(
    *,
    project_id: str,
    media: MediaItem,
    metadata: MediaMetadataSummary | None,
    caches: list[AnalysisModuleCacheRecord],
    embedding_vector_count: int,
    source_fingerprint: str | None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> ClipAnalysisSummary:
    now = utc_now_iso()
    module_statuses = build_module_status_map(caches)
    metadata_status = metadata.status if metadata is not None else ProcessingStatus.PENDING
    overall_status = aggregate_overall_status(
        import_status=media.import_status,
        module_statuses=module_statuses,
        metadata_status=metadata_status,
    )
    readiness, modules_ready, modules_total = compute_readiness(module_statuses)

    scene = _parse_module_result(AnalysisModuleId.SCENE.value, _cache_for(caches, AnalysisModuleId.SCENE.value))
    motion = _parse_module_result(AnalysisModuleId.MOTION.value, _cache_for(caches, AnalysisModuleId.MOTION.value))
    ocr = _parse_module_result(AnalysisModuleId.OCR.value, _cache_for(caches, AnalysisModuleId.OCR.value))
    obj = _parse_module_result(AnalysisModuleId.OBJECT.value, _cache_for(caches, AnalysisModuleId.OBJECT.value))
    embedding = _parse_module_result(
        AnalysisModuleId.EMBEDDING.value,
        _cache_for(caches, AnalysisModuleId.EMBEDDING.value),
    )

    return ClipAnalysisSummary(
        media_id=media.id,
        project_id=project_id,
        overall_status=overall_status,
        readiness=readiness,
        modules_ready=modules_ready,
        modules_total=modules_total,
        source_fingerprint=source_fingerprint,
        scene_count=len(scene.segments) if scene is not None else None,
        overall_motion_score=motion.summary.overall_motion_score if motion is not None else None,
        ocr_unique_text_count=len(ocr.unique_texts) if ocr is not None else None,
        object_detection_count=obj.summary.detection_count if obj is not None else None,
        embedding_count=embedding.summary.total_embeddings if embedding is not None else embedding_vector_count or None,
        has_metadata=metadata is not None and metadata.status == ProcessingStatus.READY,
        processing=build_processing_snapshot(media),
        assets=build_asset_snapshot(media),
        video=build_video_snapshot(media),
        modules=module_statuses,
        versions=build_versions(module_statuses=module_statuses, metadata=metadata),
        updated_at=updated_at or now,
        created_at=created_at or now,
    )


def build_clip_analysis_record(
    *,
    project_id: str,
    media: MediaItem,
    metadata: MediaMetadataSummary | None,
    caches: list[AnalysisModuleCacheRecord],
    embedding_vector_count: int,
    source_fingerprint: str | None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> ClipAnalysisRecord:
    summary = build_clip_analysis_summary(
        project_id=project_id,
        media=media,
        metadata=metadata,
        caches=caches,
        embedding_vector_count=embedding_vector_count,
        source_fingerprint=source_fingerprint,
        created_at=created_at,
        updated_at=updated_at,
    )
    scene = _parse_module_result(AnalysisModuleId.SCENE.value, _cache_for(caches, AnalysisModuleId.SCENE.value))
    motion = _parse_module_result(AnalysisModuleId.MOTION.value, _cache_for(caches, AnalysisModuleId.MOTION.value))
    audio = _parse_module_result(AnalysisModuleId.AUDIO.value, _cache_for(caches, AnalysisModuleId.AUDIO.value))
    ocr = _parse_module_result(AnalysisModuleId.OCR.value, _cache_for(caches, AnalysisModuleId.OCR.value))
    obj = _parse_module_result(AnalysisModuleId.OBJECT.value, _cache_for(caches, AnalysisModuleId.OBJECT.value))
    embedding = _parse_module_result(
        AnalysisModuleId.EMBEDDING.value,
        _cache_for(caches, AnalysisModuleId.EMBEDDING.value),
    )

    return ClipAnalysisRecord(
        media_id=media.id,
        project_id=project_id,
        overall_status=summary.overall_status,
        source_fingerprint=source_fingerprint,
        processing=summary.processing,
        assets=summary.assets,
        video=summary.video,
        metadata=metadata,
        modules=summary.modules,
        scene=scene,
        motion=motion,
        audio=audio,
        ocr=ocr,
        object=obj,
        embedding=embedding,
        embedding_vector_count=embedding_vector_count,
        versions=summary.versions,
        summary=summary,
        updated_at=summary.updated_at,
        created_at=summary.created_at,
    )


def build_project_analysis_overview(
    project_id: str,
    summaries: list[ClipAnalysisSummary],
) -> ProjectAnalysisOverview:
    module_ready_counts = {module_id: 0 for module_id in DEFAULT_MODULE_IDS}
    ready_count = 0
    processing_count = 0
    pending_count = 0
    error_count = 0

    for summary in summaries:
        if summary.overall_status == ProcessingStatus.READY:
            ready_count += 1
        elif summary.overall_status == ProcessingStatus.PROCESSING:
            processing_count += 1
        elif summary.overall_status == ProcessingStatus.ERROR:
            error_count += 1
        else:
            pending_count += 1

        for module_id, entry in summary.modules.items():
            if entry.status == ProcessingStatus.READY:
                module_ready_counts[module_id] = module_ready_counts.get(module_id, 0) + 1

    return ProjectAnalysisOverview(
        project_id=project_id,
        clip_count=len(summaries),
        analysis_ready_count=ready_count,
        analysis_processing_count=processing_count,
        analysis_pending_count=pending_count,
        analysis_error_count=error_count,
        module_ready_counts=module_ready_counts,
        clips=summaries,
    )


def _cache_for(caches: list[AnalysisModuleCacheRecord], module_id: str) -> AnalysisModuleCacheRecord | None:
    for cache in caches:
        if cache.module_id == module_id:
            return cache
    return None
