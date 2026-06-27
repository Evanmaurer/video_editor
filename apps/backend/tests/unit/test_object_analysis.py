from __future__ import annotations

import pytest

from montage_backend.analysis.modules.object import ObjectAnalyzer
from montage_backend.analysis.object.engine import ObjectDetector, RawObjectDetection
from montage_backend.analysis.object_analysis import (
    ObjectBoundingBox,
    ObjectCategory,
    bbox_iou,
    build_object_analysis_result,
    dedupe_detections,
    raw_to_detection,
)
from montage_backend.services.analysis_service import build_default_registry


class FakeObjectDetector(ObjectDetector):
    detector_id = "fake"
    version = "test-1.0"

    def __init__(self, detections: list[RawObjectDetection] | None = None) -> None:
        self._detections = detections or [
            RawObjectDetection(
                category="character",
                label="person",
                confidence=0.91,
                x=400,
                y=200,
                width=120,
                height=240,
                source_model="fake",
            ),
            RawObjectDetection(
                category="minimap",
                label="minimap_region",
                confidence=0.76,
                x=1500,
                y=780,
                width=360,
                height=260,
                source_model="fake",
            ),
            RawObjectDetection(
                category="health_bar",
                label="health_bar",
                confidence=0.68,
                x=20,
                y=140,
                width=140,
                height=10,
                source_model="fake",
            ),
            RawObjectDetection(
                category="spell_effect",
                label="bright_effect",
                confidence=0.72,
                x=300,
                y=180,
                width=900,
                height=540,
                source_model="fake",
            ),
        ]

    def is_available(self) -> bool:
        return True

    def detect_png(self, png_bytes: bytes) -> list[RawObjectDetection]:
        _ = png_bytes
        return list(self._detections)


def test_bbox_iou_overlap():
    a = ObjectBoundingBox(x=0, y=0, width=100, height=100)
    b = ObjectBoundingBox(x=50, y=50, width=100, height=100)
    assert bbox_iou(a, b) == pytest.approx(0.142857, rel=0.01)


def test_dedupe_detections_removes_iou_duplicates():
    first = raw_to_detection(
        RawObjectDetection("character", "person", 0.7, 10, 10, 50, 80, "fake"),
        timestamp_ms=1000,
        frame_rate=60.0,
    )
    second = raw_to_detection(
        RawObjectDetection("character", "person", 0.9, 12, 12, 48, 78, "fake"),
        timestamp_ms=1000,
        frame_rate=60.0,
    )
    third = raw_to_detection(
        RawObjectDetection("mount", "horse", 0.85, 500, 300, 200, 180, "fake"),
        timestamp_ms=1000,
        frame_rate=60.0,
    )
    deduped = dedupe_detections([first, second, third])
    assert len(deduped) == 2
    assert deduped[0].confidence == 0.9


def test_build_object_analysis_result():
    engine = FakeObjectDetector()
    detections = [
        raw_to_detection(raw, timestamp_ms=index * 2500, frame_rate=60.0)
        for index, raw in enumerate(engine.detect_png(b""))
    ]
    result = build_object_analysis_result(
        analyzer_version="object-analyzer-v1.0",
        cache_key="object:test",
        duration_ms=5000,
        frame_rate=60.0,
        sample_interval_ms=2500,
        frames_sampled=2,
        detector=engine,
        detections=detections,
    )
    assert result.summary.detector_id == "fake"
    assert result.summary.by_category[ObjectCategory.CHARACTER.value] >= 1
    assert result.summary.by_category[ObjectCategory.MINIMAP.value] >= 1
    assert result.summary.by_category[ObjectCategory.HEALTH_BAR.value] >= 1
    assert result.summary.by_category[ObjectCategory.SPELL_EFFECT.value] >= 1


def test_object_analyzer_cache_key_includes_detector():
    analyzer = ObjectAnalyzer(object_detector=FakeObjectDetector())
    key = analyzer.cache_key("fp123", frame_rate=60.0)
    assert "detector=fake" in key
    assert "interval=2500" in key


@pytest.mark.asyncio
async def test_object_analyzer_runs_with_fake_detector(monkeypatch):
    analyzer = ObjectAnalyzer(object_detector=FakeObjectDetector())

    async def fake_probe(video, *, ctx=None):
        from montage_backend.models.domain.media import VideoProbeResult

        return VideoProbeResult(
            width=1920,
            height=1080,
            frame_rate=60.0,
            codec="h264",
            duration_ms=5000,
            frame_count=300,
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
        duration_ms=5000,
        frame_rate=60.0,
        frame_count=300,
    )
    assert output.module_id == "object"
    assert output.payload["summary"]["detection_count"] >= 4
    assert output.payload["summary"]["detector_id"] == "fake"


def test_default_registry_includes_object_module():
    registry = build_default_registry()
    assert "object" in registry.list_modules()
