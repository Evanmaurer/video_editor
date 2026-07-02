from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

ALBION_OCR_DETECTOR_VERSION = "albion-ocr-v1.0"
DEFAULT_WINDOW_MS = 1500


class AlbionOcrCategory(str, Enum):
    PLAYER_NAME = "player_name"
    GUILD_TAG = "guild_tag"
    ALLIANCE_TAG = "alliance_tag"
    DAMAGE_NUMBER = "damage_number"
    HEALING_NUMBER = "healing_number"
    ZONE_NAME = "zone_name"
    ABILITY_NAME = "ability_name"
    KILL_MESSAGE = "kill_message"
    DEATH_MESSAGE = "death_message"
    LOOT_NOTIFICATION = "loot_notification"
    UNKNOWN = "unknown"


class AlbionOcrBoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class AlbionOcrDetection(BaseModel):
    text: str
    category: AlbionOcrCategory
    timestamp_ms: int
    window_start_ms: int
    window_end_ms: int
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: AlbionOcrBoundingBox | None = None
    metadata: dict = Field(default_factory=dict)


class AlbionOcrFrameWindow(BaseModel):
    window_start_ms: int
    window_end_ms: int
    cache_key: str
    engine_id: str
    engine_version: str
    detection_count: int = 0
    detections: list[AlbionOcrDetection] = Field(default_factory=list)


class AlbionOcrSummary(BaseModel):
    frames_sampled: int
    window_count: int
    detection_count: int
    unique_text_count: int
    engine_id: str
    engine_version: str
    by_category: dict[str, int] = Field(default_factory=dict)
    reused_m3_ocr: bool = False


class AlbionOcrAnalysisResult(BaseModel):
    detector_version: str = ALBION_OCR_DETECTOR_VERSION
    cache_key: str
    duration_ms: int
    frame_rate: float
    window_ms: int
    sample_interval_ms: int
    summary: AlbionOcrSummary
    frame_windows: list[AlbionOcrFrameWindow] = Field(default_factory=list)
    detections: list[AlbionOcrDetection] = Field(default_factory=list)
    unique_texts: list[str] = Field(default_factory=list)
