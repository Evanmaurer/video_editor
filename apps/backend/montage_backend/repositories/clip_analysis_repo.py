from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.clip_analysis import ClipAnalysisSummary
from montage_backend.models.db.clip_analysis_db import ClipAnalysisSnapshotRow


class ClipAnalysisRepository:
    def summary_to_row(
        self,
        *,
        project_id: str,
        summary: ClipAnalysisSummary,
        row_id: str | None = None,
        created_at: str | None = None,
    ) -> ClipAnalysisSnapshotRow:
        return ClipAnalysisSnapshotRow(
            id=row_id or new_uuid(),
            project_id=project_id,
            media_id=summary.media_id,
            overall_status=summary.overall_status.value,
            readiness=summary.readiness,
            source_fingerprint=summary.source_fingerprint,
            schema_version=summary.versions.schema_version,
            summary_json=summary.model_dump_json(),
            created_at=created_at or summary.created_at,
            updated_at=summary.updated_at,
        )

    def row_to_summary(self, row: ClipAnalysisSnapshotRow) -> ClipAnalysisSummary:
        return ClipAnalysisSummary.model_validate(json.loads(row.summary_json))

    async def get_for_media(
        self,
        session: AsyncSession,
        media_id: str,
    ) -> ClipAnalysisSummary | None:
        result = await session.execute(
            select(ClipAnalysisSnapshotRow).where(ClipAnalysisSnapshotRow.media_id == media_id),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_summary(row)

    async def list_for_project(
        self,
        session: AsyncSession,
        project_id: str,
    ) -> list[ClipAnalysisSummary]:
        result = await session.execute(
            select(ClipAnalysisSnapshotRow)
            .where(ClipAnalysisSnapshotRow.project_id == project_id)
            .order_by(ClipAnalysisSnapshotRow.updated_at.desc()),
        )
        rows = result.scalars().all()
        return [self.row_to_summary(row) for row in rows]

    async def upsert_summary(
        self,
        session: AsyncSession,
        *,
        project_id: str,
        summary: ClipAnalysisSummary,
    ) -> ClipAnalysisSummary:
        result = await session.execute(
            select(ClipAnalysisSnapshotRow).where(ClipAnalysisSnapshotRow.media_id == summary.media_id),
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = self.summary_to_row(project_id=project_id, summary=summary)
            session.add(row)
        else:
            row.project_id = project_id
            row.overall_status = summary.overall_status.value
            row.readiness = summary.readiness
            row.source_fingerprint = summary.source_fingerprint
            row.schema_version = summary.versions.schema_version
            row.summary_json = summary.model_dump_json()
            row.updated_at = summary.updated_at
        await session.commit()
        await session.refresh(row)
        return self.row_to_summary(row)

    async def delete_for_media(self, session: AsyncSession, media_id: str) -> None:
        await session.execute(
            delete(ClipAnalysisSnapshotRow).where(ClipAnalysisSnapshotRow.media_id == media_id),
        )
        await session.commit()
