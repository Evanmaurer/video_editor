from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from montage_backend.config import settings
from montage_backend.models.db.app_db import AppSettingRow, RecentProjectRow
from montage_backend.models.db.base import Base

_ = (AppSettingRow, RecentProjectRow)


def get_app_db_path() -> Path:
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    return settings.app_data_dir / "app.db"


def create_app_engine() -> AsyncEngine:
    db_path = get_app_db_path()
    return create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )


async def init_app_db(engine: AsyncEngine) -> None:
    tables = [AppSettingRow.__table__, RecentProjectRow.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))


def get_project_db_url(project_path: Path) -> str:
    return f"sqlite+aiosqlite:///{project_path / 'project.db'}"


def create_project_engine(project_root: Path) -> AsyncEngine:
    return create_async_engine(get_project_db_url(project_root), echo=False)


async def init_project_db(engine: AsyncEngine) -> None:
    from montage_backend.database_migrations import migrate_media_items_schema
    from montage_backend.models.db.media_db import MediaItemRow
    from montage_backend.models.db.metadata_db import MediaMetadataFeatureRow
    from montage_backend.models.db.project_db import ProjectRow
    from montage_backend.models.db.timeline_db import TimelineRow

    tables = [
        ProjectRow.__table__,
        MediaItemRow.__table__,
        MediaMetadataFeatureRow.__table__,
        TimelineRow.__table__,
    ]

    def setup(sync_conn) -> None:
        Base.metadata.create_all(sync_conn, tables=tables)
        migrate_media_items_schema(sync_conn)

    async with engine.begin() as conn:
        await conn.run_sync(setup)


class DatabaseManager:
    def __init__(self) -> None:
        self._app_engine: AsyncEngine | None = None
        self._app_session_factory: async_sessionmaker[AsyncSession] | None = None
        self._started = False
        self._startup_lock = asyncio.Lock()

    @property
    def app_engine(self) -> AsyncEngine:
        if self._app_engine is None:
            self._app_engine = create_app_engine()
        return self._app_engine

    @app_engine.setter
    def app_engine(self, engine: AsyncEngine) -> None:
        self._app_engine = engine
        self._app_session_factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        self._started = False

    @property
    def app_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._app_session_factory is None:
            self._app_session_factory = async_sessionmaker(
                self.app_engine, expire_on_commit=False, class_=AsyncSession
            )
        return self._app_session_factory

    @app_session_factory.setter
    def app_session_factory(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._app_session_factory = factory

    async def ensure_started(self) -> None:
        if self._started:
            return
        async with self._startup_lock:
            if self._started:
                return
            await init_app_db(self.app_engine)
            self._started = True

    async def startup(self) -> None:
        await self.ensure_started()

    async def shutdown(self) -> None:
        if self._app_engine is not None:
            await self._app_engine.dispose()
            self._app_engine = None
            self._app_session_factory = None
            self._started = False

    async def get_app_session(self) -> AsyncGenerator[AsyncSession, None]:
        await self.ensure_started()
        async with self.app_session_factory() as session:
            yield session


db_manager = DatabaseManager()
