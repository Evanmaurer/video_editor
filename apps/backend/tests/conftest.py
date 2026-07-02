import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from montage_backend.config import settings
from montage_backend.models.db.app_db import AppSettingRow, RecentProjectRow
from montage_backend.models.db.base import Base
from montage_backend.main import app
from montage_backend.services.project_service import AppSettingsService, ProjectService


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-Montage-Token": settings.auth_token}


@pytest_asyncio.fixture
async def test_app_engine(tmp_path, monkeypatch) -> AsyncEngine:
    monkeypatch.setattr(settings, "app_data_dir", tmp_path / "app_data")
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test_app.db'}")
    tables = [AppSettingRow.__table__, RecentProjectRow.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    return engine


@pytest_asyncio.fixture
async def client(test_app_engine, monkeypatch, auth_headers):
    from montage_backend import database
    from montage_backend.api import deps

    database.db_manager.app_engine = test_app_engine
    database.db_manager.app_session_factory = async_sessionmaker(
        test_app_engine, expire_on_commit=False, class_=AsyncSession
    )

    deps._project_service = ProjectService(database.db_manager.app_session_factory)
    deps._settings_service = AppSettingsService(database.db_manager.app_session_factory)
    deps._media_service = None
    deps._timeline_service = None
    deps._playback_service = None
    deps._render_service = None
    deps._metadata_service = None
    deps._analysis_service = None
    deps._montage_plan_service = None

    async def mock_startup():
        pass

    async def mock_shutdown():
        await test_app_engine.dispose()

    monkeypatch.setattr(database.db_manager, "startup", mock_startup)
    monkeypatch.setattr(database.db_manager, "shutdown", mock_shutdown)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as ac:
        yield ac
