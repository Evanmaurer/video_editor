from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

ALBION_UI_DETECTOR_VERSION = "albion-ui-v1.0"
DEFAULT_WINDOW_MS = 2000


class AlbionUiElementType(str, Enum):
    PARTY_FRAME = "party_frame"
    MINIMAP = "minimap"
    HEALTH_BAR = "health_bar"
    ABILITY_BAR = "ability_bar"
    KILL_FEED = "kill_feed"
    UI_PANEL = "ui_panel"
    SPELL_EFFECT = "spell_effect"
    CHAT_PANEL = "chat_panel"
    RESOURCE_BAR = "resource_bar"
    UNKNOWN = "unknown"


class AlbionUiBoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class AlbionUiDetection(BaseModel):
    element_type: AlbionUiElementType
    label: str
    timestamp_ms: int
    window_start_ms: int
    window_end_ms: int
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: AlbionUiBoundingBox
    template_id: str
    metadata: dict = Field(default_factory=dict)


class AlbionUiFrameWindow(BaseModel):
    window_start_ms: int
    window_end_ms: int
    cache_key: str
    template_id: str
    engine_id: str
    engine_version: str
    detection_count: int = 0
    detections: list[AlbionUiDetection] = Field(default_factory=list)


class AlbionUiSummary(BaseModel):
    frames_sampled: int
    window_count: int
    detection_count: int
    unique_element_count: int
    template_id: str
    engine_id: str
    engine_version: str
    by_element: dict[str, int] = Field(default_factory=dict)
    reused_m3_object: bool = False


class AlbionUiAnalysisResult(BaseModel):
    detector_version: str = ALBION_UI_DETECTOR_VERSION
    cache_key: str
    duration_ms: int
    frame_rate: float
    window_ms: int
    sample_interval_ms: int
    template_id: str
    summary: AlbionUiSummary
    frame_windows: list[AlbionUiFrameWindow] = Field(default_factory=list)
    detections: list[AlbionUiDetection] = Field(default_factory=list)
