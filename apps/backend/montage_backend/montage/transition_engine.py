from __future__ import annotations

import hashlib
import random

from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.montage_plan import (
    MontagePlan,
    MontagePlanClip,
    MontageTransition,
    TransitionType,
)
from montage_backend.models.domain.plan_transitions import (
    TRANSITION_ENGINE_VERSION,
    PlanTransitionAnalysis,
    TransitionJunctionRecommendation,
)

BEAT_ALIGN_TOLERANCE_MS = 80

TRANSITION_DURATIONS_MS: dict[TransitionType, int] = {
    TransitionType.HARD_CUT: 0,
    TransitionType.FADE: 300,
    TransitionType.CROSSFADE: 400,
    TransitionType.FLASH: 120,
    TransitionType.MOTION_BLUR: 250,
    TransitionType.SPEED_RAMP: 450,
    TransitionType.ZOOM: 300,
    TransitionType.WHIP: 200,
}

PACING_BIAS: dict[str, dict[TransitionType, float]] = {
    "balanced": {
        TransitionType.HARD_CUT: 1.0,
        TransitionType.CROSSFADE: 1.15,
        TransitionType.FADE: 1.05,
        TransitionType.FLASH: 0.95,
        TransitionType.MOTION_BLUR: 1.0,
        TransitionType.SPEED_RAMP: 0.9,
        TransitionType.ZOOM: 0.95,
        TransitionType.WHIP: 0.9,
    },
    "aggressive": {
        TransitionType.FLASH: 1.45,
        TransitionType.WHIP: 1.35,
        TransitionType.HARD_CUT: 1.25,
        TransitionType.MOTION_BLUR: 1.2,
        TransitionType.SPEED_RAMP: 1.15,
        TransitionType.ZOOM: 1.1,
        TransitionType.CROSSFADE: 0.75,
        TransitionType.FADE: 0.7,
    },
    "cinematic": {
        TransitionType.FADE: 1.45,
        TransitionType.CROSSFADE: 1.35,
        TransitionType.ZOOM: 1.1,
        TransitionType.HARD_CUT: 0.85,
        TransitionType.FLASH: 0.65,
        TransitionType.WHIP: 0.7,
        TransitionType.MOTION_BLUR: 0.95,
        TransitionType.SPEED_RAMP: 1.0,
    },
    "music_driven": {
        TransitionType.HARD_CUT: 1.35,
        TransitionType.FLASH: 1.25,
        TransitionType.WHIP: 1.1,
        TransitionType.CROSSFADE: 1.0,
        TransitionType.FADE: 0.9,
        TransitionType.MOTION_BLUR: 1.05,
        TransitionType.SPEED_RAMP: 1.0,
        TransitionType.ZOOM: 0.95,
    },
}


def normalize_pacing_profile(pacing_profile: str | None) -> str:
    if not pacing_profile:
        return "balanced"
    normalized = pacing_profile.lower().replace("-", "_").replace(" ", "_")
    if normalized in {"aggressive", "fast", "fast_montage"}:
        return "aggressive"
    if normalized in {"cinematic", "slow", "slow_cinematic"}:
        return "cinematic"
    if normalized in {"music_driven", "music"}:
        return "music_driven"
    return "balanced"


