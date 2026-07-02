from __future__ import annotations

import pytest

from montage_backend.analysis.albion.albion_analysis import AlbionAnalysisResult, build_albion_analysis_result
from montage_backend.analysis.albion.base import (
    ALBION_FRAMEWORK_VERSION,
    AlbionDetectorContext,
    AlbionDetectorEvent,
    AlbionDetectorId,
    AlbionDetectorOutput,
)
from montage_backend.analysis.albion.detectors.framework_probe import FrameworkProbeDetector
from montage_backend.analysis.albion.registry import AlbionDetectorNotFoundError, AlbionDetectorRegistry
from montage_backend.analysis.albion.runtime import AlbionAnalysisEngine, build_default_albion_registry
from montage_backend.analysis.base import AnalysisModuleId
from montage_backend.analysis.modules.albion import AlbionAnalyzer
from montage_backend.analysis.registry import AnalyzerRegistry
from montage_backend.models.domain.analysis import AnalysisCancelledError
from montage_backend.analysis.object.engine import ObjectDetector
from montage_backend.analysis.object_analysis import (
    ObjectBoundingBox,
    ObjectCategory,
    ObjectDetection,
    build_object_analysis_result,
)
from montage_backend.analysis.ocr.engine import OcrEngine, RawOcrDetection
from montage_backend.analysis.ocr_analysis import build_ocr_analysis_result
from montage_backend.services.analysis_service import build_default_registry


def _build_m3_object_for_framework() -> dict:
    class _Detector(ObjectDetector):
        detector_id = "ui_heuristic"
        version = "1.0"

        def is_available(self) -> bool:
            return True

        def detect_png(self, png_bytes: bytes) -> list:
            _ = png_bytes
            return []

    m3 = build_object_analysis_result(
        analyzer_version="object-analyzer-v1.0",
        cache_key="object:framework-test",
        duration_ms=3000,
        frame_rate=30.0,
        sample_interval_ms=1500,
        frames_sampled=2,
        detector=_Detector(),
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
    return m3.model_dump(mode="json")


class FakeOcrEngineForFramework(OcrEngine):
    engine_id = "fake"
    version = "test-1.0"

    def is_available(self) -> bool:
        return True

    def recognize_png(self, png_bytes: bytes) -> list[RawOcrDetection]:
        _ = png_bytes
        return [RawOcrDetection(text="842k", confidence=0.9)]


@pytest.mark.asyncio
async def test_albion_detector_registry_register_and_hot_swap():
    registry = AlbionDetectorRegistry()
    probe = FrameworkProbeDetector()
    registry.register(probe)
    assert registry.get(AlbionDetectorId.FRAMEWORK_PROBE) is probe
    assert registry.list_detectors() == ["framework_probe"]

    replacement = FrameworkProbeDetector()
    replacement.version = "framework-probe-v1.1"
    registry.replace(replacement)
    assert registry.get(AlbionDetectorId.FRAMEWORK_PROBE).version == "framework-probe-v1.1"


def test_albion_detector_registry_missing_detector():
    registry = AlbionDetectorRegistry()
    with pytest.raises(AlbionDetectorNotFoundError):
        registry.get("missing")


def test_albion_detector_cache_key_is_stable():
    detector = FrameworkProbeDetector()
    key_a = detector.cache_key("fp-1", frame_rate=60.0)
    key_b = detector.cache_key("fp-1", frame_rate=60.0)
    key_c = detector.cache_key("fp-2", frame_rate=60.0)
    assert key_a == key_b
    assert key_a != key_c
    assert detector.is_cache_valid(detector.version, key_a, "fp-1", frame_rate=60.0)


@pytest.mark.asyncio
async def test_framework_probe_detector_lifecycle():
    detector = FrameworkProbeDetector()
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-1",
        gpu_enabled=True,
    )
    progress_messages: list[str] = []

    async def on_progress(progress) -> None:
        progress_messages.append(progress.message)

    ctx.bind_progress(on_progress)
    await detector.initialize(ctx)
    output = await detector.analyze(
        ctx,
        video_path="/tmp/fake.mp4",
        duration_ms=5000,
        frame_rate=60.0,
    )
    assert output.detector_id == "framework_probe"
    assert output.confidence == 1.0
    assert len(output.events) == 1
    assert output.events[0].event_type == "framework_probe"
    assert any("initialized" in message.lower() for message in progress_messages)


@pytest.mark.asyncio
async def test_albion_detector_context_cancel():
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp",
    )
    await ctx.cancel()
    with pytest.raises(AnalysisCancelledError):
        ctx.check_cancelled()


