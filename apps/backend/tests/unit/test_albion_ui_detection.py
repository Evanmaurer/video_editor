from __future__ import annotations

import pytest

from montage_backend.analysis.albion.base import AlbionDetectorContext, AlbionDetectorId
from montage_backend.analysis.albion.detectors.ui_detector import AlbionUiDetector
from montage_backend.analysis.albion.runtime import build_default_albion_registry
from montage_backend.analysis.albion.ui.albion_ui_analysis import AlbionUiElementType
from montage_backend.analysis.albion.ui.engine import AlbionUiDetectionEngine, RawUiDetection
from montage_backend.analysis.albion.ui.pipeline import (
    build_window_cache_key,
    group_detections_into_windows,
    raw_to_albion_ui_detection,
    reclassify_m3_object_result,
)
from montage_backend.analysis.albion.ui.templates import get_template, list_template_ids, resolve_template
from montage_backend.analysis.object.engine import ObjectDetector
from montage_backend.analysis.object_analysis import (
    ObjectBoundingBox,
    ObjectCategory,
    ObjectDetection,
    build_object_analysis_result,
)


class FakeObjectDetectorForUi(ObjectDetector):
    detector_id = "ui_heuristic"
    version = "1.0"

    def is_available(self) -> bool:
        return True

    def detect_png(self, png_bytes: bytes) -> list:
        _ = png_bytes
        return []


class FakeUiEngine(AlbionUiDetectionEngine):
    engine_id = "fake"
    version = "test-1.0"

    def __init__(self, detections: list[RawUiDetection] | None = None) -> None:
        self._detections = detections or [
            RawUiDetection(
                element_type=AlbionUiElementType.PARTY_FRAME,
                label="party_frame",
                confidence=0.82,
                x=0,
                y=120,
                width=300,
                height=500,
                region_name="party_frame",
            ),
            RawUiDetection(
                element_type=AlbionUiElementType.MINIMAP,
                label="minimap",
                confidence=0.77,
                x=1500,
                y=780,
                width=400,
                height=280,
                region_name="minimap",
            ),
            RawUiDetection(
                element_type=AlbionUiElementType.HEALTH_BAR,
                label="health_bar",
                confidence=0.71,
                x=760,
                y=980,
                width=380,
                height=40,
                region_name="health_bar",
            ),
            RawUiDetection(
                element_type=AlbionUiElementType.KILL_FEED,
                label="kill_feed",
                confidence=0.69,
                x=1500,
                y=50,
                width=380,
                height=420,
                region_name="kill_feed",
            ),
        ]

    def is_available(self) -> bool:
        return True

    def detect_png(self, png_bytes: bytes, *, template) -> list[RawUiDetection]:
        _ = png_bytes, template
        return list(self._detections)


def test_builtin_templates_include_expected_presets():
    template_ids = list_template_ids()
    assert "albion_1080p_default" in template_ids
    assert "albion_1440p_default" in template_ids
    template = get_template("albion_1080p_default")
    assert template is not None
    assert "kill_feed" in template.regions
    assert template.regions["kill_feed"].element_type == AlbionUiElementType.KILL_FEED


def test_resolve_template_prefers_closest_resolution():
    template = resolve_template(frame_width=1920, frame_height=1080)
    assert template.id == "albion_1080p_default"
    template_1440 = resolve_template(frame_width=2560, frame_height=1440)
    assert template_1440.id == "albion_1440p_default"


def test_raw_to_albion_ui_detection_includes_bbox_and_template():
    detection = raw_to_albion_ui_detection(
        RawUiDetection(
            element_type=AlbionUiElementType.MINIMAP,
            label="minimap",
            confidence=0.8,
            x=10,
            y=20,
            width=100,
            height=80,
            region_name="minimap",
        ),
        timestamp_ms=2000,
        window_start_ms=2000,
        window_end_ms=4000,
        template_id="albion_1080p_default",
    )
    assert detection.element_type == AlbionUiElementType.MINIMAP
    assert detection.bbox.width == 100
    assert detection.template_id == "albion_1080p_default"
    assert detection.timestamp_ms == 2000


