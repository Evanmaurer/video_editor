from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

ALBION_ABILITY_DETECTOR_VERSION = "albion-ability-v1.0"
DEFAULT_WINDOW_MS = 2000


class AlbionAbilityEventType(str, Enum):
    ACTIVATION = "activation"
    COOLDOWN_START = "cooldown_start"
    COOLDOWN_READY = "cooldown_ready"
    ULTIMATE_ACTIVATION = "ultimate_activation"


class AlbionAbilityEvent(BaseModel):
    ability_id: str
    ability_name: str
    event_type: AlbionAbilityEventType
    timestamp_ms: int
    window_start_ms: int
    window_end_ms: int
    confidence: float = Field(ge=0.0, le=1.0)
    is_ultimate: bool = False
    cooldown_ms: int | None = None
    metadata: dict = Field(default_factory=dict)


class AlbionAbilityFrameWindow(BaseModel):
    window_start_ms: int
    window_end_ms: int
    cache_key: str
    catalog_id: str
    event_count: int = 0
    events: list[AlbionAbilityEvent] = Field(default_factory=list)


class AlbionAbilitySummary(BaseModel):
    frames_sampled: int
    window_count: int
    mention_count: int
    activation_count: int
    ultimate_count: int
    cooldown_event_count: int
    unique_ability_count: int
    catalog_id: str
    by_ability: dict[str, int] = Field(default_factory=dict)
    by_event_type: dict[str, int] = Field(default_factory=dict)
    reused_albion_ocr: bool = False


class AlbionAbilityAnalysisResult(BaseModel):
    detector_version: str = ALBION_ABILITY_DETECTOR_VERSION
    cache_key: str
    duration_ms: int
    frame_rate: float
    window_ms: int
    sample_interval_ms: int
    catalog_id: str
    summary: AlbionAbilitySummary
    frame_windows: list[AlbionAbilityFrameWindow] = Field(default_factory=list)
    events: list[AlbionAbilityEvent] = Field(default_factory=list)
    unique_abilities: list[str] = Field(default_factory=list)
