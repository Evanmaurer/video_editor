from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.clip_analysis import ClipAnalysisRecord
from montage_backend.models.domain.montage_plan import (
    MontageEffect,
    MontageEffectType,
    MontagePlan,
    MontagePlanClip,
)
from montage_backend.models.domain.plan_effects import (
    EFFECTS_ENGINE_VERSION,
    ClipEffectRecommendation,
    PlanEffectsAnalysis,
)

MAX_EFFECTS_PER_CLIP = 3


@dataclass(frozen=True)
class ClipMotionSignals:
    motion_score: float = 0.5
    average_shake: float = 0.0
    fast_ratio: float = 0.0
    average_pan: float = 0.0
    zoom: float = 0.0


EFFECT_PACING_BIAS: dict[str, dict[MontageEffectType, float]] = {
    "balanced": {
        MontageEffectType.ZOOM_PUNCH: 1.0,
        MontageEffectType.SPEED_RAMP: 1.0,
        MontageEffectType.CAMERA_SHAKE: 0.95,
        MontageEffectType.MOTION_BLUR: 1.0,
        MontageEffectType.COLOR_GRADE: 1.05,
        MontageEffectType.GLOW: 0.9,
        MontageEffectType.SHARPEN: 1.0,
        MontageEffectType.VIGNETTE: 1.0,
    },
    "aggressive": {
        MontageEffectType.ZOOM_PUNCH: 1.45,
        MontageEffectType.SPEED_RAMP: 1.35,
        MontageEffectType.CAMERA_SHAKE: 1.25,
        MontageEffectType.MOTION_BLUR: 1.2,
        MontageEffectType.SHARPEN: 1.15,
        MontageEffectType.GLOW: 1.1,
        MontageEffectType.COLOR_GRADE: 0.85,
        MontageEffectType.VIGNETTE: 0.8,
    },
    "cinematic": {
        MontageEffectType.COLOR_GRADE: 1.45,
        MontageEffectType.VIGNETTE: 1.35,
        MontageEffectType.MOTION_BLUR: 1.1,
        MontageEffectType.SPEED_RAMP: 1.0,
        MontageEffectType.ZOOM_PUNCH: 0.9,
        MontageEffectType.CAMERA_SHAKE: 0.7,
        MontageEffectType.GLOW: 0.95,
        MontageEffectType.SHARPEN: 0.85,
    },
    "music_driven": {
        MontageEffectType.SPEED_RAMP: 1.4,
        MontageEffectType.ZOOM_PUNCH: 1.25,
        MontageEffectType.GLOW: 1.15,
        MontageEffectType.MOTION_BLUR: 1.1,
        MontageEffectType.CAMERA_SHAKE: 1.0,
        MontageEffectType.COLOR_GRADE: 0.95,
        MontageEffectType.SHARPEN: 1.0,
        MontageEffectType.VIGNETTE: 0.9,
    },
    "story_driven": {
        MontageEffectType.COLOR_GRADE: 1.3,
        MontageEffectType.VIGNETTE: 1.2,
        MontageEffectType.SPEED_RAMP: 1.05,
        MontageEffectType.ZOOM_PUNCH: 0.95,
        MontageEffectType.CAMERA_SHAKE: 0.8,
        MontageEffectType.MOTION_BLUR: 0.95,
        MontageEffectType.GLOW: 0.9,
        MontageEffectType.SHARPEN: 0.9,
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
    if normalized in {"story_driven", "story"}:
        return "story_driven"
    if normalized in EFFECT_PACING_BIAS:
        return normalized
    return "balanced"


def build_clip_signature(clips: list[MontagePlanClip]) -> str:
    ordered = sorted(clips, key=lambda clip: clip.order)
    payload = "|".join(
        f"{clip.id}:{clip.order}:{clip.media_id}:{clip.timeline_end_ms}:{clip.clip_score:.1f}"
        for clip in ordered
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_media_fingerprint_signature(media_fingerprints: dict[str, str]) -> str:
    if not media_fingerprints:
        return "none"
    payload = "|".join(f"{media_id}:{fingerprint}" for media_id, fingerprint in sorted(media_fingerprints.items()))
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def build_cache_key(
    plan_id: str,
    random_seed: int,
    pacing_profile: str | None,
    clips: list[MontagePlanClip],
    media_fingerprints: dict[str, str] | None = None,
) -> str:
    profile = normalize_pacing_profile(pacing_profile)
    signature = build_clip_signature(clips)
    fp_signature = build_media_fingerprint_signature(media_fingerprints or {})
    return f"{EFFECTS_ENGINE_VERSION}:{plan_id}:{random_seed}:{profile}:{signature}:{fp_signature}"


def extract_motion_signals(record: ClipAnalysisRecord | None) -> ClipMotionSignals:
    if record is None or record.motion is None:
        return ClipMotionSignals()

    summary = record.motion.summary
    zoom = 0.0
    if record.metadata is not None and record.metadata.visual is not None:
        zoom = record.metadata.visual.camera_movement.zoom

    return ClipMotionSignals(
        motion_score=summary.overall_motion_score,
        average_shake=summary.average_shake,
        fast_ratio=summary.fast_ratio,
        average_pan=summary.average_pan,
        zoom=zoom,
    )


def _motion_level(clip: MontagePlanClip, signals: ClipMotionSignals) -> float:
    score_component = clip.clip_score / 100.0
    if signals.motion_score > 0.0:
        return min(max((signals.motion_score * 0.55) + (score_component * 0.45), 0.0), 1.0)
    return min(max(score_component, 0.0), 1.0)


def _score_effect_type(
    effect_type: MontageEffectType,
    *,
    pacing: str,
    clip: MontagePlanClip,
    signals: ClipMotionSignals,
    clip_index: int,
    clip_count: int,
    beat_aligned: bool,
) -> float:
    bias = EFFECT_PACING_BIAS.get(pacing, EFFECT_PACING_BIAS["balanced"])
    score = bias.get(effect_type, 1.0)
    motion = _motion_level(clip, signals)

    if motion >= 0.75:
        if effect_type in {
            MontageEffectType.ZOOM_PUNCH,
            MontageEffectType.SPEED_RAMP,
            MontageEffectType.MOTION_BLUR,
        }:
            score += 0.35
        if effect_type == MontageEffectType.CAMERA_SHAKE and signals.average_shake < 0.35:
            score += 0.25
        if effect_type == MontageEffectType.SHARPEN and signals.average_shake >= 0.35:
            score += 0.2
        if effect_type in {MontageEffectType.VIGNETTE, MontageEffectType.COLOR_GRADE}:
            score -= 0.15
    elif motion <= 0.35:
        if effect_type in {MontageEffectType.COLOR_GRADE, MontageEffectType.VIGNETTE}:
            score += 0.3
        if effect_type in {MontageEffectType.ZOOM_PUNCH, MontageEffectType.CAMERA_SHAKE}:
            score -= 0.2

    if clip.clip_score >= 80:
        if effect_type in {MontageEffectType.ZOOM_PUNCH, MontageEffectType.SPEED_RAMP, MontageEffectType.GLOW}:
            score += 0.2

    if clip_index == 0 and effect_type == MontageEffectType.ZOOM_PUNCH:
        score += 0.25

    if clip_index == clip_count - 1 and effect_type == MontageEffectType.VIGNETTE:
        score += 0.15

    if signals.average_shake >= 0.45 and effect_type == MontageEffectType.CAMERA_SHAKE:
        score -= 0.35

    if beat_aligned and effect_type in {MontageEffectType.SPEED_RAMP, MontageEffectType.ZOOM_PUNCH}:
        score += 0.2

    if signals.fast_ratio >= 0.5 and effect_type == MontageEffectType.MOTION_BLUR:
        score += 0.15

    return score


def _effect_parameters(
    effect_type: MontageEffectType,
    *,
    clip: MontagePlanClip,
    signals: ClipMotionSignals,
    rng: random.Random,
) -> dict:
    duration_ms = max(clip.timeline_end_ms - clip.timeline_start_ms, 1)
    if effect_type == MontageEffectType.SPEED_RAMP:
        peak = 1.15 + (signals.fast_ratio * 0.35) + rng.uniform(0.0, 0.1)
        return {
            "start_speed": round(0.85 + rng.uniform(0.0, 0.1), 2),
            "end_speed": round(min(peak, 1.8), 2),
            "ease": "ease_in_out",
            "duration_ms": min(int(duration_ms * 0.6), 1200),
        }
    if effect_type == MontageEffectType.ZOOM_PUNCH:
        return {
            "scale": round(1.08 + (clip.clip_score / 100.0) * 0.12 + rng.uniform(0.0, 0.05), 2),
            "duration_ms": min(int(duration_ms * 0.35), 800),
            "anchor": "center",
        }
    if effect_type == MontageEffectType.CAMERA_SHAKE:
        return {
            "intensity": round(0.25 + signals.average_shake * 0.35 + rng.uniform(0.0, 0.1), 2),
            "duration_ms": min(int(duration_ms * 0.5), 1000),
        }
    if effect_type == MontageEffectType.COLOR_GRADE:
        preset = "warm" if clip.clip_score >= 75 else "neutral"
        return {"preset": preset, "intensity": round(0.35 + rng.uniform(0.0, 0.15), 2)}
    if effect_type == MontageEffectType.MOTION_BLUR:
        return {"amount": round(0.2 + signals.motion_score * 0.35 + rng.uniform(0.0, 0.1), 2)}
    if effect_type == MontageEffectType.GLOW:
        return {"intensity": round(0.25 + (clip.clip_score / 100.0) * 0.25, 2)}
    if effect_type == MontageEffectType.SHARPEN:
        return {"amount": round(0.15 + signals.motion_score * 0.2, 2)}
    if effect_type == MontageEffectType.VIGNETTE:
        return {"strength": round(0.2 + rng.uniform(0.0, 0.2), 2)}
    return {}


def _build_effect(
    effect_type: MontageEffectType,
    *,
    clip: MontagePlanClip,
    signals: ClipMotionSignals,
    confidence: float,
    reasoning: str,
    rng: random.Random,
) -> MontageEffect:
    return MontageEffect(
        id=new_uuid(),
        type=effect_type,
        enabled=True,
        parameters=_effect_parameters(effect_type, clip=clip, signals=signals, rng=rng),
        confidence=confidence,
        reasoning=reasoning,
    )


def _is_beat_aligned(clip: MontagePlanClip, beat_markers_ms: list[int]) -> bool:
    start = clip.timeline_start_ms
    end = clip.timeline_end_ms
    return any(start - 80 <= beat <= end + 80 for beat in beat_markers_ms)


def _pick_effects_for_clip(
    *,
    clip: MontagePlanClip,
    clip_index: int,
    clip_count: int,
    pacing: str,
    signals: ClipMotionSignals,
    beat_markers_ms: list[int],
    random_seed: int,
) -> ClipEffectRecommendation:
    beat_aligned = _is_beat_aligned(clip, beat_markers_ms)
    ranked: list[tuple[MontageEffectType, float]] = []
    for effect_type in MontageEffectType:
        ranked.append(
            (
                effect_type,
                _score_effect_type(
                    effect_type,
                    pacing=pacing,
                    clip=clip,
                    signals=signals,
                    clip_index=clip_index,
                    clip_count=clip_count,
                    beat_aligned=beat_aligned,
                ),
            ),
        )
    ranked.sort(key=lambda item: item[1], reverse=True)

    rng = random.Random(random_seed + clip_index * 7919)
    selected_types: list[MontageEffectType] = []
    for effect_type, effect_score in ranked:
        if len(selected_types) >= MAX_EFFECTS_PER_CLIP:
            break
        if effect_score < 0.85:
            continue
        if effect_type in selected_types:
            continue
        selected_types.append(effect_type)

    if not selected_types and ranked:
        selected_types.append(ranked[0][0])

    effects: list[MontageEffect] = []
    reason_parts: list[str] = []
    for effect_type in selected_types:
        effect_score = next(score for et, score in ranked if et == effect_type)
        confidence = round(min(0.45 + (effect_score / 3.0), 0.95), 2)
        label = effect_type.value.replace("_", " ")
        context = f"{pacing.replace('_', ' ')} pacing"
        if beat_aligned:
            context += ", beat-aligned"
        if _motion_level(clip, signals) >= 0.75:
            context += ", high action"
        elif _motion_level(clip, signals) <= 0.35:
            context += ", calmer clip"
        reasoning = f"{label.title()} for clip {clip_index + 1}: {context}"
        effects.append(
            _build_effect(
                effect_type,
                clip=clip,
                signals=signals,
                confidence=confidence,
                reasoning=reasoning,
                rng=rng,
            ),
        )
        reason_parts.append(label)

    clip_confidence = (
        round(sum(effect.confidence for effect in effects) / len(effects), 2) if effects else 0.0
    )
    summary = (
        f"Applied {', '.join(reason_parts)}"
        if reason_parts
        else "No effects recommended for this clip"
    )
    return ClipEffectRecommendation(
        clip_id=clip.id,
        media_id=clip.media_id,
        order=clip.order,
        effects=effects,
        confidence=clip_confidence,
        reasoning=summary,
    )


def recommend_plan_effects(
    *,
    project_id: str,
    plan: MontagePlan,
    clip_signals: dict[str, ClipMotionSignals] | None = None,
    media_fingerprints: dict[str, str] | None = None,
    beat_markers_ms: list[int] | None = None,
    updated_at: str | None = None,
) -> PlanEffectsAnalysis:
    pacing = normalize_pacing_profile(plan.metadata.pacing_profile)
    ordered = sorted(plan.clips, key=lambda clip: clip.order)
    signals_map = clip_signals or {}
    beats = beat_markers_ms or (plan.music.beat_markers_ms if plan.music else [])
    seed = plan.metadata.random_seed
    clip_count = len(ordered)

    recommendations: list[ClipEffectRecommendation] = []
    for index, clip in enumerate(ordered):
        signals = signals_map.get(clip.media_id, ClipMotionSignals())
        recommendations.append(
            _pick_effects_for_clip(
                clip=clip,
                clip_index=index,
                clip_count=clip_count,
                pacing=pacing,
                signals=signals,
                beat_markers_ms=beats,
                random_seed=seed,
            ),
        )

    avg_confidence = (
        round(sum(item.confidence for item in recommendations) / len(recommendations), 2)
        if recommendations
        else 0.0
    )
    reasoning = (
        f"Recommended effects for {len(recommendations)} clips using {pacing} pacing."
        if recommendations
        else "No clips available; add clips to generate effect recommendations."
    )

    return PlanEffectsAnalysis(
        plan_id=plan.id,
        project_id=project_id,
        pacing_profile=pacing,
        clip_count=len(recommendations),
        recommendations=recommendations,
        confidence=avg_confidence,
        reasoning=reasoning,
        cache_key=build_cache_key(
            plan.id,
            seed,
            pacing,
            plan.clips,
            media_fingerprints,
        ),
        random_seed=seed,
        updated_at=updated_at or utc_now_iso(),
    )


def apply_effect_recommendations(
    plan: MontagePlan,
    recommendations: list[ClipEffectRecommendation],
) -> None:
    clip_map = {clip.id: clip for clip in plan.clips}
    for recommendation in recommendations:
        clip = clip_map.get(recommendation.clip_id)
        if clip is not None:
            clip.effects = list(recommendation.effects)
