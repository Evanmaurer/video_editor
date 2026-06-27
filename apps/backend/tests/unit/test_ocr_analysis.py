from __future__ import annotations

import pytest

from montage_backend.analysis.modules.ocr import OcrAnalyzer
from montage_backend.analysis.ocr.engine import OcrEngine, RawOcrDetection
from montage_backend.analysis.ocr_analysis import (
    OcrTextCategory,
    build_ocr_analysis_result,
    classify_ocr_text,
    dedupe_detections,
    normalize_ocr_text,
    raw_to_detection,
    sample_timestamps_ms,
)
from montage_backend.services.analysis_service import build_default_registry


class FakeOcrEngine(OcrEngine):
    engine_id = "fake"
    version = "test-1.0"

    def __init__(self, detections: list[RawOcrDetection] | None = None) -> None:
        self._detections = detections or [
            RawOcrDetection(text="[RAVER] PlayerOne killed [ENEMY] Target", confidence=0.92),
            RawOcrDetection(text="1,240", confidence=0.88, x=100, y=200, width=40, height=16),
            RawOcrDetection(text="HP", confidence=0.7),
        ]

    def is_available(self) -> bool:
        return True

    def recognize_png(self, png_bytes: bytes) -> list[RawOcrDetection]:
        _ = png_bytes
        return list(self._detections)


def test_classify_ocr_text_categories():
    assert classify_ocr_text("1,240") == OcrTextCategory.DAMAGE_NUMBER
    assert classify_ocr_text("842k") == OcrTextCategory.DAMAGE_NUMBER
    assert classify_ocr_text("[RAVER] PlayerOne") == OcrTextCategory.PLAYER_NAME
    assert classify_ocr_text("[RAVER]") == OcrTextCategory.GUILD_NAME
    assert (
        classify_ocr_text("[RAVER] PlayerOne killed [ENEMY] Target")
        == OcrTextCategory.COMBAT
    )
    assert classify_ocr_text("PlayerOne: need backup at bridge") == OcrTextCategory.CHAT
    assert classify_ocr_text("FPS") == OcrTextCategory.HUD


def test_normalize_and_dedupe_detections():
    first = raw_to_detection(
        RawOcrDetection(text="  PlayerOne  ", confidence=0.7),
        timestamp_ms=1000,
        frame_rate=60.0,
    )
    second = raw_to_detection(
        RawOcrDetection(text="playerone", confidence=0.9),
        timestamp_ms=2000,
        frame_rate=60.0,
    )
    deduped = dedupe_detections([first, second])
    assert len(deduped) == 1
    assert deduped[0].confidence == 0.9
    assert normalize_ocr_text("  Player One ") == "player one"


def test_sample_timestamps_respects_max_frames():
    timestamps = sample_timestamps_ms(20_000, interval_ms=2000, max_frames=5)
    assert len(timestamps) == 5
    assert timestamps[0] == 0


def test_build_ocr_analysis_result():
    engine = FakeOcrEngine()
    detections = [
        raw_to_detection(raw, timestamp_ms=index * 1000, frame_rate=60.0)
        for index, raw in enumerate(engine.recognize_png(b""))
    ]
    result = build_ocr_analysis_result(
        analyzer_version="ocr-analyzer-v1.0",
        cache_key="ocr:test",
        duration_ms=5000,
        frame_rate=60.0,
        sample_interval_ms=2000,
        frames_sampled=3,
        engine=engine,
        detections=detections,
    )
    assert result.summary.engine_id == "fake"
    assert result.summary.detection_count == 3
    assert result.summary.by_category[OcrTextCategory.COMBAT.value] >= 1
    assert result.summary.by_category[OcrTextCategory.DAMAGE_NUMBER.value] >= 1
    assert len(result.unique_texts) >= 2


def test_ocr_analyzer_cache_key_includes_engine():
    analyzer = OcrAnalyzer(ocr_engine=FakeOcrEngine())
    key = analyzer.cache_key("fp123", frame_rate=60.0)
    assert "engine=fake" in key
    assert "interval=2000" in key


@pytest.mark.asyncio
async def test_ocr_analyzer_runs_with_fake_engine(monkeypatch):
    analyzer = OcrAnalyzer(ocr_engine=FakeOcrEngine())

    async def fake_probe(video, *, ctx=None):
        from montage_backend.models.domain.media import VideoProbeResult

        return VideoProbeResult(
            width=1920,
            height=1080,
            frame_rate=60.0,
            codec="h264",
            duration_ms=4000,
            frame_count=240,
            file_size_bytes=1000,
        )

    async def fake_export_png_frame(video, timestamp_s, *, ctx):
        _ = video, timestamp_s, ctx
        return b"fake-png"

    monkeypatch.setattr(analyzer._processor, "probe", fake_probe)
    monkeypatch.setattr(analyzer, "_export_png_frame", fake_export_png_frame)

    from montage_backend.analysis.base import AnalysisRunContext

    ctx = AnalysisRunContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp",
    )
    output = await analyzer.analyze(
        ctx,
        video_path="/tmp/video.mp4",
        duration_ms=4000,
        frame_rate=60.0,
        frame_count=240,
    )
    assert output.module_id == "ocr"
    assert output.payload["summary"]["detection_count"] >= 3
    assert output.payload["summary"]["engine_id"] == "fake"


def test_default_registry_includes_ocr_module():
    registry = build_default_registry()
    assert "ocr" in registry.list_modules()
