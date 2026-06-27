from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

from montage_backend.analysis.scene_detection import frame_to_ms, ms_to_frame

_YAVG_RE = re.compile(r"lavfi\.signalstats\.YAVG=([0-9.+-eE]+)")
_YMIN_RE = re.compile(r"lavfi\.signalstats\.YMIN=([0-9.+-eE]+)")
_YMAX_RE = re.compile(r"lavfi\.signalstats\.YMAX=([0-9.+-eE]+)")

STATIC_THRESHOLD = 0.15
FAST_THRESHOLD = 0.45


class MotionMovementClass(str, Enum):
    STATIC = "static"
    SLOW = "slow"
    FAST = "fast"


class CameraMovementMetrics(BaseModel):
    pan: float = Field(ge=0.0, le=1.0)
    zoom: float = Field(ge=0.0, le=1.0)
    shake: float = Field(ge=0.0, le=1.0)


class SignalStatSample(BaseModel):
    index: int
    timestamp_ms: int
    frame: int
    yavg: float
    ymin: float
    ymax: float


class MotionWindow(BaseModel):
    start_ms: int
    end_ms: int
    start_frame: int
    end_frame: int
    duration_ms: int
    motion_score: float = Field(ge=0.0, le=1.0)
    motion_intensity: float = Field(ge=0.0, le=1.0)
    movement_class: MotionMovementClass
    camera_movement: CameraMovementMetrics
    confidence: float = Field(ge=0.0, le=1.0)


class MotionAnalysisSummary(BaseModel):
    overall_motion_score: float = Field(ge=0.0, le=1.0)
    dominant_movement_class: MotionMovementClass
    static_ratio: float = Field(ge=0.0, le=1.0)
    slow_ratio: float = Field(ge=0.0, le=1.0)
    fast_ratio: float = Field(ge=0.0, le=1.0)
    average_shake: float = Field(ge=0.0, le=1.0)
    average_pan: float = Field(ge=0.0, le=1.0)


class MotionAnalysisResult(BaseModel):
    analyzer_version: str
    cache_key: str
    frame_rate: float
    duration_ms: int
    window_ms: int
    sample_stride_frames: int
    summary: MotionAnalysisSummary
    windows: list[MotionWindow] = Field(default_factory=list)


def parse_signalstats_stderr(stderr: str) -> list[dict[str, float]]:
    samples: list[dict[str, float]] = []
    current: dict[str, float] = {}
    for line in stderr.splitlines():
        yavg = _YAVG_RE.search(line)
        if yavg:
            current["yavg"] = float(yavg.group(1))
        ymin = _YMIN_RE.search(line)
        if ymin:
            current["ymin"] = float(ymin.group(1))
        ymax = _YMAX_RE.search(line)
        if ymax:
            current["ymax"] = float(ymax.group(1))
        if "yavg" in current and "ymin" in current and "ymax" in current:
            samples.append(dict(current))
            current = {}
    return samples


def index_samples(
    raw_samples: list[dict[str, float]],
    *,
    frame_rate: float,
    sample_stride_frames: int,
) -> list[SignalStatSample]:
    indexed: list[SignalStatSample] = []
    for index, sample in enumerate(raw_samples):
        frame = index * sample_stride_frames
        timestamp_ms = frame_to_ms(frame, frame_rate)
        indexed.append(
            SignalStatSample(
                index=index,
                timestamp_ms=timestamp_ms,
                frame=frame,
                yavg=sample["yavg"],
                ymin=sample["ymin"],
                ymax=sample["ymax"],
            ),
        )
    return indexed


def classify_movement(motion_score: float) -> MotionMovementClass:
    if motion_score < STATIC_THRESHOLD:
        return MotionMovementClass.STATIC
    if motion_score < FAST_THRESHOLD:
        return MotionMovementClass.SLOW
    return MotionMovementClass.FAST


