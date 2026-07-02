from __future__ import annotations

from pydantic import BaseModel, Field

HIGHLIGHT_DETECTOR_VERSION = "highlight-detector-v1.0"


class HighlightSignal(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class HighlightSegment(BaseModel):
    id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    signals: list[HighlightSignal] = Field(default_factory=list)
    category: str = "mixed"


class ClipHighlights(BaseModel):
    media_id: str
    project_id: str
    file_name: str | None = None
    highlight_count: int = Field(ge=0)
    highlights: list[HighlightSegment] = Field(default_factory=list)
    detector_version: str = HIGHLIGHT_DETECTOR_VERSION
    cache_key: str
    source_fingerprint: str | None = None
    duration_ms: int | None = None
    updated_at: str


class ProjectClipHighlightsResponse(BaseModel):
    project_id: str
    detector_version: str
    clip_count: int
    clips: list[ClipHighlights] = Field(default_factory=list)