def test_frame_windows_have_per_window_cache_keys():
    detections = [
        raw_to_albion_ui_detection(
            RawUiDetection(
                element_type=AlbionUiElementType.HEALTH_BAR,
                label="health_bar",
                confidence=0.7,
                x=1,
                y=2,
                width=3,
                height=4,
                region_name="health_bar",
            ),
            timestamp_ms=0,
            window_start_ms=0,
            window_end_ms=2000,
            template_id="albion_1080p_default",
        ),
        raw_to_albion_ui_detection(
            RawUiDetection(
                element_type=AlbionUiElementType.ABILITY_BAR,
                label="ability_bar",
                confidence=0.66,
                x=5,
                y=6,
                width=7,
                height=8,
                region_name="ability_bar",
            ),
            timestamp_ms=2000,
            window_start_ms=2000,
            window_end_ms=4000,
            template_id="albion_1080p_default",
        ),
    ]
    windows = group_detections_into_windows(
        detections,
        timestamps=[0, 2000],
        window_ms=2000,
        source_fingerprint="fp-ui",
        template_id="albion_1080p_default",
        engine_id="fake",
        engine_version="test-1.0",
    )
    assert len(windows) == 2
    assert windows[0].cache_key != windows[1].cache_key
    assert windows[0].detection_count == 1
    assert build_window_cache_key(
        source_fingerprint="fp-ui",
        template_id="albion_1080p_default",
        window_start_ms=0,
        window_end_ms=2000,
        engine_id="fake",
        engine_version="test-1.0",
    ) in windows[0].cache_key


def test_reclassify_m3_object_result_builds_albion_ui_windows():
    detector = FakeObjectDetectorForUi()
    m3 = build_object_analysis_result(
        analyzer_version="object-analyzer-v1.0",
        cache_key="object:m3-test",
        duration_ms=4000,
        frame_rate=60.0,
        sample_interval_ms=2000,
        frames_sampled=2,
        detector=detector,
        detections=[
            ObjectDetection(
                category=ObjectCategory.PARTY_FRAME,
                label="party_frame_stack",
                timestamp_ms=0,
                frame=0,
                confidence=0.8,
                bbox=ObjectBoundingBox(x=0, y=120, width=300, height=500),
                source_model="ui_heuristic",
            ),
            ObjectDetection(
                category=ObjectCategory.MINIMAP,
                label="minimap_region",
                timestamp_ms=2000,
                frame=120,
                confidence=0.75,
                bbox=ObjectBoundingBox(x=1500, y=780, width=400, height=280),
                source_model="ui_heuristic",
            ),
            ObjectDetection(
                category=ObjectCategory.HEALTH_BAR,
                label="health_bar",
                timestamp_ms=2000,
                frame=120,
                confidence=0.7,
                bbox=ObjectBoundingBox(x=760, y=980, width=380, height=40),
                source_model="ui_heuristic",
            ),
        ],
    )
    result = reclassify_m3_object_result(
        m3,
        source_fingerprint="fp-ui",
        template_id="albion_1080p_default",
        window_ms=2000,
        sample_interval_ms=2000,
    )
    assert result.summary.reused_m3_object is True
    assert result.summary.detection_count == 3
    assert result.summary.by_element["party_frame"] == 1
    assert result.summary.by_element["minimap"] == 1
    assert result.summary.by_element["health_bar"] == 1
    assert len(result.frame_windows) == 2
    assert all(detection.bbox.width > 0 for detection in result.detections)


@pytest.mark.asyncio
async def test_albion_ui_detector_reuses_m3_object_cache():
    detector_engine = FakeObjectDetectorForUi()
    m3 = build_object_analysis_result(
        analyzer_version="object-analyzer-v1.0",
        cache_key="object:m3-test",
        duration_ms=4000,
        frame_rate=60.0,
        sample_interval_ms=2000,
        frames_sampled=2,
        detector=detector_engine,
        detections=[
            ObjectDetection(
                category=ObjectCategory.PARTY_FRAME,
                label="party_frame_stack",
                timestamp_ms=0,
                frame=0,
                confidence=0.8,
                bbox=ObjectBoundingBox(x=0, y=120, width=300, height=500),
                source_model="ui_heuristic",
            ),
        ],
    )
    detector = AlbionUiDetector(ui_engine=FakeUiEngine())
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-ui-detector",
        extras={"object_analysis": m3.model_dump(mode="json")},
    )
    output = await detector.analyze(
        ctx,
        video_path="/tmp/fake.mp4",
        duration_ms=4000,
        frame_rate=60.0,
    )
    assert output.detector_id == AlbionDetectorId.UI.value
    payload = output.payload
    assert payload["summary"]["reused_m3_object"] is True
    assert payload["summary"]["detection_count"] >= 1
    assert payload["detections"][0]["bbox"]["width"] > 0


def test_default_albion_registry_includes_ui_detector():
    registry = build_default_albion_registry()
    assert registry.list_detectors() == ["framework_probe", "ui", "ocr", "ability", "combat"]
    assert registry.detector_versions()["ui"] == "albion-ui-v1.0"
