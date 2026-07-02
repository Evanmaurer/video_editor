from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from montage_backend.logging import get_logger
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.plan_timeline import PlanTimelineApplication
from montage_backend.models.domain.plan_feedback import (
    FeedbackActionType,
    PlanFeedbackEvent,
    PlanFeedbackRegenerationResult,
    PlanFeedbackState,
    PlanQualityAnalysis,
    SubmitPlanFeedbackRequest,
)
from montage_backend.models.domain.plan_draft import PlanDraftAnalysis
from montage_backend.models.domain.plan_effects import PlanEffectsAnalysis
from montage_backend.models.domain.plan_pacing import PlanPacingAnalysis
from montage_backend.models.domain.plan_transitions import PlanTransitionAnalysis
from montage_backend.models.domain.music_sync import (
    MUSIC_SYNC_VERSION,
    MusicSyncAnalysis,
    ProjectMusicSyncResponse,
)
from montage_backend.models.domain.clip_highlight import (
    HIGHLIGHT_DETECTOR_VERSION,
    ClipHighlights,
    ProjectClipHighlightsResponse,
)
from montage_backend.models.domain.clip_score import (
    CLIP_SCORER_VERSION,
    ClipScore,
    ProjectClipScoresResponse,
)
from montage_backend.models.domain.media import MediaItem, MediaNotFoundError, MediaRole
from montage_backend.models.domain.montage_plan import (
    CreateMontagePlanRequest,
    MontagePlan,
    MontagePlanMusic,
    MontagePlanNotFoundError,
    MontagePlanNotReadyError,
    MontagePlanStatus,
    MontagePlanSummary,
    UpdateMontagePlanRequest,
    compute_plan_duration_ms,
    new_montage_plan,
    plan_to_summary,
    validate_montage_plan,
)
from montage_backend.montage.base import MontageModuleId, MontagePlanContext, MontagePlanState
from montage_backend.montage.draft_generator import (
    apply_draft_to_plan,
    build_cache_key as build_draft_cache_key,
    build_project_signature,
    generate_plan_draft,
)
from montage_backend.montage.effects_engine import (
    ClipMotionSignals,
    apply_effect_recommendations,
    build_cache_key as build_effects_cache_key,
    extract_motion_signals,
    recommend_plan_effects,
)
from montage_backend.montage.pacing_engine import (
    apply_pacing_recommendations,
    build_cache_key as build_pacing_cache_key,
    recommend_plan_pacing,
)
from montage_backend.montage.transition_engine import (
    apply_transition_recommendations,
    build_cache_key as build_transition_cache_key,
    recommend_plan_transitions,
)
from montage_backend.montage.music_sync import analyze_music_sync
from montage_backend.montage.music_sync import build_cache_key as build_music_sync_cache_key
from montage_backend.montage.highlight_detection import build_cache_key as build_highlight_cache_key
from montage_backend.montage.highlight_detection import detect_clip_highlights
from montage_backend.montage.clip_scoring import build_cache_key, score_clip_analysis
from montage_backend.montage.feedback_engine import (
    apply_feedback_action,
    build_feedback_event,
    derive_regeneration_hints,
    estimate_plan_quality,
)
from montage_backend.montage.timeline_generator import (
    apply_plan_to_timeline_document,
    build_plan_timeline_application,
    requires_overwrite_confirmation,
    timeline_has_content,
)
from montage_backend.montage.registry import MontagePlannerRegistry, build_default_montage_registry
from montage_backend.repositories.plan_feedback_repo import PlanFeedbackRepository, PlanQualityRepository
from montage_backend.repositories.plan_timeline_repo import PlanTimelineRepository
from montage_backend.repositories.plan_draft_repo import PlanDraftRepository
from montage_backend.repositories.plan_effects_repo import PlanEffectsRepository
from montage_backend.repositories.plan_pacing_repo import PlanPacingRepository
from montage_backend.repositories.plan_transition_repo import PlanTransitionRepository
from montage_backend.repositories.music_sync_repo import MusicSyncRepository
from montage_backend.repositories.clip_highlight_repo import ClipHighlightRepository
from montage_backend.repositories.clip_score_repo import ClipScoreRepository
from montage_backend.repositories.montage_plan_repo import MontagePlanRepository
from montage_backend.services.project_service import ProjectService
from montage_backend.services.timeline_service import TimelineService

logger = get_logger(__name__)


