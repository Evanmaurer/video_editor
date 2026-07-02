from __future__ import annotations

from pydantic import BaseModel, Field

PACING_ENGINE_VERSION = "pacing-engine-v1.0"


class ClipPacingRecommendation(BaseModel):
    clip_id: str
    media_id: str
    order: int = Field(ge=0)
    timeline_start_ms: int = Field(ge=0)
    timeline_end_ms: int = Field(ge=0)
    timeline_duration_ms: int = Field(ge=0)
    source_start_ms: int = Field(ge=0)
    source_end_ms: int = Field(ge=0)
    playback_speed: float = Field(gt=0.0, default=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class PlanPacingAnalysis(BaseModel):
    plan_id: str
    project_id: str
    pacing_profile: str
    target_duration_ms: int | None = None
    total_duration_ms: int = Field(ge=0)
    clip_count: int = Field(ge=0)
    recommendations: list[ClipPacingRecommendation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    engine_version: str = PACING_ENGINE_VERSION
    cache_key: str
    random_seed: int
    updated_at: str
