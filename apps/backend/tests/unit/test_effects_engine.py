from __future__ import annotations

import pytest

from montage_backend.analysis.motion_analysis import (
    MotionAnalysisResult,
    MotionAnalysisSummary,
    MotionMovementClass,
)
from montage_backend.models.domain.clip_analysis import ClipAnalysisRecord, ClipAnalysisSummary, ClipProcessingSnapshot
from montage_backend.models.domain.media import ImportStatus, ProcessingStatus
from montage_backend.models.domain.montage_plan import (
    MontageEffectType,
    MontagePlan,
    MontagePlanClip,
    MontagePlanMetadata,
    MontagePlanStatus,
)
from montage_backend.models.domain.plan_effects import EFFECTS_ENGINE_VERSION
from montage_backend.montage.base import MontagePlanContext, MontagePlanState
from montage_backend.montage.effects_engine import (
    ClipMotionSignals,
    apply_effect_recommendations,
    build_cache_key,
    extract_motion_signals,
    normalize_pacing_profile,
    recommend_plan_effects,
)
from montage_backend.montage.modules.effects import EffectsEngineModule
from montage_backend.montage.registry import build_default_montage_registry


def _clip(
    clip_id: str,
    *,
    order: int,
    media_id: str,
    score: float,
) -> MontagePlanClip:
    return MontagePlanClip(
        id=clip_id,
        media_id=media_id,
        order=order,
        source_start_ms=0,
        source_end_ms=4000,
        timeline_start_ms=order * 3000,
        timeline_end_ms=(order + 1) * 3000,
        clip_score=score,
        confidence=0.9,
        reasoning="test clip",
    )


def _plan(*, pacing_profile: str, clips: list[MontagePlanClip], seed: int = 42) -> MontagePlan:
    return MontagePlan(
        id="plan-effects-1",
        project_id="project-1",
        name="Effects Test",
        status=MontagePlanStatus.DRAFT,
        clips=clips,
        metadata=MontagePlanMetadata(
            random_seed=seed,
            pacing_profile=pacing_profile,
        ),
        created_at="2026-06-27T00:00:00Z",
        updated_at="2026-06-27T00:00:00Z",
    )


def _motion_record(*, media_id: str, motion_score: float, shake: float, fast_ratio: float) -> ClipAnalysisRecord:
    return ClipAnalysisRecord(
        media_id=media_id,
        project_id="project-1",
        overall_status=ProcessingStatus.READY,
        source_fingerprint=f"fp-{media_id}",
        processing=ClipProcessingSnapshot(
            import_status=ImportStatus.READY,
            proxy_status=ProcessingStatus.READY,
            waveform_status=ProcessingStatus.READY,
            scene_cache_status=ProcessingStatus.READY,
            metadata_status=ProcessingStatus.READY,
        ),
        assets={},
        video={},
        motion=MotionAnalysisResult(
            analyzer_version="motion-analyzer-v1.0",
            cache_key="motion:test",
            frame_rate=60.0,
            duration_ms=8000,
            window_ms=1000,
            sample_stride_frames=30,
            summary=MotionAnalysisSummary(
                overall_motion_score=motion_score,
                dominant_movement_class=MotionMovementClass.FAST,
                static_ratio=0.1,
                slow_ratio=0.2,
                fast_ratio=fast_ratio,
                average_shake=shake,
                average_pan=0.2,
            ),
        ),
        summary=ClipAnalysisSummary(
            media_id=media_id,
            project_id="project-1",
            overall_status=ProcessingStatus.READY,
            readiness=1.0,
            modules_ready=1,
            modules_total=1,
            processing=ClipProcessingSnapshot(
                import_status=ImportStatus.READY,
                proxy_status=ProcessingStatus.READY,
                waveform_status=ProcessingStatus.READY,
                scene_cache_status=ProcessingStatus.READY,
                metadata_status=ProcessingStatus.READY,
            ),
            assets={},
            video={},
            updated_at="2026-06-27T00:00:00Z",
            created_at="2026-06-27T00:00:00Z",
        ),
        updated_at="2026-06-27T00:00:00Z",
        created_at="2026-06-27T00:00:00Z",
    )


def test_normalize_pacing_profile_supports_story_driven():
    assert normalize_pacing_profile("story-driven") == "story_driven"


