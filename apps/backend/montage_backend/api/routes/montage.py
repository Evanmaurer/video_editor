from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from montage_backend.api.deps import get_montage_plan_service
from montage_backend.models.domain.plan_timeline import PlanTimelineApplication, PlanTimelineApplicationNotFoundError
from montage_backend.models.domain.plan_feedback import (
    FeedbackActionType,
    PlanFeedbackRegenerationResult,
    PlanFeedbackState,
    PlanQualityAnalysis,
    SubmitPlanFeedbackRequest,
)
from montage_backend.models.domain.plan_draft import PlanDraftAnalysis
from montage_backend.models.domain.plan_effects import PlanEffectsAnalysis
from montage_backend.models.domain.plan_pacing import PlanPacingAnalysis
from montage_backend.models.domain.plan_transitions import PlanTransitionAnalysis
from montage_backend.models.domain.music_sync import MusicSyncAnalysis, ProjectMusicSyncResponse
from montage_backend.models.domain.clip_highlight import ClipHighlights, ProjectClipHighlightsResponse
from montage_backend.models.domain.clip_score import ClipScore, ProjectClipScoresResponse
from montage_backend.models.domain.montage_plan import (
    CreateMontagePlanRequest,
    MontagePlan,
    MontagePlanSummary,
    UpdateMontagePlanRequest,
)
from montage_backend.montage.registry import MontagePlannerRegistry
from montage_backend.services.montage_plan_service import MontagePlanService

router = APIRouter(prefix="/projects", tags=["montage"])


