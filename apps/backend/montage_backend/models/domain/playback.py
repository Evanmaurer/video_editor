from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from montage_backend.models.domain import MontageError


class PlaybackDecodeRequest(BaseModel):
    media_id: str
    source_ms: int = Field(ge=0)
    frame_rate: float = Field(default=60.0, gt=0)
    quality: Literal["proxy", "full"] = "proxy"


class PlaybackPrefetchItem(BaseModel):
    media_id: str
    source_ms: int = Field(ge=0)
    quality: Literal["proxy", "full"] = "proxy"


class PlaybackPrefetchRequest(BaseModel):
    frame_rate: float = Field(default=60.0, gt=0)
    requests: list[PlaybackPrefetchItem] = Field(default_factory=list)


class PlaybackClientMetrics(BaseModel):
    playback_fps: float = Field(ge=0)
    dropped_frames: int = Field(ge=0)


class PlaybackDecodeResponse(BaseModel):
    image_base64: str
    decode_time_ms: float
    cache_hit: bool
    gpu_accelerated: bool


class PlaybackMetricsResponse(BaseModel):
    playback_fps: float
    dropped_frames: int
    decode_time_ms: float
    memory_usage_mb: float
    gpu_accelerated: bool
    cache_hit_rate: float


class PlaybackError(MontageError):
    code = "PLAYBACK_ERROR"
