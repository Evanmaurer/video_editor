from __future__ import annotations

from pydantic import BaseModel, Field

from montage_backend.models.domain.montage_plan import MontagePlanCard

DRAFT_GENERATOR_VERSION = "draft-generator-v1.0"


class DraftClipCandidate(BaseModel):
    clip_id: str
    media_id: str
    file_name: str | None = None
    order: int = Field(ge=0)
    source_start_ms: int = Field(ge=0)
    source_end_ms: int = Field(ge=0)
    clip_score: float = Field(ge=0.0, le=100.0)
    highlight_score: float = Field(ge=0.0, le=100.0)
    combined_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class PlanDraftAnalysis(BaseModel):
    plan_id: str
    project_id: str
    pacing_profile: str
    target_duration_ms: int | None = None
    clip_count: int = Field(ge=0)
    candidates: list[DraftClipCandidate] = Field(default_factory=list)
    title_card: MontagePlanCard
    ending_card: MontagePlanCard
    music_media_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    engine_version: str = DRAFT_GENERATOR_VERSION
    cache_key: str
    random_seed: int
    updated_at: str
