from __future__ import annotations

import pytest

from montage_backend.analysis.embedding.backends.histogram_backend import (
    HistogramEmbeddingEngine,
    normalize_vector,
)
from montage_backend.analysis.embedding.engine import EmbeddingEngine
from montage_backend.analysis.embedding_analysis import (
    EmbeddingScopeType,
    build_embedding_analysis_result,
    build_embedding_records,
    cache_payload_from_result,
    cosine_similarity,
    keyframe_timestamps,
    scene_segment_refs,
)
from montage_backend.analysis.modules.embedding import EmbeddingAnalyzer
from montage_backend.services.analysis_service import build_default_registry


class FakeEmbeddingEngine(EmbeddingEngine):
    model_id = "fake-embed"
    version = "test-1.0"
    dimensions = 8

    def is_available(self) -> bool:
        return True

    def embed_png(self, png_bytes: bytes) -> list[float]:
        seed = sum(png_bytes[:32]) if png_bytes else 0
        values = [((seed + index) % 7) / 7.0 for index in range(self.dimensions)]
        return normalize_vector(values)

    def embed_text(self, text: str) -> list[float]:
        seed = sum(text.encode("utf-8"))
        values = [((seed + index) % 11) / 11.0 for index in range(self.dimensions)]
        return normalize_vector(values)


def test_cosine_similarity_identical_vectors():
    vector = [1.0, 0.0, 0.0]
    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_scene_segment_refs_fallback():
    refs = scene_segment_refs(None, 8000)
    assert len(refs) >= 2
    assert refs[0].start_ms == 0


def test_build_embedding_records_and_cache_payload():
    engine = FakeEmbeddingEngine()
    segments = scene_segment_refs([{"start_ms": 0, "end_ms": 2000}], 5000)
    records = build_embedding_records(
        media_id="media-1",
        engine=engine,
        clip_vector=engine.embed_text("clip"),
        scene_vectors=[(segments[0], engine.embed_text("scene"))],
        keyframe_vectors=[(0, engine.embed_text("kf0")), (3000, engine.embed_text("kf1"))],
    )
    result = build_embedding_analysis_result(
        analyzer_version="embedding-analyzer-v1.0",
        cache_key="embedding:test",
        duration_ms=5000,
        frame_rate=60.0,
        engine=engine,
        records=records,
    )
    assert result.summary.total_embeddings == 4
    cached = cache_payload_from_result(result)
    assert "embeddings" not in cached
    assert len(cached["embedding_ids"]) == 4


def test_keyframe_timestamps_respect_max():
    timestamps = keyframe_timestamps(30_000, interval_ms=3000, max_frames=5)
    assert len(timestamps) == 5


def test_histogram_engine_normalizes():
    engine = HistogramEmbeddingEngine()
    vector = engine.embed_png(b"\x89PNG fake")
    assert len(vector) == engine.dimensions
    magnitude = sum(value * value for value in vector) ** 0.5
    assert magnitude == pytest.approx(1.0, rel=0.01)


@pytest.mark.asyncio
async def test_embedding_analyzer_with_fake_engine(monkeypatch):
    analyzer = EmbeddingAnalyzer(embedding_engine=FakeEmbeddingEngine())

    async def fake_probe(video, *, ctx=None):
        from montage_backend.models.domain.media import VideoProbeResult

        return VideoProbeResult(
            width=1920,
            height=1080,
            frame_rate=60.0,
            codec="h264",
            duration_ms=6000,
            frame_count=360,
            file_size_bytes=1000,
        )

    async def fake_export_png_frame(video, timestamp_s, *, ctx):
        _ = video, timestamp_s, ctx
        return b"png-bytes"

    monkeypatch.setattr(analyzer._processor, "probe", fake_probe)
    monkeypatch.setattr(analyzer, "_export_png_frame", fake_export_png_frame)

    from montage_backend.analysis.base import AnalysisRunContext

    ctx = AnalysisRunContext(
        project_id="p1",
        media_id="media-1",
        source_fingerprint="fp",
        extras={"scene_segments": [{"start_ms": 0, "end_ms": 3000}]},
    )
    output = await analyzer.analyze(
        ctx,
        video_path="/tmp/video.mp4",
        duration_ms=6000,
        frame_rate=60.0,
        frame_count=360,
    )
    assert output.module_id == "embedding"
    assert output.payload["summary"]["scene_count"] >= 1
    assert output.payload["summary"]["keyframe_count"] >= 1


def test_default_registry_includes_embedding_module():
    registry = build_default_registry()
    assert "embedding" in registry.list_modules()
