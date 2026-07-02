from __future__ import annotations

import pytest

from montage_backend.analysis.albion.ability.albion_ability_analysis import AlbionAbilityEventType
from montage_backend.analysis.albion.base import AlbionDetectorContext, AlbionDetectorId
from montage_backend.analysis.albion.bomb.config import get_bomb_config
from montage_backend.analysis.albion.bomb.pipeline import (
    KillMention,
    build_detector_cache_key,
    build_window_cache_key,
    dedupe_bomb_events,
    extract_kills_from_combat_payload,
    find_kill_spike_windows,
    fuse_bomb_confidence,
    run_albion_bomb_pipeline,
)
from montage_backend.analysis.albion.bomb.albion_bomb_analysis import AlbionBombEvent, AlbionBombFusionScores
from montage_backend.analysis.albion.detectors.bomb_detector import AlbionBombDetector
from montage_backend.analysis.albion.runtime import build_default_albion_registry
from montage_backend.analysis.audio_analysis import AudioEventType


def test_bomb_config_loads_builtin_and_external_default():
    builtin = get_bomb_config("albion-bomb-default")
    assert builtin.id == "albion-bomb-default"
    assert builtin.bomb_min_kills == 3

    external = get_bomb_config("default")
    assert external.id == "default"
    assert external.bomb_kill_window_ms == 2000


def test_extract_kills_from_combat_payload():
    payload = {
        "entries": [
            {
                "event_type": "kill",
                "timestamp_ms": 2500,
                "confidence": 0.9,
                "label": "Kill: Enemy",
                "metadata": {"matched_text": "Enemy killed"},
            },
            {
                "event_type": "death",
                "timestamp_ms": 3000,
                "confidence": 0.8,
                "label": "Death",
                "metadata": {},
            },
        ],
    }
    kills = extract_kills_from_combat_payload(payload)
    assert len(kills) == 1
    assert kills[0].text == "Enemy killed"


def test_find_kill_spike_windows_requires_min_kills():
    config = get_bomb_config("default")
    kills = [
        KillMention(timestamp_ms=1000, confidence=0.9, text="a", source="test"),
        KillMention(timestamp_ms=1500, confidence=0.9, text="b", source="test"),
        KillMention(timestamp_ms=1800, confidence=0.9, text="c", source="test"),
        KillMention(timestamp_ms=2100, confidence=0.9, text="d", source="test"),
    ]
    windows = find_kill_spike_windows(kills, config=config)
    assert len(windows) >= 1
    assert len(windows[0][2]) >= config.bomb_min_kills


def test_fuse_bomb_confidence_combines_motion_audio_and_ability():
    config = get_bomb_config("default")
    confidence, fusion = fuse_bomb_confidence(
        kill_count=4,
        config=config,
        motion_raw=0.7,
        audio_raw=0.8,
        ability_raw=0.6,
    )
    assert confidence > 0.6
    assert fusion.ocr_score == 1.0
    assert fusion.motion_score > 0
    assert fusion.audio_score > 0
    assert fusion.ability_score == 0.6


def test_run_albion_bomb_pipeline_fuses_all_sources():
    combat_payload = {
        "cache_key": "combat:test",
        "duration_ms": 8000,
        "frame_rate": 60.0,
        "entries": [
            {"event_type": "kill", "timestamp_ms": 2500, "confidence": 0.9, "label": "Kill: a", "metadata": {"matched_text": "a killed"}},
            {"event_type": "kill", "timestamp_ms": 2600, "confidence": 0.88, "label": "Kill: b", "metadata": {"matched_text": "b killed"}},
            {"event_type": "kill", "timestamp_ms": 2700, "confidence": 0.87, "label": "Kill: c", "metadata": {"matched_text": "c killed"}},
            {"event_type": "kill", "timestamp_ms": 2800, "confidence": 0.86, "label": "Kill: d", "metadata": {"matched_text": "d killed"}},
        ],
    }
    ability_payload = {
        "events": [
            {
                "event_type": AlbionAbilityEventType.ULTIMATE_ACTIVATION.value,
                "timestamp_ms": 2550,
                "ability_id": "meteor",
            },
        ],
    }
    motion_payload = {
        "windows": [{"start_ms": 2500, "end_ms": 4500, "motion_score": 0.82}],
    }
    audio_payload = {
        "window_ms": 1000,
        "events": [
            {
                "timestamp_ms": 2600,
                "event_type": AudioEventType.PEAK.value,
                "value": 0.9,
            },
        ],
        "peaks": [],
    }
    result = run_albion_bomb_pipeline(
        source_fingerprint="fp-bomb",
        duration_ms=8000,
        frame_rate=60.0,
        combat_payload=combat_payload,
        albion_ocr_payload=None,
        m3_ocr_payload=None,
        albion_ability_payload=ability_payload,
        motion_payload=motion_payload,
        audio_payload=audio_payload,
        config_id="default",
    )
    assert result.summary.bomb_count >= 1
    assert result.summary.top_bomb_score > 0
    assert result.summary.reused_albion_combat is True
    assert result.summary.reused_motion is True
    assert result.summary.reused_audio is True
    assert result.summary.reused_albion_ability is True
    bomb = result.events[0]
    assert bomb.kill_count >= 3
    assert bomb.confidence > 0
    assert bomb.fusion.motion_score > 0
    assert bomb.fusion.audio_score > 0
    assert bomb.fusion.ability_score > 0
    assert "bomb" in bomb.search_text


