from __future__ import annotations

import pytest

from montage_backend.analysis.albion.base import AlbionDetectorContext, AlbionDetectorId
from montage_backend.analysis.albion.detectors.engagement_detector import AlbionEngagementDetector
from montage_backend.analysis.albion.engagement.albion_engagement_analysis import AlbionEngagementType
from montage_backend.analysis.albion.engagement.config import get_engagement_config
from montage_backend.analysis.albion.engagement.pipeline import (
    build_detector_cache_key,
    classify_engagement_tags,
    extract_fight_durations,
    resolve_clip_signals,
    run_albion_engagement_pipeline,
)
from montage_backend.analysis.albion.runtime import build_default_albion_registry


def test_engagement_config_loads_builtin_and_external_default():
    builtin = get_engagement_config("albion-engagement-default")
    assert builtin.id == "albion-engagement-default"
    assert builtin.engagement_min_duration_ms == 5000

    external = get_engagement_config("default")
    assert external.id == "default"
    assert external.zvz_min_kills == 4


def test_extract_fight_durations_from_combat_payload():
    payload = {
        "entries": [
            {
                "event_type": "fight_start",
                "timestamp_ms": 1000,
                "metadata": {"fight_end_ms": 7000},
            },
            {
                "event_type": "fight_end",
                "timestamp_ms": 7000,
                "metadata": {"fight_start_ms": 1000},
            },
        ],
    }
    durations = extract_fight_durations(payload)
    assert durations == [6000]


def test_classify_zvz_with_bomb_and_kill_spike():
    config = get_engagement_config("default")
    signals = resolve_clip_signals(
        duration_ms=8000,
        combat_payload={
            "summary": {"kill_count": 5, "death_count": 0, "fight_count": 0},
            "entries": [
                {"event_type": "kill", "timestamp_ms": 4000},
                {"event_type": "kill", "timestamp_ms": 4100},
                {"event_type": "kill", "timestamp_ms": 4200},
                {"event_type": "kill", "timestamp_ms": 4300},
                {"event_type": "kill", "timestamp_ms": 4400},
            ],
        },
        bomb_payload={"summary": {"bomb_count": 1, "top_bomb_score": 8.4}},
        ui_payload={"summary": {"by_element": {"party_frame": 3}}},
        albion_ocr_payload=None,
        m3_ocr_payload=None,
        motion_payload=None,
        keywords=config.gathering_keywords,
    )
    tags = classify_engagement_tags(signals, config=config)
    tag_types = {tag.engagement_type for tag in tags}
    assert AlbionEngagementType.ZVZ in tag_types
    assert len(tags) >= 2


def test_classify_ganking_for_short_burst():
    config = get_engagement_config("default")
    signals = resolve_clip_signals(
        duration_ms=6000,
        combat_payload={
            "summary": {"kill_count": 2, "death_count": 0, "fight_count": 0},
            "entries": [
                {"event_type": "kill", "timestamp_ms": 2000},
                {"event_type": "kill", "timestamp_ms": 2600},
            ],
        },
        bomb_payload={"summary": {"bomb_count": 0, "top_bomb_score": 0.0}},
        ui_payload=None,
        albion_ocr_payload=None,
        m3_ocr_payload=None,
        motion_payload=None,
        keywords=config.gathering_keywords,
    )
    tags = classify_engagement_tags(signals, config=config)
    assert any(tag.engagement_type == AlbionEngagementType.GANKING for tag in tags)


