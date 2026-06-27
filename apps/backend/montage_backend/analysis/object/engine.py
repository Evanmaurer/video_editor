from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RawObjectDetection:
    category: str
    label: str
    confidence: float
    x: int
    y: int
    width: int
    height: int
    source_model: str


class ObjectDetector(ABC):
    """Replaceable object detection backend (YOLO, UI heuristics, future Albion models)."""

    detector_id: str
    version: str

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when this detector can run on the current system."""

    @abstractmethod
    def detect_png(self, png_bytes: bytes) -> list[RawObjectDetection]:
        """Run object detection on a PNG frame."""


class UnavailableObjectDetector(ObjectDetector):
    detector_id = "unavailable"
    version = "0.0.0"

    def is_available(self) -> bool:
        return True

    def detect_png(self, png_bytes: bytes) -> list[RawObjectDetection]:
        _ = png_bytes
        return []


class CompositeObjectDetector(ObjectDetector):
    detector_id = "composite"
    version = "1.0"

    def __init__(self, detectors: list[ObjectDetector]) -> None:
        self._detectors = [detector for detector in detectors if detector.is_available()]

    def is_available(self) -> bool:
        return bool(self._detectors)

    def detect_png(self, png_bytes: bytes) -> list[RawObjectDetection]:
        detections: list[RawObjectDetection] = []
        for detector in self._detectors:
            detections.extend(detector.detect_png(png_bytes))
        return detections


def resolve_object_detector(*, prefer_gpu: bool = False) -> ObjectDetector:
    from montage_backend.analysis.object.backends.ui_heuristic_backend import UiHeuristicObjectDetector
    from montage_backend.analysis.object.backends.yolo_backend import YoloObjectDetector

    detectors: list[ObjectDetector] = [
        YoloObjectDetector(gpu=prefer_gpu),
        UiHeuristicObjectDetector(),
    ]
    composite = CompositeObjectDetector(detectors)
    if composite.is_available():
        return composite
    return UnavailableObjectDetector()
