from __future__ import annotations

from montage_backend.analysis.albion.base import AlbionDetector, AlbionDetectorId
from montage_backend.models.domain import MontageError


class AlbionDetectorNotFoundError(MontageError):
    code = "ALBION_DETECTOR_NOT_FOUND"


class AlbionDetectorRegistry:
    """Hot-swappable registry for Albion-specific detector plugins."""

    def __init__(self) -> None:
        self._detectors: dict[str, AlbionDetector] = {}

    def register(self, detector: AlbionDetector) -> None:
        self._detectors[detector.detector_id.value] = detector

    def replace(self, detector: AlbionDetector) -> None:
        """Replace an existing detector implementation without restarting the service."""
        self.register(detector)

    def unregister(self, detector_id: AlbionDetectorId | str) -> None:
        key = detector_id.value if isinstance(detector_id, AlbionDetectorId) else detector_id
        self._detectors.pop(key, None)

    def get(self, detector_id: AlbionDetectorId | str) -> AlbionDetector:
        key = detector_id.value if isinstance(detector_id, AlbionDetectorId) else detector_id
        detector = self._detectors.get(key)
        if detector is None:
            raise AlbionDetectorNotFoundError(f"Albion detector not registered: {key}")
        return detector

    def list_detectors(self) -> list[str]:
        return list(self._detectors.keys())

    def detector_versions(self) -> dict[str, str]:
        return {detector_id: self._detectors[detector_id].version for detector_id in self.list_detectors()}
