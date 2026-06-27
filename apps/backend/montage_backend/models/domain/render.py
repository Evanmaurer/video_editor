from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from montage_backend.models.domain import MontageError


class RenderJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RenderCodec(str, Enum):
    H264 = "h264"
    H265 = "h265"
    AV1 = "av1"


class StartRenderRequest(BaseModel):
    timeline_id: str | None = None
    preset_id: str = "h264_1080p60"
    output_name: str | None = None
    use_hardware_encoding: bool = True


class RenderPresetInfo(BaseModel):
    id: str
    label: str
    codec: RenderCodec
    width: int
    height: int
    frame_rate: float
    hardware_available: bool = False


class RenderJobSummary(BaseModel):
    id: str
    project_id: str
    timeline_id: str
    preset_id: str
    status: RenderJobStatus
    progress: float = Field(ge=0, le=1)
    output_path: str | None = None
    error_message: str | None = None
    eta_seconds: float | None = None
    elapsed_seconds: float = 0
    created_at: str
    updated_at: str


class RenderJobDetail(RenderJobSummary):
    ffmpeg_command: str | None = None
    hardware_encoding: bool = False
    log_tail: list[str] = Field(default_factory=list)


class RenderLogResponse(BaseModel):
    job_id: str
    lines: list[str]
    total_lines: int


class RenderError(MontageError):
    code = "RENDER_ERROR"


class RenderJobNotFoundError(MontageError):
    code = "RENDER_JOB_NOT_FOUND"
