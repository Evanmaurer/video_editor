from __future__ import annotations

import hashlib

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.montage_plan import MontagePlan
from montage_backend.models.domain.plan_effects import PlanEffectsAnalysis
from montage_backend.models.domain.plan_feedback import (
    FEEDBACK_ENGINE_VERSION,
    FeedbackActionType,
    PlanFeedbackEvent,
    PlanQualityAnalysis,
    QualityDimension,
    QualityEstimate,
)
from montage_backend.models.domain.plan_pacing import PlanPacingAnalysis
from montage_backend.models.domain.plan_transitions import PlanTransitionAnalysis

REDUCE_LENGTH_SCALE = 0.8
THUMBS_UP_BIAS = 0.05
THUMBS_DOWN_BIAS = -0.08


def build_cache_key(plan: MontagePlan) -> str:
    clip_sig = "|".join(
        f"{clip.id}:{clip.order}:{clip.clip_score:.1f}:{clip.confidence:.2f}"
        for clip in sorted(plan.clips, key=lambda item: item.order)
    )
    signature = hashlib.sha256(clip_sig.encode()).hexdigest()[:16]
    return f"{FEEDBACK_ENGINE_VERSION}:{plan.id}:{plan.version}:{signature}"


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _estimate_montage_quality(plan: MontagePlan) -> QualityEstimate:
    if not plan.clips:
        return QualityEstimate(
            dimension=QualityDimension.MONTAGE,
            score=20.0,
            confidence=0.3,
            reasoning="No clips in plan; montage quality cannot be assessed.",
        )
    avg_clip_score = sum(clip.clip_score for clip in plan.clips) / len(plan.clips)
    avg_confidence = sum(clip.confidence for clip in plan.clips) / len(plan.clips)
    score = _clamp_score((avg_clip_score * 0.65) + (avg_confidence * 100.0 * 0.35))
    return QualityEstimate(
        dimension=QualityDimension.MONTAGE,
        score=score,
        confidence=round(avg_confidence, 2),
        reasoning=f"Average clip score {avg_clip_score:.1f} across {len(plan.clips)} clips.",
    )


def _estimate_pacing_quality(
    plan: MontagePlan,
    pacing: PlanPacingAnalysis | None,
) -> QualityEstimate:
    if not plan.clips:
        return QualityEstimate(
            dimension=QualityDimension.PACING,
            score=25.0,
            confidence=0.3,
            reasoning="No clips available for pacing analysis.",
        )

    beat_aligned = sum(
        1 for clip in plan.clips if clip.beat_alignment is not None and clip.beat_alignment.aligned
    )
    beat_ratio = beat_aligned / len(plan.clips)
    durations = [max(clip.timeline_end_ms - clip.timeline_start_ms, 0) for clip in plan.clips]
    avg_duration = sum(durations) / len(durations) if durations else 0.0
    duration_variance = 0.0
    if len(durations) > 1:
        mean = avg_duration
        duration_variance = sum((value - mean) ** 2 for value in durations) / len(durations)
    consistency_bonus = max(0.0, 12.0 - min(duration_variance / 250_000.0, 12.0))

    pacing_confidence = pacing.confidence if pacing is not None else plan.overall_confidence
    target_bonus = 0.0
    if plan.metadata.target_duration_ms and plan.duration_ms > 0:
        delta_ratio = abs(plan.duration_ms - plan.metadata.target_duration_ms) / plan.metadata.target_duration_ms
        target_bonus = max(0.0, 15.0 - (delta_ratio * 30.0))

    score = _clamp_score(
        (pacing_confidence * 55.0) + (beat_ratio * 25.0) + consistency_bonus + target_bonus,
    )
    return QualityEstimate(
        dimension=QualityDimension.PACING,
        score=score,
        confidence=round(pacing_confidence, 2),
        reasoning=(
            f"Beat alignment {beat_ratio:.0%}, average clip duration {avg_duration:.0f}ms, "
            f"profile {plan.metadata.pacing_profile or 'balanced'}."
        ),
    )


def _estimate_transition_quality(
    plan: MontagePlan,
    transitions: PlanTransitionAnalysis | None,
) -> QualityEstimate:
    if len(plan.clips) < 2:
        return QualityEstimate(
            dimension=QualityDimension.TRANSITIONS,
            score=50.0,
            confidence=0.4,
            reasoning="Single-clip montage; transition quality is neutral.",
        )

    junction_confidence = transitions.confidence if transitions is not None else plan.overall_confidence
    assigned = sum(
        1 for clip in plan.clips if clip.transition_in is not None or clip.transition_out is not None
    )
    coverage = assigned / max(len(plan.clips), 1)
    variety = 0.0
    if transitions is not None and transitions.recommendations:
        unique_types = {
            item.transition_out.type.value for item in transitions.recommendations
        }
        variety = min(len(unique_types) / 4.0, 1.0) * 15.0

    score = _clamp_score((junction_confidence * 60.0) + (coverage * 25.0) + variety)
    return QualityEstimate(
        dimension=QualityDimension.TRANSITIONS,
        score=score,
        confidence=round(junction_confidence, 2),
        reasoning=f"Transition coverage {coverage:.0%} with {transitions.junction_count if transitions else 0} junctions.",
    )


