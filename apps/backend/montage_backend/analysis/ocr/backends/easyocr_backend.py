from __future__ import annotations

from montage_backend.analysis.ocr.engine import OcrEngine, RawOcrDetection

_reader = None


class EasyOcrEngine(OcrEngine):
    engine_id = "easyocr"
    version = "1.7"

    def __init__(self, *, gpu: bool = False, languages: list[str] | None = None) -> None:
        self._gpu = gpu
        self._languages = languages or ["en"]

    def is_available(self) -> bool:
        try:
            import easyocr  # noqa: F401
            import numpy  # noqa: F401

            return True
        except ImportError:
            return False

    def recognize_png(self, png_bytes: bytes) -> list[RawOcrDetection]:
        if not png_bytes:
            return []

        import cv2
        import numpy as np

        reader = self._get_reader()
        array = np.frombuffer(png_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return []

        results = reader.readtext(image)
        detections: list[RawOcrDetection] = []
        for bbox, text, confidence in results:
            cleaned = str(text).strip()
            if len(cleaned) < 2:
                continue
            xs = [int(point[0]) for point in bbox]
            ys = [int(point[1]) for point in bbox]
            x = min(xs)
            y = min(ys)
            width = max(max(xs) - x, 1)
            height = max(max(ys) - y, 1)
            detections.append(
                RawOcrDetection(
                    text=cleaned,
                    confidence=float(confidence),
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                ),
            )
        return detections

    def _get_reader(self):
        global _reader
        if _reader is None:
            import easyocr

            _reader = easyocr.Reader(self._languages, gpu=self._gpu)
        return _reader
