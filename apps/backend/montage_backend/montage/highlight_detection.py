from __future__ import annotations

from dataclasses import dataclass

from montage_backend.analysis.audio_analysis import AudioEventType
from montage_backend.analysis.motion_analysis import MotionMovementClass
from montage_backend.analysis.object_analysis import ObjectCategory
from montage_backend.analysis.ocr_analysis import OcrTextCategory
from montage_backend.models.domain import new_uuid
from montage_backend.models.domain.clip_analysis import ClipAnalysisRecord
from montage_backend.models.domain.clip_highlight import (
    HIGHLIGHT_DETECTOR_VERSION,
    ClipHighlights,
    HighlightSegment,
    HighlightSignal,
)

MIN_HIGHLIGHT_MS = 1000
MAX_HIGHLIGHT_MS = 15000
MERGE_GAP_MS = 500
PRE_ROLL_MS = 800
POST_ROLL_MS = 1200
DEFAULT_MAX_HIGHLIGHTS = 10

SIGNAL_WEIGHTS: dict[str, tuple[str, float]] = {
    "motion": ("High motion", 0.30),
    "audio": ("Loud moment", 0.25),
    "ocr": ("Combat activity", 0.25),
    "object": ("Visual action", 0.20),
}


@dataclass(frozen=True)
class TimeInterval:
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass
class SignalPoint:
    timestamp_ms: int
    intensity: float
    signal_key: str
    reasoning: str


def _clamp_ms(value: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    result = max(minimum, value)
    if maximum is not None:
        result = min(result, maximum)
    return result


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def build_cache_key(source_fingerprint: str | None) -> str:
    fingerprint = source_fingerprint or "unknown"
    return f"{HIGHLIGHT_DETECTOR_VERSION}:{fingerprint}"


def collect_signal_points(record: ClipAnalysisRecord) -> list[SignalPoint]:
    points: list[SignalPoint] = []

    if record.motion is not None:
        for window in record.motion.windows:
            if window.motion_score < 0.25 and window.movement_class == MotionMovementClass.STATIC:
                continue
            center_ms = (window.start_ms + window.end_ms) // 2
            intensity = min(window.motion_score * 0.6 + window.motion_intensity * 0.4, 1.0)
            if window.movement_class == MotionMovementClass.FAST:
                intensity = min(intensity + 0.15, 1.0)
            points.append(
                SignalPoint(
                    timestamp_ms=center_ms,
                    intensity=intensity,
                    signal_key="motion",
                    reasoning=(
                        f"{window.movement_class.value} motion "
                        f"(score {window.motion_score:.2f})"
                    ),
                ),
            )

    if record.audio is not None and record.audio.has_audio:
        for event in record.audio.events:
            if event.event_type not in {AudioEventType.PEAK, AudioEventType.BEAT}:
                continue
            intensity = min(event.value, 1.0)
            if event.event_type == AudioEventType.PEAK:
                intensity = min(intensity + 0.1, 1.0)
            points.append(
                SignalPoint(
                    timestamp_ms=event.timestamp_ms,
                    intensity=intensity,
                    signal_key="audio",
                    reasoning=f"Audio {event.event_type.value} at {event.timestamp_ms}ms",
                ),
            )

    if record.ocr is not None:
        for detection in record.ocr.detections:
            if detection.category not in {
                OcrTextCategory.COMBAT,
                OcrTextCategory.DAMAGE_NUMBER,
            }:
                continue
            points.append(
                SignalPoint(
                    timestamp_ms=detection.timestamp_ms,
                    intensity=min(detection.confidence, 1.0),
                    signal_key="ocr",
                    reasoning=f"OCR {detection.category.value}: {detection.text[:32]}",
                ),
            )

    if record.object is not None:
        for detection in record.object.detections:
            if detection.category not in {
                ObjectCategory.SPELL_EFFECT,
                ObjectCategory.CHARACTER,
            }:
                continue
            points.append(
                SignalPoint(
                    timestamp_ms=detection.timestamp_ms,
                    intensity=min(detection.confidence, 1.0),
                    signal_key="object",
                    reasoning=f"{detection.category.value} detected ({detection.label})",
                ),
            )

    return points


def expand_point(point: SignalPoint, duration_ms: int) -> TimeInterval:
    start = _clamp_ms(point.timestamp_ms - PRE_ROLL_MS, maximum=duration_ms)
    end = _clamp_ms(point.timestamp_ms + POST_ROLL_MS, maximum=duration_ms)
    if end - start < MIN_HIGHLIGHT_MS:
        end = _clamp_ms(start + MIN_HIGHLIGHT_MS, maximum=duration_ms)
        start = _clamp_ms(end - MIN_HIGHLIGHT_MS, maximum=duration_ms)
    return TimeInterval(start_ms=start, end_ms=end)


def merge_intervals(intervals: list[TimeInterval]) -> list[TimeInterval]:
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda item: item.start_ms)
    merged: list[TimeInterval] = [sorted_intervals[0]]
    for interval in sorted_intervals[1:]:
        current = merged[-1]
        if interval.start_ms <= current.end_ms + MERGE_GAP_MS:
            merged[-1] = TimeInterval(
                start_ms=current.start_ms,
                end_ms=max(current.end_ms, interval.end_ms),
            )
        else:
            merged.append(interval)
    return merged