def _estimate_excitement(
    plan: MontagePlan,
    effects: PlanEffectsAnalysis | None,
) -> QualityEstimate:
    if not plan.clips:
        return QualityEstimate(
            dimension=QualityDimension.EXCITEMENT,
            score=20.0,
            confidence=0.3,
            reasoning="No clips available for excitement estimate.",
        )

    avg_clip_score = sum(clip.clip_score for clip in plan.clips) / len(plan.clips)
    effect_density = 0.0
    if effects is not None and effects.recommendations:
        effect_count = sum(len(item.effects) for item in effects.recommendations)
        effect_density = min(effect_count / max(len(plan.clips) * 2, 1), 1.0)
    elif plan.clips:
        effect_count = sum(len(clip.effects) for clip in plan.clips)
        effect_density = min(effect_count / max(len(plan.clips) * 2, 1), 1.0)

    fast_transitions = sum(
        1
        for clip in plan.clips
        if clip.transition_out is not None
        and clip.transition_out.type.value in {"flash", "whip", "hard_cut"}
    )
    action_ratio = fast_transitions / max(len(plan.clips), 1)
    profile = (plan.metadata.pacing_profile or "balanced").lower()
    profile_bonus = {"aggressive": 12.0, "music_driven": 8.0, "cinematic": -4.0}.get(profile, 0.0)

    score = _clamp_score(
        (avg_clip_score * 0.55) + (effect_density * 25.0) + (action_ratio * 20.0) + profile_bonus,
    )
    confidence = effects.confidence if effects is not None else plan.overall_confidence
    return QualityEstimate(
        dimension=QualityDimension.EXCITEMENT,
        score=score,
        confidence=round(confidence, 2),
        reasoning=(
            f"Clip intensity {avg_clip_score:.1f}, effect density {effect_density:.0%}, "
            f"fast transitions {action_ratio:.0%}."
        ),
    )


def _estimate_viewer_retention(estimates: list[QualityEstimate]) -> QualityEstimate:
    by_dimension = {item.dimension: item for item in estimates}
    montage = by_dimension[QualityDimension.MONTAGE].score
    pacing = by_dimension[QualityDimension.PACING].score
    transitions = by_dimension[QualityDimension.TRANSITIONS].score
    excitement = by_dimension[QualityDimension.EXCITEMENT].score
    score = _clamp_score(
        (montage * 0.30) + (pacing * 0.25) + (excitement * 0.25) + (transitions * 0.20),
    )
    confidence = round(
        sum(item.confidence for item in estimates[:4]) / 4,
        2,
    )
    return QualityEstimate(
        dimension=QualityDimension.RETENTION,
        score=score,
        confidence=confidence,
        reasoning="Composite retention estimate from montage, pacing, excitement, and transitions.",
    )


def estimate_plan_quality(
    *,
    project_id: str,
    plan: MontagePlan,
    transitions: PlanTransitionAnalysis | None = None,
    pacing: PlanPacingAnalysis | None = None,
    effects: PlanEffectsAnalysis | None = None,
    updated_at: str | None = None,
) -> PlanQualityAnalysis:
    estimates = [
        _estimate_montage_quality(plan),
        _estimate_pacing_quality(plan, pacing),
        _estimate_transition_quality(plan, transitions),
        _estimate_excitement(plan, effects),
    ]
    estimates.append(_estimate_viewer_retention(estimates))

    overall_score = _clamp_score(sum(item.score for item in estimates) / len(estimates))
    overall_confidence = round(sum(item.confidence for item in estimates) / len(estimates), 2)
    reasoning = (
        f"Estimated montage quality at {overall_score:.1f}/100 from {len(plan.clips)} clips "
        f"and module confidences."
    )

    return PlanQualityAnalysis(
        plan_id=plan.id,
        project_id=project_id,
        plan_version=plan.version,
        estimates=estimates,
        overall_score=overall_score,
        overall_confidence=overall_confidence,
        reasoning=reasoning,
        cache_key=build_cache_key(plan),
        updated_at=updated_at or utc_now_iso(),
    )


