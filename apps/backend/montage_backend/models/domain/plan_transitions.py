from __future__ import annotations

from pydantic import BaseModel, Field

from montage_backend.models.domain.montage_plan import MontageTransition

TRANSITION_ENGINE_VERSION = "transition-engine-v1.0"


class TransitionJunctionRecommendation(BaseModel):
    junction_index: int = Field(ge=0)
    from_clip_id: str
    to_clip_id: str
    from_media_id: str
    to_media_id: str
    timeline_ms: int = Field(ge=0)
    transition_out: MontageTransition
    transition_in: MontageTransition
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class PlanTransitionAnalysis(BaseModel):
    plan_id: str
    project_id: str
    pacing_profile: str
    junction_count: int = Field(ge=0)
    recommendations: list[TransitionJunctionRecommendation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    engine_version: str = TRANSITION_ENGINE_VERSION
    cache_key: str
    random_seed: int
    updated_at: str