def compute_window_metrics(samples: list[SignalStatSample]) -> tuple[float, float, CameraMovementMetrics, float]:
    if len(samples) < 2:
        intensity = 0.0
        camera = CameraMovementMetrics(pan=0.0, zoom=0.0, shake=0.0)
        score = 0.0
        confidence = 0.5 if samples else 0.3
        return intensity, score, camera, confidence

    yavg_values = [sample.yavg for sample in samples]
    deltas = [abs(yavg_values[i] - yavg_values[i - 1]) for i in range(1, len(yavg_values))]
    motion_intensity = min(sum(deltas) / len(deltas) / 32.0, 1.0)

    luminance_spreads = [max(0.0, sample.ymax - sample.ymin) / 255.0 for sample in samples]
    spread = sum(luminance_spreads) / len(luminance_spreads)
    pan = min(motion_intensity * 0.7 + spread * 0.3, 1.0)
    zoom = min(spread * 0.55, 1.0)

    mean_delta = sum(deltas) / len(deltas)
    if len(deltas) >= 2:
        variance = sum((delta - mean_delta) ** 2 for delta in deltas) / len(deltas)
        shake = min(variance**0.5 / 16.0, 1.0)
    else:
        shake = min(motion_intensity * 0.45, 1.0)

    motion_score = round(
        min(max(motion_intensity * 0.55 + pan * 0.25 + shake * 0.2, 0.0), 1.0),
        3,
    )
    camera = CameraMovementMetrics(
        pan=round(pan, 3),
        zoom=round(zoom, 3),
        shake=round(shake, 3),
    )
    confidence = min(1.0, 0.55 + len(samples) * 0.08)
    return round(motion_intensity, 3), motion_score, camera, round(confidence, 3)


def build_motion_windows(
    samples: list[SignalStatSample],
    *,
    duration_ms: int,
    frame_rate: float,
    window_ms: int,
) -> list[MotionWindow]:
    if duration_ms <= 0:
        return []

    windows: list[MotionWindow] = []
    start_ms = 0
    while start_ms < duration_ms:
        end_ms = min(start_ms + window_ms, duration_ms)
        window_samples = [
            sample for sample in samples if start_ms <= sample.timestamp_ms < end_ms
        ]
        intensity, score, camera, confidence = compute_window_metrics(window_samples)
        movement_class = classify_movement(score)
        start_frame = ms_to_frame(start_ms, frame_rate)
        end_frame = max(start_frame, ms_to_frame(end_ms, frame_rate) - 1)
        windows.append(
            MotionWindow(
                start_ms=start_ms,
                end_ms=end_ms,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_ms=end_ms - start_ms,
                motion_score=score,
                motion_intensity=intensity,
                movement_class=movement_class,
                camera_movement=camera,
                confidence=confidence,
            ),
        )
        if end_ms >= duration_ms:
            break
        start_ms = end_ms

    return windows


def build_motion_summary(windows: list[MotionWindow]) -> MotionAnalysisSummary:
    if not windows:
        return MotionAnalysisSummary(
            overall_motion_score=0.0,
            dominant_movement_class=MotionMovementClass.STATIC,
            static_ratio=1.0,
            slow_ratio=0.0,
            fast_ratio=0.0,
            average_shake=0.0,
            average_pan=0.0,
        )

    overall = round(sum(window.motion_score for window in windows) / len(windows), 3)
    static_count = sum(1 for window in windows if window.movement_class == MotionMovementClass.STATIC)
    slow_count = sum(1 for window in windows if window.movement_class == MotionMovementClass.SLOW)
    fast_count = sum(1 for window in windows if window.movement_class == MotionMovementClass.FAST)
    total = len(windows)

    class_counts = {
        MotionMovementClass.STATIC: static_count,
        MotionMovementClass.SLOW: slow_count,
        MotionMovementClass.FAST: fast_count,
    }
    dominant = max(class_counts, key=lambda key: class_counts[key])

    return MotionAnalysisSummary(
        overall_motion_score=overall,
        dominant_movement_class=dominant,
        static_ratio=round(static_count / total, 3),
        slow_ratio=round(slow_count / total, 3),
        fast_ratio=round(fast_count / total, 3),
        average_shake=round(
            sum(window.camera_movement.shake for window in windows) / total,
            3,
        ),
        average_pan=round(
            sum(window.camera_movement.pan for window in windows) / total,
            3,
        ),
    )


def build_motion_analysis_result(
    *,
    analyzer_version: str,
    cache_key: str,
    frame_rate: float,
    duration_ms: int,
    signalstats_stderr: str,
    window_ms: int,
    sample_stride_frames: int,
) -> MotionAnalysisResult:
    raw_samples = parse_signalstats_stderr(signalstats_stderr)
    indexed = index_samples(raw_samples, frame_rate=frame_rate, sample_stride_frames=sample_stride_frames)
    windows = build_motion_windows(
        indexed,
        duration_ms=duration_ms,
        frame_rate=frame_rate,
        window_ms=window_ms,
    )
    summary = build_motion_summary(windows)
    return MotionAnalysisResult(
        analyzer_version=analyzer_version,
        cache_key=cache_key,
        frame_rate=frame_rate,
        duration_ms=duration_ms,
        window_ms=window_ms,
        sample_stride_frames=sample_stride_frames,
        summary=summary,
        windows=windows,
    )
