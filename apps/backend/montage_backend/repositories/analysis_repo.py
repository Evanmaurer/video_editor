from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.analysis import (
    AnalysisJobRecord,
    AnalysisModuleCacheRecord,
)
from montage_backend.models.domain.media import ProcessingStatus
from montage_backend.models.db.analysis_db import AnalysisJobRow, AnalysisModuleCacheRow


class AnalysisRepository:
    def cache_row_to_record(self, row: AnalysisModuleCacheRow) -> AnalysisModuleCacheRecord:
        return AnalysisModuleCacheRecord(
            id=row.id,
            media_id=row.media_id,
            module_id=row.module_id,
            analyzer_version=row.analyzer_version,
            cache_key=row.cache_key,
            status=ProcessingStatus(row.status),
            payload=json.loads(row.payload_json) if row.payload_json else {},
            confidence=row.confidence,
            reasoning=row.reasoning,
            source_fingerprint=row.source_fingerprint,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def job_row_to_record(self, row: AnalysisJobRow) -> AnalysisJobRecord:
        return AnalysisJobRecord(
            id=row.id,
            project_id=row.project_id,
            media_id=row.media_id,
            module_id=row.module_id,
            status=ProcessingStatus(row.status),
            progress=row.progress,
            message=row.message,
            error_message=row.error_message,
            cache_id=row.cache_id,
            priority=row.priority,
            retry_count=row.retry_count,
            max_retries=row.max_retries,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_cache(
        self,
        session: AsyncSession,
        media_id: str,
        module_id: str,
    ) -> AnalysisModuleCacheRecord | None:
        result = await session.execute(
            select(AnalysisModuleCacheRow).where(
                AnalysisModuleCacheRow.media_id == media_id,
                AnalysisModuleCacheRow.module_id == module_id,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.cache_row_to_record(row)

    async def list_caches_for_media(
        self,
        session: AsyncSession,
        media_id: str,
    ) -> list[AnalysisModuleCacheRecord]:
        result = await session.execute(
            select(AnalysisModuleCacheRow).where(AnalysisModuleCacheRow.media_id == media_id),
        )
        rows = result.scalars().all()
        return [self.cache_row_to_record(row) for row in rows]

    async def upsert_cache(
        self,
        session: AsyncSession,
        *,
        media_id: str,
        module_id: str,
        analyzer_version: str,
        cache_key: str,
        status: ProcessingStatus,
        payload: dict,
        source_fingerprint: str | None = None,
        confidence: float | None = None,
        reasoning: str | None = None,
    ) -> AnalysisModuleCacheRecord:
        result = await session.execute(
            select(AnalysisModuleCacheRow).where(
                AnalysisModuleCacheRow.media_id == media_id,
                AnalysisModuleCacheRow.module_id == module_id,
            ),
        )
        row = result.scalar_one_or_none()
        now = utc_now_iso()
        payload_json = json.dumps(payload)

        if row is None:
            row = AnalysisModuleCacheRow(
                id=new_uuid(),
                media_id=media_id,
                module_id=module_id,
                analyzer_version=analyzer_version,
                cache_key=cache_key,
                status=status.value,
                payload_json=payload_json,
                confidence=confidence,
                reasoning=reasoning,
                source_fingerprint=source_fingerprint,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.analyzer_version = analyzer_version
            row.cache_key = cache_key
            row.status = status.value
            row.payload_json = payload_json
            row.confidence = confidence
            row.reasoning = reasoning
            row.source_fingerprint = source_fingerprint
            row.updated_at = now

        await session.commit()
        await session.refresh(row)
        return self.cache_row_to_record(row)

    async def invalidate_cache(
        self,
        session: AsyncSession,
        media_id: str,
        module_id: str | None = None,
    ) -> None:
        stmt = delete(AnalysisModuleCacheRow).where(AnalysisModuleCacheRow.media_id == media_id)
        if module_id is not None:
            stmt = stmt.where(AnalysisModuleCacheRow.module_id == module_id)
        await session.execute(stmt)
        await session.commit()

    async def create_job(
        self,
        session: AsyncSession,
        job: AnalysisJobRecord,
        *,
        priority: int = 0,
    ) -> AnalysisJobRecord:
        row = AnalysisJobRow(
            id=job.id,
            project_id=job.project_id,
            media_id=job.media_id,
            module_id=job.module_id,
            status=job.status.value,
            progress=job.progress,
            message=job.message,
            error_message=job.error_message,
            cache_id=job.cache_id,
            priority=priority if priority else job.priority,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return self.job_row_to_record(row)

    async def update_job(
        self,
        session: AsyncSession,
        job_id: str,
        *,
        status: ProcessingStatus | None = None,
        progress: float | None = None,
        message: str | None = None,
        error_message: str | None = None,
        cache_id: str | None = None,
        priority: int | None = None,
        retry_count: int | None = None,
    ) -> AnalysisJobRecord | None:
        result = await session.execute(select(AnalysisJobRow).where(AnalysisJobRow.id == job_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if status is not None:
            row.status = status.value
        if progress is not None:
            row.progress = progress
        if message is not None:
            row.message = message
        if error_message is not None:
            row.error_message = error_message
        if cache_id is not None:
            row.cache_id = cache_id
        if priority is not None:
            row.priority = priority
        if retry_count is not None:
            row.retry_count = retry_count
        row.updated_at = utc_now_iso()
        await session.commit()
        await session.refresh(row)
        return self.job_row_to_record(row)

    async def get_job(self, session: AsyncSession, job_id: str) -> AnalysisJobRecord | None:
        result = await session.execute(select(AnalysisJobRow).where(AnalysisJobRow.id == job_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.job_row_to_record(row)

    async def get_active_job(
        self,
        session: AsyncSession,
        media_id: str,
        module_id: str,
    ) -> AnalysisJobRecord | None:
        result = await session.execute(
            select(AnalysisJobRow)
            .where(
                AnalysisJobRow.media_id == media_id,
                AnalysisJobRow.module_id == module_id,
                AnalysisJobRow.status.in_(
                    [
                        ProcessingStatus.PENDING.value,
                        ProcessingStatus.PROCESSING.value,
                        ProcessingStatus.PAUSED.value,
                    ],
                ),
            )
            .order_by(AnalysisJobRow.priority.desc(), AnalysisJobRow.created_at.desc()),
        )
        row = result.scalars().first()
        if row is None:
            return None
        return self.job_row_to_record(row)

    async def list_jobs_for_project(
        self,
        session: AsyncSession,
        project_id: str,
        *,
        limit: int = 100,
    ) -> list[AnalysisJobRecord]:
        result = await session.execute(
            select(AnalysisJobRow)
            .where(AnalysisJobRow.project_id == project_id)
            .order_by(AnalysisJobRow.priority.desc(), AnalysisJobRow.updated_at.desc())
            .limit(limit),
        )
        return [self.job_row_to_record(row) for row in result.scalars().all()]
