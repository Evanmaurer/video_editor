from __future__ import annotations

from pydantic import BaseModel, Field

from montage_backend.models.domain.montage_plan import MontageEffect

EFFECTS_ENGINE_VERSION = "effects-engine-v1.0"


class ClipEffectRecommendation(BaseModel):
    clip_id: str
    media_id: str
    order: int = Field(ge=0)
    effects: list[MontageEffect] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class PlanEffectsAnalysis(BaseModel):
    plan_id: str
    project_id: str
    pacing_profile: str
    clip_count: int = Field(ge=0)
    recommendations: list[ClipEffectRecommendation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    engine_version: str = EFFECTS_ENGINE_VERSION
    cache_key: str
    random_seed: int
    updated_at: str
