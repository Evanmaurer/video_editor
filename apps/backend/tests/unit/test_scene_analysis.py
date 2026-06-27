from __future__ import annotations

import pytest

from montage_backend.analysis.base import AnalysisModuleId
from montage_backend.analysis.modules.scene import SceneAnalyzer
from montage_backend.analysis.scene_detection import (
    build_scene_analysis_result,
    build_scene_segments,
    classify_scene_score,
    dedupe_events,
    parse_black_regions,
    parse_freeze_regions,
    parse_scene_markers,
    scene_events_from_markers,
)
from montage_backend.models.domain.analysis import SceneTransitionType


def test_parse_scene_markers():
    stderr = (
        "[Parsed_showinfo_0 @ 0x1] n:   0 pts:      0 pts_time:0.5 "
        "pos:    12345 fmt:yuv420p sar:1/1 s:1920x1080 "
        "i:P iskey:0 type:P checksum:ABC scene_score:0.42\n"
        "[Parsed_showinfo_0 @ 0x1] n:   0 pts:      0 pts_time:2.0 "
        "scene_score:0.12\n"
    )
    markers = parse_scene_markers(stderr)
    assert len(markers) == 2
    assert markers[0] == (500, 0.42)
    assert markers[1] == (2000, 0.12)


def test_classify_scene_score():
    assert classify_scene_score(0.5) == SceneTransitionType.HARD_CUT
    assert classify_scene_score(0.2) == SceneTransitionType.SHOT_BOUNDARY
    assert classify_scene_score(0.08) == SceneTransitionType.FADE


def test_parse_black_and_freeze_regions():
    black_stderr = "black_start:0.5 black_end:1.0 black_duration:0.5\n"
    freeze_stderr = "freeze_start:2.0 freeze_end:3.0 freeze_duration:1.0\n"
    black = parse_black_regions(black_stderr)
    freeze = parse_freeze_regions(freeze_stderr)
    assert black == [(500, 1000, 1.0)]
    assert freeze == [(2000, 3000, 1.0)]


def test_build_scene_segments_from_events():
    events = scene_events_from_markers(
        [(1000, 0.45), (3000, 0.35)],
        frame_rate=60.0,
    )
    segments = build_scene_segments(
        events,
        duration_ms=5000,
        frame_rate=60.0,
        frame_count=300,
    )
    assert len(segments) == 3
    assert segments[0].start_ms == 0
    assert segments[0].end_ms == 1000
    assert segments[1].start_ms == 1000
    assert segments[2].start_ms == 3000


def test_dedupe_events_keeps_higher_confidence():
    events = scene_events_from_markers([(1000, 0.4), (1010, 0.9)], frame_rate=60.0)
    deduped = dedupe_events(events, frame_rate=60.0, min_gap_ms=50)
    assert len(deduped) == 1
    assert deduped[0].confidence == pytest.approx(0.9)


def test_build_scene_analysis_result():
    result = build_scene_analysis_result(
        analyzer_version="scene-analyzer-v1.0",
        cache_key="scene:test",
        frame_rate=60.0,
        frame_count=600,
        duration_ms=10000,
        scene_stderr="pts_time:1.0 scene_score:0.5\n",
        black_stderr="black_start:4.0 black_end:4.5 black_duration:0.5\n",
        freeze_stderr="",
    )
    assert result.analyzer_version == "scene-analyzer-v1.0"
    assert len(result.events) >= 2
    assert len(result.segments) >= 2


def test_scene_analyzer_cache_key():
    analyzer = SceneAnalyzer()
    key = analyzer.cache_key("fp123", frame_rate=60.0)
    assert key.startswith(f"{AnalysisModuleId.SCENE.value}:scene-analyzer-v1.0:fp123")


def test_scene_analyzer_cache_validation():
    analyzer = SceneAnalyzer()
    fingerprint = "abc:123"
    key = analyzer.cache_key(fingerprint, frame_rate=60.0)
    assert analyzer.is_cache_valid(analyzer.version, key, fingerprint, frame_rate=60.0)
    assert not analyzer.is_cache_valid("old-version", key, fingerprint, frame_rate=60.0)
    assert not analyzer.is_cache_valid(analyzer.version, "wrong-key", fingerprint, frame_rate=60.0)
