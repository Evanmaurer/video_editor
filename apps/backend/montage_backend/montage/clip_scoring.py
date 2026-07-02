from __future__ import annotations

from montage_backend.models.domain.clip_analysis import ClipAnalysisRecord
from montage_backend.models.domain.clip_score import (
    CLIP_SCORER_VERSION,
    ClipScore,
    ClipScoreBreakdown,
    ClipScoreComponent,
)

IDEAL_SCENE_LENGTH_MS = 8000
MIN_SCENE_LENGTH_MS = 2000
MAX_SCENE_LENGTH_MS = 30000
IDEAL_BRIGHTNESS = 140.0

SCORE_WEIGHTS: dict[str, tuple[str, float]] = {
    "motion": ("Motion intensity", 0.20),
    "camera_shake": ("Camera shake / action energy", 0.10),
    "audio_intensity": ("Audio intensity", 0.15),
    "ocr_activity": ("OCR activity", 0.15),
    "scene_complexity": ("Scene complexity", 0.10),
    "visual_quality": ("Visual quality", 0.10),
    "exposure": ("Exposure", 0.10),
    "scene_length": ("Scene length fit", 0.10),
}


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _component(key: str, score: float, reasoning: str) -> ClipScoreComponent:
    label, weight = SCORE_WEIGHTS[key]
    weighted = score * weight
    return ClipScoreComponent(
        key=key,
        label=label,
        score=_clamp_score(score),
        weight=weight,
        weighted_score=round(weighted, 2),
        reasoning=reasoning,
    )


def score_motion(record: ClipAnalysisRecord) -> tuple[float, str, bool]:
    if record.motion is not None:
        value = record.motion.summary.overall_motion_score * 100.0
        return _clamp_score(value), f"Motion score {record.motion.summary.overall_motion_score:.2f}", True
    if record.metadata is not None and record.metadata.visual is not None:
        value = record.metadata.visual.motion_score * 100.0
        return _clamp_score(value), f"Metadata motion score {record.metadata.visual.motion_score:.2f}", True
    return 35.0, "No motion analysis available; using neutral baseline", False


def score_camera_shake(record: ClipAnalysisRecord) -> tuple[float, str, bool]:
    if record.motion is None:
        return 40.0, "No motion data for shake scoring", False
    summary = record.motion.summary
    action_energy = (summary.average_shake * 0.55) + (summary.fast_ratio * 0.45)
    value = action_energy * 100.0
    return (
        _clamp_score(value),
        f"Shake {summary.average_shake:.2f}, fast ratio {summary.fast_ratio:.2f}",
        True,
    )


def score_audio_intensity(record: ClipAnalysisRecord) -> tuple[float, str, bool]:
    if record.audio is None or not record.audio.has_audio:
        return 30.0, "No audio track detected", False
    summary = record.audio.summary
    peak_factor = min(summary.peak_count / 8.0, 1.0)
    silence_factor = 1.0 - summary.silence_ratio
    dynamic_factor = min(summary.dynamic_range_db / 24.0, 1.0)
    value = (peak_factor * 0.45 + silence_factor * 0.35 + dynamic_factor * 0.20) * 100.0
    return (
        _clamp_score(value),
        f"Peaks {summary.peak_count}, silence ratio {summary.silence_ratio:.2f}, "
        f"dynamic range {summary.dynamic_range_db:.1f} dB",
        True,
    )


def score_ocr_activity(record: ClipAnalysisRecord) -> tuple[float, str, bool]:
    if record.ocr is None:
        return 25.0, "No OCR analysis available", False
    summary = record.ocr.summary
    unique_factor = min(summary.unique_text_count / 6.0, 1.0)
    combat_count = summary.by_category.get("combat_text", 0)
    damage_count = summary.by_category.get("damage_number", 0)
    activity_factor = min((combat_count + damage_count) / 5.0, 1.0)
    value = (unique_factor * 0.55 + activity_factor * 0.45) * 100.0
    return (
        _clamp_score(value),
        f"{summary.unique_text_count} unique texts, {combat_count} combat, {damage_count} damage hits",
        True,
    )


def score_scene_complexity(record: ClipAnalysisRecord) -> tuple[float, str, bool]:
    duration_ms = record.video.duration_ms or (record.scene.duration_ms if record.scene else None)
    if record.scene is None or not duration_ms:
        return 35.0, "No scene segmentation available", False
    segment_count = len(record.scene.segments)
    minutes = max(duration_ms / 60_000.0, 0.05)
    segments_per_minute = segment_count / minutes
    value = min(segments_per_minute / 12.0, 1.0) * 100.0
    return (
        _clamp_score(value),
        f"{segment_count} scenes over {duration_ms / 1000:.1f}s ({segments_per_minute:.1f}/min)",
        True,
    )


