from __future__ import annotations

import struct

import pytest

from montage_backend.analysis.audio_analysis import (
    AudioEventType,
    TimestampedAudioEvent,
    build_audio_analysis_result,
    detect_beat_events,
    detect_peak_events,
    downsample_peaks,
    estimate_tempo_bpm,
    parse_silence_regions,
    parse_volume_stats,
)
from montage_backend.analysis.modules.audio import AudioAnalyzer
from montage_backend.services.analysis_service import build_default_registry


def test_parse_volume_stats():
    stderr = "mean_volume: -18.5 dB\nmax_volume: -3.2 dB\n"
    mean_db, max_db = parse_volume_stats(stderr)
    assert mean_db == pytest.approx(-18.5)
    assert max_db == pytest.approx(-3.2)


def test_parse_silence_regions_same_line_and_multiline():
    stderr = (
        "silence_start: 1.0 silence_end: 2.5\n"
        "silence_start: 4.0\n"
        "silence_end: 5.0\n"
    )
    regions = parse_silence_regions(stderr, 10_000)
    assert regions == [(1000, 2500), (4000, 5000)]


def test_downsample_peaks_from_f32():
    floats = [0.0, 0.5, 1.0, 0.25]
    raw = struct.pack(f"{len(floats)}f", *floats)
    peaks = downsample_peaks(raw, 4)
    assert len(peaks) == 4
    assert peaks[2] == 1.0


def test_detect_peak_and_beat_events():
    samples = [0.0, 0.2, 0.9, 0.3, 0.1, 0.85, 0.2]
    peaks = detect_peak_events(samples, 7000)
    beats = detect_beat_events(samples, 7000)
    assert all(event.event_type == AudioEventType.PEAK for event in peaks)
    assert all(event.event_type == AudioEventType.BEAT for event in beats)
    assert len(beats) >= 2
    assert all(event.timestamp_ms >= 0 for event in beats)


def test_estimate_tempo_bpm():
    beats = [
        TimestampedAudioEvent(timestamp_ms=0, event_type=AudioEventType.BEAT, value=0.9),
        TimestampedAudioEvent(timestamp_ms=500, event_type=AudioEventType.BEAT, value=0.85),
        TimestampedAudioEvent(timestamp_ms=1000, event_type=AudioEventType.BEAT, value=0.8),
    ]
    tempo = estimate_tempo_bpm(beats)
    assert tempo == pytest.approx(120.0, rel=0.01)


def test_build_audio_analysis_result():
    volume_stderr = (
        "mean_volume: -20.0 dB\nmax_volume: -4.0 dB\n"
        "silence_start: 0.5 silence_end: 1.0\n"
    )
    ebur128_stderr = "I:         -19.5 LUFS\nLRA:         8.0 LU\n"
    peaks = [0.0, 0.1, 0.8, 0.2, 0.1, 0.75, 0.15, 0.05]
    result = build_audio_analysis_result(
        analyzer_version="audio-analyzer-v1.0",
        cache_key="audio:test",
        duration_ms=8000,
        volume_stderr=volume_stderr,
        ebur128_stderr=ebur128_stderr,
        peaks=peaks,
        window_ms=1000,
    )
    assert result.summary.loudness_lufs == pytest.approx(-19.5)
    assert result.summary.dynamic_range_db >= 8.0
    assert result.summary.beat_count >= 1
    assert any(event.event_type == AudioEventType.SILENCE for event in result.events)
    assert len(result.loudness_windows) == 8
    assert 0.0 <= result.summary.music_probability <= 1.0
    assert 0.0 <= result.summary.voice_probability <= 1.0


def test_build_audio_analysis_result_no_audio():
    result = build_audio_analysis_result(
        analyzer_version="audio-analyzer-v1.0",
        cache_key="audio:test",
        duration_ms=5000,
        volume_stderr="",
        ebur128_stderr="",
        peaks=[],
        window_ms=1000,
        has_audio=False,
    )
    assert result.has_audio is False
    assert result.events == []


def test_audio_analyzer_cache_key():
    analyzer = AudioAnalyzer()
    key = analyzer.cache_key("fp123")
    assert key.startswith("audio:audio-analyzer-v1.0:fp123")
    assert "samples=512" in key


def test_default_registry_includes_audio_module():
    registry = build_default_registry()
    assert "audio" in registry.list_modules()
