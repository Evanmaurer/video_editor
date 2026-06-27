from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import (
    AppSettings,
    Project,
    ProjectSettings,
    ProjectSummary,
    utc_now_iso,
)
from montage_backend.models.db.app_db import AppSettingRow, RecentProjectRow
from montage_backend.models.db.project_db import ProjectRow


class AppSettingsRepository:
    SETTINGS_KEY = "app_settings"

    async def get_settings(self, session: AsyncSession) -> AppSettings:
        result = await session.execute(
            select(AppSettingRow).where(AppSettingRow.key == self.SETTINGS_KEY)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return AppSettings()
        return AppSettings.model_validate_json(row.value_json)

    async def save_settings(self, session: AsyncSession, app_settings: AppSettings) -> AppSettings:
        now = utc_now_iso()
        result = await session.execute(
            select(AppSettingRow).where(AppSettingRow.key == self.SETTINGS_KEY)
        )
        row = result.scalar_one_or_none()
        payload = app_settings.model_dump_json()
        if row is None:
            session.add(
                AppSettingRow(key=self.SETTINGS_KEY, value_json=payload, updated_at=now)
            )
        else:
            row.value_json = payload
            row.updated_at = now
        await session.commit()
        return app_settings


class RecentProjectsRepository:
    async def list_recent(self, session: AsyncSession, limit: int = 10) -> list[ProjectSummary]:
        result = await session.execute(
            select(RecentProjectRow).order_by(RecentProjectRow.updated_at.desc()).limit(limit)
        )
        rows = result.scalars().all()
        return [
            ProjectSummary(id=r.id, name=r.name, path=r.path, updated_at=r.updated_at)
            for r in rows
        ]

    async def upsert(
        self, session: AsyncSession, project_id: str, name: str, path: str
    ) -> None:
        now = utc_now_iso()
        result = await session.execute(
            select(RecentProjectRow).where(RecentProjectRow.path == path)
        )
        row = result.scalar_one_or_none()
        if row is None:
            session.add(
                RecentProjectRow(id=project_id, name=name, path=path, updated_at=now)
            )
        else:
            row.id = project_id
            row.name = name
            row.updated_at = now
        await session.commit()


class ProjectRepository:
    def row_to_project(self, row: ProjectRow) -> Project:
        settings = ProjectSettings.model_validate_json(row.settings_json)
        return Project(
            id=row.id,
            name=row.name,
            root_path=row.root_path,
            width=row.width,
            height=row.height,
            frame_rate=row.frame_rate,
            target_game=row.target_game,
            settings=settings,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_by_root_path(self, session: AsyncSession, root_path: str) -> Project | None:
        result = await session.execute(
            select(ProjectRow).where(ProjectRow.root_path == root_path)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_project(row)

    async def create(self, session: AsyncSession, project: Project) -> Project:
        row = ProjectRow(
            id=project.id,
            name=project.name,
            root_path=project.root_path,
            width=project.width,
            height=project.height,
            frame_rate=project.frame_rate,
            target_game=project.target_game,
            settings_json=project.settings.model_dump_json(),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
        session.add(row)
        await session.commit()
        return project

    async def update(self, session: AsyncSession, project: Project) -> Project:
        result = await session.execute(
            select(ProjectRow).where(ProjectRow.id == project.id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"Project {project.id} not found")
        row.name = project.name
        row.settings_json = project.settings.model_dump_json()
        row.updated_at = project.updated_at
        await session.commit()
        return project


def write_project_manifest(project: Project, root: Path) -> None:
    manifest = {
        "id": project.id,
        "name": project.name,
        "version": "1.0",
        "schema_version": 1,
    }
    (root / "project.json").write_text(json.dumps(manifest, indent=2))


def create_project_directories(root: Path) -> None:
    for subdir in ("media/originals", "media/proxies", "thumbnails", "analysis", "timelines", "exports", "cache", "logs"):
        (root / subdir).mkdir(parents=True, exist_ok=True)


def is_valid_project_path(path: Path) -> bool:
    return path.is_dir() and ((path / "project.json").exists() or (path / "project.db").exists())


def detect_gpu() -> tuple[bool, str | None]:
    """Detect GPU availability without requiring GPU for the app."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and "Chipset Model" in result.stdout:
            for line in result.stdout.splitlines():
                if "Chipset Model:" in line:
                    name = line.split(":", 1)[1].strip()
                    if name and "Intel" not in name:
                        return True, name
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return False, None
