from __future__ import annotations

import asyncio
from pathlib import Path

from montage_backend.analysis.albion.ocr.albion_ocr_analysis import (
    ALBION_OCR_DETECTOR_VERSION,
    AlbionOcrAnalysisResult,
    AlbionOcrBoundingBox,
    AlbionOcrCategory,
    AlbionOcrDetection,
    AlbionOcrFrameWindow,
    AlbionOcrSummary,
    DEFAULT_WINDOW_MS,
)
from montage_backend.analysis.albion.ocr.classifier import classify_albion_text, extract_albion_metadata, normalize_albion_text
from montage_backend.analysis.ocr.engine import OcrEngine, RawOcrDetection
from montage_backend.analysis.ocr_analysis import OcrAnalysisResult, sample_timestamps_ms


def build_window_cache_key(
    *,
    source_fingerprint: str,
    window_start_ms: int,
    window_end_ms: int,
    engine_id: str,
    engine_version: str,
) -> str:
    return (
        f"{ALBION_OCR_DETECTOR_VERSION}:{source_fingerprint}:"
        f"window={window_start_ms}-{window_end_ms}:engine={engine_id}@{engine_version}"
    )


def build_detector_cache_key(
    source_fingerprint: str,
    *,
    frame_rate: float | None,
    sample_interval_ms: int,
    window_ms: int,
    engine_id: str,
    engine_version: str,
    reused_m3_ocr: bool,
) -> str:
    fps_part = f"{frame_rate:.3f}" if frame_rate is not None else "unknown"
    source = "m3-cache" if reused_m3_ocr else "live-ocr"
    return (
        f"{ALBION_OCR_DETECTOR_VERSION}:{source_fingerprint}:fps={fps_part}:"
        f"interval={sample_interval_ms}:window={window_ms}:engine={engine_id}@{engine_version}:"
        f"source={source}"
    )


def _bbox_from_raw(raw: RawOcrDetection) -> AlbionOcrBoundingBox | None:
    if raw.width <= 0 or raw.height <= 0:
        return None
    return AlbionOcrBoundingBox(x=raw.x, y=raw.y, width=raw.width, height=raw.height)


def _bbox_from_ocr_payload(bbox: dict | None) -> AlbionOcrBoundingBox | None:
    if not bbox:
        return None
    return AlbionOcrBoundingBox(
        x=int(bbox.get("x", 0)),
        y=int(bbox.get("y", 0)),
        width=int(bbox.get("width", 0)),
        height=int(bbox.get("height", 0)),
    )


def raw_to_albion_detection(
    raw: RawOcrDetection,
    *,
    timestamp_ms: int,
    window_start_ms: int,
    window_end_ms: int,
) -> AlbionOcrDetection:
    text = raw.text.strip()
    category = classify_albion_text(text)
    metadata = extract_albion_metadata(text, category)
    if category == AlbionOcrCategory.PLAYER_NAME and metadata.get("alliance_tag"):
        category = AlbionOcrCategory.PLAYER_NAME
    if metadata.get("alliance_tag") and category == AlbionOcrCategory.GUILD_TAG:
        category = AlbionOcrCategory.ALLIANCE_TAG
    return AlbionOcrDetection(
        text=text,
        category=category,
        timestamp_ms=timestamp_ms,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        confidence=round(min(max(raw.confidence, 0.0), 1.0), 3),
        bbox=_bbox_from_raw(raw),
        metadata=metadata,
    )


def m3_detection_to_albion(
    detection: dict,
    *,
    window_start_ms: int,
    window_end_ms: int,
) -> AlbionOcrDetection:
    text = str(detection.get("text", "")).strip()
    category = classify_albion_text(text)
    metadata = extract_albion_metadata(text, category)
    bbox_payload = detection.get("bbox")
    return AlbionOcrDetection(
        text=text,
        category=category,
        timestamp_ms=int(detection.get("timestamp_ms", window_start_ms)),
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        confidence=round(float(detection.get("confidence", 0.0)), 3),
        bbox=_bbox_from_ocr_payload(bbox_payload if isinstance(bbox_payload, dict) else None),
        metadata={**dict(detection.get("metadata", {})), **metadata},
    )


def build_category_counts(detections: list[AlbionOcrDetection]) -> dict[str, int]:
    counts: dict[str, int] = {category.value: 0 for category in AlbionOcrCategory}
    for detection in detections:
        counts[detection.category.value] += 1
    return counts


def dedupe_albion_detections(detections: list[AlbionOcrDetection]) -> list[AlbionOcrDetection]:
    best_by_text: dict[str, AlbionOcrDetection] = {}
    for detection in detections:
        key = normalize_albion_text(detection.text)
        if not key:
            continue
        existing = best_by_text.get(key)
        if existing is None or detection.confidence > existing.confidence:
            best_by_text[key] = detection
    return sorted(best_by_text.values(), key=lambda item: (item.timestamp_ms, item.text))