class MontagePlanService:
    def __init__(
        self,
        project_service: ProjectService,
        registry: MontagePlannerRegistry | None = None,
        timeline_service: TimelineService | None = None,
        *,
        get_clip_analysis: Callable[[str, str], Awaitable[object]] | None = None,
        list_project_media: Callable[[str], Awaitable[list[MediaItem]]] | None = None,
    ) -> None:
        self._project_service = project_service
        self._repo = MontagePlanRepository()
        self._score_repo = ClipScoreRepository()
        self._highlight_repo = ClipHighlightRepository()
        self._music_sync_repo = MusicSyncRepository()
        self._transition_repo = PlanTransitionRepository()
        self._pacing_repo = PlanPacingRepository()
        self._effects_repo = PlanEffectsRepository()
        self._draft_repo = PlanDraftRepository()
        self._timeline_repo = PlanTimelineRepository()
        self._quality_repo = PlanQualityRepository()
        self._feedback_repo = PlanFeedbackRepository()
        self._timeline_service = timeline_service
        self._registry = registry or build_default_montage_registry()
        self._get_clip_analysis = get_clip_analysis
        self._list_project_media = list_project_media

    @property
    def registry(self) -> MontagePlannerRegistry:
        return self._registry

    def wire_analysis_hooks(
        self,
        *,
        get_clip_analysis: Callable[[str, str], Awaitable[object]],
        list_project_media: Callable[[str], Awaitable[list[MediaItem]]],
    ) -> None:
        self._get_clip_analysis = get_clip_analysis
        self._list_project_media = list_project_media

    async def create_plan(
        self,
        project_id: str,
        request: CreateMontagePlanRequest,
    ) -> MontagePlan:
        await self._project_service.get_project(project_id)
        plan = new_montage_plan(
            project_id=project_id,
            name=request.name,
            random_seed=request.random_seed,
            target_duration_ms=request.target_duration_ms,
            pacing_profile=request.pacing_profile,
        )
        validate_montage_plan(plan)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._repo.create(session, plan)

    async def get_plan(self, project_id: str, plan_id: str) -> MontagePlan:
        plan = await self._load_plan(project_id, plan_id)
        return plan

    async def list_plans(self, project_id: str, *, limit: int = 100) -> list[MontagePlanSummary]:
        await self._project_service.get_project(project_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            plans = await self._repo.list_for_project(session, project_id, limit=limit)
        return [plan_to_summary(plan) for plan in plans]

    async def update_plan(
        self,
        project_id: str,
        plan_id: str,
        request: UpdateMontagePlanRequest,
    ) -> MontagePlan:
        plan = await self._load_plan(project_id, plan_id)
        if request.name is not None:
            plan.name = request.name
        if request.status is not None:
            plan.status = request.status
        if request.clips is not None:
            plan.clips = request.clips
        if request.title_card is not None:
            plan.title_card = request.title_card
        if request.ending_card is not None:
            plan.ending_card = request.ending_card
        if request.music is not None:
            plan.music = request.music
        if request.overall_confidence is not None:
            plan.overall_confidence = request.overall_confidence
        if request.overall_reasoning is not None:
            plan.overall_reasoning = request.overall_reasoning
        if request.duration_ms is not None:
            plan.duration_ms = request.duration_ms
        if request.applied_timeline_id is not None:
            plan.applied_timeline_id = request.applied_timeline_id
        if request.metadata is not None:
            plan.metadata = request.metadata
        plan.version += 1
        plan.duration_ms = compute_plan_duration_ms(plan)
        plan.updated_at = utc_now_iso()
        validate_montage_plan(plan)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._repo.update(session, plan)

    async def delete_plan(self, project_id: str, plan_id: str) -> None:
        await self._load_plan(project_id, plan_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._repo.delete(session, plan_id)

    async def score_clip(self, project_id: str, media_id: str, *, force: bool = False) -> ClipScore:
        await self._ensure_hooks()
        media_items = await self._list_project_media(project_id)
        media = next((item for item in media_items if item.id == media_id), None)
        if media is None:
            raise MediaNotFoundError(f"Media not found: {media_id}")

        record = await self._fetch_analysis(project_id, media_id)
        expected_cache_key = build_cache_key(record.source_fingerprint)

        _, session_factory = await self._project_session(project_id)
        if not force:
            async with session_factory() as session:
                cached = await self._score_repo.get_for_media(session, media_id)
            if cached is not None and cached.cache_key == expected_cache_key:
                return cached

        score = score_clip_analysis(
            project_id=project_id,
            media_id=media_id,
            record=record,
            file_name=media.file_name,
            updated_at=utc_now_iso(),
        )
        async with session_factory() as session:
            return await self._score_repo.upsert(session, score)

    async def score_project(self, project_id: str, *, force: bool = False) -> ProjectClipScoresResponse:
        await self._ensure_hooks()
        media_items = await self._list_project_media(project_id)
        clips = [item for item in media_items if item.role == MediaRole.CLIP]
        scores: list[ClipScore] = []
        for media in clips:
            score = await self.score_clip(project_id, media.id, force=force)
            scores.append(score)
        scores.sort(key=lambda item: item.montage_score, reverse=True)
        return ProjectClipScoresResponse(
            project_id=project_id,
            scorer_version=CLIP_SCORER_VERSION,
            clip_count=len(scores),
            scores=scores,
        )

    async def get_clip_score(self, project_id: str, media_id: str) -> ClipScore | None:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._score_repo.get_for_media(session, media_id)

    async def list_clip_scores(self, project_id: str) -> ProjectClipScoresResponse:
        await self._project_service.get_project(project_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            scores = await self._score_repo.list_for_project(session, project_id)
        return ProjectClipScoresResponse(
            project_id=project_id,
            scorer_version=CLIP_SCORER_VERSION,
            clip_count=len(scores),
            scores=scores,
        )

    async def detect_highlights(
        self,
        project_id: str,
        media_id: str,
        *,
        force: bool = False,
    ) -> ClipHighlights:
        await self._ensure_hooks()
        media_items = await self._list_project_media(project_id)
        media = next((item for item in media_items if item.id == media_id), None)
        if media is None:
            raise MediaNotFoundError(f"Media not found: {media_id}")

        record = await self._fetch_analysis(project_id, media_id)
        expected_cache_key = build_highlight_cache_key(record.source_fingerprint)

        _, session_factory = await self._project_session(project_id)
        if not force:
            async with session_factory() as session:
                cached = await self._highlight_repo.get_for_media(session, media_id)
            if cached is not None and cached.cache_key == expected_cache_key:
                return cached

        highlights = detect_clip_highlights(
            project_id=project_id,
            media_id=media_id,
            record=record,
            file_name=media.file_name,
            updated_at=utc_now_iso(),
        )
        async with session_factory() as session:
            return await self._highlight_repo.upsert(session, highlights)

    async def detect_project_highlights(
        self,
        project_id: str,
        *,
        force: bool = False,
    ) -> ProjectClipHighlightsResponse:
        await self._ensure_hooks()
        media_items = await self._list_project_media(project_id)
        clips = [item for item in media_items if item.role == MediaRole.CLIP]
        results: list[ClipHighlights] = []
        for media in clips:
            result = await self.detect_highlights(project_id, media.id, force=force)
            results.append(result)
        results.sort(key=lambda item: item.highlight_count, reverse=True)
        return ProjectClipHighlightsResponse(
            project_id=project_id,
            detector_version=HIGHLIGHT_DETECTOR_VERSION,
            clip_count=len(results),
            clips=results,
        )

    async def get_clip_highlights(self, project_id: str, media_id: str) -> ClipHighlights | None:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._highlight_repo.get_for_media(session, media_id)

    async def list_clip_highlights(self, project_id: str) -> ProjectClipHighlightsResponse:
        await self._project_service.get_project(project_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            clips = await self._highlight_repo.list_for_project(session, project_id)
        return ProjectClipHighlightsResponse(
            project_id=project_id,
            detector_version=HIGHLIGHT_DETECTOR_VERSION,
            clip_count=len(clips),
            clips=clips,
        )

    async def sync_music(
        self,
        project_id: str,
        media_id: str,
        *,
        force: bool = False,
    ) -> MusicSyncAnalysis:
        await self._ensure_hooks()
        media_items = await self._list_project_media(project_id)
        media = next((item for item in media_items if item.id == media_id), None)
        if media is None:
            raise MediaNotFoundError(f"Media not found: {media_id}")

        record = await self._fetch_analysis(project_id, media_id)
        expected_cache_key = build_music_sync_cache_key(record.source_fingerprint)

        _, session_factory = await self._project_session(project_id)
        if not force:
            async with session_factory() as session:
                cached = await self._music_sync_repo.get_for_media(session, media_id)
            if cached is not None and cached.cache_key == expected_cache_key:
                return cached

        analysis = analyze_music_sync(
            project_id=project_id,
            media_id=media_id,
            record=record,
            file_name=media.file_name,
            updated_at=utc_now_iso(),
        )
        async with session_factory() as session:
            return await self._music_sync_repo.upsert(session, analysis)

    async def sync_project_music(
        self,
        project_id: str,
        *,
        force: bool = False,
    ) -> ProjectMusicSyncResponse:
        await self._ensure_hooks()
        media_items = await self._list_project_media(project_id)
        tracks = [item for item in media_items if item.role == MediaRole.MUSIC]
        results: list[MusicSyncAnalysis] = []
        for media in tracks:
            result = await self.sync_music(project_id, media.id, force=force)
            results.append(result)
        return ProjectMusicSyncResponse(
            project_id=project_id,
            sync_version=MUSIC_SYNC_VERSION,
            track_count=len(results),
            tracks=results,
        )

    async def get_music_sync(self, project_id: str, media_id: str) -> MusicSyncAnalysis | None:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._music_sync_repo.get_for_media(session, media_id)

    async def list_music_sync(self, project_id: str) -> ProjectMusicSyncResponse:
        await self._project_service.get_project(project_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            tracks = await self._music_sync_repo.list_for_project(session, project_id)
        return ProjectMusicSyncResponse(
            project_id=project_id,
            sync_version=MUSIC_SYNC_VERSION,
            track_count=len(tracks),
            tracks=tracks,
        )

    async def run_music_sync_module(self, project_id: str, plan_id: str) -> MontagePlan:
        await self._ensure_hooks()
        plan = await self._load_plan(project_id, plan_id)
        media_items = await self._list_project_media(project_id)
        music_items = [item for item in media_items if item.role == MediaRole.MUSIC]
        if plan.music is not None and plan.music.media_id:
            selected = next(
                (item for item in music_items if item.id == plan.music.media_id),
                None,
            )
            if selected is not None:
                music_items = [selected]

        records = []
        for media in music_items:
            records.append(await self._fetch_analysis(project_id, media.id))

        ctx = MontagePlanContext(
            project_id=project_id,
            plan_id=plan_id,
            random_seed=plan.metadata.random_seed,
            target_duration_ms=plan.metadata.target_duration_ms,
            pacing_profile=plan.metadata.pacing_profile,
        )
        ctx.extras["music_records"] = records
        state = MontagePlanState()
        module = self._registry.get(MontageModuleId.MUSIC_SYNC)
        output = await module.plan(ctx, state)

        now = utc_now_iso()
        primary: MusicSyncAnalysis | None = None
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            for record in records:
                media = next(item for item in music_items if item.id == record.media_id)
                analysis = analyze_music_sync(
                    project_id=project_id,
                    media_id=record.media_id,
                    record=record,
                    file_name=media.file_name,
                    updated_at=now,
                )
                saved = await self._music_sync_repo.upsert(session, analysis)
                if primary is None:
                    primary = saved

        if primary is not None:
            plan.music = plan.music or MontagePlanMusic()
            plan.music.media_id = primary.media_id
            plan.music.bpm = primary.tempo_bpm
            plan.music.beat_markers_ms = [beat.timestamp_ms for beat in primary.beat_markers]
            plan.music.confidence = primary.confidence
            plan.music.reasoning = primary.reasoning

        plan.metadata.module_outputs[MontageModuleId.MUSIC_SYNC.value] = output.model_dump(mode="json")
        plan.updated_at = now
        async with session_factory() as session:
            return await self._repo.update(session, plan)

    async def recommend_transitions(
        self,
        project_id: str,
        plan_id: str,
        *,
        force: bool = False,
        apply: bool = False,
    ) -> PlanTransitionAnalysis:
        plan = await self._load_plan(project_id, plan_id)
        beat_markers_ms = plan.music.beat_markers_ms if plan.music else []
        expected_cache_key = build_transition_cache_key(
            plan.id,
            plan.metadata.random_seed,
            plan.metadata.pacing_profile,
            plan.clips,
        )

        _, session_factory = await self._project_session(project_id)
        if not force:
            async with session_factory() as session:
                cached = await self._transition_repo.get_for_plan(session, plan_id)
            if cached is not None and cached.cache_key == expected_cache_key:
                if apply and cached.recommendations:
                    plan = await self._load_plan(project_id, plan_id)
                    apply_transition_recommendations(plan, cached.recommendations)
                    plan.version += 1
                    plan.updated_at = utc_now_iso()
                    validate_montage_plan(plan)
                    async with session_factory() as session:
                        await self._repo.update(session, plan)
                return cached

        analysis = recommend_plan_transitions(
            project_id=project_id,
            plan=plan,
            beat_markers_ms=beat_markers_ms,
            updated_at=utc_now_iso(),
        )
        async with session_factory() as session:
            saved = await self._transition_repo.upsert(session, analysis)

        if apply and saved.recommendations:
            plan = await self._load_plan(project_id, plan_id)
            apply_transition_recommendations(plan, saved.recommendations)
            plan.version += 1
            plan.updated_at = utc_now_iso()
            validate_montage_plan(plan)
            async with session_factory() as session:
                await self._repo.update(session, plan)

        return saved

    async def get_plan_transitions(
        self,
        project_id: str,
        plan_id: str,
    ) -> PlanTransitionAnalysis | None:
        await self._load_plan(project_id, plan_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._transition_repo.get_for_plan(session, plan_id)

    async def run_transitions_module(self, project_id: str, plan_id: str) -> MontagePlan:
        plan = await self._load_plan(project_id, plan_id)
        beat_markers_ms = plan.music.beat_markers_ms if plan.music else []

        ctx = MontagePlanContext(
            project_id=project_id,
            plan_id=plan_id,
            random_seed=plan.metadata.random_seed,
            target_duration_ms=plan.metadata.target_duration_ms,
            pacing_profile=plan.metadata.pacing_profile,
        )
        ctx.extras["plan"] = plan
        ctx.extras["beat_markers_ms"] = beat_markers_ms
        state = MontagePlanState()
        module = self._registry.get(MontageModuleId.TRANSITIONS)
        output = await module.plan(ctx, state)

        analysis = PlanTransitionAnalysis.model_validate(output.payload)
        now = utc_now_iso()
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._transition_repo.upsert(session, analysis)

        apply_transition_recommendations(plan, analysis.recommendations)
        plan.metadata.module_outputs[MontageModuleId.TRANSITIONS.value] = output.model_dump(mode="json")
        plan.version += 1
        plan.updated_at = now
        validate_montage_plan(plan)
        async with session_factory() as session:
            return await self._repo.update(session, plan)

    async def recommend_pacing(
        self,
        project_id: str,
        plan_id: str,
        *,
        force: bool = False,
        apply: bool = False,
    ) -> PlanPacingAnalysis:
        plan = await self._load_plan(project_id, plan_id)
        beat_markers_ms = plan.music.beat_markers_ms if plan.music else []
        expected_cache_key = build_pacing_cache_key(
            plan.id,
            plan.metadata.random_seed,
            plan.metadata.pacing_profile,
            plan.metadata.target_duration_ms,
            plan.clips,
        )

        _, session_factory = await self._project_session(project_id)
        if not force:
            async with session_factory() as session:
                cached = await self._pacing_repo.get_for_plan(session, plan_id)
            if cached is not None and cached.cache_key == expected_cache_key:
                if apply and cached.recommendations:
                    plan = await self._load_plan(project_id, plan_id)
                    apply_pacing_recommendations(plan, cached.recommendations)
                    plan.duration_ms = compute_plan_duration_ms(plan)
                    plan.version += 1
                    plan.updated_at = utc_now_iso()
                    validate_montage_plan(plan)
                    async with session_factory() as session:
                        await self._repo.update(session, plan)
                return cached

        analysis = recommend_plan_pacing(
            project_id=project_id,
            plan=plan,
            beat_markers_ms=beat_markers_ms,
            updated_at=utc_now_iso(),
        )
        async with session_factory() as session:
            saved = await self._pacing_repo.upsert(session, analysis)

        if apply and saved.recommendations:
            plan = await self._load_plan(project_id, plan_id)
            apply_pacing_recommendations(plan, saved.recommendations)
            plan.duration_ms = compute_plan_duration_ms(plan)
            plan.version += 1
            plan.updated_at = utc_now_iso()
            validate_montage_plan(plan)
            async with session_factory() as session:
                await self._repo.update(session, plan)

        return saved

    async def get_plan_pacing(
        self,
        project_id: str,
        plan_id: str,
    ) -> PlanPacingAnalysis | None:
        await self._load_plan(project_id, plan_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._pacing_repo.get_for_plan(session, plan_id)

    async def run_pacing_module(self, project_id: str, plan_id: str) -> MontagePlan:
        plan = await self._load_plan(project_id, plan_id)
        beat_markers_ms = plan.music.beat_markers_ms if plan.music else []

        ctx = MontagePlanContext(
            project_id=project_id,
            plan_id=plan_id,
            random_seed=plan.metadata.random_seed,
            target_duration_ms=plan.metadata.target_duration_ms,
            pacing_profile=plan.metadata.pacing_profile,
        )
        ctx.extras["plan"] = plan
        ctx.extras["beat_markers_ms"] = beat_markers_ms
        state = MontagePlanState()
        module = self._registry.get(MontageModuleId.PACING)
        output = await module.plan(ctx, state)

        analysis = PlanPacingAnalysis.model_validate(output.payload)
        now = utc_now_iso()
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._pacing_repo.upsert(session, analysis)

        apply_pacing_recommendations(plan, analysis.recommendations)
        plan.duration_ms = compute_plan_duration_ms(plan)
        plan.metadata.module_outputs[MontageModuleId.PACING.value] = output.model_dump(mode="json")
        plan.version += 1
        plan.updated_at = now
        validate_montage_plan(plan)
        async with session_factory() as session:
            return await self._repo.update(session, plan)

    async def _list_music_media_ids(self, project_id: str) -> list[str]:
        await self._ensure_hooks()
        media_items = await self._list_project_media(project_id)
        return [item.id for item in media_items if item.role == MediaRole.MUSIC]

    async def generate_draft(
        self,
        project_id: str,
        plan_id: str,
        *,
        force: bool = False,
        apply: bool = True,
        refresh_sources: bool = False,
    ) -> PlanDraftAnalysis:
        await self._ensure_hooks()
        plan = await self._load_plan(project_id, plan_id)

        if force or refresh_sources:
            await self.score_project(project_id, force=True)
            await self.detect_project_highlights(project_id, force=True)
        else:
            scores_response = await self.list_clip_scores(project_id)
            highlights_response = await self.list_clip_highlights(project_id)
            if scores_response.clip_count == 0:
                await self.score_project(project_id, force=True)
            if highlights_response.clip_count == 0:
                await self.detect_project_highlights(project_id, force=True)

        scores_response = await self.list_clip_scores(project_id)
        highlights_response = await self.list_clip_highlights(project_id)
        music_media_ids = await self._list_music_media_ids(project_id)

        project_signature = build_project_signature(
            scores_response.scores,
            highlights_response.clips,
        )
        music_media_id = plan.music.media_id if plan.music and plan.music.media_id else (
            music_media_ids[0] if music_media_ids else None
        )
        expected_cache_key = build_draft_cache_key(
            plan.id,
            plan.metadata.random_seed,
            plan.metadata.pacing_profile,
            plan.metadata.target_duration_ms,
            project_signature,
            music_media_id,
        )

        _, session_factory = await self._project_session(project_id)
        if not force:
            async with session_factory() as session:
                cached = await self._draft_repo.get_for_plan(session, plan_id)
            if cached is not None and cached.cache_key == expected_cache_key:
                if apply:
                    await self._apply_draft_pipeline(project_id, plan_id, cached)
                return cached

        analysis = generate_plan_draft(
            project_id=project_id,
            plan=plan,
            scores=scores_response.scores,
            highlights=highlights_response.clips,
            available_music_ids=music_media_ids,
            updated_at=utc_now_iso(),
        )
        async with session_factory() as session:
            saved = await self._draft_repo.upsert(session, analysis)

        if apply:
            await self._apply_draft_pipeline(project_id, plan_id, saved)

        return saved

    async def get_plan_draft(
        self,
        project_id: str,
        plan_id: str,
    ) -> PlanDraftAnalysis | None:
        await self._load_plan(project_id, plan_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._draft_repo.get_for_plan(session, plan_id)

    async def _apply_draft_pipeline(
        self,
        project_id: str,
        plan_id: str,
        analysis: PlanDraftAnalysis,
    ) -> MontagePlan:
        plan = await self._load_plan(project_id, plan_id)
        apply_draft_to_plan(plan, analysis)
        plan.metadata.module_outputs[MontageModuleId.DRAFT.value] = analysis.model_dump(mode="json")
        plan.version += 1
        plan.updated_at = utc_now_iso()
        validate_montage_plan(plan)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._repo.update(session, plan)

        if plan.music is not None and plan.music.media_id:
            await self.run_music_sync_module(project_id, plan_id)

        await self.run_pacing_module(project_id, plan_id)
        await self.run_transitions_module(project_id, plan_id)
        await self.run_effects_module(project_id, plan_id)

        plan = await self._load_plan(project_id, plan_id)
        plan.status = MontagePlanStatus.READY
        plan.overall_confidence = analysis.confidence
        plan.overall_reasoning = analysis.reasoning
        plan.duration_ms = compute_plan_duration_ms(plan)
        plan.version += 1
        plan.updated_at = utc_now_iso()
        validate_montage_plan(plan)
        async with session_factory() as session:
            return await self._repo.update(session, plan)

    async def run_draft_module(self, project_id: str, plan_id: str) -> MontagePlan:
        await self.generate_draft(project_id, plan_id, force=True, apply=True)
        return await self.get_plan(project_id, plan_id)

    async def apply_plan_to_timeline(
        self,
        project_id: str,
        plan_id: str,
        *,
        timeline_id: str | None = None,
        confirm_overwrite: bool = False,
        clip_ids: list[str] | None = None,
    ) -> PlanTimelineApplication:
        timeline_service = self._require_timeline_service()
        plan = await self._load_plan(project_id, plan_id)
        if not plan.clips:
            raise MontagePlanNotReadyError(
                "Montage plan has no clips; generate a draft before applying to the timeline.",
            )

        if timeline_id is None:
            document = await timeline_service.get_or_create_active(project_id)
            timeline_id = document.id
        else:
            document = await timeline_service.get_timeline(project_id, timeline_id)

        overwritten = timeline_has_content(document) and requires_overwrite_confirmation(
            document,
            plan,
            partial_clip_ids=clip_ids,
        )
        updated_document = apply_plan_to_timeline_document(
            plan,
            document,
            partial_clip_ids=clip_ids,
            confirm_overwrite=confirm_overwrite,
        )
        await timeline_service.save_timeline(project_id, updated_document)

        plan = await self._load_plan(project_id, plan_id)
        plan.status = MontagePlanStatus.APPLIED
        plan.applied_timeline_id = timeline_id
        plan.version += 1
        plan.updated_at = utc_now_iso()
        validate_montage_plan(plan)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._repo.update(session, plan)

        application = build_plan_timeline_application(
            project_id=project_id,
            plan=plan,
            timeline_id=timeline_id,
            document=updated_document,
            overwritten=overwritten,
            partial_clip_ids=clip_ids,
            updated_at=utc_now_iso(),
        )
        async with session_factory() as session:
            return await self._timeline_repo.upsert(session, application)

    async def get_plan_timeline_application(
        self,
        project_id: str,
        plan_id: str,
    ) -> PlanTimelineApplication | None:
        await self._load_plan(project_id, plan_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._timeline_repo.get_for_plan(session, plan_id)

    def _require_timeline_service(self) -> TimelineService:
        if self._timeline_service is None:
            raise RuntimeError("MontagePlanService timeline service not wired")
        return self._timeline_service

    async def _collect_plan_clip_context(
        self,
        project_id: str,
        plan: MontagePlan,
    ) -> tuple[dict[str, ClipMotionSignals], dict[str, str], list[object]]:
        await self._ensure_hooks()
        clip_signals: dict[str, ClipMotionSignals] = {}
        media_fingerprints: dict[str, str] = {}
        clip_records: list[object] = []
        seen_media: set[str] = set()

        for clip in plan.clips:
            if clip.media_id in seen_media:
                continue
            seen_media.add(clip.media_id)
            try:
                record = await self._fetch_analysis(project_id, clip.media_id)
            except MediaNotFoundError:
                clip_signals[clip.media_id] = ClipMotionSignals()
                continue
            clip_records.append(record)
            clip_signals[clip.media_id] = extract_motion_signals(record)
            if record.source_fingerprint:
                media_fingerprints[clip.media_id] = record.source_fingerprint

        return clip_signals, media_fingerprints, clip_records

    async def recommend_effects(
        self,
        project_id: str,
        plan_id: str,
        *,
        force: bool = False,
        apply: bool = False,
    ) -> PlanEffectsAnalysis:
        plan = await self._load_plan(project_id, plan_id)
        clip_signals, media_fingerprints, _ = await self._collect_plan_clip_context(project_id, plan)
        beat_markers_ms = plan.music.beat_markers_ms if plan.music else []
        expected_cache_key = build_effects_cache_key(
            plan.id,
            plan.metadata.random_seed,
            plan.metadata.pacing_profile,
            plan.clips,
            media_fingerprints,
        )

        _, session_factory = await self._project_session(project_id)
        if not force:
            async with session_factory() as session:
                cached = await self._effects_repo.get_for_plan(session, plan_id)
            if cached is not None and cached.cache_key == expected_cache_key:
                if apply and cached.recommendations:
                    plan = await self._load_plan(project_id, plan_id)
                    apply_effect_recommendations(plan, cached.recommendations)
                    plan.version += 1
                    plan.updated_at = utc_now_iso()
                    validate_montage_plan(plan)
                    async with session_factory() as session:
                        await self._repo.update(session, plan)
                return cached

        analysis = recommend_plan_effects(
            project_id=project_id,
            plan=plan,
            clip_signals=clip_signals,
            media_fingerprints=media_fingerprints,
            beat_markers_ms=beat_markers_ms,
            updated_at=utc_now_iso(),
        )
        async with session_factory() as session:
            saved = await self._effects_repo.upsert(session, analysis)

        if apply and saved.recommendations:
            plan = await self._load_plan(project_id, plan_id)
            apply_effect_recommendations(plan, saved.recommendations)
            plan.version += 1
            plan.updated_at = utc_now_iso()
            validate_montage_plan(plan)
            async with session_factory() as session:
                await self._repo.update(session, plan)

        return saved

    async def get_plan_effects(
        self,
        project_id: str,
        plan_id: str,
    ) -> PlanEffectsAnalysis | None:
        await self._load_plan(project_id, plan_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            return await self._effects_repo.get_for_plan(session, plan_id)

    async def run_effects_module(self, project_id: str, plan_id: str) -> MontagePlan:
        plan = await self._load_plan(project_id, plan_id)
        clip_signals, media_fingerprints, clip_records = await self._collect_plan_clip_context(
            project_id,
            plan,
        )
        beat_markers_ms = plan.music.beat_markers_ms if plan.music else []

        ctx = MontagePlanContext(
            project_id=project_id,
            plan_id=plan_id,
            random_seed=plan.metadata.random_seed,
            target_duration_ms=plan.metadata.target_duration_ms,
            pacing_profile=plan.metadata.pacing_profile,
        )
        ctx.extras["plan"] = plan
        ctx.extras["beat_markers_ms"] = beat_markers_ms
        ctx.extras["clip_records"] = clip_records
        state = MontagePlanState()
        module = self._registry.get(MontageModuleId.EFFECTS)
        output = await module.plan(ctx, state)

        analysis = PlanEffectsAnalysis.model_validate(output.payload)
        now = utc_now_iso()
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._effects_repo.upsert(session, analysis)

        apply_effect_recommendations(plan, analysis.recommendations)
        plan.metadata.module_outputs[MontageModuleId.EFFECTS.value] = output.model_dump(mode="json")
        plan.version += 1
        plan.updated_at = now
        validate_montage_plan(plan)
        async with session_factory() as session:
            return await self._repo.update(session, plan)

    async def run_highlights_module(self, project_id: str, plan_id: str) -> MontagePlan:
        await self._ensure_hooks()
        plan = await self._load_plan(project_id, plan_id)
        media_items = await self._list_project_media(project_id)
        clips = [item for item in media_items if item.role == MediaRole.CLIP]
        records = []
        for media in clips:
            records.append(await self._fetch_analysis(project_id, media.id))

        ctx = MontagePlanContext(
            project_id=project_id,
            plan_id=plan_id,
            random_seed=plan.metadata.random_seed,
            target_duration_ms=plan.metadata.target_duration_ms,
            pacing_profile=plan.metadata.pacing_profile,
        )
        ctx.extras["clip_records"] = records
        state = MontagePlanState()
        module = self._registry.get(MontageModuleId.HIGHLIGHTS)
        output = await module.plan(ctx, state)

        now = utc_now_iso()
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            for record in records:
                media = next(item for item in clips if item.id == record.media_id)
                highlights = detect_clip_highlights(
                    project_id=project_id,
                    media_id=record.media_id,
                    record=record,
                    file_name=media.file_name,
                    updated_at=now,
                )
                await self._highlight_repo.upsert(session, highlights)

        plan.metadata.module_outputs[MontageModuleId.HIGHLIGHTS.value] = output.model_dump(mode="json")
        plan.updated_at = now
        async with session_factory() as session:
            return await self._repo.update(session, plan)

    async def run_scoring_module(self, project_id: str, plan_id: str) -> MontagePlan:
        await self._ensure_hooks()
        plan = await self._load_plan(project_id, plan_id)
        media_items = await self._list_project_media(project_id)
        clips = [item for item in media_items if item.role == MediaRole.CLIP]
        records = []
        for media in clips:
            records.append(await self._fetch_analysis(project_id, media.id))

        ctx = MontagePlanContext(
            project_id=project_id,
            plan_id=plan_id,
            random_seed=plan.metadata.random_seed,
            target_duration_ms=plan.metadata.target_duration_ms,
            pacing_profile=plan.metadata.pacing_profile,
        )
        ctx.extras["clip_records"] = records
        state = MontagePlanState()
        module = self._registry.get(MontageModuleId.SCORING)
        output = await module.plan(ctx, state)

        now = utc_now_iso()
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            for record in records:
                media = next(item for item in clips if item.id == record.media_id)
                score = score_clip_analysis(
                    project_id=project_id,
                    media_id=record.media_id,
                    record=record,
                    file_name=media.file_name,
                    updated_at=now,
                )
                await self._score_repo.upsert(session, score)

        plan.metadata.module_outputs[MontageModuleId.SCORING.value] = output.model_dump(mode="json")
        plan.updated_at = now
        async with session_factory() as session:
            return await self._repo.update(session, plan)

    async def _load_plan_module_analyses(
        self,
        project_id: str,
        plan_id: str,
    ) -> tuple[PlanTransitionAnalysis | None, PlanPacingAnalysis | None, PlanEffectsAnalysis | None]:
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            transitions = await self._transition_repo.get_for_plan(session, plan_id)
            pacing = await self._pacing_repo.get_for_plan(session, plan_id)
            effects = await self._effects_repo.get_for_plan(session, plan_id)
        return transitions, pacing, effects

    async def analyze_plan_quality(
        self,
        project_id: str,
        plan_id: str,
        *,
        force: bool = False,
    ) -> PlanQualityAnalysis:
        plan = await self._load_plan(project_id, plan_id)
        transitions, pacing, effects = await self._load_plan_module_analyses(project_id, plan_id)
        expected_cache_key = estimate_plan_quality(
            project_id=project_id,
            plan=plan,
            transitions=transitions,
            pacing=pacing,
            effects=effects,
        ).cache_key

        _, session_factory = await self._project_session(project_id)
        if not force:
            async with session_factory() as session:
                cached = await self._quality_repo.get_for_plan(session, plan_id)
            if cached is not None and cached.cache_key == expected_cache_key:
                return cached

        analysis = estimate_plan_quality(
            project_id=project_id,
            plan=plan,
            transitions=transitions,
            pacing=pacing,
            effects=effects,
            updated_at=utc_now_iso(),
        )
        async with session_factory() as session:
            return await self._quality_repo.upsert(session, analysis)

    async def get_plan_feedback(
        self,
        project_id: str,
        plan_id: str,
    ) -> PlanFeedbackState:
        plan = await self._load_plan(project_id, plan_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            quality = await self._quality_repo.get_for_plan(session, plan_id)
            events = await self._feedback_repo.list_for_plan(session, plan_id)

        if quality is None:
            quality = await self.analyze_plan_quality(project_id, plan_id)

        return PlanFeedbackState(
            plan_id=plan_id,
            project_id=project_id,
            quality=quality,
            events=events,
            feedback_preferences=dict(plan.metadata.feedback_preferences or {}),
            regeneration_hints=derive_regeneration_hints(plan, events),
        )

    async def submit_feedback(
        self,
        project_id: str,
        plan_id: str,
        request: SubmitPlanFeedbackRequest,
    ) -> PlanFeedbackState:
        plan = await self._load_plan(project_id, plan_id)
        applied_changes = apply_feedback_action(plan, request.action)
        event = build_feedback_event(
            project_id=project_id,
            plan_id=plan_id,
            action=request.action,
            comment=request.comment,
            applied_changes=applied_changes,
        )

        plan.version += 1
        plan.updated_at = utc_now_iso()
        validate_montage_plan(plan)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._repo.update(session, plan)
            await self._feedback_repo.create(session, event)
            await self._quality_repo.delete_for_plan(session, plan_id)

        return await self.get_plan_feedback(project_id, plan_id)

    async def regenerate_from_feedback(
        self,
        project_id: str,
        plan_id: str,
        *,
        action: FeedbackActionType | None = None,
    ) -> PlanFeedbackRegenerationResult:
        plan = await self._load_plan(project_id, plan_id)
        event: PlanFeedbackEvent | None = None
        if action is not None:
            applied_changes = apply_feedback_action(plan, action)
            event = build_feedback_event(
                project_id=project_id,
                plan_id=plan_id,
                action=action,
                comment="",
                applied_changes=applied_changes,
            )
            plan.version += 1
            plan.updated_at = utc_now_iso()
            validate_montage_plan(plan)
            _, session_factory = await self._project_session(project_id)
            async with session_factory() as session:
                await self._repo.update(session, plan)
                event = await self._feedback_repo.create(session, event)

        prefs = dict(plan.metadata.feedback_preferences or {})
        full_regen = bool(
            prefs.get("full_regeneration_requested")
            or (action == FeedbackActionType.REGENERATE)
            or prefs.get("preferred_profile")
            or prefs.get("target_duration_scale", 1.0) != 1.0
        )
        pacing_only = bool(prefs.get("pacing_refresh_requested")) and not full_regen

        if full_regen:
            await self.generate_draft(project_id, plan_id, force=True, apply=True)
        elif pacing_only:
            await self.run_pacing_module(project_id, plan_id)
            await self.run_transitions_module(project_id, plan_id)
            await self.run_effects_module(project_id, plan_id)
        else:
            await self.run_pacing_module(project_id, plan_id)

        plan = await self._load_plan(project_id, plan_id)
        cleared_prefs = dict(plan.metadata.feedback_preferences or {})
        cleared_prefs.pop("pacing_refresh_requested", None)
        cleared_prefs.pop("full_regeneration_requested", None)
        plan.metadata.feedback_preferences = cleared_prefs
        plan.version += 1
        plan.updated_at = utc_now_iso()
        validate_montage_plan(plan)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._repo.update(session, plan)
            await self._quality_repo.delete_for_plan(session, plan_id)

        quality = await self.analyze_plan_quality(project_id, plan_id, force=True)
        plan = await self._load_plan(project_id, plan_id)
        if event is None:
            async with session_factory() as session:
                events = await self._feedback_repo.list_for_plan(session, plan_id)
            event = events[-1] if events else build_feedback_event(
                project_id=project_id,
                plan_id=plan_id,
                action=action or FeedbackActionType.REGENERATE,
                comment="",
                applied_changes={},
            )

        return PlanFeedbackRegenerationResult(
            plan_id=plan_id,
            project_id=project_id,
            action=event.action,
            quality=quality,
            event=event,
            plan_status=plan.status.value,
            applied_changes=event.applied_changes,
        )

    async def run_feedback_module(self, project_id: str, plan_id: str) -> PlanQualityAnalysis:
        plan = await self._load_plan(project_id, plan_id)
        transitions, pacing, effects = await self._load_plan_module_analyses(project_id, plan_id)

        ctx = MontagePlanContext(
            project_id=project_id,
            plan_id=plan_id,
            random_seed=plan.metadata.random_seed,
            target_duration_ms=plan.metadata.target_duration_ms,
            pacing_profile=plan.metadata.pacing_profile,
        )
        ctx.extras["plan"] = plan
        ctx.extras["transitions"] = transitions
        ctx.extras["pacing"] = pacing
        ctx.extras["effects"] = effects
        state = MontagePlanState()
        module = self._registry.get(MontageModuleId.FEEDBACK)
        output = await module.plan(ctx, state)

        analysis = PlanQualityAnalysis.model_validate(output.payload)
        plan.metadata.module_outputs[MontageModuleId.FEEDBACK.value] = output.model_dump(mode="json")
        plan.updated_at = utc_now_iso()
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            await self._quality_repo.upsert(session, analysis)
            await self._repo.update(session, plan)
        return analysis

    async def _fetch_analysis(self, project_id: str, media_id: str):
        assert self._get_clip_analysis is not None
        record = await self._get_clip_analysis(project_id, media_id)
        if record is None:
            raise MediaNotFoundError(f"Analysis not available for media: {media_id}")
        return record

    async def _ensure_hooks(self) -> None:
        if self._get_clip_analysis is None or self._list_project_media is None:
            raise RuntimeError("MontagePlanService analysis hooks not wired")

    async def _load_plan(self, project_id: str, plan_id: str) -> MontagePlan:
        await self._project_service.get_project(project_id)
        _, session_factory = await self._project_session(project_id)
        async with session_factory() as session:
            plan = await self._repo.get(session, plan_id)
        if plan is None or plan.project_id != project_id:
            raise MontagePlanNotFoundError(f"Montage plan not found: {plan_id}")
        return plan

    async def _project_session(self, project_id: str):
        project = await self._project_service.get_project(project_id)
        session_factory = await self._project_service._ensure_project_db(Path(project.root_path))
        return project, session_factory
