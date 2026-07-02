from __future__ import annotations

import pytest

from montage_backend.models.domain.montage_plan import (
    MontagePlan,
    MontagePlanClip,
    MontagePlanMetadata,
    MontagePlanMusic,
    MontagePlanStatus,
    MontageTransition,
    TransitionType,
)
from montage_backend.models.domain.plan_transitions import TRANSITION_ENGINE_VERSION
from montage_backend.montage.base import MontagePlanContext, MontagePlanState
from montage_backend.montage.modules.transitions import TransitionEngineModule
from montage_backend.montage.registry import build_default_montage_registry
from montage_backend.montage.transition_engine import (
    apply_transition_recommendations,
    build_cache_key,
    normalize_pacing_profile,
    recommend_plan_transitions,
)


def _clip(
    clip_id: str,
    *,
    order: int,
    media_id: str,
    score: float,
    timeline_start_ms: int,
    timeline_end_ms: int,
) -> MontagePlanClip:
    return MontagePlanClip(
        id=clip_id,
        media_id=media_id,
        order=order,
        source_start_ms=0,
        source_end_ms=timeline_end_ms - timeline_start_ms,
        timeline_start_ms=timeline_start_ms,
        timeline_end_ms=timeline_end_ms,
        clip_score=score,
        confidence=0.9,
        reasoning="test clip",
    )


def _plan(*, pacing_profile: str, clips: list[MontagePlanClip], seed: int = 42) -> MontagePlan:
    return MontagePlan(
        id="plan-1",
        project_id="project-1",
        name="Test Plan",
        status=MontagePlanStatus.DRAFT,
        clips=clips,
        music=MontagePlanMusic(
            media_id="music-1",
            bpm=128.0,
            beat_markers_ms=[3000, 6000],
            confidence=0.9,
            reasoning="test music",
        ),
        metadata=MontagePlanMetadata(
            random_seed=seed,
            pacing_profile=pacing_profile,
        ),
        created_at="2026-06-27T00:00:00Z",
        updated_at="2026-06-27T00:00:00Z",
    )


def test_normalize_pacing_profile():
    assert normalize_pacing_profile("fast montage") == "aggressive"
    assert normalize_pacing_profile("slow cinematic") == "cinematic"
    assert normalize_pacing_profile("music-driven") == "music_driven"
    assert normalize_pacing_profile(None) == "balanced"


def test_recommend_plan_transitions_generates_junctions():
    plan = _plan(
        pacing_profile="balanced",
        clips=[
            _clip("c1", order=0, media_id="m1", score=70, timeline_start_ms=0, timeline_end_ms=3000),
            _clip("c2", order=1, media_id="m2", score=85, timeline_start_ms=3000, timeline_end_ms=5500),
            _clip("c3", order=2, media_id="m3", score=60, timeline_start_ms=5500, timeline_end_ms=8000),
        ],
    )
    analysis = recommend_plan_transitions(project_id="project-1", plan=plan)
    assert analysis.junction_count == 2
    assert len(analysis.recommendations) == 2
    assert analysis.recommendations[0].timeline_ms == 3000
    assert analysis.recommendations[0].transition_out.type in TransitionType
    assert analysis.cache_key.startswith(TRANSITION_ENGINE_VERSION)


def test_aggressive_pacing_prefers_high_energy_transitions():
    plan = _plan(
        pacing_profile="aggressive",
        clips=[
            _clip("c1", order=0, media_id="m1", score=90, timeline_start_ms=0, timeline_end_ms=2500),
            _clip("c2", order=1, media_id="m2", score=92, timeline_start_ms=2500, timeline_end_ms=5000),
        ],
        seed=99,
    )
    analysis = recommend_plan_transitions(project_id="project-1", plan=plan)
    transition_type = analysis.recommendations[0].transition_out.type
    assert transition_type in {
        TransitionType.FLASH,
        TransitionType.WHIP,
        TransitionType.HARD_CUT,
        TransitionType.MOTION_BLUR,
        TransitionType.SPEED_RAMP,
        TransitionType.ZOOM,
    }


def test_beat_aligned_junction_boosts_hard_cut_or_flash():
    plan = _plan(
        pacing_profile="music_driven",
        clips=[
            _clip("c1", order=0, media_id="m1", score=75, timeline_start_ms=0, timeline_end_ms=3000),
            _clip("c2", order=1, media_id="m2", score=78, timeline_start_ms=3000, timeline_end_ms=6000),
        ],
    )
    analysis = recommend_plan_transitions(
        project_id="project-1",
        plan=plan,
        beat_markers_ms=[3000],
    )
    transition_type = analysis.recommendations[0].transition_out.type
    assert transition_type in {TransitionType.HARD_CUT, TransitionType.FLASH}


def test_cache_key_is_stable_for_same_plan():
    clips = [
        _clip("c1", order=0, media_id="m1", score=70, timeline_start_ms=0, timeline_end_ms=3000),
        _clip("c2", order=1, media_id="m2", score=80, timeline_start_ms=3000, timeline_end_ms=6000),
    ]
    plan = _plan(pacing_profile="balanced", clips=clips, seed=7)
    key_a = build_cache_key(plan.id, plan.metadata.random_seed, plan.metadata.pacing_profile, clips)
    key_b = build_cache_key(plan.id, plan.metadata.random_seed, plan.metadata.pacing_profile, clips)
    assert key_a == key_b


def test_apply_transition_recommendations_updates_plan_clips():
    plan = _plan(
        pacing_profile="balanced",
        clips=[
            _clip("c1", order=0, media_id="m1", score=70, timeline_start_ms=0, timeline_end_ms=3000),
            _clip("c2", order=1, media_id="m2", score=80, timeline_start_ms=3000, timeline_end_ms=6000),
        ],
    )
    analysis = recommend_plan_transitions(project_id="project-1", plan=plan)
    apply_transition_recommendations(plan, analysis.recommendations)
    assert plan.clips[0].transition_out is not None
    assert plan.clips[1].transition_in is not None
    assert plan.clips[0].transition_out.type == analysis.recommendations[0].transition_out.type


@pytest.mark.asyncio
async def test_transition_engine_module_plan():
    plan = _plan(
        pacing_profile="balanced",
        clips=[
            _clip("c1", order=0, media_id="m1", score=70, timeline_start_ms=0, timeline_end_ms=3000),
            _clip("c2", order=1, media_id="m2", score=80, timeline_start_ms=3000, timeline_end_ms=6000),
        ],
    )
    module = TransitionEngineModule()
    ctx = MontagePlanContext(
        project_id="project-1",
        plan_id="plan-1",
        random_seed=42,
        extras={"plan": plan, "beat_markers_ms": [3000]},
    )
    output = await module.plan(ctx, MontagePlanState())
    assert output.module_id == "transitions"
    assert output.payload["junction_count"] == 1


def test_default_registry_registers_transitions():
    registry = build_default_montage_registry()
    module = registry.get("transitions")
    assert module.module_id.value == "transitions"
