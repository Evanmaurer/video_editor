from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

ALBION_ANNOTATION_ENGINE_VERSION = "albion-annotation-v1.0"


class AlbionTimelineMarkerType(str, Enum):
    BOMB = "bomb"
    KILL = "kill"
    OCR = "ocr"
    ABILITY = "ability"
    FIGHT_START = "fight_start"
    FIGHT_END = "fight_end"
    ENGAGEMENT = "engagement"
    HIGHLIGHT = "highlight"
    RECOMMENDATION = "recommendation"


MARKER_COLORS: dict[str, str] = {
    AlbionTimelineMarkerType.BOMB.value: "#e74c3c",
    AlbionTimelineMarkerType.KILL.value: "#3498db",
    AlbionTimelineMarkerType.OCR.value: "#95a5a6",
    AlbionTimelineMarkerType.ABILITY.value: "#9b59b6",
    AlbionTimelineMarkerType.FIGHT_START.value: "#e67e22",
    AlbionTimelineMarkerType.FIGHT_END.value: "#d35400",
    AlbionTimelineMarkerType.ENGAGEMENT.value: "#e67e22",
    AlbionTimelineMarkerType.HIGHLIGHT.value: "#f1c40f",
    AlbionTimelineMarkerType.RECOMMENDATION.value: "#2ecc71",
}


class AlbionTimelineMarker(BaseModel):
    marker_id: str
    marker_type: AlbionTimelineMarkerType
    timestamp_ms: int
    end_ms: int | None = None
    seek_ms: int
    label: str
    color: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    search_text: str
    metadata: dict = Field(default_factory=dict)


class AlbionTimelineRecommendation(BaseModel):
    recommendation_id: str
    timestamp_ms: int
    seek_ms: int
    label: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class AlbionTimelineAnnotationSummary(BaseModel):
    marker_count: int
    recommendation_count: int
    highlight_score: float | None = Field(default=None, ge=0.0, le=100.0)
    primary_engagement: str | None = None
    by_marker_type: dict[str, int] = Field(default_factory=dict)
    reused_albion_combat: bool = False
    reused_albion_bomb: bool = False
    reused_albion_engagement: bool = False
    reused_albion_ability: bool = False
    reused_albion_ocr: bool = False
    reused_albion_highlight: bool = False


class AlbionTimelineAnnotationResult(BaseModel):
    engine_version: str = ALBION_ANNOTATION_ENGINE_VERSION
    cache_key: str
    duration_ms: int
    frame_rate: float
    summary: AlbionTimelineAnnotationSummary
    markers: list[AlbionTimelineMarker] = Field(default_factory=list)
    recommendations: list[AlbionTimelineRecommendation] = Field(default_factory=list)
