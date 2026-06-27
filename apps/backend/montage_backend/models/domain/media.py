from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from montage_backend.models.domain import MontageError, new_uuid, utc_now_iso


class MediaType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"


class MediaRole(str, Enum):
    CLIP = "clip"
    MUSIC = "music"
    REFERENCE = "reference"
    VOICE = "voice"
    OTHER = "other"


class ImportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    CANCELLED = "cancelled"
    DUPLICATE = "duplicate"


class StorageMode(str, Enum):
    COPY = "copy"
    REFERENCE = "reference"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class MediaSortField(str, Enum):
    NAME = "name"
    DURATION = "duration"
    CREATED_AT = "created_at"
    FAVORITE = "favorite"


class MediaSortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class MediaNotFoundError(MontageError):
    code = "MEDIA_NOT_FOUND"


class MediaProcessingError(MontageError):
    code = "MEDIA_PROCESSING_ERROR"


class ProcessingCancelledError(MontageError):
    code = "PROCESSING_CANCELLED"


class CorruptMediaError(MontageError):
    code = "CORRUPT_MEDIA"


class DuplicateMediaError(MontageError):
    code = "DUPLICATE_MEDIA"


class VideoProbeResult(BaseModel):
    width: int
    height: int
    frame_rate: float
    codec: str
    duration_ms: int
    frame_count: int
    audio_sample_rate: int | None = None
    bitrate: int | None = None
    file_size_bytes: int


class SceneMarker(BaseModel):
    timestamp_ms: int
    score: float


class MediaCachePaths(BaseModel):
    original_path: str
    proxy_path: str
    thumbnail_poster_path: str
    thumbnail_strip_path: str
    waveform_path: str
    probe_cache_path: str
    scenes_cache_path: str
    manifest_path: str


class MediaItem(BaseModel):
    id: str
    project_id: str
    file_path: str
    file_name: str
    source_path: str | None = None
    media_type: MediaType
    role: MediaRole
    storage_mode: StorageMode = StorageMode.COPY
    sha256_hash: str | None = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    codec: str | None = None
    frame_count: int | None = None
    audio_sample_rate: int | None = None
    bitrate: int | None = None
    file_size_bytes: int | None = None
    proxy_path: str | None = None
    thumbnail_path: str | None = None
    waveform_path: str | None = None
    proxy_status: ProcessingStatus = ProcessingStatus.PENDING
    waveform_status: ProcessingStatus = ProcessingStatus.PENDING
    scene_status: ProcessingStatus = ProcessingStatus.PENDING
    tags: list[str] = Field(default_factory=list)
    is_favorite: bool = False
    import_status: ImportStatus = ImportStatus.PENDING
    error_message: str | None = None
    cache_paths: MediaCachePaths | None = None
    created_at: str
    updated_at: str


class ImportMediaRequest(BaseModel):
    paths: list[str] = Field(min_length=1)
    role: MediaRole = MediaRole.CLIP
    storage_mode: StorageMode = StorageMode.COPY


class ImportFolderRequest(BaseModel):
    path: str
    role: MediaRole = MediaRole.CLIP
    storage_mode: StorageMode = StorageMode.COPY


class ImportMediaResult(BaseModel):
    media_id: str
    file_name: str
    status: ImportStatus
    error: str | None = None
    sha256_hash: str | None = None


class ImportMediaResponse(BaseModel):
    imported: list[ImportMediaResult] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    duplicates: list[ImportMediaResult] = Field(default_factory=list)


class MediaListQuery(BaseModel):
    search: str | None = None
    sort_by: MediaSortField = MediaSortField.CREATED_AT
    sort_order: MediaSortOrder = MediaSortOrder.DESC
    tags: list[str] = Field(default_factory=list)
    favorites_only: bool = False


class UpdateMediaRequest(BaseModel):
    tags: list[str] | None = None
    is_favorite: bool | None = None


def new_media_item(
    *,
    project_id: str,
    file_path: Path,
    role: MediaRole,
    media_type: MediaType = MediaType.VIDEO,
    storage_mode: StorageMode = StorageMode.COPY,
    source_path: str | None = None,
    sha256_hash: str | None = None,
) -> MediaItem:
    now = utc_now_iso()
    return MediaItem(
        id=new_uuid(),
        project_id=project_id,
        file_path=str(file_path),
        file_name=file_path.name,
        source_path=source_path,
        media_type=media_type,
        role=role,
        storage_mode=storage_mode,
        sha256_hash=sha256_hash,
        import_status=ImportStatus.PENDING,
        proxy_status=ProcessingStatus.PENDING,
        waveform_status=ProcessingStatus.PENDING,
        scene_status=ProcessingStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
