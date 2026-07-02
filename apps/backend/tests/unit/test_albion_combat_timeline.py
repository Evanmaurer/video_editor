from __future__ import annotations

import pytest

from montage_backend.analysis.albion.base import AlbionDetectorContext, AlbionDetectorId
from montage_backend.analysis.albion.combat.albion_combat_analysis import AlbionCombatEventType
from montage_backend.analysis.albion.combat.config import get_combat_config
from montage_backend.analysis.albion.combat.pipeline import (
    build_detector_cache_key,
    build_window_cache_key,
    dedupe_signals,
    extract_signals_from_albion_ocr,
    run_albion_combat_pipeline,
    segment_fight_boundaries,
    CombatSignal,
)
from montage_backend.analysis.albion.detectors.combat_detector import AlbionCombatDetector
from montage_backend.analysis.albion.runtime import build_default_albion_registry


def test_combat_config_loads_builtin_and_external_default():
    builtin = get_combat_config("albion-combat-default")
    assert builtin.id == "albion-combat-default"

    external = get_combat_config("default")
    assert external.id == "default"
    assert external.fight_activity_threshold == 0.3


def test_extract_kill_and_death_signals_from_albion_ocr():
    payload = {
        "detections": [
            {
                "text": "PlayerOne killed Enemy",
                "category": "kill_message",
                "timestamp_ms": 1500,
                "confidence": 0.9,
                "metadata": {},
            },
            {
                "text": "You died",
                "category": "death_message",
                "timestamp_ms": 4200,
                "confidence": 0.88,
                "metadata": {},
            },
        ],
    }
    signals = extract_signals_from_albion_ocr(payload)
    assert len(signals) == 2
    assert {signal.event_type for signal in signals} == {
        AlbionCombatEventType.KILL,
        AlbionCombatEventType.DEATH,
    }


def test_dedupe_signals_collapses_near_duplicate_kills():
    signals = [
        CombatSignal(
            event_type=AlbionCombatEventType.KILL,
            timestamp_ms=1000,
            confidence=0.9,
            text="Enemy killed",
            source="test",
            metadata={},
        ),
        CombatSignal(
            event_type=AlbionCombatEventType.KILL,
            timestamp_ms=1200,
            confidence=0.85,
            text="Enemy killed",
            source="test",
            metadata={},
        ),
    ]
    assert len(dedupe_signals(signals)) == 1


def test_segment_fight_boundaries_detects_sustained_activity():
    config = get_combat_config("default")
    window_activity = [
        (0, 2000, 0.1),
        (2000, 4000, 0.55),
        (4000, 6000, 0.62),
        (6000, 8000, 0.12),
        (8000, 10000, 0.08),
    ]
    fights = segment_fight_boundaries(window_activity, config=config)
    assert len(fights) == 1
    assert fights[0][0] == 2000
    assert fights[0][1] >= 4000


def test_run_albion_combat_pipeline_builds_searchable_entries():
    albion_ocr_payload = {
        "cache_key": "albion-ocr:test",
        "duration_ms": 8000,
        "frame_rate": 60.0,
        "detections": [
            {
                "text": "Bojukre killed Enemy",
                "category": "kill_message",
                "timestamp_ms": 2500,
                "confidence": 0.91,
                "metadata": {},
            },
            {
                "text": "adic killed",
                "category": "kill_message",
                "timestamp_ms": 2800,
                "confidence": 0.87,
                "metadata": {},
            },
            {
                "text": "4872",
                "category": "damage_number",
                "timestamp_ms": 2600,
                "confidence": 0.8,
                "metadata": {},
            },
        ],
    }
    motion_payload = {
        "duration_ms": 8000,
        "frame_rate": 60.0,
        "windows": [
            {"start_ms": 2000, "end_ms": 4000, "motion_score": 0.85},
            {"start_ms": 4000, "end_ms": 6000, "motion_score": 0.8},
        ],
    }
    result = run_albion_combat_pipeline(
        source_fingerprint="fp-combat",
        duration_ms=8000,
        frame_rate=60.0,
        albion_ocr_payload=albion_ocr_payload,
        m3_ocr_payload=None,
        albion_ability_payload=None,
        albion_ui_payload=None,
        motion_payload=motion_payload,
        config_id="default",
    )
    event_types = {entry.event_type for entry in result.entries}
    assert AlbionCombatEventType.KILL in event_types
    assert AlbionCombatEventType.FIGHT_START in event_types
    assert AlbionCombatEventType.FIGHT_END in event_types
    assert AlbionCombatEventType.RETREAT in event_types
    assert result.summary.kill_count >= 1
    assert result.summary.reused_albion_ocr is True
    assert result.summary.reused_motion is True
    assert all(entry.search_text for entry in result.entries)
    assert result.frame_windows[0].cache_key


def test_frame_windows_have_per_window_cache_keys():
    result = run_albion_combat_pipeline(
        source_fingerprint="fp-combat-windows",
        duration_ms=6000,
        frame_rate=60.0,
        albion_ocr_payload={
            "duration_ms": 6000,
            "frame_rate": 60.0,
            "detections": [
                {
                    "text": "ha killed",
                    "category": "kill_message",
                    "timestamp_ms": 1000,
                    "confidence": 0.9,
                    "metadata": {},
                },
            ],
        },
        m3_ocr_payload=None,
        albion_ability_payload=None,
        albion_ui_payload=None,
        motion_payload=None,
        config_id="default",
    )
    assert len(result.frame_windows) >= 2
    assert result.frame_windows[0].cache_key != result.frame_windows[1].cache_key
    assert build_window_cache_key(
        source_fingerprint="fp-combat-windows",
        config_id="default",
        window_start_ms=0,
        window_end_ms=2000,
    ) in result.frame_windows[0].cache_key


@pytest.mark.asyncio
async def test_albion_combat_detector_uses_inline_detector_results():
    detector = AlbionCombatDetector(config_id="default")
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-combat-detector",
        extras={
            "detector_results": {
                "ocr": {
                    "payload": {
                        "cache_key": "albion-ocr:inline",
                        "duration_ms": 5000,
                        "frame_rate": 60.0,
                        "detections": [
                            {
                                "text": "fozadiac killed",
                                "category": "kill_message",
                                "timestamp_ms": 3000,
                                "confidence": 0.9,
                                "metadata": {},
                            },
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
    assert output.detector_id == AlbionDetectorId.COMBAT.value
    assert output.payload["summary"]["kill_count"] >= 1
    assert output.payload["summary"]["reused_albion_ocr"] is True


def test_default_albion_registry_includes_combat_detector():
    registry = build_default_albion_registry()
    assert registry.list_detectors() == ["framework_probe", "ui", "ocr", "ability", "combat", "bomb", "engagement", "highlight"]
    assert registry.detector_versions()["combat"] == "albion-combat-v1.0"
    assert "config=" in build_detector_cache_key(
        "fp",
        frame_rate=60.0,
        config_id="albion-combat-default",
        config_token="albion-combat-default@1.0",
        sample_interval_ms=2000,
        window_ms=2000,
        source_flags="albion-ocr",
    )
