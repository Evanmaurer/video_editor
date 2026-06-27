from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.timeline import TimelineDocument, TimelineSummary
from montage_backend.models.db.timeline_db import TimelineRow


class TimelineRepository:
    def row_to_summary(self, row: TimelineRow) -> TimelineSummary:
        return TimelineSummary(
            id=row.id,
            project_id=row.project_id,
            name=row.name,
            duration_ms=row.duration_ms or 0,
            is_active=bool(row.is_active),
            version=row.version,
            updated_at=row.updated_at,
        )

    async def get_by_id(self, session: AsyncSession, timeline_id: str) -> TimelineRow | None:
        result = await session.execute(select(TimelineRow).where(TimelineRow.id == timeline_id))
        return result.scalar_one_or_none()

    async def get_active(self, session: AsyncSession, project_id: str) -> TimelineRow | None:
        result = await session.execute(
            select(TimelineRow)
            .where(TimelineRow.project_id == project_id, TimelineRow.is_active == 1)
            .limit(1),
        )
        return result.scalar_one_or_none()

    async def list_for_project(self, session: AsyncSession, project_id: str) -> list[TimelineRow]:
        result = await session.execute(
            select(TimelineRow)
            .where(TimelineRow.project_id == project_id)
            .order_by(TimelineRow.created_at.asc()),
        )
        return list(result.scalars().all())

    async def create(self, session: AsyncSession, row: TimelineRow) -> TimelineRow:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row

    async def update_row(self, session: AsyncSession, row: TimelineRow) -> TimelineRow:
        await session.commit()
        await session.refresh(row)
        return row

    async def set_active(self, session: AsyncSession, project_id: str, timeline_id: str) -> None:
        await session.execute(
            update(TimelineRow)
            .where(TimelineRow.project_id == project_id)
            .values(is_active=0),
        )
        await session.execute(
            update(TimelineRow).where(TimelineRow.id == timeline_id).values(is_active=1),
        )
        await session.commit()

    def timeline_file_path(self, project_root: Path, timeline_id: str) -> Path:
        return project_root / "timelines" / f"{timeline_id}.timeline.json"

    def write_document(self, project_root: Path, document: TimelineDocument) -> Path:
        path = self.timeline_file_path(project_root, document.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document.model_dump_json(indent=2))
        return path

    def read_document(self, file_path: Path) -> TimelineDocument:
        return TimelineDocument.model_validate_json(file_path.read_text())

    def read_document_if_exists(self, file_path: Path) -> TimelineDocument | None:
        if not file_path.is_file():
            return None
        try:
            return self.read_document(file_path)
        except (json.JSONDecodeError, ValueError):
            return None
