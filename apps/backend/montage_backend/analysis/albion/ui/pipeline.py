from __future__ import annotations

import asyncio
from pathlib import Path

from montage_backend.analysis.albion.ui.albion_ui_analysis import (
    ALBION_UI_DETECTOR_VERSION,
    AlbionUiAnalysisResult,
    AlbionUiBoundingBox,
    AlbionUiDetection,
    AlbionUiElementType,
    AlbionUiFrameWindow,
    AlbionUiSummary,
)
from montage_backend.analysis.albion.ui.engine import AlbionUiDetectionEngine, RawUiDetection, resolve_ui_detection_engine
from montage_backend.analysis.albion.ui.templates import AlbionUiTemplate, resolve_template
from montage_backend.analysis.object_analysis import ObjectAnalysisResult, ObjectCategory
from montage_backend.analysis.ocr_analysis import sample_timestamps_ms

M3_TO_ALBION_ELEMENT: dict[str, AlbionUiElementType] = {
    ObjectCategory.PARTY_FRAME.value: AlbionUiElementType.PARTY_FRAME,
    ObjectCategory.MINIMAP.value: AlbionUiElementType.MINIMAP,
    ObjectCategory.HEALTH_BAR.value: AlbionUiElementType.HEALTH_BAR,
    ObjectCategory.UI_PANEL.value: AlbionUiElementType.UI_PANEL,
    ObjectCategory.SPELL_EFFECT.value: AlbionUiElementType.SPELL_EFFECT,
    ObjectCategory.CHARACTER.value: AlbionUiElementType.UNKNOWN,
    ObjectCategory.MOUNT.value: AlbionUiElementType.UNKNOWN,
    ObjectCategory.UNKNOWN.value: AlbionUiElementType.UNKNOWN,
}


def build_window_cache_key(
    *,
    source_fingerprint: str,
    template_id: str,
    window_start_ms: int,
    window_end_ms: int,
    engine_id: str,
    engine_version: str,
) -> str:
    return (
        f"{ALBION_UI_DETECTOR_VERSION}:{source_fingerprint}:template={template_id}:"
        f"window={window_start_ms}-{window_end_ms}:engine={engine_id}@{engine_version}"
    )


def build_detector_cache_key(
    source_fingerprint: str,
    *,
    frame_rate: float | None,
    template_id: str,
    sample_interval_ms: int,
    window_ms: int,
    engine_id: str,
    engine_version: str,
    reused_m3_object: bool,
) -> str:
    fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
    source = "m3-cache" if reused_m3_object else "live-ui"
    return (
        f"{ALBION_UI_DETECTOR_VERSION}:{source_fingerprint}:fps={fps_part}:"
        f"template={template_id}:interval={sample_interval_ms}:window={window_ms}:"
        f"engine={engine_id}@{engine_version}:source={source}"
    )


def build_element_counts(detections: list[AlbionUiDetection]) -> dict[str, int]:
    counts: dict[str, int] = {element.value: 0 for element in AlbionUiElementType}
    for detection in detections:
        counts[detection.element_type.value] += 1
    return counts


def raw_to_albion_ui_detection(
    raw: RawUiDetection,
    *,
    timestamp_ms: int,
    window_start_ms: int,
    window_end_ms: int,
    template_id: str,
) -> AlbionUiDetection:
    return AlbionUiDetection(
        element_type=raw.element_type,
        label=raw.label,
        timestamp_ms=timestamp_ms,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        confidence=round(min(max(raw.confidence, 0.0), 1.0), 3),
        bbox=AlbionUiBoundingBox(x=raw.x, y=raw.y, width=raw.width, height=raw.height),
        template_id=template_id,
        metadata={"region_name": raw.region_name},
    )


def m3_detection_to_albion_ui(
    detection: dict,
    *,
    template_id: str,
    window_start_ms: int,
    window_end_ms: int,
) -> AlbionUiDetection:
    category = str(detection.get("category", "unknown"))
    element_type = M3_TO_ALBION_ELEMENT.get(category, AlbionUiElementType.UNKNOWN)
    bbox_payload = detection.get("bbox") or {}
    return AlbionUiDetection(
        element_type=element_type,
        label=str(detection.get("label", category)),
        timestamp_ms=int(detection.get("timestamp_ms", window_start_ms)),
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        confidence=round(float(detection.get("confidence", 0.0)), 3),
        bbox=AlbionUiBoundingBox(
            x=int(bbox_payload.get("x", 0)),
            y=int(bbox_payload.get("y", 0)),
            width=int(bbox_payload.get("width", 0)),
            height=int(bbox_payload.get("height", 0)),
        ),
        template_id=template_id,
        metadata={"source": "m3_object", **dict(detection.get("metadata", {}))},
    )


def dedupe_ui_detections(detections: list[AlbionUiDetection]) -> list[AlbionUiDetection]:
    best: dict[tuple[int, str, int, int, int, int], AlbionUiDetection] = {}
    for detection in detections:
        key = (
            detection.timestamp_ms,
            detection.element_type.value,
            detection.bbox.x,
            detection.bbox.y,
            detection.bbox.width,
            detection.bbox.height,
        )
        existing = best.get(key)
        if existing is None or detection.confidence > existing.confidence:
            best[key] = detection
    return sorted(best.values(), key=lambda item: (item.timestamp_ms, item.element_type.value))


