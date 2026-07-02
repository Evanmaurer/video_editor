from __future__ import annotations

from pydantic import BaseModel, Field

ALBION_BOMB_DETECTOR_VERSION = "albion-bomb-v1.0"
DEFAULT_WINDOW_MS = 2000


class AlbionBombFusionScores(BaseModel):
    ocr_score: float = Field(ge=0.0, le=1.0)
    motion_score: float = Field(ge=0.0, le=1.0)
    audio_score: float = Field(ge=0.0, le=1.0)
    ability_score: float = Field(ge=0.0, le=1.0)


class AlbionBombEvent(BaseModel):
    event_id: str
    timestamp_ms: int
    window_start_ms: int
    window_end_ms: int
    confidence: float = Field(ge=0.0, le=1.0)
    bomb_score: float = Field(ge=0.0, le=10.0)
    kill_count: int = Field(ge=0)
    fusion: AlbionBombFusionScores
    search_text: str
    reasoning: str
    metadata: dict = Field(default_factory=dict)


class AlbionBombFrameWindow(BaseModel):
    window_start_ms: int
    window_end_ms: int
    cache_key: str
    config_id: str
    bomb_count: int = 0
    max_bomb_score: float = Field(ge=0.0, le=10.0, default=0.0)
    events: list[AlbionBombEvent] = Field(default_factory=list)


class AlbionBombSummary(BaseModel):
    frames_sampled: int
    window_count: int
    bomb_count: int
    top_bomb_score: float = Field(ge=0.0, le=10.0, default=0.0)
    total_kill_count: int = 0
    config_id: str
    by_source: dict[str, bool] = Field(default_factory=dict)
    reused_albion_combat: bool = False
    reused_albion_ocr: bool = False
    reused_albion_ability: bool = False
    reused_motion: bool = False
    reused_audio: bool = False


class AlbionBombAnalysisResult(BaseModel):
    detector_version: str = ALBION_BOMB_DETECTOR_VERSION
    cache_key: str
    duration_ms: int
    frame_rate: float
    window_ms: int
    sample_interval_ms: int
    config_id: str
    summary: AlbionBombSummary
    frame_windows: list[AlbionBombFrameWindow] = Field(default_factory=list)
    events: list[AlbionBombEvent] = Field(default_factory=list)
