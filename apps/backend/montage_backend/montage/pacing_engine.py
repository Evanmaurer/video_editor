from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.montage_plan import MontagePlan, MontagePlanClip
from montage_backend.models.domain.plan_pacing import (
    PACING_ENGINE_VERSION,
    ClipPacingRecommendation,
    PlanPacingAnalysis,
)

BEAT_SNAP_TOLERANCE_MS = 120
ABSOLUTE_MIN_CLIP_MS = 600


@dataclass(frozen=True)
class PacingProfileConfig:
    base_duration_ms: int
    min_duration_ms: int
    max_duration_ms: int
    score_bias: float
    snap_to_beats: bool = False


PACING_PROFILES: dict[str, PacingProfileConfig] = {
    "balanced": PacingProfileConfig(
        base_duration_ms=3000,
        min_duration_ms=1500,
        max_duration_ms=5000,
        score_bias=0.008,
    ),
    "aggressive": PacingProfileConfig(
        base_duration_ms=1800,
        min_duration_ms=800,
        max_duration_ms=2800,
        score_bias=-0.004,
    ),
    "cinematic": PacingProfileConfig(
        base_duration_ms=4800,
        min_duration_ms=2500,
        max_duration_ms=8500,
        score_bias=0.012,
    ),
    "music_driven": PacingProfileConfig(
        base_duration_ms=2400,
        min_duration_ms=1000,
        max_duration_ms=4200,
        score_bias=0.002,
        snap_to_beats=True,
    ),
    "story_driven": PacingProfileConfig(
        base_duration_ms=4200,
        min_duration_ms=2200,
        max_duration_ms=7500,
        score_bias=0.006,
    ),
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
    if normalized in PACING_PROFILES:
        return normalized
    return "balanced"


def build_clip_signature(clips: list[MontagePlanClip]) -> str:
    ordered = sorted(clips, key=lambda clip: clip.order)
    payload = "|".join(
        f"{clip.id}:{clip.order}:{clip.media_id}:{clip.source_start_ms}:{clip.source_end_ms}:{clip.clip_score:.1f}"
        for clip in ordered
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_cache_key(
    plan_id: str,
    random_seed: int,
    pacing_profile: str | None,
    target_duration_ms: int | None,
    clips: list[MontagePlanClip],
) -> str:
    profile = normalize_pacing_profile(pacing_profile)
    signature = build_clip_signature(clips)
    target = target_duration_ms if target_duration_ms is not None else 0
    return f"{PACING_ENGINE_VERSION}:{plan_id}:{random_seed}:{profile}:{target}:{signature}"


def _clamp_duration(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _source_duration_ms(clip: MontagePlanClip) -> int:
    return max(clip.source_end_ms - clip.source_start_ms, ABSOLUTE_MIN_CLIP_MS)


def _raw_clip_duration(
    clip: MontagePlanClip,
    config: PacingProfileConfig,
    *,
    random_seed: int,
) -> int:
    score_delta = clip.clip_score - 50.0
    duration = int(config.base_duration_ms + (score_delta * config.score_bias * 100.0))
    rng = random.Random(random_seed + clip.order * 3571)
    jitter = rng.randint(-120, 120)
    duration += jitter
    duration = _clamp_duration(duration, minimum=config.min_duration_ms, maximum=config.max_duration_ms)
    duration = min(duration, _source_duration_ms(clip))
    return max(duration, ABSOLUTE_MIN_CLIP_MS)


def _snap_end_to_beat(end_ms: int, beat_markers_ms: list[int]) -> int:
    if not beat_markers_ms:
        return end_ms
    candidates = [
        beat_ms
        for beat_ms in beat_markers_ms
        if abs(beat_ms - end_ms) <= BEAT_SNAP_TOLERANCE_MS
    ]
    if not candidates:
        return end_ms
    return min(candidates, key=lambda beat_ms: abs(beat_ms - end_ms))


def _scale_durations_to_target(
    durations: list[int],
    *,
    target_duration_ms: int,
    min_duration_ms: int,
) -> list[int]:
    total = sum(durations)
    if total <= 0:
        return durations
    scale = target_duration_ms / total
    scaled = [max(min_duration_ms, int(duration * scale)) for duration in durations]
    adjusted_total = sum(scaled)
    if adjusted_total == target_duration_ms or not scaled:
        return scaled

    delta = target_duration_ms - adjusted_total
    index = max(range(len(scaled)), key=lambda idx: scaled[idx])
    scaled[index] = max(min_duration_ms, scaled[index] + delta)
    return scaled


def recommend_plan_pacing(
    *,
    project_id: str,
    plan: MontagePlan,
    beat_markers_ms: list[int] | None = None,
    updated_at: str | None = None,
) -> PlanPacingAnalysis:
    profile = normalize_pacing_profile(plan.metadata.pacing_profile)
    config = PACING_PROFILES[profile]
    ordered = sorted(plan.clips, key=lambda clip: clip.order)
    beats = beat_markers_ms or (plan.music.beat_markers_ms if plan.music else [])
    seed = plan.metadata.random_seed

    raw_durations = [
        _raw_clip_duration(clip, config, random_seed=seed)
        for clip in ordered
    ]
    if plan.metadata.target_duration_ms is not None and raw_durations:
        raw_durations = _scale_durations_to_target(
            raw_durations,
            target_duration_ms=plan.metadata.target_duration_ms,
            min_duration_ms=config.min_duration_ms,
        )

    recommendations: list[ClipPacingRecommendation] = []
    timeline_cursor = 0
    for clip, duration in zip(ordered, raw_durations, strict=True):
        source_available = _source_duration_ms(clip)
        timeline_duration = min(duration, source_available)
        timeline_end = timeline_cursor + timeline_duration
        if config.snap_to_beats:
            snapped_end = _snap_end_to_beat(timeline_end, beats)
            if snapped_end > timeline_cursor + ABSOLUTE_MIN_CLIP_MS:
                timeline_end = snapped_end
                timeline_duration = timeline_end - timeline_cursor

        source_start = clip.source_start_ms
        source_end = min(source_start + timeline_duration, clip.source_end_ms)
        if source_end <= source_start:
            source_end = min(source_start + ABSOLUTE_MIN_CLIP_MS, clip.source_end_ms)

        playback_speed = 1.0
        if timeline_duration > 0 and (source_end - source_start) > timeline_duration:
            playback_speed = round((source_end - source_start) / timeline_duration, 3)

        confidence = round(min(0.5 + (clip.confidence * 0.35) + (clip.clip_score / 200.0), 0.95), 2)
        reasoning = (
            f"{profile.replace('_', ' ')} pacing: {timeline_duration}ms timeline "
            f"from {source_end - source_start}ms source"
        )
        if config.snap_to_beats and timeline_end in beats:
            reasoning += "; beat-snapped end"

        recommendations.append(
            ClipPacingRecommendation(
                clip_id=clip.id,
                media_id=clip.media_id,
                order=clip.order,
                timeline_start_ms=timeline_cursor,
                timeline_end_ms=timeline_end,
                timeline_duration_ms=timeline_duration,
                source_start_ms=source_start,
                source_end_ms=source_end,
                playback_speed=playback_speed,
                confidence=confidence,
                reasoning=reasoning,
            ),
        )
        timeline_cursor = timeline_end

    total_duration_ms = timeline_cursor
    avg_confidence = (
        round(sum(item.confidence for item in recommendations) / len(recommendations), 2)
        if recommendations
        else 0.0
    )
    reasoning = (
        f"Paced {len(recommendations)} clips for {profile} profile "
        f"(total {total_duration_ms}ms)."
        if recommendations
        else "No clips available; add clips to generate pacing recommendations."
    )

    return PlanPacingAnalysis(
        plan_id=plan.id,
        project_id=project_id,
        pacing_profile=profile,
        target_duration_ms=plan.metadata.target_duration_ms,
        total_duration_ms=total_duration_ms,
        clip_count=len(recommendations),
        recommendations=recommendations,
        confidence=avg_confidence,
        reasoning=reasoning,
        cache_key=build_cache_key(
            plan.id,
            seed,
            profile,
            plan.metadata.target_duration_ms,
            plan.clips,
        ),
        random_seed=seed,
        updated_at=updated_at or utc_now_iso(),
    )


def apply_pacing_recommendations(
    plan: MontagePlan,
    recommendations: list[ClipPacingRecommendation],
) -> None:
    clip_map = {clip.id: clip for clip in plan.clips}
    for recommendation in recommendations:
        clip = clip_map.get(recommendation.clip_id)
        if clip is None:
            continue
        clip.timeline_start_ms = recommendation.timeline_start_ms
        clip.timeline_end_ms = recommendation.timeline_end_ms
        clip.source_start_ms = recommendation.source_start_ms
        clip.source_end_ms = recommendation.source_end_ms
        clip.playback_speed = recommendation.playback_speed
    plan.duration_ms = max((item.timeline_end_ms for item in recommendations), default=0)
