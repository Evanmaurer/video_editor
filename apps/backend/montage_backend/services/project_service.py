from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from montage_backend.database import (
    create_project_engine,
    init_project_db,
)
from montage_backend.logging import get_logger
from montage_backend.models.domain import (
    CreateProjectRequest,
    GpuInfo,
    InvalidProjectError,
    Project,
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    ProjectSettings,
    ProjectSummary,
    new_uuid,
    utc_now_iso,
)
from montage_backend.repositories.project_repo import (
    AppSettingsRepository,
    ProjectRepository,
    RecentProjectsRepository,
    create_project_directories,
    detect_gpu,
    is_valid_project_path,
    write_project_manifest,
)

logger = get_logger(__name__)


class ProjectService:
    def __init__(
        self,
        app_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._app_session_factory = app_session_factory
        self._project_repo = ProjectRepository()
        self._recent_repo = RecentProjectsRepository()
        self._settings_repo = AppSettingsRepository()
        self._project_engines: dict[str, AsyncEngine] = {}

    def _get_project_engine(self, root_path: Path) -> AsyncEngine:
        key = str(root_path.resolve())
        if key not in self._project_engines:
            engine = create_project_engine(root_path)
            self._project_engines[key] = engine
        return self._project_engines[key]

    async def _ensure_project_db(self, root_path: Path) -> async_sessionmaker[AsyncSession]:
        engine = self._get_project_engine(root_path)
        await init_project_db(engine)
        return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def create_project(self, request: CreateProjectRequest) -> Project:
        root = Path(request.root_path).resolve()

        if root.exists():
            if is_valid_project_path(root):
                raise ProjectAlreadyExistsError(f"Project already exists at {root}")
            if any(root.iterdir()):
                raise ProjectAlreadyExistsError(
                    f"Directory already exists and is not empty: {root}",
                )
        else:
            root.mkdir(parents=True, exist_ok=True)

        now = utc_now_iso()
        settings = request.settings or ProjectSettings()
        project = Project(
            id=new_uuid(),
            name=request.name,
            root_path=str(root),
            width=request.width,
            height=request.height,
            frame_rate=request.frame_rate,
            target_game=request.target_game,
            settings=settings,
            created_at=now,
            updated_at=now,
        )

        create_project_directories(root)
        session_factory = await self._ensure_project_db(root)
        async with session_factory() as session:
            existing = await self._project_repo.get_by_root_path(session, str(root))
            if existing is not None:
                raise ProjectAlreadyExistsError(f"Project already exists at {root}")
            await self._project_repo.create(session, project)

        write_project_manifest(project, root)
        (root / "timelines").mkdir(exist_ok=True)

        async with self._app_session_factory() as app_session:
            await self._recent_repo.upsert(
                app_session, project.id, project.name, project.root_path
            )

        logger.info("project_created", project_id=project.id, root_path=project.root_path)
        return project

    async def open_project(self, path: str) -> Project:
        root = Path(path).resolve()
        if not is_valid_project_path(root):
            raise InvalidProjectError(f"Not a valid MontageAI project: {root}")

        session_factory = await self._ensure_project_db(root)
        async with session_factory() as session:
            project = await self._project_repo.get_by_root_path(session, str(root))
            if project is None:
                raise ProjectNotFoundError(f"Project metadata not found in {root}")

        async with self._app_session_factory() as app_session:
            await self._recent_repo.upsert(
                app_session, project.id, project.name, project.root_path
            )

        logger.info("project_opened", project_id=project.id)
        return project

    async def get_project(self, project_id: str) -> Project:
        async with self._app_session_factory() as app_session:
            recents = await self._recent_repo.list_recent(app_session, limit=100)
        for summary in recents:
            root = Path(summary.path)
            session_factory = await self._ensure_project_db(root)
            async with session_factory() as session:
                project = await self._project_repo.get_by_root_path(session, str(root))
                if project is not None and project.id == project_id:
                    return project
        raise ProjectNotFoundError(f"Project not found: {project_id}")

    async def save_project(self, project: Project) -> Project:
        root = Path(project.root_path).resolve()
        project.updated_at = utc_now_iso()
        session_factory = await self._ensure_project_db(root)
        async with session_factory() as session:
            await self._project_repo.update(session, project)

        write_project_manifest(project, root)
        async with self._app_session_factory() as app_session:
            await self._recent_repo.upsert(
                app_session, project.id, project.name, project.root_path
            )

        logger.info("project_saved", project_id=project.id)
        return project

    async def close_project(self, project_id: str) -> None:
        logger.info("project_closed", project_id=project_id)

    async def get_recent_projects(self) -> list[ProjectSummary]:
        async with self._app_session_factory() as app_session:
            recents = await self._recent_repo.list_recent(app_session)
        valid: list[ProjectSummary] = []
        for summary in recents:
            if is_valid_project_path(Path(summary.path)):
                valid.append(summary)
        return valid

    def get_gpu_info(self, gpu_enabled: bool) -> GpuInfo:
        available, name = detect_gpu()
        if available and gpu_enabled:
            return GpuInfo(
                available=True,
                name=name,
                estimated_speedup="3-5x faster than CPU",
                cpu_only_warning=None,
            )
        warning = (
            "No compatible GPU detected. Analysis and rendering will use CPU only "
            "and may take 3-5x longer. All features remain available."
        )
        if not gpu_enabled:
            warning = (
                "GPU acceleration is disabled in settings. Analysis and rendering "
                "will use CPU only and may take 3-5x longer."
            )
        return GpuInfo(
            available=False,
            name=name,
            estimated_speedup="1x (CPU only)",
            cpu_only_warning=warning,
        )


class AppSettingsService:
    def __init__(self, app_session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._app_session_factory = app_session_factory
        self._repo = AppSettingsRepository()

    async def get_settings(self) -> AppSettings:
        from montage_backend.models.domain import AppSettings

        async with self._app_session_factory() as session:
            return await self._repo.get_settings(session)

    async def update_settings(self, updates: dict[str, object]) -> AppSettings:
        from montage_backend.models.domain import AppSettings

        async with self._app_session_factory() as session:
            current = await self._repo.get_settings(session)
            merged = AppSettings.model_validate(
                {**current.model_dump(), **updates},
            )
            return await self._repo.save_settings(session, merged)