def test_classify_gathering_with_low_motion_and_keywords():
    config = get_engagement_config("default")
    signals = resolve_clip_signals(
        duration_ms=12000,
        combat_payload={"summary": {"kill_count": 0, "death_count": 0, "fight_count": 0}, "entries": []},
        bomb_payload={"summary": {"bomb_count": 0, "top_bomb_score": 0.0}},
        ui_payload={"summary": {"by_element": {"resource_bar": 2}}},
        albion_ocr_payload={
            "mentions": [{"text": "You harvested Birch logs", "timestamp_ms": 3000}],
        },
        m3_ocr_payload=None,
        motion_payload={"windows": [{"start_ms": 0, "motion_score": 0.12}]},
        keywords=config.gathering_keywords,
    )
    tags = classify_engagement_tags(signals, config=config)
    assert any(tag.engagement_type == AlbionEngagementType.GATHERING for tag in tags)


def test_run_albion_engagement_pipeline_supports_multiple_tags():
    config = get_engagement_config("default")
    result = run_albion_engagement_pipeline(
        source_fingerprint="fp-engagement",
        duration_ms=8000,
        frame_rate=60.0,
        combat_payload={
            "cache_key": "combat:test",
            "summary": {"kill_count": 5, "death_count": 0, "fight_count": 0},
            "entries": [
                {"event_type": "kill", "timestamp_ms": 4000},
                {"event_type": "kill", "timestamp_ms": 4100},
                {"event_type": "kill", "timestamp_ms": 4200},
                {"event_type": "kill", "timestamp_ms": 4300},
                {"event_type": "kill", "timestamp_ms": 4400},
            ],
        },
        bomb_payload={
            "cache_key": "bomb:test",
            "summary": {"bomb_count": 1, "top_bomb_score": 8.4},
        },
        ui_payload=None,
        albion_ocr_payload=None,
        m3_ocr_payload=None,
        motion_payload=None,
        config_id="default",
    )
    assert result.summary.tag_count >= 2
    assert result.summary.primary_engagement == AlbionEngagementType.ZVZ
    assert result.summary.reused_albion_combat is True
    assert result.summary.reused_albion_bomb is True
    assert all(tag.search_text for tag in result.tags)


@pytest.mark.asyncio
async def test_engagement_detector_reuses_combat_and_bomb_payloads():
    detector = AlbionEngagementDetector(config_id="default")
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-inline-engagement",
        gpu_enabled=False,
        extras={
            "detector_results": {
                "combat": {
                    "payload": {
                        "cache_key": "combat:inline",
                        "duration_ms": 8000,
                        "frame_rate": 60.0,
                        "summary": {"kill_count": 5, "death_count": 0, "fight_count": 0},
                        "entries": [
                            {"event_type": "kill", "timestamp_ms": 4000},
                            {"event_type": "kill", "timestamp_ms": 4100},
                            {"event_type": "kill", "timestamp_ms": 4200},
                            {"event_type": "kill", "timestamp_ms": 4300},
                            {"event_type": "kill", "timestamp_ms": 4400},
                        ],
                    },
                },
                "bomb": {
                    "payload": {
                        "cache_key": "bomb:inline",
                        "summary": {"bomb_count": 1, "top_bomb_score": 8.4},
                    },
                },
            },
        },
    )
    output = await detector.analyze(
        ctx,
        video_path="/tmp/fake.mp4",
        duration_ms=8000,
        frame_rate=60.0,
    )
    assert output.detector_id == AlbionDetectorId.ENGAGEMENT.value
    assert output.payload["summary"]["tag_count"] >= 1
    assert output.payload["summary"]["primary_engagement"] == AlbionEngagementType.ZVZ.value


def test_default_albion_registry_includes_engagement_detector():
    registry = build_default_albion_registry()
    assert registry.list_detectors() == [
        "framework_probe",
        "ui",
        "ocr",
        "ability",
        "combat",
        "bomb",
        "engagement",
        "highlight",
    ]
    assert registry.detector_versions()["engagement"] == "albion-engagement-v1.0"
    assert "config=" in build_detector_cache_key(
        "fp",
        frame_rate=60.0,
        config_id="albion-engagement-default",
        config_token="albion-engagement-default@1.0",
        sample_interval_ms=2000,
        window_ms=2000,
        source_flags="combat,bomb",
    )
