from __future__ import annotations

from pathlib import Path

from sqlalchemy import update

from montage_backend.logging import get_logger
from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.timeline import (
    CreateTimelineRequest,
    SaveTimelineResponse,
    TimelineDocument,
    TimelineNotFoundError,
    TimelineSummary,
    default_timeline_document,
)
from montage_backend.models.db.timeline_db import TimelineRow
from montage_backend.repositories.timeline_repo import TimelineRepository
from montage_backend.services.project_service import ProjectService

logger = get_logger(__name__)


class TimelineService:
    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service
        self._repo = TimelineRepository()

    async def _session_for_project(self, project_id: str):
        project = await self._project_service.get_project(project_id)
        project_root = Path(project.root_path)
        session_factory = await self._project_service._ensure_project_db(project_root)
        return project, project_root, session_factory

    async def list_timelines(self, project_id: str) -> list[TimelineSummary]:
        _, _, session_factory = await self._session_for_project(project_id)
        async with session_factory() as session:
            rows = await self._repo.list_for_project(session, project_id)
            return [self._repo.row_to_summary(row) for row in rows]

    async def get_or_create_active(self, project_id: str) -> TimelineDocument:
        project, project_root, session_factory = await self._session_for_project(project_id)

        async with session_factory() as session:
            active = await self._repo.get_active(session, project_id)
            if active is not None:
                doc = self._repo.read_document_if_exists(Path(active.file_path))
                if doc is not None:
                    return doc

            return await self._create_timeline_internal(
                session,
                project_id,
                project_root,
                project.width,
                project.height,
                project.frame_rate,
                CreateTimelineRequest(name="Main"),
                set_active=True,
            )

    async def create_timeline(
        self,
        project_id: str,
        request: CreateTimelineRequest,
    ) -> TimelineDocument:
        project, project_root, session_factory = await self._session_for_project(project_id)

        async with session_factory() as session:
            return await self._create_timeline_internal(
                session,
                project_id,
                project_root,
                project.width,
                project.height,
                project.frame_rate,
                request,
                set_active=False,
            )

    async def get_timeline(self, project_id: str, timeline_id: str) -> TimelineDocument:
        _, project_root, session_factory = await self._session_for_project(project_id)

        async with session_factory() as session:
            row = await self._repo.get_by_id(session, timeline_id)
            if row is None or row.project_id != project_id:
                raise TimelineNotFoundError(f"Timeline not found: {timeline_id}")

        doc = self._repo.read_document_if_exists(Path(row.file_path))
        if doc is None:
            raise TimelineNotFoundError(f"Timeline file missing: {timeline_id}")
        return doc

    async def save_timeline(self, project_id: str, document: TimelineDocument) -> SaveTimelineResponse:
        _, project_root, session_factory = await self._session_for_project(project_id)

        async with session_factory() as session:
            row = await self._repo.get_by_id(session, document.id)
            if row is None or row.project_id != project_id:
                raise TimelineNotFoundError(f"Timeline not found: {document.id}")

            document.version = row.version + 1
            document.updated_at = utc_now_iso()
            document.project_id = project_id

            file_path = self._repo.write_document(project_root, document)

            row.duration_ms = document.duration_ms
            row.version = document.version
            row.updated_at = document.updated_at
            row.file_path = str(file_path)
            row.name = document.name
            await self._repo.update_row(session, row)

        logger.info("timeline_saved", timeline_id=document.id, version=document.version)
        return SaveTimelineResponse(
            id=document.id,
            version=document.version,
            updated_at=document.updated_at,
        )

    async def _create_timeline_internal(
        self,
        session,
        project_id: str,
        project_root: Path,
        width: int,
        height: int,
        frame_rate: float,
        request: CreateTimelineRequest,
        *,
        set_active: bool,
    ) -> TimelineDocument:
        document = default_timeline_document(
            project_id=project_id,
            width=width,
            height=height,
            frame_rate=frame_rate,
            name=request.name,
        )
        file_path = self._repo.write_document(project_root, document)
        now = utc_now_iso()

        if set_active:
            await session.execute(
                update(TimelineRow)
                .where(TimelineRow.project_id == project_id)
                .values(is_active=0),
            )

        row = TimelineRow(
            id=document.id,
            project_id=project_id,
            name=document.name,
            file_path=str(file_path),
            duration_ms=0,
            is_active=1 if set_active else 0,
            version=document.version,
            created_at=now,
            updated_at=now,
        )
        await self._repo.create(session, row)
        return document