def group_detections_into_windows(
    detections: list[AlbionUiDetection],
    *,
    timestamps: list[int],
    window_ms: int,
    source_fingerprint: str,
    template_id: str,
    engine_id: str,
    engine_version: str,
) -> list[AlbionUiFrameWindow]:
    windows: list[AlbionUiFrameWindow] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        window_detections = [
            detection
            for detection in detections
            if window_start <= detection.timestamp_ms < window_end
        ]
        windows.append(
            AlbionUiFrameWindow(
                window_start_ms=window_start,
                window_end_ms=window_end,
                cache_key=build_window_cache_key(
                    source_fingerprint=source_fingerprint,
                    template_id=template_id,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                    engine_id=engine_id,
                    engine_version=engine_version,
                ),
                template_id=template_id,
                engine_id=engine_id,
                engine_version=engine_version,
                detection_count=len(window_detections),
                detections=window_detections,
            ),
        )
    return windows


def reclassify_m3_object_result(
    object_result: ObjectAnalysisResult | dict,
    *,
    source_fingerprint: str,
    template_id: str,
    window_ms: int,
    sample_interval_ms: int,
) -> AlbionUiAnalysisResult:
    if isinstance(object_result, dict):
        object_result = ObjectAnalysisResult.model_validate(object_result)

    timestamps = sample_timestamps_ms(
        object_result.duration_ms,
        interval_ms=sample_interval_ms,
        max_frames=max(object_result.summary.frames_sampled, 1),
    )
    if not timestamps:
        timestamps = [0]

    detections: list[AlbionUiDetection] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        for item in object_result.detections:
            item_ts = int(item.timestamp_ms)
            if window_start <= item_ts < window_end:
                converted = m3_detection_to_albion_ui(
                    item.model_dump(mode="json"),
                    template_id=template_id,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                )
                if converted.element_type != AlbionUiElementType.UNKNOWN:
                    detections.append(converted)

    engine_id = object_result.summary.detector_id
    engine_version = object_result.summary.detector_version
    frame_windows = group_detections_into_windows(
        detections,
        timestamps=timestamps,
        window_ms=window_ms,
        source_fingerprint=source_fingerprint,
        template_id=template_id,
        engine_id=engine_id,
        engine_version=engine_version,
    )
    deduped = dedupe_ui_detections(detections)
    cache_key = build_detector_cache_key(
        source_fingerprint,
        frame_rate=object_result.frame_rate,
        template_id=template_id,
        sample_interval_ms=sample_interval_ms,
        window_ms=window_ms,
        engine_id=engine_id,
        engine_version=engine_version,
        reused_m3_object=True,
    )
    return AlbionUiAnalysisResult(
        cache_key=cache_key,
        duration_ms=object_result.duration_ms,
        frame_rate=object_result.frame_rate,
        window_ms=window_ms,
        sample_interval_ms=sample_interval_ms,
        template_id=template_id,
        summary=AlbionUiSummary(
            frames_sampled=len(timestamps),
            window_count=len(frame_windows),
            detection_count=len(detections),
            unique_element_count=len(deduped),
            template_id=template_id,
            engine_id=engine_id,
            engine_version=engine_version,
            by_element=build_element_counts(detections),
            reused_m3_object=True,
        ),
        frame_windows=frame_windows,
        detections=detections,
    )


async def run_albion_ui_pipeline(
    *,
    source_fingerprint: str,
    duration_ms: int,
    frame_rate: float,
    sample_interval_ms: int,
    window_ms: int,
    timestamps: list[int],
    template: AlbionUiTemplate,
    engine: AlbionUiDetectionEngine,
    video_path: Path,
    export_png_frame,
    check_cancelled,
    report_progress,
) -> AlbionUiAnalysisResult:
    detections: list[AlbionUiDetection] = []
    total = max(len(timestamps), 1)

    for index, timestamp_ms in enumerate(timestamps):
        check_cancelled()
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        await report_progress(
            0.1 + (0.85 * (index / total)),
            f"Albion UI window {index + 1}/{total}",
        )

        png_bytes = await export_png_frame(video_path, timestamp_ms / 1000.0)
        if not png_bytes:
            continue

        raw_items = await asyncio.to_thread(engine.detect_png, png_bytes, template=template)
        for raw in raw_items:
            detections.append(
                raw_to_albion_ui_detection(
                    raw,
                    timestamp_ms=timestamp_ms,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                    template_id=template.id,
                ),
            )

    frame_windows = group_detections_into_windows(
        detections,
        timestamps=timestamps,
        window_ms=window_ms,
        source_fingerprint=source_fingerprint,
        template_id=template.id,
        engine_id=engine.engine_id,
        engine_version=engine.version,
    )
    deduped = dedupe_ui_detections(detections)
    cache_key = build_detector_cache_key(
        source_fingerprint,
        frame_rate=frame_rate,
        template_id=template.id,
        sample_interval_ms=sample_interval_ms,
        window_ms=window_ms,
        engine_id=engine.engine_id,
        engine_version=engine.version,
        reused_m3_object=False,
    )
    return AlbionUiAnalysisResult(
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        window_ms=window_ms,
        sample_interval_ms=sample_interval_ms,
        template_id=template.id,
        summary=AlbionUiSummary(
            frames_sampled=len(timestamps),
            window_count=len(frame_windows),
            detection_count=len(detections),
            unique_element_count=len(deduped),
            template_id=template.id,
            engine_id=engine.engine_id,
            engine_version=engine.version,
            by_element=build_element_counts(detections),
            reused_m3_object=False,
        ),
        frame_windows=frame_windows,
        detections=detections,
    )


def resolve_pipeline_template(
    *,
    frame_width: int,
    frame_height: int,
    template_id: str | None = None,
) -> AlbionUiTemplate:
    return resolve_template(
        frame_width=frame_width,
        frame_height=frame_height,
        template_id=template_id,
    )


def default_pipeline_engine() -> AlbionUiDetectionEngine:
    return resolve_ui_detection_engine()
