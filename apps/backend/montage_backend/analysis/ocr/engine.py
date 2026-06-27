from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RawOcrDetection:
    text: str
    confidence: float
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


class OcrEngine(ABC):
    """Replaceable OCR backend (EasyOCR, Tesseract, future Albion models)."""

    engine_id: str
    version: str

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when this engine can run on the current system."""

    @abstractmethod
    def recognize_png(self, png_bytes: bytes) -> list[RawOcrDetection]:
        """Run OCR on a PNG image and return raw detections."""


class UnavailableOcrEngine(OcrEngine):
    engine_id = "unavailable"
    version = "0.0.0"

    def is_available(self) -> bool:
        return True

    def recognize_png(self, png_bytes: bytes) -> list[RawOcrDetection]:
        _ = png_bytes
        return []


def resolve_ocr_engine(*, prefer_gpu: bool = False) -> OcrEngine:
    from montage_backend.analysis.ocr.backends.easyocr_backend import EasyOcrEngine
    from montage_backend.analysis.ocr.backends.tesseract_backend import TesseractOcrEngine

    for factory in (
        lambda: EasyOcrEngine(gpu=prefer_gpu),
        TesseractOcrEngine,
    ):
        engine = factory()
        if engine.is_available():
            return engine
    return UnavailableOcrEngine()
