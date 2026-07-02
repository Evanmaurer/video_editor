from __future__ import annotations

from pydantic import BaseModel, Field

from montage_backend.models.domain import MontageError


class PlanTimelineApplicationNotFoundError(MontageError):
    code = "PLAN_TIMELINE_APPLICATION_NOT_FOUND"


TIMELINE_GENERATOR_VERSION = "timeline-generator-v1.0"


class PlanTimelineApplication(BaseModel):
    plan_id: str
    project_id: str
    timeline_id: str
    plan_version: int = Field(ge=1)
    clip_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    video_clip_count: int = Field(ge=0)
    audio_clip_count: int = Field(ge=0)
    music_media_id: str | None = None
    overwritten: bool = False
    partial: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    engine_version: str = TIMELINE_GENERATOR_VERSION
    cache_key: str
    updated_at: str