@router.get("/{project_id}/montage/modules")
async def list_montage_modules(
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> list[dict[str, str]]:
    registry: MontagePlannerRegistry = service.registry
    return [{"module_id": module_id} for module_id in registry.list_modules()]


@router.get("/{project_id}/montage/plans", response_model=list[MontagePlanSummary])
async def list_montage_plans(
    project_id: str,
    limit: int = 100,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> list[MontagePlanSummary]:
    return await service.list_plans(project_id, limit=limit)


@router.post("/{project_id}/montage/plans", response_model=MontagePlan, status_code=201)
async def create_montage_plan(
    project_id: str,
    request: CreateMontagePlanRequest,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> MontagePlan:
    return await service.create_plan(project_id, request)


@router.get("/{project_id}/montage/plans/{plan_id}", response_model=MontagePlan)
async def get_montage_plan(
    project_id: str,
    plan_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> MontagePlan:
    return await service.get_plan(project_id, plan_id)


@router.put("/{project_id}/montage/plans/{plan_id}", response_model=MontagePlan)
async def update_montage_plan(
    project_id: str,
    plan_id: str,
    request: UpdateMontagePlanRequest,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> MontagePlan:
    return await service.update_plan(project_id, plan_id, request)


@router.delete(
    "/{project_id}/montage/plans/{plan_id}",
    status_code=204,
    response_class=Response,
)
async def delete_montage_plan(
    project_id: str,
    plan_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> Response:
    await service.delete_plan(project_id, plan_id)
    return Response(status_code=204)


@router.get("/{project_id}/montage/scores", response_model=ProjectClipScoresResponse)
async def list_clip_scores(
    project_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> ProjectClipScoresResponse:
    return await service.list_clip_scores(project_id)


@router.post("/{project_id}/montage/scores/refresh", response_model=ProjectClipScoresResponse)
async def refresh_clip_scores(
    project_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> ProjectClipScoresResponse:
    return await service.score_project(project_id, force=True)


@router.get("/{project_id}/media/{media_id}/montage/score", response_model=ClipScore)
async def get_clip_score(
    project_id: str,
    media_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> ClipScore:
    return await service.score_clip(project_id, media_id)


@router.get("/{project_id}/montage/highlights", response_model=ProjectClipHighlightsResponse)
async def list_clip_highlights(
    project_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> ProjectClipHighlightsResponse:
    return await service.list_clip_highlights(project_id)


@router.post(
    "/{project_id}/montage/highlights/refresh",
    response_model=ProjectClipHighlightsResponse,
)
async def refresh_clip_highlights(
    project_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> ProjectClipHighlightsResponse:
    return await service.detect_project_highlights(project_id, force=True)


@router.get(
    "/{project_id}/media/{media_id}/montage/highlights",
    response_model=ClipHighlights,
)
async def get_clip_highlights(
    project_id: str,
    media_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> ClipHighlights:
    return await service.detect_highlights(project_id, media_id)


@router.get("/{project_id}/montage/music-sync", response_model=ProjectMusicSyncResponse)
async def list_music_sync(
    project_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> ProjectMusicSyncResponse:
    return await service.list_music_sync(project_id)


@router.post(
    "/{project_id}/montage/music-sync/refresh",
    response_model=ProjectMusicSyncResponse,
)
async def refresh_music_sync(
    project_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> ProjectMusicSyncResponse:
    return await service.sync_project_music(project_id, force=True)


@router.get(
    "/{project_id}/media/{media_id}/montage/music-sync",
    response_model=MusicSyncAnalysis,
)
async def get_music_sync(
    project_id: str,
    media_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> MusicSyncAnalysis:
    return await service.sync_music(project_id, media_id)


@router.get(
    "/{project_id}/montage/plans/{plan_id}/transitions",
    response_model=PlanTransitionAnalysis,
)
async def get_plan_transitions(
    project_id: str,
    plan_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanTransitionAnalysis:
    analysis = await service.get_plan_transitions(project_id, plan_id)
    if analysis is None:
        return await service.recommend_transitions(project_id, plan_id)
    return analysis


@router.post(
    "/{project_id}/montage/plans/{plan_id}/transitions/refresh",
    response_model=PlanTransitionAnalysis,
)
async def refresh_plan_transitions(
    project_id: str,
    plan_id: str,
    apply: bool = False,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanTransitionAnalysis:
    return await service.recommend_transitions(project_id, plan_id, force=True, apply=apply)


@router.get(
    "/{project_id}/montage/plans/{plan_id}/pacing",
    response_model=PlanPacingAnalysis,
)
async def get_plan_pacing(
    project_id: str,
    plan_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanPacingAnalysis:
    analysis = await service.get_plan_pacing(project_id, plan_id)
    if analysis is None:
        return await service.recommend_pacing(project_id, plan_id)
    return analysis


@router.post(
    "/{project_id}/montage/plans/{plan_id}/pacing/refresh",
    response_model=PlanPacingAnalysis,
)
async def refresh_plan_pacing(
    project_id: str,
    plan_id: str,
    apply: bool = False,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanPacingAnalysis:
    return await service.recommend_pacing(project_id, plan_id, force=True, apply=apply)


@router.get(
    "/{project_id}/montage/plans/{plan_id}/effects",
    response_model=PlanEffectsAnalysis,
)
async def get_plan_effects(
    project_id: str,
    plan_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanEffectsAnalysis:
    analysis = await service.get_plan_effects(project_id, plan_id)
    if analysis is None:
        return await service.recommend_effects(project_id, plan_id)
    return analysis


@router.post(
    "/{project_id}/montage/plans/{plan_id}/effects/refresh",
    response_model=PlanEffectsAnalysis,
)
async def refresh_plan_effects(
    project_id: str,
    plan_id: str,
    apply: bool = False,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanEffectsAnalysis:
    return await service.recommend_effects(project_id, plan_id, force=True, apply=apply)


@router.get(
    "/{project_id}/montage/plans/{plan_id}/draft",
    response_model=PlanDraftAnalysis,
)
async def get_plan_draft(
    project_id: str,
    plan_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanDraftAnalysis:
    analysis = await service.get_plan_draft(project_id, plan_id)
    if analysis is None:
        return await service.generate_draft(project_id, plan_id, apply=False)
    return analysis


@router.post(
    "/{project_id}/montage/plans/{plan_id}/draft/generate",
    response_model=PlanDraftAnalysis,
)
async def generate_plan_draft(
    project_id: str,
    plan_id: str,
    apply: bool = True,
    refresh_sources: bool = False,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanDraftAnalysis:
    return await service.generate_draft(
        project_id,
        plan_id,
        force=True,
        apply=apply,
        refresh_sources=refresh_sources,
    )


@router.get(
    "/{project_id}/montage/plans/{plan_id}/timeline-application",
    response_model=PlanTimelineApplication,
)
async def get_plan_timeline_application(
    project_id: str,
    plan_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanTimelineApplication:
    application = await service.get_plan_timeline_application(project_id, plan_id)
    if application is None:
        raise PlanTimelineApplicationNotFoundError(
            f"No timeline application found for plan: {plan_id}",
        )
    return application


@router.post(
    "/{project_id}/montage/plans/{plan_id}/timeline/apply",
    response_model=PlanTimelineApplication,
)
async def apply_plan_to_timeline(
    project_id: str,
    plan_id: str,
    timeline_id: str | None = None,
    confirm_overwrite: bool = False,
    clip_ids: list[str] | None = None,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanTimelineApplication:
    return await service.apply_plan_to_timeline(
        project_id,
        plan_id,
        timeline_id=timeline_id,
        confirm_overwrite=confirm_overwrite,
        clip_ids=clip_ids,
    )


@router.get(
    "/{project_id}/montage/plans/{plan_id}/feedback",
    response_model=PlanFeedbackState,
)
async def get_plan_feedback(
    project_id: str,
    plan_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanFeedbackState:
    return await service.get_plan_feedback(project_id, plan_id)


@router.post(
    "/{project_id}/montage/plans/{plan_id}/feedback/analyze",
    response_model=PlanQualityAnalysis,
)
async def analyze_plan_quality(
    project_id: str,
    plan_id: str,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanQualityAnalysis:
    return await service.analyze_plan_quality(project_id, plan_id, force=True)


@router.post(
    "/{project_id}/montage/plans/{plan_id}/feedback",
    response_model=PlanFeedbackState,
)
async def submit_plan_feedback(
    project_id: str,
    plan_id: str,
    request: SubmitPlanFeedbackRequest,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanFeedbackState:
    return await service.submit_feedback(project_id, plan_id, request)


@router.post(
    "/{project_id}/montage/plans/{plan_id}/feedback/regenerate",
    response_model=PlanFeedbackRegenerationResult,
)
async def regenerate_plan_from_feedback(
    project_id: str,
    plan_id: str,
    action: FeedbackActionType | None = None,
    service: MontagePlanService = Depends(get_montage_plan_service),
) -> PlanFeedbackRegenerationResult:
    return await service.regenerate_from_feedback(project_id, plan_id, action=action)