def derive_regeneration_hints(
    plan: MontagePlan,
    events: list[PlanFeedbackEvent],
) -> list[str]:
    hints: list[str] = []
    prefs = plan.metadata.feedback_preferences

    if prefs.get("thumbs_up_count", 0) > prefs.get("thumbs_down_count", 0):
        hints.append("User feedback is generally positive; keep current pacing profile.")
    if prefs.get("thumbs_down_count", 0) > 0:
        hints.append("Recent thumbs-down signals; increase variety and tighten pacing.")

    action_counts: dict[str, int] = {}
    for event in events:
        action_counts[event.action.value] = action_counts.get(event.action.value, 0) + 1

    if action_counts.get(FeedbackActionType.IMPROVE_PACING.value, 0) > 0:
        hints.append("Prioritize beat alignment and smoother duration flow.")
    if action_counts.get(FeedbackActionType.INCREASE_ACTION.value, 0) > 0:
        hints.append("Favor higher-motion clips and faster transitions.")
    if action_counts.get(FeedbackActionType.REDUCE_LENGTH.value, 0) > 0:
        hints.append("Target shorter total runtime on regeneration.")
    if action_counts.get(FeedbackActionType.MORE_CINEMATIC.value, 0) > 0:
        hints.append("Prefer longer holds and cinematic transitions.")
    if action_counts.get(FeedbackActionType.MORE_AGGRESSIVE.value, 0) > 0:
        hints.append("Prefer aggressive pacing and punchy effects.")

    if plan.metadata.pacing_profile:
        hints.append(f"Active pacing profile: {plan.metadata.pacing_profile}.")

    return hints


def apply_feedback_action(plan: MontagePlan, action: FeedbackActionType) -> dict:
    prefs = dict(plan.metadata.feedback_preferences or {})
    changes: dict = {"action": action.value}

    if action == FeedbackActionType.THUMBS_UP:
        prefs["thumbs_up_count"] = int(prefs.get("thumbs_up_count", 0)) + 1
        prefs["quality_bias"] = round(float(prefs.get("quality_bias", 0.0)) + THUMBS_UP_BIAS, 3)
        changes["quality_bias"] = prefs["quality_bias"]
    elif action == FeedbackActionType.THUMBS_DOWN:
        prefs["thumbs_down_count"] = int(prefs.get("thumbs_down_count", 0)) + 1
        prefs["quality_bias"] = round(float(prefs.get("quality_bias", 0.0)) + THUMBS_DOWN_BIAS, 3)
        changes["quality_bias"] = prefs["quality_bias"]
    elif action == FeedbackActionType.IMPROVE_PACING:
        prefs["pacing_refresh_requested"] = True
        changes["pacing_refresh_requested"] = True
    elif action == FeedbackActionType.INCREASE_ACTION:
        plan.metadata.pacing_profile = "aggressive"
        prefs["action_bias"] = round(float(prefs.get("action_bias", 0.0)) + 0.15, 3)
        changes["pacing_profile"] = "aggressive"
    elif action == FeedbackActionType.REDUCE_LENGTH:
        if plan.metadata.target_duration_ms:
            plan.metadata.target_duration_ms = int(plan.metadata.target_duration_ms * REDUCE_LENGTH_SCALE)
        elif plan.duration_ms > 0:
            plan.metadata.target_duration_ms = int(plan.duration_ms * REDUCE_LENGTH_SCALE)
        prefs["target_duration_scale"] = round(
            float(prefs.get("target_duration_scale", 1.0)) * REDUCE_LENGTH_SCALE,
            3,
        )
        changes["target_duration_ms"] = plan.metadata.target_duration_ms
    elif action == FeedbackActionType.MORE_CINEMATIC:
        plan.metadata.pacing_profile = "cinematic"
        prefs["preferred_profile"] = "cinematic"
        changes["pacing_profile"] = "cinematic"
    elif action == FeedbackActionType.MORE_AGGRESSIVE:
        plan.metadata.pacing_profile = "aggressive"
        prefs["preferred_profile"] = "aggressive"
        changes["pacing_profile"] = "aggressive"
    elif action == FeedbackActionType.REGENERATE:
        prefs["full_regeneration_requested"] = True
        changes["full_regeneration_requested"] = True

    plan.metadata.feedback_preferences = prefs
    return changes


def build_feedback_event(
    *,
    project_id: str,
    plan_id: str,
    action: FeedbackActionType,
    comment: str,
    applied_changes: dict,
) -> PlanFeedbackEvent:
    return PlanFeedbackEvent(
        id=new_uuid(),
        plan_id=plan_id,
        project_id=project_id,
        action=action,
        comment=comment,
        applied_changes=applied_changes,
        created_at=utc_now_iso(),
    )
