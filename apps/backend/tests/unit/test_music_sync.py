from __future__ import annotations

import pytest

from montage_backend.analysis.base import AnalysisModuleId
from montage_backend.analysis.clip_analysis_aggregation import build_clip_analysis_record
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.analysis import AnalysisModuleCacheRecord
from montage_backend.models.domain.media import (
    ImportStatus,
    MediaItem,
    MediaRole,
    MediaType,
    ProcessingStatus,
    StorageMode,
)
from montage_backend.models.domain.montage_plan import TransitionType
from montage_backend.montage.base import MontagePlanContext, MontagePlanState
from montage_backend.montage.music_sync import (
    analyze_music_sync,
    build_cache_key,
    build_cut_suggestions,
    detect_chorus_sections,
    detect_drop_sections,
    extract_beat_markers,
)
from montage_backend.montage.modules.music_sync import MusicSyncModule
from montage_backend.montage.registry import build_default_montage_registry


def _music_media() -> MediaItem:
    now = utc_now_iso()
    return MediaItem(
        id="music-1",
        project_id="project-1",
        file_path="/tmp/track.mp3",
        file_name="track.mp3",
        media_type=MediaType.AUDIO,
        role=MediaRole.MUSIC,
        storage_mode=StorageMode.COPY,
        import_status=ImportStatus.READY,
        proxy_status=ProcessingStatus.READY,
        waveform_status=ProcessingStatus.READY,
        scene_status=ProcessingStatus.PENDING,
        metadata_status=ProcessingStatus.READY,
        duration_ms=30000,
        frame_rate=0.0,
        created_at=now,
        updated_at=now,
    )


def _cache(module_id: str, *, payload: dict):
    now = utc_now_iso()
    return AnalysisModuleCacheRecord(
        id=f"cache-{module_id}",
        media_id="music-1",
        module_id=module_id,
        analyzer_version=f"{module_id}-v1",
        cache_key=f"{module_id}:test",
        status=ProcessingStatus.READY,
        payload=payload,
        confidence=0.9,
        source_fingerprint="fp-music",
        created_at=now,
        updated_at=now,
    )


def _music_record():
    audio_payload = {
        "analyzer_version": "audio-analyzer-v1.0",
        "cache_key": "audio:test",
        "duration_ms": 30000,
        "sample_count": 1000,
        "window_ms": 1000,
        "has_audio": True,
        "summary": {
            "dynamic_range_db": 22.0,
            "silence_ratio": 0.05,
            "peak_count": 6,
            "beat_count": 4,
            "tempo_bpm": 120.0,
            "music_probability": 0.82,
            "voice_probability": 0.1,
        },
        "events": [
            {
                "timestamp_ms": 5000,
                "event_type": "beat",
                "value": 0.82,
                "confidence": 0.9,
                "metadata": {"strength": 0.82},
            },
            {
                "timestamp_ms": 5500,
                "event_type": "beat",
                "value": 0.62,
                "confidence": 0.75,
                "metadata": {"strength": 0.62},
            },
            {
                "timestamp_ms": 15000,
                "event_type": "peak",
                "value": 0.95,
                "confidence": 0.92,
                "metadata": {"amplitude": 0.95},
            },
        ],
        "loudness_windows": [
            {
                "start_ms": 0,
                "end_ms": 5000,
                "duration_ms": 5000,
                "loudness_db": -32.0,
                "dynamic_range_db": 6.0,
                "music_probability": 0.3,
                "voice_probability": 0.2,
                "confidence": 0.8,
            },
            {
                "start_ms": 5000,
                "end_ms": 10000,
                "duration_ms": 5000,
                "loudness_db": -14.0,
                "dynamic_range_db": 12.0,
                "music_probability": 0.78,
                "voice_probability": 0.1,
                "confidence": 0.85,
            },
            {
                "start_ms": 10000,
                "end_ms": 15000,
                "duration_ms": 5000,
                "loudness_db": -13.0,
                "dynamic_range_db": 11.0,
                "music_probability": 0.8,
                "voice_probability": 0.08,
                "confidence": 0.86,
            },
            {
                "start_ms": 15000,
                "end_ms": 20000,
                "duration_ms": 5000,
                "loudness_db": -8.0,
                "dynamic_range_db": 18.0,
                "music_probability": 0.88,
                "voice_probability": 0.05,
                "confidence": 0.9,
            },
        ],
        "peaks": [],
    }
    return build_clip_analysis_record(
        project_id="project-1",
        media=_music_media(),
        metadata=None,
        caches=[_cache(AnalysisModuleId.AUDIO.value, payload=audio_payload)],
        embedding_vector_count=0,
        source_fingerprint="fp-music",
    )


def test_extract_beat_markers_from_audio_events():
    record = _music_record()
    markers, tempo = extract_beat_markers(record)
    assert tempo == pytest.approx(120.0)
    assert len(markers) == 2
    assert markers[0].timestamp_ms == 5000


def test_detect_chorus_and_drop_sections():
    record = _music_record()
    assert record.audio is not None
    windows = record.audio.loudness_windows
    chorus = detect_chorus_sections(windows, 30000)
    drops = detect_drop_sections(windows)
    assert len(chorus) >= 1
    assert any(section.section_type == "chorus" for section in chorus)
    assert len(drops) >= 1
    assert any(section.section_type == "drop" for section in drops)


def test_build_cut_suggestions_prefers_drops_and_strong_beats():
    record = _music_record()
    markers, _ = extract_beat_markers(record)
    windows = record.audio.loudness_windows
    sections = [*detect_chorus_sections(windows, 30000), *detect_drop_sections(windows)]
    cuts = build_cut_suggestions(markers, sections)
    assert len(cuts) >= 2
    assert any(cut.beat_aligned for cut in cuts)


def test_analyze_music_sync_returns_full_payload():
    record = _music_record()
    result = analyze_music_sync(
        project_id="project-1",
        media_id="music-1",
        record=record,
        file_name="track.mp3",
        updated_at=utc_now_iso(),
    )
    assert result.tempo_bpm == pytest.approx(120.0)
    assert result.cache_key == build_cache_key("fp-music")
    assert len(result.beat_markers) == 2
    assert len(result.sections) >= 2
    assert len(result.cut_suggestions) >= 2
    assert len(result.transition_suggestions) >= 1
    assert result.confidence >= 0.5
    assert "BPM" in result.reasoning
    assert any(
        suggestion.transition_type == TransitionType.FLASH.value
        for suggestion in result.transition_suggestions
    )


@pytest.mark.asyncio
async def test_music_sync_module_plan():
    record = _music_record()
    module = MusicSyncModule()
    ctx = MontagePlanContext(
        project_id="project-1",
        plan_id="plan-1",
        random_seed=7,
        extras={"music_records": [record]},
    )
    output = await module.plan(ctx, MontagePlanState())
    assert output.module_id == "music_sync"
    assert output.payload["track_count"] == 1
    assert output.payload["tracks"][0]["tempo_bpm"] == pytest.approx(120.0)


def test_default_registry_registers_music_sync():
    registry = build_default_montage_registry()
    module = registry.get("music_sync")
    assert module.module_id.value == "music_sync"