def group_detections_into_windows(
    detections: list[AlbionOcrDetection],
    *,
    timestamps: list[int],
    window_ms: int,
    source_fingerprint: str,
    engine_id: str,
    engine_version: str,
) -> list[AlbionOcrFrameWindow]:
    windows: list[AlbionOcrFrameWindow] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        window_detections = [
            detection
            for detection in detections
            if window_start <= detection.timestamp_ms < window_end
        ]
        windows.append(
            AlbionOcrFrameWindow(
                window_start_ms=window_start,
                window_end_ms=window_end,
                cache_key=build_window_cache_key(
                    source_fingerprint=source_fingerprint,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                    engine_id=engine_id,
                    engine_version=engine_version,
                ),
                engine_id=engine_id,
                engine_version=engine_version,
                detection_count=len(window_detections),
                detections=window_detections,
            ),
        )
    return windows


def reclassify_m3_ocr_result(
    ocr_result: OcrAnalysisResult | dict,
    *,
    source_fingerprint: str,
    window_ms: int,
    sample_interval_ms: int,
) -> AlbionOcrAnalysisResult:
    if isinstance(ocr_result, dict):
        ocr_result = OcrAnalysisResult.model_validate(ocr_result)

    timestamps = sample_timestamps_ms(
        ocr_result.duration_ms,
        interval_ms=sample_interval_ms,
        max_frames=max(ocr_result.summary.frames_sampled, 1),
    )
    if not timestamps:
        timestamps = [0]

    detections: list[AlbionOcrDetection] = []
    for timestamp_ms in timestamps:
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        for item in ocr_result.detections:
            item_ts = int(item.timestamp_ms)
            if window_start <= item_ts < window_end:
                detections.append(
                    m3_detection_to_albion(
                        item.model_dump(mode="json"),
                        window_start_ms=window_start,
                        window_end_ms=window_end,
                    ),
                )

    engine_id = ocr_result.summary.engine_id
    engine_version = ocr_result.summary.engine_version
    frame_windows = group_detections_into_windows(
        detections,
        timestamps=timestamps,
        window_ms=window_ms,
        source_fingerprint=source_fingerprint,
        engine_id=engine_id,
        engine_version=engine_version,
    )
    deduped = dedupe_albion_detections(detections)
    cache_key = build_detector_cache_key(
        source_fingerprint,
        frame_rate=ocr_result.frame_rate,
        sample_interval_ms=sample_interval_ms,
        window_ms=window_ms,
        engine_id=engine_id,
        engine_version=engine_version,
        reused_m3_ocr=True,
    )
    return AlbionOcrAnalysisResult(
        cache_key=cache_key,
        duration_ms=ocr_result.duration_ms,
        frame_rate=ocr_result.frame_rate,
        window_ms=window_ms,
        sample_interval_ms=sample_interval_ms,
        summary=AlbionOcrSummary(
            frames_sampled=len(timestamps),
            window_count=len(frame_windows),
            detection_count=len(detections),
            unique_text_count=len(deduped),
            engine_id=engine_id,
            engine_version=engine_version,
            by_category=build_category_counts(detections),
            reused_m3_ocr=True,
        ),
        frame_windows=frame_windows,
        detections=detections,
        unique_texts=[item.text for item in deduped],
    )


async def run_albion_ocr_pipeline(
    *,
    source_fingerprint: str,
    duration_ms: int,
    frame_rate: float,
    sample_interval_ms: int,
    window_ms: int,
    timestamps: list[int],
    engine: OcrEngine,
    video_path: Path,
    export_png_frame,
    check_cancelled,
    report_progress,
) -> AlbionOcrAnalysisResult:
    detections: list[AlbionOcrDetection] = []
    total = max(len(timestamps), 1)

    for index, timestamp_ms in enumerate(timestamps):
        check_cancelled()
        window_start = timestamp_ms
        window_end = timestamp_ms + window_ms
        await report_progress(
            0.1 + (0.85 * (index / total)),
            f"Albion OCR window {index + 1}/{total}",
        )

        png_bytes = await export_png_frame(video_path, timestamp_ms / 1000.0)
        if not png_bytes:
            continue

        raw_items = await asyncio.to_thread(engine.recognize_png, png_bytes)
        for raw in raw_items:
            detections.append(
                raw_to_albion_detection(
                    raw,
                    timestamp_ms=timestamp_ms,
                    window_start_ms=window_start,
                    window_end_ms=window_end,
                ),
            )

    frame_windows = group_detections_into_windows(
        detections,
        timestamps=timestamps,
        window_ms=window_ms,
        source_fingerprint=source_fingerprint,
        engine_id=engine.engine_id,
        engine_version=engine.version,
    )
    deduped = dedupe_albion_detections(detections)
    cache_key = build_detector_cache_key(
        source_fingerprint,
        frame_rate=frame_rate,
        sample_interval_ms=sample_interval_ms,
        window_ms=window_ms,
        engine_id=engine.engine_id,
        engine_version=engine.version,
        reused_m3_ocr=False,
    )
    return AlbionOcrAnalysisResult(
        cache_key=cache_key,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        window_ms=window_ms,
        sample_interval_ms=sample_interval_ms,
        summary=AlbionOcrSummary(
            frames_sampled=len(timestamps),
            window_count=len(frame_windows),
            detection_count=len(detections),
            unique_text_count=len(deduped),
            engine_id=engine.engine_id,
            engine_version=engine.version,
            by_category=build_category_counts(detections),
            reused_m3_ocr=False,
        ),
        frame_windows=frame_windows,
        detections=detections,
        unique_texts=[item.text for item in deduped],
    )
