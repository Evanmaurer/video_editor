from __future__ import annotations

import pytest

from montage_backend.analysis.albion.base import AlbionDetectorContext, AlbionDetectorId
from montage_backend.analysis.albion.detectors.ocr_detector import AlbionOcrDetector
from montage_backend.analysis.albion.ocr.albion_ocr_analysis import AlbionOcrCategory
from montage_backend.analysis.albion.ocr.classifier import classify_albion_text, normalize_albion_text
from montage_backend.analysis.albion.ocr.pipeline import (
    build_window_cache_key,
    dedupe_albion_detections,
    group_detections_into_windows,
    raw_to_albion_detection,
    reclassify_m3_ocr_result,
)
from montage_backend.analysis.albion.runtime import build_default_albion_registry
from montage_backend.analysis.ocr.engine import OcrEngine, RawOcrDetection
from montage_backend.analysis.ocr_analysis import build_ocr_analysis_result


class FakeOcrEngine(OcrEngine):
    engine_id = "fake"
    version = "test-1.0"

    def __init__(self, detections: list[RawOcrDetection] | None = None) -> None:
        self._detections = detections or [
            RawOcrDetection(text="[RAVER] PlayerOne killed [ENEMY] Target", confidence=0.92),
            RawOcrDetection(text="+1,240", confidence=0.88, x=100, y=200, width=40, height=16),
            RawOcrDetection(text="842k", confidence=0.86),
            RawOcrDetection(text="Bridgewatch", confidence=0.8),
            RawOcrDetection(text="Galatine Pair", confidence=0.77),
            RawOcrDetection(text="Loot received: Adept's Cape", confidence=0.75),
            RawOcrDetection(text="You died", confidence=0.9),
            RawOcrDetection(text="[ALLY] [RAVER] SlayerX", confidence=0.84),
        ]

    def is_available(self) -> bool:
        return True

    def recognize_png(self, png_bytes: bytes) -> list[RawOcrDetection]:
        _ = png_bytes
        return list(self._detections)


def test_classify_albion_text_categories():
    assert classify_albion_text("[RAVER] PlayerOne") == AlbionOcrCategory.PLAYER_NAME
    assert classify_albion_text("[RAVER]") == AlbionOcrCategory.GUILD_TAG
    assert classify_albion_text("[ALLY] [RAVER] SlayerX") == AlbionOcrCategory.PLAYER_NAME
    assert classify_albion_text("842k") == AlbionOcrCategory.DAMAGE_NUMBER
    assert classify_albion_text("+1,240") == AlbionOcrCategory.HEALING_NUMBER
    assert classify_albion_text("Bridgewatch") == AlbionOcrCategory.ZONE_NAME
    assert classify_albion_text("Galatine Pair") == AlbionOcrCategory.ABILITY_NAME
    assert (
        classify_albion_text("[RAVER] PlayerOne killed [ENEMY] Target")
        == AlbionOcrCategory.KILL_MESSAGE
    )
    assert classify_albion_text("You died") == AlbionOcrCategory.DEATH_MESSAGE
    assert classify_albion_text("Loot received: Adept's Cape") == AlbionOcrCategory.LOOT_NOTIFICATION


def test_raw_to_albion_detection_extracts_guild_metadata():
    detection = raw_to_albion_detection(
        RawOcrDetection(text="[RAVER] SlayerX", confidence=0.9),
        timestamp_ms=1500,
        window_start_ms=1500,
        window_end_ms=3000,
    )
    assert detection.category == AlbionOcrCategory.PLAYER_NAME
    assert detection.metadata["guild_tag"] == "RAVER"
    assert detection.metadata["player_name"] == "SlayerX"


def test_frame_windows_have_per_window_cache_keys():
    detections = [
        raw_to_albion_detection(
            RawOcrDetection(text="842k", confidence=0.9),
            timestamp_ms=0,
            window_start_ms=0,
            window_end_ms=1500,
        ),
        raw_to_albion_detection(
            RawOcrDetection(text="+500", confidence=0.85),
            timestamp_ms=1500,
            window_start_ms=1500,
            window_end_ms=3000,
        ),
    ]
    windows = group_detections_into_windows(
        detections,
        timestamps=[0, 1500],
        window_ms=1500,
        source_fingerprint="fp-ocr",
        engine_id="fake",
        engine_version="test-1.0",
    )
    assert len(windows) == 2
    assert windows[0].cache_key != windows[1].cache_key
    assert windows[0].detection_count == 1
    assert build_window_cache_key(
        source_fingerprint="fp-ocr",
        window_start_ms=0,
        window_end_ms=1500,
        engine_id="fake",
        engine_version="test-1.0",
    ) in windows[0].cache_key


