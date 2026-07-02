from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.database import db_manager
from montage_backend.media.processor import MediaProcessor
from montage_backend.services.llm_service import llm_service
from montage_backend.services.media_service import MediaService
from montage_backend.services.project_service import AppSettingsService, ProjectService

from montage_backend.playback.playback_service import PlaybackService
from montage_backend.services.timeline_service import TimelineService

_project_service: ProjectService | None = None
_settings_service: AppSettingsService | None = None
_media_service: MediaService | None = None
_timeline_service: TimelineService | None = None
_playback_service: PlaybackService | None = None
_render_service: "RenderService | None" = None
_metadata_service: "MetadataService | None" = None
_analysis_service: "AnalysisService | None" = None
_montage_plan_service: "MontagePlanService | None" = None


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


def get_playback_service() -> PlaybackService:
    global _playback_service
    if _playback_service is None:
        from montage_backend.config import settings

        _playback_service = PlaybackService(
            get_project_service(),
            get_media_service(),
            worker_count=settings.worker_count,
        )
    return _playback_service


def get_render_service():
    global _render_service
    if _render_service is None:
        from montage_backend.config import settings
        from montage_backend.media.ffmpeg_runner import FFmpegRunner
        from montage_backend.services.render_service import RenderService

        runner = FFmpegRunner(
            ffmpeg_bin=settings.ffmpeg_bin,
            ffprobe_bin=settings.ffprobe_bin,
        )
        _render_service = RenderService(
            get_project_service(),
            get_timeline_service(),
            get_media_service(),
            runner,
        )
    return _render_service


def get_metadata_service():
    global _metadata_service
    if _metadata_service is None:
        from montage_backend.config import settings
        from montage_backend.services.metadata_service import MetadataService

        media_service = get_media_service()
        _metadata_service = MetadataService(
            get_project_service(),
            worker_count=max(1, settings.worker_count // 2),
        )
        _metadata_service.wire_media_hooks(
            get_media_item=media_service.get_media_item,
            update_media_status=media_service.update_metadata_status,
        )
        media_service.set_metadata_enqueue(_metadata_service.enqueue_analysis)
    return _metadata_service


def get_analysis_service():
    global _analysis_service
    if _analysis_service is None:
        from montage_backend.config import settings
        from montage_backend.services.analysis_service import AnalysisService

        media_service = get_media_service()
        _analysis_service = AnalysisService(
            get_project_service(),
            worker_count=max(1, settings.worker_count // 2),
        )
        _analysis_service.wire_media_hooks(
            get_media_item=media_service.get_media_item,
        )
        media_service.set_analysis_enqueue(_analysis_service.enqueue_default_modules)
    return _analysis_service


def get_montage_plan_service():
    global _montage_plan_service
    if _montage_plan_service is None:
        from montage_backend.services.montage_plan_service import MontagePlanService

        analysis_service = get_analysis_service()
        media_service = get_media_service()
        _montage_plan_service = MontagePlanService(
            get_project_service(),
            timeline_service=get_timeline_service(),
        )
        _montage_plan_service.wire_analysis_hooks(
            get_clip_analysis=analysis_service.get_clip_analysis,
            list_project_media=media_service.list_media,
        )
    return _montage_plan_service