def build_clip_signature(clips: list[MontagePlanClip]) -> str:
    ordered = sorted(clips, key=lambda clip: clip.order)
    payload = "|".join(
        f"{clip.id}:{clip.order}:{clip.media_id}:{clip.timeline_end_ms}:{clip.clip_score:.1f}"
        for clip in ordered
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_cache_key(
    plan_id: str,
    random_seed: int,
    pacing_profile: str | None,
    clips: list[MontagePlanClip],
) -> str:
    profile = normalize_pacing_profile(pacing_profile)
    signature = build_clip_signature(clips)
    return f"{TRANSITION_ENGINE_VERSION}:{plan_id}:{random_seed}:{profile}:{signature}"


def _is_beat_aligned(timeline_ms: int, beat_markers_ms: list[int]) -> bool:
    return any(abs(timeline_ms - beat_ms) <= BEAT_ALIGN_TOLERANCE_MS for beat_ms in beat_markers_ms)


def _motion_level(clip: MontagePlanClip) -> float:
    return min(max(clip.clip_score / 100.0, 0.0), 1.0)


def _score_transition_type(
    transition_type: TransitionType,
    *,
    pacing: str,
    score_delta: float,
    avg_motion: float,
    beat_aligned: bool,
) -> float:
    bias = PACING_BIAS.get(pacing, PACING_BIAS["balanced"])
    score = bias.get(transition_type, 1.0)

    if avg_motion >= 0.75:
        if transition_type in {TransitionType.FLASH, TransitionType.WHIP, TransitionType.MOTION_BLUR}:
            score += 0.35
        if transition_type in {TransitionType.FADE, TransitionType.CROSSFADE}:
            score -= 0.15
    elif avg_motion <= 0.4:
        if transition_type in {TransitionType.FADE, TransitionType.CROSSFADE}:
            score += 0.25
        if transition_type in {TransitionType.FLASH, TransitionType.WHIP}:
            score -= 0.2

    if score_delta >= 0.25:
        if transition_type in {TransitionType.FLASH, TransitionType.WHIP, TransitionType.ZOOM}:
            score += 0.2
    elif score_delta <= 0.1:
        if transition_type in {TransitionType.CROSSFADE, TransitionType.FADE}:
            score += 0.15

    if beat_aligned:
        if transition_type in {TransitionType.HARD_CUT, TransitionType.FLASH}:
            score += 0.3
        if pacing == "music_driven" and transition_type == TransitionType.HARD_CUT:
            score += 0.2

    return score


def _pick_transition_type(
    *,
    pacing: str,
    from_clip: MontagePlanClip,
    to_clip: MontagePlanClip,
    beat_aligned: bool,
    random_seed: int,
    junction_index: int,
) -> tuple[TransitionType, float, str]:
    score_delta = abs(from_clip.clip_score - to_clip.clip_score) / 100.0
    avg_motion = (_motion_level(from_clip) + _motion_level(to_clip)) / 2.0

    ranked: list[tuple[TransitionType, float]] = []
    for transition_type in TransitionType:
        ranked.append(
            (
                transition_type,
                _score_transition_type(
                    transition_type,
                    pacing=pacing,
                    score_delta=score_delta,
                    avg_motion=avg_motion,
                    beat_aligned=beat_aligned,
                ),
            ),
        )
    ranked.sort(key=lambda item: item[1], reverse=True)

    rng = random.Random(random_seed + junction_index * 9973)
    top_score = ranked[0][1]
    candidates = [item for item in ranked if item[1] >= top_score - 0.05]
    chosen_type, chosen_score = rng.choice(candidates)

    reason_parts = [f"{pacing.replace('_', ' ')} pacing"]
    if beat_aligned:
        reason_parts.append("beat-aligned cut")
    if avg_motion >= 0.75:
        reason_parts.append("high-action clips")
    elif avg_motion <= 0.4:
        reason_parts.append("calmer clips")
    if score_delta >= 0.25:
        reason_parts.append("strong score contrast")

    confidence = round(min(0.45 + (chosen_score / 3.0), 0.95), 2)
    return chosen_type, confidence, "; ".join(reason_parts)


def _build_transition(
    transition_type: TransitionType,
    *,
    confidence: float,
    reasoning: str,
) -> MontageTransition:
    return MontageTransition(
        type=transition_type,
        duration_ms=TRANSITION_DURATIONS_MS[transition_type],
        confidence=confidence,
        reasoning=reasoning,
    )


def _matching_transition_in(transition_out: MontageTransition) -> MontageTransition:
    if transition_out.type in {TransitionType.CROSSFADE, TransitionType.FADE}:
        return MontageTransition(
            type=transition_out.type,
            duration_ms=transition_out.duration_ms,
            confidence=transition_out.confidence,
            reasoning=f"Incoming {transition_out.type.value} matches outgoing transition",
        )
    if transition_out.type == TransitionType.HARD_CUT:
        return MontageTransition(
            type=TransitionType.HARD_CUT,
            duration_ms=0,
            confidence=transition_out.confidence,
            reasoning="Hard cut entry",
        )
    return MontageTransition(
        type=TransitionType.HARD_CUT,
        duration_ms=0,
        confidence=max(0.5, transition_out.confidence - 0.05),
        reasoning=f"Hard cut entry after {transition_out.type.value}",
    )


def recommend_plan_transitions(
    *,
    project_id: str,
    plan: MontagePlan,
    beat_markers_ms: list[int] | None = None,
    updated_at: str | None = None,
) -> PlanTransitionAnalysis:
    pacing = normalize_pacing_profile(plan.metadata.pacing_profile)
    ordered = sorted(plan.clips, key=lambda clip: clip.order)
    beats = beat_markers_ms or (plan.music.beat_markers_ms if plan.music else [])
    seed = plan.metadata.random_seed

    recommendations: list[TransitionJunctionRecommendation] = []
    for index in range(len(ordered) - 1):
        from_clip = ordered[index]
        to_clip = ordered[index + 1]
        timeline_ms = from_clip.timeline_end_ms
        beat_aligned = _is_beat_aligned(timeline_ms, beats)
        transition_type, confidence, context = _pick_transition_type(
            pacing=pacing,
            from_clip=from_clip,
            to_clip=to_clip,
            beat_aligned=beat_aligned,
            random_seed=seed,
            junction_index=index,
        )
        reasoning = f"{transition_type.value.replace('_', ' ').title()} between clips {index + 1}→{index + 2}: {context}"
        transition_out = _build_transition(
            transition_type,
            confidence=confidence,
            reasoning=reasoning,
        )
        transition_in = _matching_transition_in(transition_out)
        recommendations.append(
            TransitionJunctionRecommendation(
                junction_index=index,
                from_clip_id=from_clip.id,
                to_clip_id=to_clip.id,
                from_media_id=from_clip.media_id,
                to_media_id=to_clip.media_id,
                timeline_ms=timeline_ms,
                transition_out=transition_out,
                transition_in=transition_in,
                confidence=confidence,
                reasoning=reasoning,
            ),
        )

    avg_confidence = (
        round(sum(item.confidence for item in recommendations) / len(recommendations), 2)
        if recommendations
        else 0.0
    )
    reasoning = (
        f"Recommended {len(recommendations)} transitions for {pacing} pacing."
        if recommendations
        else "No clip junctions available; add at least two clips to generate transitions."
    )

    return PlanTransitionAnalysis(
        plan_id=plan.id,
        project_id=project_id,
        pacing_profile=pacing,
        junction_count=len(recommendations),
        recommendations=recommendations,
        confidence=avg_confidence,
        reasoning=reasoning,
        cache_key=build_cache_key(plan.id, seed, pacing, plan.clips),
        random_seed=seed,
        updated_at=updated_at or utc_now_iso(),
    )


def apply_transition_recommendations(
    plan: MontagePlan,
    recommendations: list[TransitionJunctionRecommendation],
) -> None:
    clip_map = {clip.id: clip for clip in plan.clips}
    for recommendation in recommendations:
        from_clip = clip_map.get(recommendation.from_clip_id)
        to_clip = clip_map.get(recommendation.to_clip_id)
        if from_clip is not None:
            from_clip.transition_out = recommendation.transition_out
        if to_clip is not None:
            to_clip.transition_in = recommendation.transition_in
