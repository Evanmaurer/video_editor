from __future__ import annotations

import pytest

from montage_backend.analysis.albion.ability.albion_ability_analysis import AlbionAbilityEventType
from montage_backend.analysis.albion.ability.catalog import get_catalog
from montage_backend.analysis.albion.ability.pipeline import (
    AbilityMention,
    build_detector_cache_key,
    build_window_cache_key,
    build_ability_events,
    group_events_into_windows,
    match_ability_definition,
    run_albion_ability_pipeline,
)
from montage_backend.analysis.albion.base import AlbionDetectorContext, AlbionDetectorId
from montage_backend.analysis.albion.detectors.ability_detector import AlbionAbilityDetector
from montage_backend.analysis.albion.runtime import build_default_albion_registry
from montage_backend.analysis.ocr.engine import OcrEngine, RawOcrDetection
from montage_backend.analysis.ocr_analysis import build_ocr_analysis_result, raw_to_detection


class FakeOcrEngine(OcrEngine):
    engine_id = "fake"
    version = "test-1.0"

    def is_available(self) -> bool:
        return True

    def recognize_png(self, png_bytes: bytes) -> list[RawOcrDetection]:
        _ = png_bytes
        return [
            RawOcrDetection(text="Galatine Pair", confidence=0.9),
            RawOcrDetection(text="Meteor", confidence=0.88),
            RawOcrDetection(text="Galatine Pair", confidence=0.86),
        ]


def test_catalog_loads_builtin_and_external_default():
    catalog = get_catalog("albion-abilities-default")
    assert catalog.id == "albion-abilities-default"
    assert any(ability.id == "meteor" for ability in catalog.abilities)

    external = get_catalog("default")
    assert external.id == "default"
    assert any(ability.id == "custom_bomb" for ability in external.abilities)


def test_match_ability_definition_uses_aliases():
    catalog = get_catalog("default")
    definition = match_ability_definition("galatine pair", catalog)
    assert definition is not None
    assert definition.id == "galatine_pair"


def test_build_ability_events_include_activation_cooldown_and_ultimate():
    catalog = get_catalog("default")
    mentions = [
        AbilityMention(text="Meteor", timestamp_ms=1000, confidence=0.9, source="test"),
        AbilityMention(text="Galatine Pair", timestamp_ms=25000, confidence=0.85, source="test"),
        AbilityMention(text="Galatine Pair", timestamp_ms=26000, confidence=0.8, source="test"),
    ]
    events = build_ability_events(mentions, catalog=catalog, window_ms=2000)
    event_types = {event.event_type for event in events}
    assert AlbionAbilityEventType.ULTIMATE_ACTIVATION in event_types
    assert AlbionAbilityEventType.ACTIVATION in event_types
    assert AlbionAbilityEventType.COOLDOWN_START in event_types
    assert AlbionAbilityEventType.COOLDOWN_READY in event_types
    assert sum(1 for event in events if event.ability_id == "galatine_pair" and event.event_type == AlbionAbilityEventType.ACTIVATION) == 1


def test_frame_windows_have_per_window_cache_keys():
    catalog = get_catalog("default")
    mentions = [
        AbilityMention(text="Meteor", timestamp_ms=0, confidence=0.9, source="test"),
        AbilityMention(text="Galatine Pair", timestamp_ms=3000, confidence=0.85, source="test"),
    ]
    events = build_ability_events(mentions, catalog=catalog, window_ms=2000)
    windows = group_events_into_windows(
        events,
        timestamps=[0, 2000],
        window_ms=2000,
        source_fingerprint="fp-ability",
        catalog_id=catalog.id,
    )
    assert len(windows) == 2
    assert windows[0].cache_key != windows[1].cache_key
    assert build_window_cache_key(
        source_fingerprint="fp-ability",
        catalog_id=catalog.id,
        window_start_ms=0,
        window_end_ms=2000,
    ) in windows[0].cache_key


def test_run_albion_ability_pipeline_from_m3_ocr():
    engine = FakeOcrEngine()
    m3 = build_ocr_analysis_result(
        analyzer_version="ocr-analyzer-v1.0",
        cache_key="ocr:ability-test",
        duration_ms=5000,
        frame_rate=60.0,
        sample_interval_ms=2000,
        frames_sampled=2,
        engine=engine,
        detections=[
            raw_to_detection(raw, timestamp_ms=index * 2500, frame_rate=60.0)
            for index, raw in enumerate(engine.recognize_png(b""))
        ],
    )
    result = run_albion_ability_pipeline(
        source_fingerprint="fp-ability",
        duration_ms=5000,
        frame_rate=60.0,
        sample_interval_ms=2000,
        window_ms=2000,
        albion_ocr_payload=None,
        m3_ocr_payload=m3.model_dump(mode="json"),
    )
    assert result.summary.mention_count >= 2
    assert result.summary.activation_count >= 1
    assert result.summary.ultimate_count >= 1
    assert result.summary.reused_albion_ocr is False
    assert "meteor" in result.unique_abilities


def test_run_albion_ability_pipeline_prefers_albion_ocr_payload():
    albion_ocr_payload = {
        "cache_key": "albion-ocr:test",
        "duration_ms": 4000,
        "frame_rate": 60.0,
        "detections": [
            {
                "text": "Custom Bomb",
                "category": "ability_name",
                "timestamp_ms": 1500,
                "confidence": 0.91,
                "metadata": {"ability_name": "Custom Bomb"},
            },
        ],
    }
    result = run_albion_ability_pipeline(
        source_fingerprint="fp-ability",
        duration_ms=4000,
        frame_rate=60.0,
        sample_interval_ms=2000,
        window_ms=2000,
        albion_ocr_payload=albion_ocr_payload,
        m3_ocr_payload=None,
        catalog_id="default",
    )
    assert result.summary.reused_albion_ocr is True
    assert result.summary.ultimate_count == 1
    assert result.events[0].ability_id == "custom_bomb"


@pytest.mark.asyncio
async def test_albion_ability_detector_uses_inline_ocr_results():
    detector = AlbionAbilityDetector(catalog_id="default")
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-ability-detector",
        extras={
            "detector_results": {
                "ocr": {
                    "payload": {
                        "cache_key": "albion-ocr:inline",
                        "duration_ms": 4000,
                        "frame_rate": 60.0,
                        "detections": [
                            {
                                "text": "Meteor",
                                "category": "ability_name",
                                "timestamp_ms": 1000,
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
        duration_ms=4000,
        frame_rate=60.0,
    )
    assert output.detector_id == AlbionDetectorId.ABILITY.value
    assert output.payload["summary"]["ultimate_count"] == 1
    assert output.payload["summary"]["reused_albion_ocr"] is True


def test_default_albion_registry_includes_ability_detector():
    registry = build_default_albion_registry()
    assert registry.list_detectors() == ["framework_probe", "ui", "ocr", "ability", "combat", "bomb", "engagement", "highlight"]
    assert registry.detector_versions()["ability"] == "albion-ability-v1.0"
    assert "catalog=" in build_detector_cache_key(
        "fp",
        frame_rate=60.0,
        catalog_id="albion-abilities-default",
        catalog_token="albion-abilities-default@1.0:30",
        sample_interval_ms=2000,
        window_ms=2000,
        reused_albion_ocr=False,
    )
