from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field

from montage_backend.models.domain.media import ProcessingStatus


ALBION_FRAMEWORK_VERSION = "albion-framework-v1.0"


class AlbionDetectorId(str, Enum):
    FRAMEWORK_PROBE = "framework_probe"
    UI = "ui"
    OCR = "ocr"
    ABILITY = "ability"
    COMBAT = "combat"


class AlbionDetectorProgress(BaseModel):
    detector_id: str
    progress: float = Field(ge=0.0, le=1.0)
    message: str = ""
    status: ProcessingStatus = ProcessingStatus.PROCESSING


class AlbionDetectorEvent(BaseModel):
    event_type: str
    timestamp_ms: int
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlbionDetectorOutput(BaseModel):
    detector_id: str
    detector_version: str
    cache_key: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    events: list[AlbionDetectorEvent] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass
class AlbionDetectorContext:
    """Runtime context passed to every Albion detector invocation."""

    project_id: str
    media_id: str
    source_fingerprint: str
    gpu_enabled: bool = True
    cancel_requested: bool = False
    extras: dict[str, Any] = field(default_factory=dict)
    _progress: AlbionDetectorProgress | None = field(default=None, repr=False)
    _on_progress: Callable[[AlbionDetectorProgress], Awaitable[None] | None] | None = field(
        default=None,
        repr=False,
    )

    def check_cancelled(self) -> None:
        from montage_backend.models.domain.analysis import AnalysisCancelledError

        if self.cancel_requested:
            raise AnalysisCancelledError("Albion analysis was cancelled")

    async def cancel(self) -> None:
        self.cancel_requested = True

    async def report(self, progress: float, message: str) -> None:
        self._progress = AlbionDetectorProgress(
            detector_id="",
            progress=min(max(progress, 0.0), 1.0),
            message=message,
            status=ProcessingStatus.PROCESSING,
        )
        if self._on_progress is not None:
            result = self._on_progress(self._progress)
            if result is not None:
                await result

    def bind_progress(
        self,
        callback: Callable[[AlbionDetectorProgress], Awaitable[None] | None],
    ) -> None:
        self._on_progress = callback

    @property
    def progress(self) -> AlbionDetectorProgress | None:
        return self._progress


class AlbionDetector(ABC):
    """Replaceable Albion-specific detector plugin interface."""

    detector_id: AlbionDetectorId
    version: str

    async def initialize(self, ctx: AlbionDetectorContext) -> None:
        """Prepare detector resources. Override for GPU/model warm-up."""

    @abstractmethod
    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        """Stable cache key including detector version and source fingerprint."""

    @abstractmethod
    async def analyze(
        self,
        ctx: AlbionDetectorContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
    ) -> AlbionDetectorOutput:
        """Run detector analysis and return standardized output."""

    async def cancel(self, ctx: AlbionDetectorContext) -> None:
        await ctx.cancel()

    def is_cache_valid(
        self,
        cached_version: str,
        cached_key: str,
        source_fingerprint: str,
        *,
        frame_rate: float | None = None,
    ) -> bool:
        expected = self.cache_key(source_fingerprint, frame_rate=frame_rate)
        return cached_version == self.version and cached_key == expected
