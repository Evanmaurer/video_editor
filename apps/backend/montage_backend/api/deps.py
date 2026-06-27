from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.database import db_manager
from montage_backend.services.llm_service import llm_service
from montage_backend.services.project_service import AppSettingsService, ProjectService

_project_service: ProjectService | None = None
_settings_service: AppSettingsService | None = None


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
