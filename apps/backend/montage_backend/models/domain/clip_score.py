from __future__ import annotations

from pydantic import BaseModel, Field

CLIP_SCORER_VERSION = "clip-scorer-v1.0"


class ClipScoreComponent(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    weighted_score: float = Field(ge=0.0, le=100.0)
    reasoning: str = ""


class ClipScoreBreakdown(BaseModel):
    motion: ClipScoreComponent
    camera_shake: ClipScoreComponent
    audio_intensity: ClipScoreComponent
    ocr_activity: ClipScoreComponent
    scene_complexity: ClipScoreComponent
    visual_quality: ClipScoreComponent
    exposure: ClipScoreComponent
    scene_length: ClipScoreComponent


class ClipScore(BaseModel):
    media_id: str
    project_id: str
    file_name: str | None = None
    montage_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    breakdown: ClipScoreBreakdown
    scorer_version: str = CLIP_SCORER_VERSION
    cache_key: str
    source_fingerprint: str | None = None
    duration_ms: int | None = None
    updated_at: str


class ProjectClipScoresResponse(BaseModel):
    project_id: str
    scorer_version: str
    clip_count: int
    scores: list[ClipScore] = Field(default_factory=list)
