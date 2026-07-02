from __future__ import annotations

import pytest

from montage_backend.models.domain.montage_plan import (
    BeatAlignment,
    MontageAudioAction,
    MontageAudioActionType,
    MontageEffect,
    MontageEffectType,
    MontagePlanClip,
    MontagePlanStatus,
    MontagePlanValidationError,
    MontageTransition,
    TransitionType,
    compute_plan_duration_ms,
    new_montage_plan,
    validate_montage_plan,
)
from montage_backend.montage.registry import build_default_montage_registry


def _sample_clip(**overrides) -> MontagePlanClip:
    data = {
        "id": "clip-1",
        "media_id": "media-1",
        "order": 0,
        "source_start_ms": 0,
        "source_end_ms": 3000,
        "source_start_frame": 0,
        "source_end_frame": 180,
        "timeline_start_ms": 0,
        "timeline_end_ms": 3000,
        "clip_score": 82.5,
        "playback_speed": 1.0,
        "transition_in": MontageTransition(
            type=TransitionType.HARD_CUT,
            confidence=0.95,
            reasoning="Opening cut",
        ),
        "transition_out": MontageTransition(
            type=TransitionType.FADE,
            duration_ms=250,
            confidence=0.88,
            reasoning="Smooth handoff",
        ),
        "audio_actions": [
            MontageAudioAction(
                type=MontageAudioActionType.DUCK,
                level_db=-6.0,
                confidence=0.7,
                reasoning="Duck under music",
            ),
        ],
        "effects": [
            MontageEffect(
                id="fx-1",
                type=MontageEffectType.ZOOM_PUNCH,
                confidence=0.75,
                reasoning="Emphasize action peak",
            ),
        ],
        "beat_alignment": BeatAlignment(
            beat_timestamp_ms=3000,
            aligned=True,
            offset_ms=0,
            confidence=0.9,
            reasoning="Cut on beat",
        ),
        "confidence": 0.91,
        "reasoning": "High motion segment with strong audio peak",
    }
    data.update(overrides)
    return MontagePlanClip(**data)


def test_new_montage_plan_has_seed_and_draft_status():
    plan = new_montage_plan(project_id="p1", name="Test Montage", random_seed=42)
    assert plan.status == MontagePlanStatus.DRAFT
    assert plan.metadata.random_seed == 42
    assert plan.project_id == "p1"
    assert plan.clips == []


def test_montage_plan_clip_contains_required_fields():
    clip = _sample_clip()
    assert clip.clip_score == pytest.approx(82.5)
    assert clip.transition_out is not None
    assert clip.transition_out.type == TransitionType.FADE
    assert clip.effects[0].type == MontageEffectType.ZOOM_PUNCH
    assert clip.beat_alignment is not None
    assert clip.beat_alignment.aligned is True


def test_compute_plan_duration_ms():
    plan = new_montage_plan(project_id="p1")
    plan.clips = [
        _sample_clip(timeline_start_ms=0, timeline_end_ms=3000, order=0),
        _sample_clip(id="clip-2", timeline_start_ms=3000, timeline_end_ms=5500, order=1),
    ]
    assert compute_plan_duration_ms(plan) == 5500


def test_validate_montage_plan_rejects_invalid_source_range():
    plan = new_montage_plan(project_id="p1")
    plan.clips = [_sample_clip(source_start_ms=5000, source_end_ms=1000)]
    with pytest.raises(MontagePlanValidationError):
        validate_montage_plan(plan)


def test_validate_montage_plan_rejects_duplicate_order():
    plan = new_montage_plan(project_id="p1")
    plan.clips = [
        _sample_clip(order=0),
        _sample_clip(id="clip-2", order=0, timeline_start_ms=3000, timeline_end_ms=6000),
    ]
    with pytest.raises(MontagePlanValidationError):
        validate_montage_plan(plan)


def test_montage_registry_includes_scoring_module():
    registry = build_default_montage_registry()
    assert registry.list_modules() == ["draft", "effects", "feedback", "highlights", "music_sync", "pacing", "scoring", "transitions"]
