from __future__ import annotations

from pydantic import BaseModel, Field

ALBION_SEARCH_ENGINE_VERSION = "albion-search-v1.0"


class AlbionSearchFilters(BaseModel):
    engagement_types: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    ability_name: str | None = None
    free_text: str | None = None
    min_kills: int | None = Field(default=None, ge=0)
    min_fight_duration_ms: int | None = Field(default=None, ge=0)
    min_highlight_score: float | None = Field(default=None, ge=0.0, le=100.0)
    has_bomb: bool | None = None


class AlbionSearchRequest(BaseModel):
    query: str = ""
    filters: AlbionSearchFilters | None = None
    limit: int = Field(default=50, ge=1, le=500)


class AlbionSearchEventMatch(BaseModel):
    event_type: str
    timestamp_ms: int
    label: str
    search_text: str
    metadata: dict = Field(default_factory=dict)


class AlbionSearchMatch(BaseModel):
    media_id: str
    file_name: str | None = None
    match_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    highlight_score: float | None = Field(default=None, ge=0.0, le=100.0)
    primary_engagement: str | None = None
    kill_count: int = 0
    bomb_count: int = 0
    sustained_combat_ms: int = 0
    matched_events: list[AlbionSearchEventMatch] = Field(default_factory=list)


class AlbionSearchResponse(BaseModel):
    engine_version: str = ALBION_SEARCH_ENGINE_VERSION
    query: str
    parsed_filters: AlbionSearchFilters
    match_count: int = 0
    clips_searched: int = 0
    clips_with_albion_cache: int = 0
    used_cached_metadata_only: bool = True
    matches: list[AlbionSearchMatch] = Field(default_factory=list)
