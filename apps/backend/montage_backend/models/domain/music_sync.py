from __future__ import annotations

from pydantic import BaseModel, Field

MUSIC_SYNC_VERSION = "music-sync-v1.0"


class MusicBeatMarker(BaseModel):
    timestamp_ms: int = Field(ge=0)
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)


class MusicSection(BaseModel):
    id: str
    section_type: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class CutSuggestion(BaseModel):
    timestamp_ms: int = Field(ge=0)
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    beat_aligned: bool = False


class TransitionTimingSuggestion(BaseModel):
    timestamp_ms: int = Field(ge=0)
    transition_type: str
    duration_ms: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class MusicSyncAnalysis(BaseModel):
    media_id: str
    project_id: str
    file_name: str | None = None
    tempo_bpm: float | None = None
    beat_markers: list[MusicBeatMarker] = Field(default_factory=list)
    sections: list[MusicSection] = Field(default_factory=list)
    cut_suggestions: list[CutSuggestion] = Field(default_factory=list)
    transition_suggestions: list[TransitionTimingSuggestion] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    sync_version: str = MUSIC_SYNC_VERSION
    cache_key: str
    source_fingerprint: str | None = None
    duration_ms: int | None = None
    updated_at: str


class ProjectMusicSyncResponse(BaseModel):
    project_id: str
    sync_version: str
    track_count: int
    tracks: list[MusicSyncAnalysis] = Field(default_factory=list)
