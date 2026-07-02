from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

FEEDBACK_ENGINE_VERSION = "feedback-engine-v1.0"


class FeedbackActionType(str, Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    IMPROVE_PACING = "improve_pacing"
    INCREASE_ACTION = "increase_action"
    REDUCE_LENGTH = "reduce_length"
    MORE_CINEMATIC = "more_cinematic"
    MORE_AGGRESSIVE = "more_aggressive"
    REGENERATE = "regenerate"


class QualityDimension(str, Enum):
    MONTAGE = "montage_quality"
    PACING = "pacing_quality"
    TRANSITIONS = "transition_quality"
    EXCITEMENT = "excitement"
    RETENTION = "viewer_retention"


class QualityEstimate(BaseModel):
    dimension: QualityDimension
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class PlanQualityAnalysis(BaseModel):
    plan_id: str
    project_id: str
    plan_version: int = Field(ge=1)
    estimates: list[QualityEstimate] = Field(default_factory=list)
    overall_score: float = Field(ge=0.0, le=100.0)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    engine_version: str = FEEDBACK_ENGINE_VERSION
    cache_key: str
    updated_at: str


class SubmitPlanFeedbackRequest(BaseModel):
    action: FeedbackActionType
    comment: str = ""


class PlanFeedbackEvent(BaseModel):
    id: str
    plan_id: str
    project_id: str
    action: FeedbackActionType
    comment: str = ""
    applied_changes: dict = Field(default_factory=dict)
    created_at: str


class PlanFeedbackState(BaseModel):
    plan_id: str
    project_id: str
    quality: PlanQualityAnalysis | None = None
    events: list[PlanFeedbackEvent] = Field(default_factory=list)
    feedback_preferences: dict = Field(default_factory=dict)
    regeneration_hints: list[str] = Field(default_factory=list)


class PlanFeedbackRegenerationResult(BaseModel):
    plan_id: str
    project_id: str
    action: FeedbackActionType
    quality: PlanQualityAnalysis
    event: PlanFeedbackEvent
    plan_status: str
    applied_changes: dict = Field(default_factory=dict)
