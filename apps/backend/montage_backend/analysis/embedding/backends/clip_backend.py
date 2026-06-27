from __future__ import annotations

import hashlib
import io
import math

from montage_backend.analysis.embedding.engine import EmbeddingEngine

_model = None


class ClipEmbeddingEngine(EmbeddingEngine):
    model_id = "clip-ViT-B-32"
    version = "2.2"
    dimensions = 512

    def __init__(self, *, gpu: bool = False, model_name: str = "clip-ViT-B-32") -> None:
        self._gpu = gpu
        self._model_name = model_name

    def is_available(self) -> bool:
        try:
            import sentence_transformers  # noqa: F401

            return True
        except ImportError:
            return False

    def embed_png(self, png_bytes: bytes) -> list[float]:
        if not png_bytes:
            return [0.0] * self.dimensions

        from PIL import Image

        model = self._get_model()
        image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        vector = model.encode(image, convert_to_numpy=True, show_progress_bar=False)
        return normalize_vector([float(value) for value in vector.tolist()])

    def embed_text(self, text: str) -> list[float]:
        model = self._get_model()
        vector = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return normalize_vector([float(value) for value in vector.tolist()])

    def _get_model(self):
        global _model
        if _model is None:
            from sentence_transformers import SentenceTransformer

            device = "cuda" if self._gpu else "cpu"
            _model = SentenceTransformer(self._model_name, device=device)
        return _model


def normalize_vector(values: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude <= 0:
        return values
    return [round(value / magnitude, 6) for value in values]
