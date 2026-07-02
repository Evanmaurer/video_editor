from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from montage_backend.analysis.base import AnalysisModuleId
from montage_backend.api.deps import get_analysis_service
from montage_backend.models.domain.analysis import (
    AnalysisJobRecord,
    AnalysisModuleCacheRecord,
    AnalysisModuleInfo,
    AnalysisQueueStatus,
    RunAnalysisRequest,
    SceneAnalysisResult,
)
from montage_backend.analysis.albion.albion_analysis import AlbionAnalysisResult
from montage_backend.analysis.albion.ocr.albion_ocr_analysis import AlbionOcrAnalysisResult
from montage_backend.analysis.audio_analysis import AudioAnalysisResult
from montage_backend.analysis.embedding_analysis import (
    EmbeddingAnalysisResult,
    EmbeddingMatch,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from montage_backend.analysis.motion_analysis import MotionAnalysisResult
from montage_backend.analysis.object_analysis import ObjectAnalysisResult
from montage_backend.analysis.ocr_analysis import OcrAnalysisResult
from montage_backend.models.domain.clip_analysis import (
    ClipAnalysisRecord,
    ClipAnalysisSummary,
    ProjectAnalysisOverview,
)
from montage_backend.models.domain.media import ProcessingStatus
from montage_backend.services.analysis_service import AnalysisService

router = APIRouter(prefix="/projects", tags=["analysis"])


@router.get("/{project_id}/analysis/overview", response_model=ProjectAnalysisOverview)
async def get_project_analysis_overview(
    project_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> ProjectAnalysisOverview:
    return await service.get_project_analysis_overview(project_id)


@router.get(
    "/{project_id}/media/{media_id}/analysis",
    response_model=ClipAnalysisRecord,
)
async def get_clip_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> ClipAnalysisRecord:
    return await service.get_clip_analysis(project_id, media_id)


@router.get(
    "/{project_id}/media/{media_id}/analysis/summary",
    response_model=ClipAnalysisSummary,
)
async def get_clip_analysis_summary(
    project_id: str,
    media_id: str,
    refresh: bool = False,
    service: AnalysisService = Depends(get_analysis_service),
) -> ClipAnalysisSummary:
    return await service.get_clip_analysis_summary(project_id, media_id, refresh=refresh)


@router.post(
    "/{project_id}/media/{media_id}/analysis/refresh",
    response_model=ClipAnalysisSummary,
)
async def refresh_clip_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> ClipAnalysisSummary:
    return await service.refresh_clip_analysis(project_id, media_id)


@router.delete(
    "/{project_id}/media/{media_id}/analysis",
    status_code=204,
    response_class=Response,
)
async def invalidate_all_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> Response:
    await service.invalidate_all_analysis(project_id, media_id)
    return Response(status_code=204)


@router.get("/{project_id}/analysis/jobs", response_model=list[AnalysisJobRecord])
async def list_analysis_jobs(
    project_id: str,
    limit: int = 100,
    service: AnalysisService = Depends(get_analysis_service),
) -> list[AnalysisJobRecord]:
    return await service.list_jobs(project_id, limit=limit)


@router.get("/{project_id}/analysis/queue", response_model=AnalysisQueueStatus)
async def get_analysis_queue_status(
    project_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisQueueStatus:
    return await service.get_queue_status(project_id)


@router.post("/{project_id}/analysis/queue/pause", response_model=AnalysisQueueStatus)
async def pause_analysis_queue(
    project_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisQueueStatus:
    return await service.pause_project_queue(project_id)


@router.post("/{project_id}/analysis/queue/resume", response_model=AnalysisQueueStatus)
async def resume_analysis_queue(
    project_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisQueueStatus:
    return await service.resume_project_queue(project_id)


@router.post("/{project_id}/analysis/jobs/{job_id}/pause", response_model=AnalysisJobRecord)
async def pause_analysis_job(
    project_id: str,
    job_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisJobRecord:
    return await service.pause_job(project_id, job_id)


@router.post("/{project_id}/analysis/jobs/{job_id}/resume", response_model=AnalysisJobRecord)
async def resume_analysis_job(
    project_id: str,
    job_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisJobRecord:
    return await service.resume_job(project_id, job_id)


@router.post("/{project_id}/analysis/jobs/{job_id}/retry", response_model=AnalysisJobRecord)
async def retry_analysis_job(
    project_id: str,
    job_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisJobRecord:
    return await service.retry_job(project_id, job_id)


@router.get("/{project_id}/analysis/modules", response_model=list[AnalysisModuleInfo])
async def list_analysis_modules(
    service: AnalysisService = Depends(get_analysis_service),
) -> list[AnalysisModuleInfo]:
    return service.list_modules()


@router.get(
    "/{project_id}/media/{media_id}/analysis/scenes",
    response_model=SceneAnalysisResult | None,
)
async def get_scene_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> SceneAnalysisResult | None:
    return await service.get_scene_analysis(project_id, media_id)


@router.get(
    "/{project_id}/media/{media_id}/analysis/motion",
    response_model=MotionAnalysisResult | None,
)
async def get_motion_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> MotionAnalysisResult | None:
    return await service.get_motion_analysis(project_id, media_id)


@router.get(
    "/{project_id}/media/{media_id}/analysis/audio",
    response_model=AudioAnalysisResult | None,
)
async def get_audio_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AudioAnalysisResult | None:
    return await service.get_audio_analysis(project_id, media_id)


@router.get(
    "/{project_id}/media/{media_id}/analysis/ocr",
    response_model=OcrAnalysisResult | None,
)
async def get_ocr_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> OcrAnalysisResult | None:
    return await service.get_ocr_analysis(project_id, media_id)


@router.get(
    "/{project_id}/media/{media_id}/analysis/object",
    response_model=ObjectAnalysisResult | None,
)
async def get_object_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> ObjectAnalysisResult | None:
    return await service.get_object_analysis(project_id, media_id)


@router.get(
    "/{project_id}/media/{media_id}/analysis/embedding",
    response_model=EmbeddingAnalysisResult | None,
)
async def get_embedding_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> EmbeddingAnalysisResult | None:
    return await service.get_embedding_analysis(project_id, media_id)


@router.get(
    "/{project_id}/media/{media_id}/analysis/albion",
    response_model=AlbionAnalysisResult | None,
)
async def get_albion_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AlbionAnalysisResult | None:
    return await service.get_albion_analysis(project_id, media_id)


@router.get(
    "/{project_id}/media/{media_id}/analysis/albion/ocr",
    response_model=AlbionOcrAnalysisResult | None,
)
async def get_albion_ocr_analysis(
    project_id: str,
    media_id: str,
    service: AnalysisService = Depends(get_analysis_service),
) -> AlbionOcrAnalysisResult | None:
    return await service.get_albion_ocr_analysis(project_id, media_id)


@router.get(
    "/{project_id}/analysis/albion/detectors",
)
async def list_albion_detectors(
    service: AnalysisService = Depends(get_analysis_service),
) -> list[dict[str, str]]:
    analyzer = service.registry.get(AnalysisModuleId.ALBION)
    from montage_backend.analysis.modules.albion import AlbionAnalyzer

    if not isinstance(analyzer, AlbionAnalyzer):
        return []
    return [
        {
            "detector_id": detector_id,
            "version": analyzer.detector_registry.get(detector_id).version,
        }
        for detector_id in analyzer.detector_registry.list_detectors()
    ]


@router.post(
    "/{project_id}/analysis/search",
    response_model=SemanticSearchResponse,
)
async def semantic_search(
    project_id: str,
    request: SemanticSearchRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> SemanticSearchResponse:
    return await service.semantic_search(project_id, request)


@router.get(
    "/{project_id}/media/{media_id}/similar",
    response_model=list[EmbeddingMatch],
)
async def find_similar_clips(
    project_id: str,
    media_id: str,
    top_k: int = 10,
    service: AnalysisService = Depends(get_analysis_service),
) -> list[EmbeddingMatch]:
    return await service.find_similar_clips(project_id, media_id, top_k=top_k)


@router.get(
    "/{project_id}/media/{media_id}/scenes/{scope_id}/similar",
    response_model=list[EmbeddingMatch],
)
async def find_similar_scenes(
    project_id: str,
    media_id: str,
    scope_id: str,
    top_k: int = 10,
    service: AnalysisService = Depends(get_analysis_service),
) -> list[EmbeddingMatch]:
    return await service.find_similar_scenes(project_id, media_id, scope_id, top_k=top_k)


@router.get(
    "/{project_id}/media/{media_id}/duplicates",
    response_model=list[EmbeddingMatch],
)
async def find_duplicate_clips(
    project_id: str,
    media_id: str,
    threshold: float = 0.95,
    service: AnalysisService = Depends(get_analysis_service),
) -> list[EmbeddingMatch]:
    return await service.find_duplicate_clips(project_id, media_id, threshold=threshold)


@router.post(
    "/{project_id}/media/{media_id}/analysis/{module_id}/run",
    response_model=AnalysisJobRecord,
    status_code=202,
)
async def run_analysis_module(
    project_id: str,
    media_id: str,
    module_id: AnalysisModuleId,
    request: RunAnalysisRequest | None = None,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisJobRecord:
    force = request.force if request is not None else False
    priority = request.priority if request is not None else None
    return await service.enqueue_module(
        project_id,
        media_id,
        module_id,
        force=force,
        priority=priority,
    )


@router.get(
    "/{project_id}/media/{media_id}/analysis/{module_id}/status",
    response_model=AnalysisJobRecord,
)
async def get_analysis_status(
    project_id: str,
    media_id: str,
    module_id: AnalysisModuleId,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisJobRecord:
    job = await service.get_job(project_id, media_id, module_id)
    if job is None:
        cache = await service.get_module_cache(project_id, media_id, module_id)
        if cache is not None and cache.status == ProcessingStatus.READY:
            raise HTTPException(status_code=404, detail="No active analysis job")
        return AnalysisJobRecord(
            id="",
            project_id=project_id,
            media_id=media_id,
            module_id=module_id.value,
            status=cache.status if cache is not None else ProcessingStatus.PENDING,
            progress=1.0 if cache and cache.status == ProcessingStatus.READY else 0.0,
            message=cache.reasoning if cache else "Pending",
            created_at=cache.created_at if cache else "",
            updated_at=cache.updated_at if cache else "",
        )
    return job


@router.post(
    "/{project_id}/media/{media_id}/analysis/{module_id}/cancel",
    status_code=204,
    response_class=Response,
)
async def cancel_analysis_module(
    project_id: str,
    media_id: str,
    module_id: AnalysisModuleId,
    service: AnalysisService = Depends(get_analysis_service),
) -> Response:
    await service.cancel_module(project_id, media_id, module_id)
    return Response(status_code=204)


@router.delete(
    "/{project_id}/media/{media_id}/analysis/{module_id}",
    status_code=204,
    response_class=Response,
)
async def invalidate_analysis_module(
    project_id: str,
    media_id: str,
    module_id: AnalysisModuleId,
    service: AnalysisService = Depends(get_analysis_service),
) -> Response:
    await service.invalidate_module(project_id, media_id, module_id)
    return Response(status_code=204)


@router.get(
    "/{project_id}/media/{media_id}/analysis/{module_id}",
    response_model=AnalysisModuleCacheRecord,
)
async def get_analysis_module_cache(
    project_id: str,
    media_id: str,
    module_id: AnalysisModuleId,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisModuleCacheRecord:
    cache = await service.get_module_cache(project_id, media_id, module_id)
    if cache is None:
        raise HTTPException(status_code=404, detail="Analysis cache not found")
    return cache
