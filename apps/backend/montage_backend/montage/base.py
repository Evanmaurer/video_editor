from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from montage_backend.models.domain.montage_plan import MontagePlan, MontagePlanClip


class MontageModuleId(str, Enum):
    SCORING = "scoring"
    HIGHLIGHTS = "highlights"
    MUSIC_SYNC = "music_sync"
    TRANSITIONS = "transitions"
    PACING = "pacing"
    EFFECTS = "effects"
    DRAFT = "draft"
    FEEDBACK = "feedback"


class MontageModuleProgress(BaseModel):
    module_id: str
    progress: float = Field(ge=0.0, le=1.0)
    message: str = ""


@dataclass
class MontagePlanContext:
    """Runtime context for montage planning modules."""

    project_id: str
    plan_id: str
    random_seed: int
    target_duration_ms: int | None = None
    pacing_profile: str | None = None
    cancel_requested: bool = False
    extras: dict[str, Any] = field(default_factory=dict)
    _progress: MontageModuleProgress | None = field(default=None, repr=False)
    _on_progress: Any = field(default=None, repr=False)

    def check_cancelled(self) -> None:
        from montage_backend.models.domain.montage_plan import MontagePlanCancelledError

        if self.cancel_requested:
            raise MontagePlanCancelledError("Montage planning was cancelled")

    def cancel(self) -> None:
        self.cancel_requested = True

    def bind_progress(self, callback: Any) -> None:
        self._on_progress = callback

    async def report(self, progress: float, message: str) -> None:
        self._progress = MontageModuleProgress(
            module_id="",
            progress=min(max(progress, 0.0), 1.0),
            message=message,
        )
        if self._on_progress is not None:
            await self._on_progress(self._progress)


class MontagePlanState(BaseModel):
    """Mutable planning state passed between modules."""

    clips: list[MontagePlanClip] = Field(default_factory=list)
    module_cache: dict[str, dict[str, Any]] = Field(default_factory=dict)
    overall_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    overall_reasoning: str = ""


class MontageModuleOutput(BaseModel):
    module_id: str
    module_version: str
    cache_key: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class MontagePlannerModule(ABC):
    """Replaceable montage planning module (scoring, pacing, transitions, etc.)."""

    module_id: MontageModuleId
    version: str

    @abstractmethod
    def cache_key(self, random_seed: int, **params: Any) -> str:
        """Stable cache key including module version and seed."""

    @abstractmethod
    async def plan(
        self,
        ctx: MontagePlanContext,
        state: MontagePlanState,
    ) -> MontageModuleOutput:
        """Run planning step and return structured output for caching."""

    async def cancel(self, ctx: MontagePlanContext) -> None:
        ctx.cancel_requested = True

    def is_cache_valid(
        self,
        cached_version: str,
        cached_key: str,
        random_seed: int,
        **params: Any,
    ) -> bool:
        expected = self.cache_key(random_seed, **params)
        return cached_version == self.version and cached_key == expected