@pytest.mark.asyncio
async def test_albion_analysis_engine_runs_registered_detectors():
    from montage_backend.analysis.ocr_analysis import raw_to_detection

    engine = FakeOcrEngineForFramework()
    m3 = build_ocr_analysis_result(
        analyzer_version="ocr-analyzer-v1.0",
        cache_key="ocr:engine-test",
        duration_ms=3000,
        frame_rate=30.0,
        sample_interval_ms=1500,
        frames_sampled=2,
        engine=engine,
        detections=[
            raw_to_detection(raw, timestamp_ms=0, frame_rate=30.0)
            for raw in engine.recognize_png(b"")
        ],
    )
    registry = build_default_albion_registry()
    analysis_engine = AlbionAnalysisEngine(registry)
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-engine",
        gpu_enabled=False,
        extras={"ocr_analysis": m3.model_dump(mode="json"), "object_analysis": _build_m3_object_for_framework()},
    )

    result = await analysis_engine.analyze(
        ctx,
        video_path="/tmp/fake.mp4",
        duration_ms=8000,
        frame_rate=30.0,
    )
    assert isinstance(result, AlbionAnalysisResult)
    assert result.analyzer_version == ALBION_FRAMEWORK_VERSION
    assert result.summary.detector_count == 3
    assert result.summary.event_count >= 1
    assert "framework_probe" in result.detector_results
    assert "ui" in result.detector_results
    assert "ocr" in result.detector_results
    assert analysis_engine.is_cache_valid(
        ALBION_FRAMEWORK_VERSION,
        result.cache_key,
        "fp-engine",
        frame_rate=30.0,
    )


@pytest.mark.asyncio
async def test_albion_analysis_engine_reuses_valid_detector_cache():
    registry = AlbionDetectorRegistry()
    registry.register(FrameworkProbeDetector())
    engine = AlbionAnalysisEngine(registry)
    detector = registry.get(AlbionDetectorId.FRAMEWORK_PROBE)
    cache_key = detector.cache_key("fp-cache", frame_rate=60.0)
    cached_output = AlbionDetectorOutput(
        detector_id=detector.detector_id.value,
        detector_version=detector.version,
        cache_key=cache_key,
        confidence=1.0,
        reasoning="cached",
        events=[
            AlbionDetectorEvent(
                event_type="framework_probe",
                timestamp_ms=0,
                confidence=1.0,
                reasoning="cached event",
            ),
        ],
    )
    ctx = AlbionDetectorContext(
        project_id="p1",
        media_id="m1",
        source_fingerprint="fp-cache",
        gpu_enabled=True,
        extras={
            "detector_caches": {
                "framework_probe": {
                    "detector_version": detector.version,
                    "cache_key": cache_key,
                },
            },
            "detector_results": {
                "framework_probe": cached_output.model_dump(mode="json"),
            },
        },
    )

    result = await engine.analyze(
        ctx,
        video_path="/tmp/fake.mp4",
        duration_ms=1000,
        frame_rate=60.0,
    )
    assert result.detector_results["framework_probe"].reasoning == "cached"


def test_build_albion_analysis_result_tracks_detector_caches():
    output = AlbionDetectorOutput(
        detector_id="framework_probe",
        detector_version="framework-probe-v1.0",
        cache_key="probe:key",
        confidence=0.9,
        reasoning="ok",
        events=[],
    )
    result = build_albion_analysis_result(
        cache_key="composite",
        duration_ms=1000,
        frame_rate=60.0,
        detector_results={"framework_probe": output},
        gpu_enabled=True,
    )
    assert result.detector_caches["framework_probe"].cache_key == "probe:key"


def test_analysis_registry_includes_albion_module():
    registry = build_default_registry()
    assert "albion" in registry.list_modules()
    analyzer = registry.get(AnalysisModuleId.ALBION)
    assert analyzer.version == ALBION_FRAMEWORK_VERSION


def test_albion_analyzer_cache_key_includes_detector_versions():
    analyzer = AlbionAnalyzer()
    key = analyzer.cache_key("fp-1", frame_rate=60.0)
    assert key.startswith(ALBION_FRAMEWORK_VERSION)
    assert "framework_probe" in key
    assert "ui" in key
    assert "ocr" in key


def test_default_albion_registry_lists_framework_probe():
    registry = build_default_albion_registry()
    assert registry.list_detectors() == ["framework_probe", "ocr", "ui"]
    assert registry.detector_versions()["framework_probe"] == "framework-probe-v1.0"
    assert registry.detector_versions()["ui"] == "albion-ui-v1.0"
    assert registry.detector_versions()["ocr"] == "albion-ocr-v1.0"
