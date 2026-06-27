from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from montage_backend.models.domain import MontageError
from montage_backend.models.domain.media import ProcessingStatus, SceneMarker


class MetadataFeatureKey(str, Enum):
    VISUAL = "visual"
    AUDIO = "audio"
    AI_CACHE = "ai_cache"


METADATA_SCHEMA_VERSION = 1


class CameraMovement(BaseModel):
    label: str
    pan: float = Field(ge=0, le=1)
    zoom: float = Field(ge=0, le=1)
    shake: float = Field(ge=0, le=1)


class BrightnessStats(BaseModel):
    mean: float
    min: float
    max: float
    std: float


class ColorHistogram(BaseModel):
    bins: int = 16
    r: list[float] = Field(default_factory=list)
    g: list[float] = Field(default_factory=list)
    b: list[float] = Field(default_factory=list)


class KeyframeMarker(BaseModel):
    timestamp_ms: int


class VisualMetadata(BaseModel):
    scenes: list[SceneMarker] = Field(default_factory=list)
    motion_score: float = Field(ge=0, le=1)
    camera_movement: CameraMovement
    brightness: BrightnessStats
    color_histogram: ColorHistogram
    blur_score: float = Field(ge=0, le=1)
    sharpness: float = Field(ge=0, le=1)
    keyframes: list[KeyframeMarker] = Field(default_factory=list)


class SilenceRegion(BaseModel):
    start_ms: int
    end_ms: int


class BeatMarker(BaseModel):
    timestamp_ms: int
    strength: float = Field(ge=0, le=1)


class SpeechDetection(BaseModel):
    has_speech: bool
    speech_ratio: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class AudioMetadata(BaseModel):
    loudness_lufs: float | None = None
    mean_volume_db: float | None = None
    max_volume_db: float | None = None
    peaks: list[float] = Field(default_factory=list)
    silence_regions: list[SilenceRegion] = Field(default_factory=list)
    beat_markers: list[BeatMarker] = Field(default_factory=list)
    speech: SpeechDetection


class AICacheMetadata(BaseModel):
    """Placeholder slots for future AI analysis modules (M3+)."""

    ocr_text: list[dict[str, Any]] | None = None
    embedding_vectors: list[float] | None = None
    object_detections: list[dict[str, Any]] | None = None
    face_detections: list[dict[str, Any]] | None = None
    optical_flow: dict[str, Any] | None = None
    clip_embeddings: list[float] | None = None
    schema_version: int = METADATA_SCHEMA_VERSION


class MetadataFeatureRecord(BaseModel):
    media_id: str
    feature_key: MetadataFeatureKey
    status: ProcessingStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    reasoning: str | None = None
    source_fingerprint: str | None = None
    schema_version: int = METADATA_SCHEMA_VERSION
    created_at: str
    updated_at: str


class MediaMetadataSummary(BaseModel):
    media_id: str
    status: ProcessingStatus
    source_fingerprint: str | None = None
    visual: VisualMetadata | None = None
    audio: AudioMetadata | None = None
    ai_cache: AICacheMetadata | None = None
    features: list[MetadataFeatureRecord] = Field(default_factory=list)


class UpsertMetadataFeatureRequest(BaseModel):
    payload: dict[str, Any]
    confidence: float | None = None
    reasoning: str | None = None
    status: ProcessingStatus = ProcessingStatus.READY


class MetadataError(MontageError):
    code = "METADATA_ERROR"


class MetadataFeatureNotFoundError(MontageError):
    code = "METADATA_FEATURE_NOT_FOUND"
