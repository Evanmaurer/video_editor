from __future__ import annotations

import hashlib
import io
import math

from montage_backend.analysis.embedding.engine import EmbeddingEngine


class HistogramEmbeddingEngine(EmbeddingEngine):
    """Deterministic image histogram embedding when CLIP is unavailable."""

    model_id = "histogram-v1"
    version = "1.0"
    dimensions = 512

    def is_available(self) -> bool:
        return True

    def embed_png(self, png_bytes: bytes) -> list[float]:
        vector = self._histogram_from_png(png_bytes)
        if not vector:
            vector = self._hash_embedding(png_bytes, self.dimensions)
        return normalize_vector(vector)

    def embed_text(self, text: str) -> list[float]:
        cleaned = " ".join(text.strip().lower().split())
        return normalize_vector(self._hash_embedding(cleaned.encode("utf-8"), self.dimensions))

    def _histogram_from_png(self, png_bytes: bytes) -> list[float]:
        try:
            from PIL import Image
        except ImportError:
            return []

        try:
            image = Image.open(io.BytesIO(png_bytes)).convert("RGB").resize((64, 64))
        except Exception:
            return []

        bins = 16
        counts = [0.0] * (bins * 3)
        pixels = list(image.getdata())
        if not pixels:
            return []

        for red, green, blue in pixels:
            counts[red * bins // 256] += 1.0
            counts[bins + green * bins // 256] += 1.0
            counts[(2 * bins) + blue * bins // 256] += 1.0

        total = float(len(pixels))
        histogram = [value / total for value in counts]
        return expand_vector(histogram, self.dimensions)

    def _hash_embedding(self, payload: bytes, dimensions: int) -> list[float]:
        seed = hashlib.sha256(payload).digest()
        values: list[float] = []
        counter = 0
        while len(values) < dimensions:
            block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            for index in range(0, len(block), 4):
                chunk = block[index : index + 4]
                if len(chunk) < 4:
                    continue
                integer = int.from_bytes(chunk, "big", signed=False)
                values.append((integer / 2**32) * 2.0 - 1.0)
                if len(values) >= dimensions:
                    break
            counter += 1
        return values[:dimensions]


def normalize_vector(values: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude <= 0:
        return values
    return [round(value / magnitude, 6) for value in values]


def expand_vector(values: list[float], dimensions: int) -> list[float]:
    if not values:
        return [0.0] * dimensions
    if len(values) >= dimensions:
        return values[:dimensions]
    expanded = list(values)
    index = 0
    while len(expanded) < dimensions:
        expanded.append(values[index % len(values)] * 0.97)
        index += 1
    return expanded
