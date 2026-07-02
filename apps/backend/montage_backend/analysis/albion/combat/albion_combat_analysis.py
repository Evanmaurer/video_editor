from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

ALBION_COMBAT_DETECTOR_VERSION = "albion-combat-v1.0"
DEFAULT_WINDOW_MS = 2000


class AlbionCombatEventType(str, Enum):
    FIGHT_START = "fight_start"
    FIGHT_END = "fight_end"
    KILL = "kill"
    DEATH = "death"
    RETREAT = "retreat"


class AlbionCombatTimelineEntry(BaseModel):
    entry_id: str
    event_type: AlbionCombatEventType
    timestamp_ms: int
    window_start_ms: int
    window_end_ms: int
    confidence: float = Field(ge=0.0, le=1.0)
    label: str
    search_text: str
    metadata: dict = Field(default_factory=dict)


class AlbionCombatFrameWindow(BaseModel):
    window_start_ms: int
    window_end_ms: int
    cache_key: str
    config_id: str
    activity_score: float = Field(ge=0.0, le=1.0)
    entry_count: int = 0
    entries: list[AlbionCombatTimelineEntry] = Field(default_factory=list)


class AlbionCombatSummary(BaseModel):
    frames_sampled: int
    window_count: int
    entry_count: int
    fight_count: int
    kill_count: int
    death_count: int
    retreat_count: int
    config_id: str
    by_event_type: dict[str, int] = Field(default_factory=dict)
    reused_albion_ocr: bool = False
    reused_albion_ability: bool = False
    reused_albion_ui: bool = False
    reused_motion: bool = False


class AlbionCombatAnalysisResult(BaseModel):
    detector_version: str = ALBION_COMBAT_DETECTOR_VERSION
    cache_key: str
    duration_ms: int
    frame_rate: float
    window_ms: int
    sample_interval_ms: int
    config_id: str
    summary: AlbionCombatSummary
    frame_windows: list[AlbionCombatFrameWindow] = Field(default_factory=list)
    entries: list[AlbionCombatTimelineEntry] = Field(default_factory=list)
