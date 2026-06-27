from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from montage_backend.models.domain import MontageError, new_uuid, utc_now_iso
from montage_backend.models.domain.media import ProcessingStatus


class SceneTransitionType(str, Enum):
    HARD_CUT = "hard_cut"
    SHOT_BOUNDARY = "shot_boundary"
    FADE = "fade"
    BLACK_FRAME = "black_frame"
    FREEZE_FRAME = "freeze_frame"


class SceneEvent(BaseModel):
    timestamp_ms: int
    frame: int
    event_type: SceneTransitionType
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)


class SceneSegment(BaseModel):
    start_frame: int
    end_frame: int
    start_ms: int
    end_ms: int
    duration_ms: int
    transition_in: SceneTransitionType | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class SceneAnalysisResult(BaseModel):
    analyzer_version: str
    cache_key: str
    frame_rate: float
    frame_count: int
    duration_ms: int
    events: list[SceneEvent] = Field(default_factory=list)
    segments: list[SceneSegment] = Field(default_factory=list)


class AnalysisModuleCacheRecord(BaseModel):
    id: str
    media_id: str
    module_id: str
    analyzer_version: str
    cache_key: str
    status: ProcessingStatus
    payload: dict
    confidence: float | None = None
    reasoning: str | None = None
    source_fingerprint: str | None = None
    created_at: str
    updated_at: str


class AnalysisJobRecord(BaseModel):
    id: str
    project_id: str
    media_id: str
    module_id: str
    status: ProcessingStatus
    progress: float = Field(ge=0.0, le=1.0, default=0.0)
    message: str | None = None
    error_message: str | None = None
    cache_id: str | None = None
    priority: int = 0
    retry_count: int = Field(ge=0, default=0)
    max_retries: int = Field(ge=0, default=2)
    created_at: str
    updated_at: str


class AnalysisModuleInfo(BaseModel):
    module_id: str
    version: str
    description: str


class RunAnalysisRequest(BaseModel):
    force: bool = False
    priority: int = 0


class AnalysisQueueStatus(BaseModel):
    project_id: str
    paused: bool = False
    pending_count: int = 0
    in_flight_count: int = 0
    max_workers: int = 0
    active_workers: int = 0


class AnalysisCancelledError(MontageError):
    code = "ANALYSIS_CANCELLED"


class AnalysisPausedError(MontageError):
    code = "ANALYSIS_PAUSED"


class AnalysisRetryLimitError(MontageError):
    code = "ANALYSIS_RETRY_LIMIT"


def new_analysis_job(
    *,
    project_id: str,
    media_id: str,
    module_id: str,
    priority: int = 0,
    max_retries: int = 2,
) -> AnalysisJobRecord:
    now = utc_now_iso()
    return AnalysisJobRecord(
        id=new_uuid(),
        project_id=project_id,
        media_id=media_id,
        module_id=module_id,
        status=ProcessingStatus.PENDING,
        progress=0.0,
        priority=priority,
        max_retries=max_retries,
        created_at=now,
        updated_at=now,
    )
