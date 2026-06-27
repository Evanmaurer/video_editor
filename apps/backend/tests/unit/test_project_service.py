import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from montage_backend.models.domain import CreateProjectRequest, ProjectSettings
from montage_backend.repositories.project_repo import is_valid_project_path
from montage_backend.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_create_and_open_project(test_app_engine, tmp_path):
    session_factory = async_sessionmaker(test_app_engine, expire_on_commit=False, class_=AsyncSession)
    service = ProjectService(session_factory)

    project_root = tmp_path / "TestProject"
    request = CreateProjectRequest(
        name="Test Montage",
        root_path=str(project_root),
        width=1920,
        height=1080,
        frame_rate=60.0,
        settings=ProjectSettings(auto_analyze_on_import=False),
    )

    created = await service.create_project(request)
    assert created.name == "Test Montage"
    assert created.id
    assert is_valid_project_path(project_root)
    assert (project_root / "project.json").exists()
    assert (project_root / "project.db").exists()
    assert (project_root / "media" / "proxies").is_dir()

    opened = await service.open_project(str(project_root))
    assert opened.id == created.id
    assert opened.name == "Test Montage"


@pytest.mark.asyncio
async def test_save_project_updates_timestamp(test_app_engine, tmp_path):
    session_factory = async_sessionmaker(test_app_engine, expire_on_commit=False, class_=AsyncSession)
    service = ProjectService(session_factory)

    project_root = tmp_path / "SaveTest"
    created = await service.create_project(
        CreateProjectRequest(name="Save Test", root_path=str(project_root))
    )
    original_updated = created.updated_at

    created.name = "Renamed Project"
    saved = await service.save_project(created)
    assert saved.name == "Renamed Project"
    assert saved.updated_at >= original_updated


@pytest.mark.asyncio
async def test_recent_projects_list(test_app_engine, tmp_path):
    session_factory = async_sessionmaker(test_app_engine, expire_on_commit=False, class_=AsyncSession)
    service = ProjectService(session_factory)

    root = tmp_path / "RecentTest"
    await service.create_project(CreateProjectRequest(name="Recent", root_path=str(root)))

    recents = await service.get_recent_projects()
    assert len(recents) >= 1
    assert any(r.path == str(root.resolve()) for r in recents)


def test_gpu_info_cpu_fallback():
    session_factory = async_sessionmaker(None)  # type: ignore[arg-type]
    service = ProjectService(session_factory)
    info = service.get_gpu_info(gpu_enabled=True)
    assert info.estimated_speedup
    if not info.available:
        assert info.cpu_only_warning is not None
