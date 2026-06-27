from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.database import db_manager
from montage_backend.media.processor import MediaProcessor
from montage_backend.services.llm_service import llm_service
from montage_backend.services.media_service import MediaService
from montage_backend.services.project_service import AppSettingsService, ProjectService

from montage_backend.services.timeline_service import TimelineService

_project_service: ProjectService | None = None
_settings_service: AppSettingsService | None = None
_media_service: MediaService | None = None
_timeline_service: TimelineService | None = None


async def ensure_database_started() -> None:
    """Initialize app.db tables before any API handler runs."""
    await db_manager.ensure_started()


def get_project_service() -> ProjectService:
    global _project_service
    if _project_service is None:
        _project_service = ProjectService(db_manager.app_session_factory)
    return _project_service


def get_settings_service() -> AppSettingsService:
    global _settings_service
    if _settings_service is None:
        _settings_service = AppSettingsService(db_manager.app_session_factory)
    return _settings_service


async def get_app_session() -> AsyncGenerator[AsyncSession, None]:
    await db_manager.ensure_started()
    async with db_manager.app_session_factory() as session:
        yield session


def get_llm_service():
    return llm_service


def get_media_service() -> MediaService:
    global _media_service
    if _media_service is None:
        from montage_backend.config import settings
        from montage_backend.media.ffmpeg_runner import FFmpegRunner

        runner = FFmpegRunner(
            ffmpeg_bin=settings.ffmpeg_bin,
            ffprobe_bin=settings.ffprobe_bin,
        )
        processor = MediaProcessor(runner=runner)
        _media_service = MediaService(
            get_project_service(),
            processor=processor,
            worker_count=settings.worker_count,
        )
    return _media_service


def get_timeline_service() -> TimelineService:
    global _timeline_service
    if _timeline_service is None:
        _timeline_service = TimelineService(get_project_service())
    return _timeline_service