def trim_interval(interval: TimeInterval, duration_ms: int) -> TimeInterval | None:
    start = _clamp_ms(interval.start_ms, maximum=duration_ms)
    end = _clamp_ms(interval.end_ms, maximum=duration_ms)
    if end <= start:
        return None
    if end - start > MAX_HIGHLIGHT_MS:
        end = start + MAX_HIGHLIGHT_MS
    if end - start < MIN_HIGHLIGHT_MS:
        return None
    return TimeInterval(start_ms=start, end_ms=end)


def score_interval(
    interval: TimeInterval,
    points: list[SignalPoint],
) -> tuple[float, float, list[HighlightSignal], str]:
    in_range = [
        point
        for point in points
        if interval.start_ms <= point.timestamp_ms <= interval.end_ms
    ]
    if not in_range:
        return 0.0, 0.0, [], "mixed"

    signals: list[HighlightSignal] = []
    weighted_total = 0.0
    weight_sum = 0.0
    categories: dict[str, float] = {}

    for key, (label, weight) in SIGNAL_WEIGHTS.items():
        key_points = [point for point in in_range if point.signal_key == key]
        if not key_points:
            continue
        avg_intensity = sum(point.intensity for point in key_points) / len(key_points)
        score = _clamp_score(avg_intensity * 100.0)
        peak = max(key_points, key=lambda point: point.intensity)
        signals.append(
            HighlightSignal(
                key=key,
                label=label,
                score=score,
                weight=weight,
                reasoning=peak.reasoning,
            ),
        )
        weighted_total += score * weight
        weight_sum += weight
        categories[key] = score

    if weight_sum == 0.0:
        return 0.0, 0.0, [], "mixed"

    montage_score = _clamp_score(weighted_total / weight_sum)
    signal_types = len(signals)
    confidence = round(min(0.35 + (signal_types * 0.18) + (len(in_range) * 0.03), 1.0), 2)

    dominant = max(categories.items(), key=lambda item: item[1])[0]
    category_map = {
        "motion": "high_motion",
        "audio": "loud_moment",
        "ocr": "combat_activity",
        "object": "spell_effects",
    }
    category = category_map.get(dominant, "mixed")
    if signal_types >= 3:
        category = "action_burst"

    return montage_score, confidence, signals, category


def build_reasoning(
    interval: TimeInterval,
    score: float,
    signals: list[HighlightSignal],
    category: str,
) -> str:
    if not signals:
        return f"Highlight {interval.start_ms}-{interval.end_ms}ms scored {score:.1f}/100"
    ranked = sorted(signals, key=lambda item: item.score * item.weight, reverse=True)
    parts = [f"{item.label}: {item.score:.0f}/100" for item in ranked[:2]]
    label = category.replace("_", " ")
    return (
        f"{label.title()} ({interval.start_ms}-{interval.end_ms}ms, "
        f"score {score:.1f}/100). Signals: " + "; ".join(parts) + "."
    )


def detect_clip_highlights(
    *,
    project_id: str,
    media_id: str,
    record: ClipAnalysisRecord,
    file_name: str | None = None,
    updated_at: str,
    max_highlights: int = DEFAULT_MAX_HIGHLIGHTS,
) -> ClipHighlights:
    duration_ms = record.video.duration_ms or 0
    if duration_ms <= 0:
        return ClipHighlights(
            media_id=media_id,
            project_id=project_id,
            file_name=file_name,
            highlight_count=0,
            highlights=[],
            cache_key=build_cache_key(record.source_fingerprint),
            source_fingerprint=record.source_fingerprint,
            duration_ms=duration_ms or None,
            updated_at=updated_at,
        )

    points = collect_signal_points(record)
    raw_intervals = [expand_point(point, duration_ms) for point in points]
    merged = merge_intervals(raw_intervals)

    segments: list[HighlightSegment] = []
    for interval in merged:
        trimmed = trim_interval(interval, duration_ms)
        if trimmed is None:
            continue
        score, confidence, signals, category = score_interval(trimmed, points)
        if score < 20.0:
            continue
        segments.append(
            HighlightSegment(
                id=new_uuid(),
                start_ms=trimmed.start_ms,
                end_ms=trimmed.end_ms,
                score=score,
                confidence=confidence,
                reasoning=build_reasoning(trimmed, score, signals, category),
                signals=signals,
                category=category,
            ),
        )

    segments.sort(key=lambda item: (item.score, item.end_ms - item.start_ms), reverse=True)
    segments = segments[:max_highlights]

    return ClipHighlights(
        media_id=media_id,
        project_id=project_id,
        file_name=file_name,
        highlight_count=len(segments),
        highlights=segments,
        cache_key=build_cache_key(record.source_fingerprint),
        source_fingerprint=record.source_fingerprint,
        duration_ms=duration_ms,
        updated_at=updated_at,
    )
