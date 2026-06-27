from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from montage_backend.analysis.object.engine import ObjectDetector, RawObjectDetection
from montage_backend.analysis.ocr_analysis import sample_timestamps_ms
from montage_backend.analysis.scene_detection import ms_to_frame


class ObjectCategory(str, Enum):
    CHARACTER = "character"
    MOUNT = "mount"
    SPELL_EFFECT = "spell_effect"
    PARTY_FRAME = "party_frame"
    UI_PANEL = "ui_panel"
    HEALTH_BAR = "health_bar"
    MINIMAP = "minimap"
    UNKNOWN = "unknown"


class ObjectBoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class ObjectDetection(BaseModel):
    category: ObjectCategory
    label: str
    timestamp_ms: int
    frame: int
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: ObjectBoundingBox
    source_model: str
    metadata: dict = Field(default_factory=dict)


class ObjectAnalysisSummary(BaseModel):
    frames_sampled: int
    detection_count: int
    unique_detection_count: int
    detector_id: str
    detector_version: str
    by_category: dict[str, int] = Field(default_factory=dict)


class ObjectAnalysisResult(BaseModel):
    analyzer_version: str
    cache_key: str
    duration_ms: int
    frame_rate: float
    sample_interval_ms: int
    summary: ObjectAnalysisSummary
    detections: list[ObjectDetection] = Field(default_factory=list)


def normalize_category(category: str) -> ObjectCategory:
    try:
        return ObjectCategory(category)
    except ValueError:
        return ObjectCategory.UNKNOWN


def bbox_iou(a: ObjectBoundingBox, b: ObjectBoundingBox) -> float:
    ax2 = a.x + a.width
    ay2 = a.y + a.height
    bx2 = b.x + b.width
    by2 = b.y + b.height
    inter_x1 = max(a.x, b.x)
    inter_y1 = max(a.y, b.y)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0
    area_a = a.width * a.height
    area_b = b.width * b.height
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def raw_to_detection(
    raw: RawObjectDetection,
    *,
    timestamp_ms: int,
    frame_rate: float,
) -> ObjectDetection:
    return ObjectDetection(
        category=normalize_category(raw.category),
        label=raw.label,
        timestamp_ms=timestamp_ms,
        frame=ms_to_frame(timestamp_ms, frame_rate),
        confidence=round(min(max(raw.confidence, 0.0), 1.0), 3),
        bbox=ObjectBoundingBox(
            x=raw.x,
            y=raw.y,
            width=raw.width,
            height=raw.height,
        ),
        source_model=raw.source_model,
        metadata={},
    )


def dedupe_detections(detections: list[ObjectDetection], *, iou_threshold: float = 0.5) -> list[ObjectDetection]:
    ordered = sorted(detections, key=lambda item: item.confidence, reverse=True)
    kept: list[ObjectDetection] = []
    for candidate in ordered:
        duplicate = False
        for existing in kept:
            if (
                candidate.timestamp_ms == existing.timestamp_ms
                and candidate.category == existing.category
                and bbox_iou(candidate.bbox, existing.bbox) >= iou_threshold
            ):
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
    return sorted(kept, key=lambda item: (item.timestamp_ms, item.category.value))


def build_category_counts(detections: list[ObjectDetection]) -> dict[str, int]:
    counts: dict[str, int] = {category.value: 0 for category in ObjectCategory}
    for detection in detections:
        counts[detection.category.value] += 1
    return counts


def build_object_analysis_result(
    *,
    analyzer_version: str,
    cache_key: str,
    duration_ms: int,
    frame_rate: float,
    sample_interval_ms: int,
    frames_sampled: int,
    detector: ObjectDetector,
    detections: list[ObjectDetection],
) -> ObjectAnalysisResult:
    deduped = dedupe_detections(detections)
    summary = ObjectAnalysisSummary(
        frames_sampled=frames_sampled,
        detection_count=len(detections),
        unique_detection_count=len(deduped),
        detector_id=detector.detector_id,
        detector_version=detector.version,
        by_category=build_category_counts(deduped),
    )
    return ObjectAnalysisResult(
        analyzer_version=analyzer_version,
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        sample_interval_ms=sample_interval_ms,
        summary=summary,
        detections=deduped,
    )


__all__ = [
    "ObjectAnalysisResult",
    "ObjectAnalysisSummary",
    "ObjectBoundingBox",
    "ObjectCategory",
    "ObjectDetection",
    "build_object_analysis_result",
    "dedupe_detections",
    "raw_to_detection",
    "sample_timestamps_ms",
]