def test_reclassify_m3_ocr_result_builds_albion_windows():
    engine = FakeOcrEngine()
    from montage_backend.analysis.ocr_analysis import raw_to_detection

    m3_detections = [
        raw_to_detection(raw, timestamp_ms=index * 1500, frame_rate=60.0)
        for index, raw in enumerate(engine.recognize_png(b""))
    ]
    m3 = build_ocr_analysis_result(
        analyzer_version="ocr-analyzer-v1.0",
        cache_key="ocr:m3-test",
        duration_ms=4500,
        frame_rate=60.0,
        sample_interval_ms=1500,
        frames_sampled=3,
        engine=engine,
        detections=m3_detections,
    )

    result = reclassify_m3_ocr_result(
        m3,
        source_fingerprint="fp-reclassify",
        window_ms=1500,
        sample_interval_ms=1500,
    )
    assert result.summary.reused_m3_ocr is True
    assert result.summary.window_count >= 1
    assert result.summary.by_category[AlbionOcrCategory.KILL_MESSAGE.value] >= 1
    assert result.summary.by_category[AlbionOcrCategory.DAMAGE_NUMBER.value] >= 1
    assert len(result.frame_windows) >= 1
    assert all(window.cache_key for window in result.frame_windows)


def test_dedupe_albion_detections_keeps_highest_confidence():
    first = raw_to_albion_detection(
        RawOcrDetection(text="PlayerOne", confidence=0.7),
        timestamp_ms=0,
        window_start_ms=0,
        window_end_ms=1500,
    )
    second = raw_to_albion_detection(
        RawOcrDetection(text="playerone", confidence=0.9),
        timestamp_ms=1500,
        window_start_ms=1500,
        window_end_ms=3000,
    )
    deduped = dedupe_albion_detections([first, second])
    assert len(deduped) == 1
    assert deduped[0].confidence == 0.9
    assert normalize_albion_text(" Player One ") == "player one"


def test_default_registry_includes_ocr_detector():
    registry = build_default_albion_registry()
    assert "ocr" in registry.list_detectors()
    assert registry.get(AlbionDetectorId.OCR).version == "albion-ocr-v1.0"


@pytest.mark.asyncio
async def test_albion_ocr_detector_reclassifies_m3_cache(monkeypatch):
    detector = AlbionOcrDetector(ocr_engine=FakeOcrEngine())
    engine = FakeOcrEngine()
    from montage_backend.analysis.ocr_analysis import raw_to_detection

    m3_detections = [
        raw_to_detection(raw, timestamp_ms=0, frame_rate=60.0)
        for raw in engine.recognize_png(b"")
    ]
    m3 = build_ocr_analysis_result(
        analyzer_version="ocr-analyzer-v1.0",
        cache_key="ocr:cached",
        duration_ms=3000,
        frame_rate=60.0,
        sample_interval_ms=1500,
        frames_sampled=2,
        engine=engine,
        detections=m3_detections,
    )

    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-ocr-detector",
        gpu_enabled=False,
        extras={"ocr_analysis": m3.model_dump(mode="json")},
    )

    output = await detector.analyze(
        ctx,
        video_path="/tmp/fake.mp4",
        duration_ms=3000,
        frame_rate=60.0,
    )
    assert output.detector_id == "ocr"
    assert output.payload["summary"]["reused_m3_ocr"] is True
    assert output.payload["summary"]["window_count"] >= 1
    assert len(output.payload["frame_windows"]) >= 1
    assert output.payload["summary"]["by_category"][AlbionOcrCategory.KILL_MESSAGE.value] >= 1
    assert any(event.event_type == AlbionOcrCategory.KILL_MESSAGE.value for event in output.events)


@pytest.mark.asyncio
async def test_albion_ocr_detector_cache_key_accepts_m3_suffix():
    detector = AlbionOcrDetector(ocr_engine=FakeOcrEngine())
    base = detector.cache_key("fp-1", frame_rate=60.0)
    assert detector.is_cache_valid(detector.version, f"{base}:m3:ocr:cached", "fp-1", frame_rate=60.0)
