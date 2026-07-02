from __future__ import annotations

from pydantic import BaseModel, Field

ALBION_HIGHLIGHT_DETECTOR_VERSION = "albion-highlight-v1.0"
DEFAULT_WINDOW_MS = 2000


class AlbionHighlightFactor(BaseModel):
    factor_id: str
    label: str
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    contribution: float = Field(ge=0.0, le=100.0)
    reasoning: str


class AlbionHighlightMoment(BaseModel):
    moment_id: str
    timestamp_ms: int
    window_start_ms: int
    window_end_ms: int
    moment_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    moment_type: str
    reasoning: str
    search_text: str
    metadata: dict = Field(default_factory=dict)


class AlbionHighlightFrameWindow(BaseModel):
    window_start_ms: int
    window_end_ms: int
    cache_key: str
    config_id: str
    window_score: float = Field(ge=0.0, le=100.0, default=0.0)
    moment_count: int = 0
    moments: list[AlbionHighlightMoment] = Field(default_factory=list)


class AlbionHighlightSummary(BaseModel):
    frames_sampled: int
    window_count: int
    moment_count: int
    highlight_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    config_id: str
    factor_count: int = 0
    top_factor_ids: list[str] = Field(default_factory=list)
    by_moment_type: dict[str, int] = Field(default_factory=dict)
    reused_albion_combat: bool = False
    reused_albion_bomb: bool = False
    reused_albion_engagement: bool = False
    reused_albion_ability: bool = False
    reused_albion_ocr: bool = False
    reused_albion_ui: bool = False
    reused_motion: bool = False
    reused_audio: bool = False


class AlbionHighlightAnalysisResult(BaseModel):
    detector_version: str = ALBION_HIGHLIGHT_DETECTOR_VERSION
    cache_key: str
    duration_ms: int
    frame_rate: float
    window_ms: int
    sample_interval_ms: int
    config_id: str
    highlight_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    summary: AlbionHighlightSummary
    factors: list[AlbionHighlightFactor] = Field(default_factory=list)
    frame_windows: list[AlbionHighlightFrameWindow] = Field(default_factory=list)
    moments: list[AlbionHighlightMoment] = Field(default_factory=list)
