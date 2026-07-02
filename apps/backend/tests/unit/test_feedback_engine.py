from __future__ import annotations

import pytest

from montage_backend.models.domain.montage_plan import (
    MontagePlan,
    MontagePlanClip,
    MontagePlanMetadata,
    MontagePlanStatus,
)
from montage_backend.models.domain.plan_feedback import (
    FEEDBACK_ENGINE_VERSION,
    FeedbackActionType,
    QualityDimension,
)
from montage_backend.montage.feedback_engine import (
    apply_feedback_action,
    build_cache_key,
    build_feedback_event,
    derive_regeneration_hints,
    estimate_plan_quality,
)
from montage_backend.montage.modules.feedback import FeedbackLoopModule
from montage_backend.montage.base import MontagePlanContext, MontagePlanState
from montage_backend.montage.registry import build_default_montage_registry


def _clip(order: int, score: float = 80.0) -> MontagePlanClip:
    return MontagePlanClip(
        id=f"clip-{order}",
        media_id=f"media-{order}",
        order=order,
        source_start_ms=0,
        source_end_ms=5000,
        timeline_start_ms=order * 3000,
        timeline_end_ms=(order + 1) * 3000,
        clip_score=score,
        confidence=0.88,
        reasoning="test clip",
    )


def _plan(*, clips: list[MontagePlanClip] | None = None) -> MontagePlan:
    clip_list = clips or [_clip(0), _clip(1, 92.0), _clip(2, 75.0)]
    return MontagePlan(
        id="plan-feedback-1",
        project_id="project-1",
        name="Feedback Test",
        status=MontagePlanStatus.READY,
        clips=clip_list,
        metadata=MontagePlanMetadata(random_seed=7, pacing_profile="balanced"),
        duration_ms=9000,
        overall_confidence=0.85,
        created_at="2026-06-27T00:00:00Z",
        updated_at="2026-06-27T00:00:00Z",
    )


def test_estimate_plan_quality_returns_five_dimensions():
    plan = _plan()
    analysis = estimate_plan_quality(project_id="project-1", plan=plan)

    assert analysis.engine_version == FEEDBACK_ENGINE_VERSION
    assert len(analysis.estimates) == 5
    dimensions = {item.dimension for item in analysis.estimates}
    assert dimensions == {
        QualityDimension.MONTAGE,
        QualityDimension.PACING,
        QualityDimension.TRANSITIONS,
        QualityDimension.EXCITEMENT,
        QualityDimension.RETENTION,
    }
    assert 0.0 <= analysis.overall_score <= 100.0
    assert analysis.cache_key.startswith(FEEDBACK_ENGINE_VERSION)


def test_build_cache_key_is_stable_for_same_plan():
    plan = _plan()
    assert build_cache_key(plan) == build_cache_key(plan)


def test_apply_feedback_action_updates_preferences_and_profile():
    plan = _plan()
    plan.metadata.target_duration_ms = 20000

    changes = apply_feedback_action(plan, FeedbackActionType.MORE_AGGRESSIVE)
    assert changes["pacing_profile"] == "aggressive"
    assert plan.metadata.pacing_profile == "aggressive"
    assert plan.metadata.feedback_preferences["preferred_profile"] == "aggressive"

    reduce_changes = apply_feedback_action(plan, FeedbackActionType.REDUCE_LENGTH)
    assert plan.metadata.target_duration_ms == 16000
    assert reduce_changes["target_duration_ms"] == 16000


def test_derive_regeneration_hints_from_feedback_history():
    plan = _plan()
    apply_feedback_action(plan, FeedbackActionType.IMPROVE_PACING)

    events = [
        build_feedback_event(
            project_id="project-1",
            plan_id=plan.id,
            action=FeedbackActionType.IMPROVE_PACING,
            comment="",
            applied_changes={},
        ),
    ]
    hints = derive_regeneration_hints(plan, events)
    assert any("beat alignment" in hint.lower() for hint in hints)


@pytest.mark.asyncio
async def test_feedback_module_runs_through_registry():
    registry = build_default_montage_registry()
    assert "feedback" in registry.list_modules()

    plan = _plan()
    module = FeedbackLoopModule()
    ctx = MontagePlanContext(
        project_id="project-1",
        plan_id=plan.id,
        random_seed=7,
    )
    ctx.extras["plan"] = plan
    state = MontagePlanState()

    output = await module.plan(ctx, state)
    assert output.module_id == "feedback"
    assert output.confidence > 0.0
    assert len(output.payload["estimates"]) == 5
