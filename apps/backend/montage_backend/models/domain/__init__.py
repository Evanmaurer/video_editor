from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from montage_backend.models.domain.project import ProjectSettings


class MontageError(Exception):
    code: str = "MONTAGE_ERROR"
    message: str = "An error occurred"
    details: dict[str, Any] | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


class ProjectNotFoundError(MontageError):
    code = "PROJECT_NOT_FOUND"


class ProjectAlreadyExistsError(MontageError):
    code = "PROJECT_ALREADY_EXISTS"


class InvalidProjectError(MontageError):
    code = "INVALID_PROJECT"


class LlmProviderType(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    NONE = "none"


class LlmProviderConfig(BaseModel):
    provider: LlmProviderType = LlmProviderType.OLLAMA
    model: str = "qwen3:8b-instruct"
    api_key: str | None = None
    base_url: str | None = "http://127.0.0.1:11434"


class AppSettings(BaseModel):
    default_project_path: str = ""
    llm: LlmProviderConfig = Field(default_factory=LlmProviderConfig)
    gpu_enabled: bool = True
    worker_count: int = 2

    def model_post_init(self, __context: object) -> None:
        if not self.default_project_path:
            from pathlib import Path

            self.default_project_path = str(Path.home() / "Videos" / "Montages")


class Project(BaseModel):
    id: str
    name: str
    root_path: str
    width: int = 1920
    height: int = 1080
    frame_rate: float = 60.0
    target_game: str = "albion"
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    created_at: str
    updated_at: str


class ProjectSummary(BaseModel):
    id: str
    name: str
    path: str
    updated_at: str


class CreateProjectRequest(BaseModel):
    name: str
    root_path: str
    width: int = 1920
    height: int = 1080
    frame_rate: float = 60.0
    target_game: str = "albion"
    settings: ProjectSettings | None = None


class OpenProjectRequest(BaseModel):
    path: str


class GpuInfo(BaseModel):
    available: bool
    name: str | None = None
    estimated_speedup: str = "1x (CPU only)"
    cpu_only_warning: str | None = None


class AiFeatureStatus(BaseModel):
    chat_enabled: bool = False
    chat_disabled_reason: str | None = "LLM provider not configured"
    ocr_available: bool = True
    albion_detection_available: bool = True
    music_analysis_available: bool = True


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_uuid() -> str:
    return str(uuid4())
