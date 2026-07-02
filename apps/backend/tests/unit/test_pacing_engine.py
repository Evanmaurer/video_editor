from __future__ import annotations

import pytest

from montage_backend.models.domain.montage_plan import (
    MontagePlan,
    MontagePlanClip,
    MontagePlanMetadata,
    MontagePlanMusic,
    MontagePlanStatus,
)
from montage_backend.models.domain.plan_pacing import PACING_ENGINE_VERSION
from montage_backend.montage.base import MontagePlanContext, MontagePlanState
from montage_backend.montage.modules.pacing import PacingEngineModule
from montage_backend.montage.pacing_engine import (
    apply_pacing_recommendations,
    build_cache_key,
    normalize_pacing_profile,
    recommend_plan_pacing,
)
from montage_backend.montage.registry import build_default_montage_registry


def _clip(
    clip_id: str,
    *,
    order: int,
    media_id: str,
    score: float,
    source_duration_ms: int = 8000,
) -> MontagePlanClip:
    return MontagePlanClip(
        id=clip_id,
        media_id=media_id,
        order=order,
        source_start_ms=0,
        source_end_ms=source_duration_ms,
        timeline_start_ms=0,
        timeline_end_ms=3000,
        clip_score=score,
        confidence=0.9,
        reasoning="test clip",
    )


def _plan(
    *,
    pacing_profile: str,
    clips: list[MontagePlanClip],
    seed: int = 42,
    target_duration_ms: int | None = None,
) -> MontagePlan:
    return MontagePlan(
        id="plan-pacing-1",
        project_id="project-1",
        name="Pacing Test",
        status=MontagePlanStatus.DRAFT,
        clips=clips,
        music=MontagePlanMusic(
            media_id="music-1",
            bpm=120.0,
            beat_markers_ms=[2400, 4800, 7200],
            confidence=0.9,
            reasoning="test music",
        ),
        metadata=MontagePlanMetadata(
            random_seed=seed,
            pacing_profile=pacing_profile,
            target_duration_ms=target_duration_ms,
        ),
        created_at="2026-06-27T00:00:00Z",
        updated_at="2026-06-27T00:00:00Z",
    )


def test_normalize_pacing_profile_supports_story_driven():
    assert normalize_pacing_profile("story-driven") == "story_driven"
    assert normalize_pacing_profile("slow cinematic") == "cinematic"


def test_aggressive_pacing_uses_shorter_durations_than_cinematic():
    clips = [
        _clip("c1", order=0, media_id="m1", score=80),
        _clip("c2", order=1, media_id="m2", score=75),
    ]
    aggressive = recommend_plan_pacing(
        project_id="project-1",
        plan=_plan(pacing_profile="aggressive", clips=clips, seed=10),
    )
    cinematic = recommend_plan_pacing(
        project_id="project-1",
        plan=_plan(pacing_profile="cinematic", clips=clips, seed=10),
    )
    assert aggressive.total_duration_ms < cinematic.total_duration_ms


def test_target_duration_scales_total_runtime():
    clips = [
        _clip("c1", order=0, media_id="m1", score=70),
        _clip("c2", order=1, media_id="m2", score=72),
        _clip("c3", order=2, media_id="m3", score=68),
    ]
    analysis = recommend_plan_pacing(
        project_id="project-1",
        plan=_plan(pacing_profile="balanced", clips=clips, seed=5, target_duration_ms=9000),
    )
    assert analysis.total_duration_ms == pytest.approx(9000, abs=1500)


def test_music_driven_can_snap_to_beat_markers():
    clips = [
        _clip("c1", order=0, media_id="m1", score=80, source_duration_ms=10000),
    ]
    analysis = recommend_plan_pacing(
        project_id="project-1",
        plan=_plan(pacing_profile="music_driven", clips=clips, seed=3),
        beat_markers_ms=[2400],
    )
    assert analysis.recommendations[0].timeline_end_ms in {2400, analysis.recommendations[0].timeline_start_ms + analysis.recommendations[0].timeline_duration_ms}


def test_recommend_plan_pacing_is_sequential_and_cached():
    clips = [
        _clip("c1", order=0, media_id="m1", score=70),
        _clip("c2", order=1, media_id="m2", score=80),
    ]
    plan = _plan(pacing_profile="balanced", clips=clips, seed=7)
    analysis = recommend_plan_pacing(project_id="project-1", plan=plan)
    assert analysis.clip_count == 2
    assert analysis.recommendations[0].timeline_start_ms == 0
    assert analysis.recommendations[1].timeline_start_ms == analysis.recommendations[0].timeline_end_ms
    assert analysis.cache_key.startswith(PACING_ENGINE_VERSION)
    assert build_cache_key(
        plan.id,
        plan.metadata.random_seed,
        plan.metadata.pacing_profile,
        plan.metadata.target_duration_ms,
        clips,
    ) == analysis.cache_key


def test_apply_pacing_recommendations_updates_plan_clips():
    clips = [
        _clip("c1", order=0, media_id="m1", score=70),
        _clip("c2", order=1, media_id="m2", score=80),
    ]
    plan = _plan(pacing_profile="balanced", clips=clips, seed=1)
    analysis = recommend_plan_pacing(project_id="project-1", plan=plan)
    apply_pacing_recommendations(plan, analysis.recommendations)
    assert plan.clips[0].timeline_end_ms == analysis.recommendations[0].timeline_end_ms
    assert plan.clips[1].timeline_start_ms == analysis.recommendations[1].timeline_start_ms
    assert plan.duration_ms == analysis.total_duration_ms


@pytest.mark.asyncio
async def test_pacing_engine_module_plan():
    clips = [_clip("c1", order=0, media_id="m1", score=75)]
    plan = _plan(pacing_profile="balanced", clips=clips)
    module = PacingEngineModule()
    ctx = MontagePlanContext(
        project_id="project-1",
        plan_id=plan.id,
        random_seed=42,
        extras={"plan": plan, "beat_markers_ms": []},
    )
    output = await module.plan(ctx, MontagePlanState())
    assert output.module_id == "pacing"
    assert output.payload["clip_count"] == 1


def test_default_registry_registers_pacing():
    registry = build_default_montage_registry()
    module = registry.get("pacing")
    assert module.module_id.value == "pacing"
