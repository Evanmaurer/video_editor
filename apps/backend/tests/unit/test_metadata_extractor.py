from __future__ import annotations

import json

import pytest

from montage_backend.metadata.extractor import (
    _beats_from_waveform,
    _brightness_from_stats,
    _camera_movement_from_metrics,
    _edge_variance,
    _motion_score_from_stats,
    _parse_silence_regions,
)
from montage_backend.models.domain.media import SceneMarker


def test_brightness_from_signalstats_samples():
    samples = [
        {"yavg": 100.0, "ymin": 80.0, "ymax": 120.0},
        {"yavg": 110.0, "ymin": 85.0, "ymax": 130.0},
    ]
    stats = _brightness_from_stats(samples)
    assert stats.mean == 105.0
    assert stats.min == 80.0
    assert stats.max == 130.0
    assert stats.std > 0


def test_motion_score_increases_with_scene_density():
    scenes = [
        SceneMarker(timestamp_ms=1000, score=0.4),
        SceneMarker(timestamp_ms=2000, score=0.5),
        SceneMarker(timestamp_ms=3000, score=0.6),
    ]
    low = _motion_score_from_stats([], [], 60_000)
    high = _motion_score_from_stats([], scenes, 5_000)
    assert high > low


def test_camera_movement_labels_static_for_low_motion():
    camera = _camera_movement_from_metrics(0.05, [], 10_000)
    assert camera.label == "static"


def test_edge_variance_returns_normalized_score():
    raw = bytes([0, 255] * (160 * 45)) + bytes([128] * (160 * 45))
    score = _edge_variance(raw, 160, 90)
    assert 0.0 <= score <= 1.0


def test_parse_silence_regions():
    stderr = "silence_start: 1.0\nsilence_end: 2.5\nsilence_start: 4.0\nsilence_end: 5.0\n"
    regions = _parse_silence_regions(stderr, 10_000)
    assert len(regions) == 2
    assert regions[0].start_ms == 1000
    assert regions[0].end_ms == 2500


def test_beats_from_waveform_finds_peaks():
    samples = [0.0, 0.2, 0.9, 0.3, 0.1, 0.85, 0.2]
    peaks, beats = _beats_from_waveform(json.dumps({"samples": samples}), 7000)
    assert len(peaks) == len(samples)
    assert len(beats) >= 2
