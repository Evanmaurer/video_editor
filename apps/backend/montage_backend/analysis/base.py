from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from montage_backend.models.domain.media import ProcessingStatus


class AnalysisModuleId(str, Enum):
    SCENE = "scene"
    MOTION = "motion"
    AUDIO = "audio"
    OCR = "ocr"
    OBJECT = "object"
    EMBEDDING = "embedding"


class AnalysisProgress(BaseModel):
    module_id: str
    progress: float = Field(ge=0.0, le=1.0)
    message: str = ""
    status: ProcessingStatus = ProcessingStatus.PROCESSING


class AnalysisOutput(BaseModel):
    module_id: str
    analyzer_version: str
    cache_key: str
    payload: dict[str, Any]
    confidence: float | None = None
    reasoning: str | None = None


@dataclass
class AnalysisRunContext:
    """Runtime context passed to every analyzer invocation."""

    project_id: str
    media_id: str
    source_fingerprint: str
    gpu_enabled: bool = True
    cancel_requested: bool = False
    pause_requested: bool = False
    extras: dict[str, Any] = field(default_factory=dict)
    _progress: AnalysisProgress | None = field(default=None, repr=False)

    def check_cancelled(self) -> None:
        from montage_backend.models.domain.analysis import AnalysisCancelledError, AnalysisPausedError

        if self.cancel_requested:
            raise AnalysisCancelledError("Analysis was cancelled")
        if self.pause_requested:
            raise AnalysisPausedError("Analysis was paused")

    def cancel(self) -> None:
        self.cancel_requested = True

    def pause(self) -> None:
        self.pause_requested = True

    async def report(self, progress: float, message: str) -> None:
        self._progress = AnalysisProgress(
            module_id="",
            progress=min(max(progress, 0.0), 1.0),
            message=message,
            status=ProcessingStatus.PROCESSING,
        )
        if self._on_progress is not None:
            await self._on_progress(self._progress)

    _on_progress: Any = field(default=None, repr=False)

    def bind_progress(self, callback: Any) -> None:
        self._on_progress = callback

    @property
    def progress(self) -> AnalysisProgress | None:
        return self._progress


class Analyzer(ABC):
    """Plugin interface for replaceable AI analysis modules."""

    module_id: AnalysisModuleId
    version: str

    @abstractmethod
    def cache_key(self, source_fingerprint: str, *, frame_rate: float | None = None) -> str:
        """Stable cache key including analyzer version and source fingerprint."""

    @abstractmethod
    async def analyze(
        self,
        ctx: AnalysisRunContext,
        *,
        video_path: str,
        duration_ms: int | None,
        frame_rate: float | None,
        frame_count: int | None,
    ) -> AnalysisOutput:
        """Run analysis and return standardized output payload."""

    async def cancel(self, ctx: AnalysisRunContext) -> None:
        ctx.cancel_requested = True

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
