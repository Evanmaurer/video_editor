from __future__ import annotations

from pydantic import BaseModel, Field

from montage_backend.analysis.audio_analysis import AudioAnalysisResult
from montage_backend.analysis.embedding_analysis import EmbeddingAnalysisResult
from montage_backend.analysis.motion_analysis import MotionAnalysisResult
from montage_backend.analysis.object_analysis import ObjectAnalysisResult
from montage_backend.analysis.ocr_analysis import OcrAnalysisResult
from montage_backend.models.domain.analysis import SceneAnalysisResult
from montage_backend.models.domain.media import ImportStatus, ProcessingStatus
from montage_backend.models.domain.metadata import MediaMetadataSummary

CLIP_ANALYSIS_SCHEMA_VERSION = 1


class ClipProcessingSnapshot(BaseModel):
    import_status: ImportStatus
    proxy_status: ProcessingStatus
    waveform_status: ProcessingStatus
    scene_cache_status: ProcessingStatus
    metadata_status: ProcessingStatus


class ClipAssetSnapshot(BaseModel):
    proxy_path: str | None = None
    thumbnail_path: str | None = None
    waveform_path: str | None = None
    thumbnail_strip_path: str | None = None


class ClipVideoSnapshot(BaseModel):
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    codec: str | None = None
    frame_count: int | None = None
    file_size_bytes: int | None = None


class AnalysisModuleStatusEntry(BaseModel):
    module_id: str
    status: ProcessingStatus
    analyzer_version: str | None = None
    cache_key: str | None = None
    confidence: float | None = None
    updated_at: str | None = None


class ClipAnalysisVersions(BaseModel):
    schema_version: int = CLIP_ANALYSIS_SCHEMA_VERSION
    metadata_schema_version: int | None = None
    module_versions: dict[str, str] = Field(default_factory=dict)


class ClipAnalysisSummary(BaseModel):
    media_id: str
    project_id: str
    overall_status: ProcessingStatus
    readiness: float = Field(ge=0.0, le=1.0)
    modules_ready: int = Field(ge=0)
    modules_total: int = Field(ge=0)
    source_fingerprint: str | None = None
    scene_count: int | None = None
    overall_motion_score: float | None = None
    ocr_unique_text_count: int | None = None
    object_detection_count: int | None = None
    embedding_count: int | None = None
    has_metadata: bool = False
    processing: ClipProcessingSnapshot
    assets: ClipAssetSnapshot
    video: ClipVideoSnapshot
    modules: dict[str, AnalysisModuleStatusEntry] = Field(default_factory=dict)
    versions: ClipAnalysisVersions = Field(default_factory=ClipAnalysisVersions)
    updated_at: str
    created_at: str


class ClipAnalysisRecord(BaseModel):
    media_id: str
    project_id: str
    overall_status: ProcessingStatus
    source_fingerprint: str | None = None
    processing: ClipProcessingSnapshot
    assets: ClipAssetSnapshot
    video: ClipVideoSnapshot
    metadata: MediaMetadataSummary | None = None
    modules: dict[str, AnalysisModuleStatusEntry] = Field(default_factory=dict)
    scene: SceneAnalysisResult | None = None
    motion: MotionAnalysisResult | None = None
    audio: AudioAnalysisResult | None = None
    ocr: OcrAnalysisResult | None = None
    object: ObjectAnalysisResult | None = None
    embedding: EmbeddingAnalysisResult | None = None
    embedding_vector_count: int = 0
    versions: ClipAnalysisVersions = Field(default_factory=ClipAnalysisVersions)
    summary: ClipAnalysisSummary
    updated_at: str
    created_at: str


class ProjectAnalysisOverview(BaseModel):
    project_id: str
    clip_count: int = 0
    analysis_ready_count: int = 0
    analysis_processing_count: int = 0
    analysis_pending_count: int = 0
    analysis_error_count: int = 0
    module_ready_counts: dict[str, int] = Field(default_factory=dict)
    clips: list[ClipAnalysisSummary] = Field(default_factory=list)