def test_frame_windows_have_per_window_cache_keys():
    result = run_albion_bomb_pipeline(
        source_fingerprint="fp-bomb-windows",
        duration_ms=6000,
        frame_rate=60.0,
        combat_payload={
            "duration_ms": 6000,
            "frame_rate": 60.0,
            "entries": [
                {"event_type": "kill", "timestamp_ms": 1000, "confidence": 0.9, "label": "k1", "metadata": {"matched_text": "k1"}},
                {"event_type": "kill", "timestamp_ms": 1200, "confidence": 0.9, "label": "k2", "metadata": {"matched_text": "k2"}},
                {"event_type": "kill", "timestamp_ms": 1400, "confidence": 0.9, "label": "k3", "metadata": {"matched_text": "k3"}},
            ],
        },
        albion_ocr_payload=None,
        m3_ocr_payload=None,
        albion_ability_payload=None,
        motion_payload=None,
        audio_payload=None,
        config_id="default",
    )
    assert len(result.frame_windows) >= 2
    assert result.frame_windows[0].cache_key != result.frame_windows[1].cache_key
    assert build_window_cache_key(
        source_fingerprint="fp-bomb-windows",
        config_id="default",
        window_start_ms=0,
        window_end_ms=2000,
    ) in result.frame_windows[0].cache_key


def test_dedupe_bomb_events_keeps_highest_confidence():
    events = [
        AlbionBombEvent(
            event_id="bomb:1000:0",
            timestamp_ms=1000,
            window_start_ms=0,
            window_end_ms=2000,
            confidence=0.7,
            bomb_score=7.0,
            kill_count=3,
            fusion=AlbionBombFusionScores(ocr_score=1.0, motion_score=0.0, audio_score=0.0, ability_score=0.0),
            search_text="bomb",
            reasoning="test",
        ),
        AlbionBombEvent(
            event_id="bomb:1100:1",
            timestamp_ms=1100,
            window_start_ms=0,
            window_end_ms=2000,
            confidence=0.9,
            bomb_score=9.0,
            kill_count=4,
            fusion=AlbionBombFusionScores(ocr_score=1.0, motion_score=0.5, audio_score=0.0, ability_score=0.0),
            search_text="bomb",
            reasoning="test",
        ),
    ]
    deduped = dedupe_bomb_events(events)
    assert len(deduped) == 1
    assert deduped[0].confidence == 0.9


@pytest.mark.asyncio
async def test_albion_bomb_detector_uses_inline_combat_results():
    detector = AlbionBombDetector(config_id="default")
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-bomb-detector",
        extras={
            "detector_results": {
                "combat": {
                    "payload": {
                        "cache_key": "combat:inline",
                        "duration_ms": 5000,
                        "frame_rate": 60.0,
                        "entries": [
                            {"event_type": "kill", "timestamp_ms": 2000, "confidence": 0.9, "label": "k1", "metadata": {"matched_text": "k1"}},
                            {"event_type": "kill", "timestamp_ms": 2100, "confidence": 0.9, "label": "k2", "metadata": {"matched_text": "k2"}},
                            {"event_type": "kill", "timestamp_ms": 2200, "confidence": 0.9, "label": "k3", "metadata": {"matched_text": "k3"}},
                        ],
                    },
                },
            },
        },
    )
    output = await detector.analyze(
        ctx,
        video_path="/tmp/fake.mp4",
        duration_ms=5000,
        frame_rate=60.0,
    )
    assert output.detector_id == AlbionDetectorId.BOMB.value
    assert output.payload["summary"]["bomb_count"] >= 1
    assert output.payload["summary"]["reused_albion_combat"] is True


def test_default_albion_registry_includes_bomb_detector():
    registry = build_default_albion_registry()
    assert registry.list_detectors() == ["framework_probe", "ui", "ocr", "ability", "combat", "bomb", "engagement", "highlight"]
    assert registry.detector_versions()["bomb"] == "albion-bomb-v1.0"
    assert "config=" in build_detector_cache_key(
        "fp",
        frame_rate=60.0,
        config_id="albion-bomb-default",
        config_token="albion-bomb-default@1.0",
        sample_interval_ms=2000,
        window_ms=2000,
        source_flags="combat",
    )
