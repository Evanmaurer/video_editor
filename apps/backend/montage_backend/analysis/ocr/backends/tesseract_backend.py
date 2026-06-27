from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from montage_backend.analysis.ocr.engine import OcrEngine, RawOcrDetection


class TesseractOcrEngine(OcrEngine):
    engine_id = "tesseract"
    version = "5.x"

    def __init__(self, *, binary: str = "tesseract") -> None:
        self._binary = binary

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                [self._binary, "--version"],
                capture_output=True,
                check=False,
            )
            return result.returncode == 0
        except OSError:
            return False

    def recognize_png(self, png_bytes: bytes) -> list[RawOcrDetection]:
        if not png_bytes:
            return []

        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            handle.write(png_bytes)
            handle.flush()
            result = subprocess.run(
                [self._binary, handle.name, "stdout", "-l", "eng", "--psm", "11"],
                capture_output=True,
                check=False,
            )
        if result.returncode != 0:
            return []
        return self._parse_tesseract_output(result.stdout.decode("utf-8", errors="ignore"))

    @staticmethod
    def _parse_tesseract_output(text: str) -> list[RawOcrDetection]:
        detections: list[RawOcrDetection] = []
        for line in text.splitlines():
            cleaned = line.strip()
            if len(cleaned) < 2:
                continue
            detections.append(RawOcrDetection(text=cleaned, confidence=0.65))
        return detections
