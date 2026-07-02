from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

ALBION_ENGAGEMENT_DETECTOR_VERSION = "albion-engagement-v1.0"
DEFAULT_WINDOW_MS = 2000


class AlbionEngagementType(str, Enum):
    ZVZ = "zvz"
    GANKING = "ganking"
    GATHERING = "gathering"
    ROAMING = "roaming"
    DUNGEON = "dungeon"
    OPEN_WORLD_PVP = "open_world_pvp"


class AlbionEngagementSignals(BaseModel):
    kill_count: int = 0
    death_count: int = 0
    fight_count: int = 0
    bomb_count: int = 0
    sustained_combat_ms: int = 0
    sustained_ui_ms: int = 0
    party_frame_count: int = 0
    resource_bar_count: int = 0
    gathering_keyword_hits: int = 0
    avg_motion_score: float = Field(ge=0.0, le=1.0, default=0.0)
    max_motion_score: float = Field(ge=0.0, le=1.0, default=0.0)


class AlbionEngagementTag(BaseModel):
    engagement_type: AlbionEngagementType
    confidence: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=10.0)
    reasoning: str
    search_text: str
    metadata: dict = Field(default_factory=dict)


class AlbionEngagementFrameWindow(BaseModel):
    window_start_ms: int
    window_end_ms: int
    cache_key: str
    config_id: str
    combat_ui_active: bool = False
    tag_count: int = 0
    tags: list[AlbionEngagementTag] = Field(default_factory=list)


class AlbionEngagementSummary(BaseModel):
    frames_sampled: int
    window_count: int
    tag_count: int
    primary_engagement: AlbionEngagementType | None = None
    sustained_combat_ms: int = 0
    config_id: str
    signals: AlbionEngagementSignals
    by_engagement_type: dict[str, int] = Field(default_factory=dict)
    reused_albion_combat: bool = False
    reused_albion_bomb: bool = False
    reused_albion_ui: bool = False
    reused_albion_ocr: bool = False
    reused_motion: bool = False


class AlbionEngagementAnalysisResult(BaseModel):
    detector_version: str = ALBION_ENGAGEMENT_DETECTOR_VERSION
    cache_key: str
    duration_ms: int
    frame_rate: float
    window_ms: int
    sample_interval_ms: int
    config_id: str
    summary: AlbionEngagementSummary
    frame_windows: list[AlbionEngagementFrameWindow] = Field(default_factory=list)
    tags: list[AlbionEngagementTag] = Field(default_factory=list)
