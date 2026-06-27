from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from montage_backend.config import settings
from montage_backend.models.db.app_db import AppSettingRow, RecentProjectRow
from montage_backend.models.db.base import Base


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
    from montage_backend.models.db.project_db import ProjectRow

    tables = [ProjectRow.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))


class DatabaseManager:
    def __init__(self) -> None:
        self.app_engine = create_app_engine()
        self.app_session_factory = async_sessionmaker(
            self.app_engine, expire_on_commit=False, class_=AsyncSession
        )

    async def startup(self) -> None:
        await init_app_db(self.app_engine)

    async def shutdown(self) -> None:
        await self.app_engine.dispose()

    async def get_app_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.app_session_factory() as session:
            yield session


db_manager = DatabaseManager()

# Ensure metadata includes all app tables
_ = (AppSettingRow, RecentProjectRow)