def test_aggressive_pacing_prefers_action_effects_over_cinematic_subtlety():
    clips = [_clip("c1", order=0, media_id="m1", score=88)]
    high_motion = {"m1": ClipMotionSignals(motion_score=0.8, average_shake=0.2, fast_ratio=0.7)}
    low_motion = {"m1": ClipMotionSignals(motion_score=0.2, average_shake=0.05, fast_ratio=0.05)}
    aggressive = recommend_plan_effects(
        project_id="project-1",
        plan=_plan(pacing_profile="aggressive", clips=clips, seed=11),
        clip_signals=high_motion,
    )
    cinematic = recommend_plan_effects(
        project_id="project-1",
        plan=_plan(pacing_profile="cinematic", clips=clips, seed=11),
        clip_signals=low_motion,
    )
    aggressive_types = {effect.type for effect in aggressive.recommendations[0].effects}
    cinematic_types = {effect.type for effect in cinematic.recommendations[0].effects}
    assert MontageEffectType.ZOOM_PUNCH in aggressive_types or MontageEffectType.SPEED_RAMP in aggressive_types
    assert MontageEffectType.VIGNETTE in cinematic_types or MontageEffectType.COLOR_GRADE in cinematic_types


def test_high_motion_clip_gets_action_effects():
    clips = [_clip("c1", order=0, media_id="m1", score=85)]
    signals = {"m1": ClipMotionSignals(motion_score=0.85, average_shake=0.25, fast_ratio=0.7)}
    analysis = recommend_plan_effects(
        project_id="project-1",
        plan=_plan(pacing_profile="balanced", clips=clips, seed=3),
        clip_signals=signals,
    )
    effect_types = {effect.type for effect in analysis.recommendations[0].effects}
    assert effect_types & {
        MontageEffectType.ZOOM_PUNCH,
        MontageEffectType.SPEED_RAMP,
        MontageEffectType.MOTION_BLUR,
    }


def test_low_motion_clip_gets_subtle_effects():
    clips = [_clip("c1", order=0, media_id="m1", score=55)]
    signals = {"m1": ClipMotionSignals(motion_score=0.15, average_shake=0.05, fast_ratio=0.05)}
    analysis = recommend_plan_effects(
        project_id="project-1",
        plan=_plan(pacing_profile="balanced", clips=clips, seed=4),
        clip_signals=signals,
    )
    effect_types = {effect.type for effect in analysis.recommendations[0].effects}
    assert effect_types & {MontageEffectType.COLOR_GRADE, MontageEffectType.VIGNETTE}


def test_extract_motion_signals_reads_analysis_record():
    record = _motion_record(media_id="m1", motion_score=0.7, shake=0.4, fast_ratio=0.5)
    signals = extract_motion_signals(record)
    assert signals.motion_score == pytest.approx(0.7)
    assert signals.average_shake == pytest.approx(0.4)
    assert signals.fast_ratio == pytest.approx(0.5)


def test_recommend_plan_effects_builds_cache_key_with_fingerprints():
    clips = [_clip("c1", order=0, media_id="m1", score=70)]
    analysis = recommend_plan_effects(
        project_id="project-1",
        plan=_plan(pacing_profile="balanced", clips=clips, seed=7),
        media_fingerprints={"m1": "fp-m1"},
    )
    assert analysis.cache_key.startswith(EFFECTS_ENGINE_VERSION)
    assert build_cache_key(
        "plan-effects-1",
        7,
        "balanced",
        clips,
        {"m1": "fp-m1"},
    ) == analysis.cache_key


def test_apply_effect_recommendations_updates_plan_clips():
    clips = [_clip("c1", order=0, media_id="m1", score=80)]
    plan = _plan(pacing_profile="aggressive", clips=clips, seed=1)
    analysis = recommend_plan_effects(project_id="project-1", plan=plan)
    apply_effect_recommendations(plan, analysis.recommendations)
    assert len(plan.clips[0].effects) >= 1
    assert plan.clips[0].effects[0].confidence > 0.0


@pytest.mark.asyncio
async def test_effects_engine_module_plan():
    clips = [_clip("c1", order=0, media_id="m1", score=75)]
    plan = _plan(pacing_profile="balanced", clips=clips)
    module = EffectsEngineModule()
    ctx = MontagePlanContext(
        project_id="project-1",
        plan_id=plan.id,
        random_seed=42,
        extras={
            "plan": plan,
            "beat_markers_ms": [],
            "clip_records": [_motion_record(media_id="m1", motion_score=0.6, shake=0.2, fast_ratio=0.4)],
        },
    )
    output = await module.plan(ctx, MontagePlanState())
    assert output.module_id == "effects"
    assert output.payload["clip_count"] == 1


def test_default_registry_registers_effects():
    registry = build_default_montage_registry()
    module = registry.get("effects")
    assert module.module_id.value == "effects"
