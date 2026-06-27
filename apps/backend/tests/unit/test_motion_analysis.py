from __future__ import annotations

import pytest

from montage_backend.analysis.modules.motion import MotionAnalyzer
from montage_backend.analysis.motion_analysis import (
    MotionMovementClass,
    SignalStatSample,
    build_motion_analysis_result,
    build_motion_summary,
    build_motion_windows,
    classify_movement,
    compute_window_metrics,
    index_samples,
    parse_signalstats_stderr,
)
from montage_backend.services.analysis_service import build_default_registry


def _sample(index: int, yavg: float, *, ymin: float | None = None, ymax: float | None = None) -> SignalStatSample:
    return SignalStatSample(
        index=index,
        timestamp_ms=index * 1000,
        frame=index * 60,
        yavg=yavg,
        ymin=ymin if ymin is not None else yavg - 10,
        ymax=ymax if ymax is not None else yavg + 10,
    )


def test_parse_signalstats_stderr():
    stderr = (
        "lavfi.signalstats.YAVG=120.0\n"
        "lavfi.signalstats.YMIN=100.0\n"
        "lavfi.signalstats.YMAX=140.0\n"
        "lavfi.signalstats.YAVG=130.0\n"
        "lavfi.signalstats.YMIN=110.0\n"
        "lavfi.signalstats.YMAX=150.0\n"
    )
    samples = parse_signalstats_stderr(stderr)
    assert len(samples) == 2
    assert samples[0]["yavg"] == 120.0


def test_index_samples_assigns_timestamps():
    raw = [{"yavg": 100.0, "ymin": 90.0, "ymax": 110.0}]
    indexed = index_samples(raw, frame_rate=60.0, sample_stride_frames=15)
    assert indexed[0].frame == 0
    assert indexed[0].timestamp_ms == 0


def test_classify_movement_thresholds():
    assert classify_movement(0.05) == MotionMovementClass.STATIC
    assert classify_movement(0.25) == MotionMovementClass.SLOW
    assert classify_movement(0.75) == MotionMovementClass.FAST


def test_compute_window_metrics_static_for_flat_samples():
    samples = [_sample(0, 120.0), _sample(1, 121.0), _sample(2, 120.5)]
    intensity, score, camera, confidence = compute_window_metrics(samples)
    assert intensity < 0.15
    assert score < 0.15
    assert camera.shake < 0.2
    assert confidence > 0.5


def test_compute_window_metrics_detects_fast_motion():
    samples = [_sample(i, 80.0 + i * 20.0) for i in range(6)]
    intensity, score, camera, _confidence = compute_window_metrics(samples)
    assert intensity > 0.2
    assert score > 0.2
    assert camera.pan > 0.0


def test_build_motion_windows_covers_duration():
    samples = [
        SignalStatSample(index=i, timestamp_ms=i * 500, frame=i * 30, yavg=100 + i * 5, ymin=90, ymax=110)
        for i in range(8)
    ]
    windows = build_motion_windows(
        samples,
        duration_ms=5000,
        frame_rate=60.0,
        window_ms=1000,
    )
    assert len(windows) == 5
    assert windows[0].start_ms == 0
    assert windows[-1].end_ms == 5000
    assert all(window.duration_ms > 0 for window in windows)


def test_build_motion_summary_ratios():
    windows = build_motion_windows(
        [
            _sample(0, 100.0),
            _sample(1, 101.0),
            _sample(2, 160.0),
            _sample(3, 220.0),
        ],
        duration_ms=2000,
        frame_rate=60.0,
        window_ms=1000,
    )
    summary = build_motion_summary(windows)
    assert summary.static_ratio + summary.slow_ratio + summary.fast_ratio == pytest.approx(1.0)
    assert summary.overall_motion_score >= 0.0


def test_build_motion_analysis_result_from_stderr():
    stderr = (
        "lavfi.signalstats.YAVG=100.0\nlavfi.signalstats.YMIN=90.0\nlavfi.signalstats.YMAX=110.0\n"
        "lavfi.signalstats.YAVG=140.0\nlavfi.signalstats.YMIN=120.0\nlavfi.signalstats.YMAX=160.0\n"
    )
    result = build_motion_analysis_result(
        analyzer_version="motion-analyzer-v1.0",
        cache_key="motion:test",
        frame_rate=60.0,
        duration_ms=3000,
        signalstats_stderr=stderr,
        window_ms=1000,
        sample_stride_frames=15,
    )
    assert result.analyzer_version == "motion-analyzer-v1.0"
    assert len(result.windows) == 3
    assert result.summary.dominant_movement_class in MotionMovementClass


def test_motion_analyzer_cache_key_includes_window_params():
    analyzer = MotionAnalyzer()
    key = analyzer.cache_key("fp123", frame_rate=60.0)
    assert "window=1000" in key
    assert "stride=15" in key


def test_default_registry_includes_motion_module():
    registry = build_default_registry()
    assert "motion" in registry.list_modules()