def score_visual_quality(record: ClipAnalysisRecord) -> tuple[float, str, bool]:
    visual = record.metadata.visual if record.metadata else None
    if visual is None:
        return 40.0, "No visual metadata available", False
    sharpness = visual.sharpness
    blur_penalty = visual.blur_score
    value = ((sharpness * 0.7) + ((1.0 - blur_penalty) * 0.3)) * 100.0
    return (
        _clamp_score(value),
        f"Sharpness {sharpness:.2f}, blur {blur_penalty:.2f}",
        True,
    )


def score_exposure(record: ClipAnalysisRecord) -> tuple[float, str, bool]:
    visual = record.metadata.visual if record.metadata else None
    if visual is None:
        return 45.0, "No brightness metadata available", False
    mean = visual.brightness.mean
    distance = abs(mean - IDEAL_BRIGHTNESS)
    value = max(0.0, 100.0 - (distance / 1.8))
    return (
        _clamp_score(value),
        f"Mean brightness {mean:.1f} (ideal ~{IDEAL_BRIGHTNESS:.0f})",
        True,
    )


def score_scene_length(record: ClipAnalysisRecord) -> tuple[float, str, bool]:
    duration_ms = record.video.duration_ms
    if duration_ms is None:
        return 40.0, "Unknown clip duration", False
    if duration_ms < MIN_SCENE_LENGTH_MS:
        value = (duration_ms / MIN_SCENE_LENGTH_MS) * 60.0
        return _clamp_score(value), f"Short clip ({duration_ms}ms)", True
    if duration_ms > MAX_SCENE_LENGTH_MS:
        over = duration_ms - MAX_SCENE_LENGTH_MS
        value = max(20.0, 100.0 - (over / 1000.0) * 3.0)
        return _clamp_score(value), f"Long clip ({duration_ms / 1000:.1f}s)", True
    distance = abs(duration_ms - IDEAL_SCENE_LENGTH_MS)
    value = max(0.0, 100.0 - (distance / 250.0))
    return (
        _clamp_score(value),
        f"Duration {duration_ms / 1000:.1f}s near montage sweet spot",
        True,
    )


def build_breakdown(record: ClipAnalysisRecord) -> tuple[ClipScoreBreakdown, list[bool]]:
    results = {
        "motion": score_motion(record),
        "camera_shake": score_camera_shake(record),
        "audio_intensity": score_audio_intensity(record),
        "ocr_activity": score_ocr_activity(record),
        "scene_complexity": score_scene_complexity(record),
        "visual_quality": score_visual_quality(record),
        "exposure": score_exposure(record),
        "scene_length": score_scene_length(record),
    }
    components = {
        key: _component(key, score, reasoning)
        for key, (score, reasoning, _) in results.items()
    }
    availability = [available for _, _, available in results.values()]
    return ClipScoreBreakdown(**components), availability


def compute_montage_score(breakdown: ClipScoreBreakdown) -> float:
    total = sum(getattr(breakdown, key).weighted_score for key in SCORE_WEIGHTS)
    return _clamp_score(total)


def build_reasoning(breakdown: ClipScoreBreakdown, montage_score: float) -> str:
    components = [getattr(breakdown, key) for key in SCORE_WEIGHTS]
    ranked = sorted(components, key=lambda item: item.weighted_score, reverse=True)
    top = ranked[:3]
    parts = [f"{item.label}: {item.score:.0f}/100 ({item.reasoning})" for item in top]
    return f"Montage score {montage_score:.1f}/100. Top factors: " + "; ".join(parts) + "."


def compute_confidence(availability: list[bool]) -> float:
    if not availability:
        return 0.0
    return round(sum(1 for item in availability if item) / len(availability), 2)


def build_cache_key(source_fingerprint: str | None) -> str:
    fingerprint = source_fingerprint or "unknown"
    return f"{CLIP_SCORER_VERSION}:{fingerprint}"


def score_clip_analysis(
    *,
    project_id: str,
    media_id: str,
    record: ClipAnalysisRecord,
    file_name: str | None = None,
    updated_at: str,
) -> ClipScore:
    breakdown, availability = build_breakdown(record)
    montage_score = compute_montage_score(breakdown)
    confidence = compute_confidence(availability)
    reasoning = build_reasoning(breakdown, montage_score)
    return ClipScore(
        media_id=media_id,
        project_id=project_id,
        file_name=file_name,
        montage_score=montage_score,
        confidence=confidence,
        reasoning=reasoning,
        breakdown=breakdown,
        cache_key=build_cache_key(record.source_fingerprint),
        source_fingerprint=record.source_fingerprint,
        duration_ms=record.video.duration_ms,
        updated_at=updated_at,
    )
