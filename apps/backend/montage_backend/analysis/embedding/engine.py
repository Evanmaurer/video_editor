from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingEngine(ABC):
    """Replaceable semantic embedding backend (CLIP, histogram fallback, custom Albion models)."""

    model_id: str
    version: str
    dimensions: int

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when this engine can run on the current system."""

    @abstractmethod
    def embed_png(self, png_bytes: bytes) -> list[float]:
        """Embed a PNG frame into a normalized vector."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed text for semantic search queries."""


def resolve_embedding_engine(*, prefer_gpu: bool = False) -> EmbeddingEngine:
    from montage_backend.analysis.embedding.backends.clip_backend import ClipEmbeddingEngine
    from montage_backend.analysis.embedding.backends.histogram_backend import HistogramEmbeddingEngine

    clip_engine = ClipEmbeddingEngine(gpu=prefer_gpu)
    if clip_engine.is_available():
        return clip_engine
    return HistogramEmbeddingEngine()
