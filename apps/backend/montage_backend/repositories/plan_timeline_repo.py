from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.plan_timeline import TIMELINE_GENERATOR_VERSION, PlanTimelineApplication
from montage_backend.models.db.plan_timeline_db import PlanTimelineRow


class PlanTimelineRepository:
    def row_to_application(self, row: PlanTimelineRow) -> PlanTimelineApplication:
        payload = json.loads(row.payload_json) if row.payload_json else {}
        return PlanTimelineApplication.model_validate(payload)

    async def get_for_plan(
        self,
        session: AsyncSession,
        plan_id: str,
        *,
        engine_version: str = TIMELINE_GENERATOR_VERSION,
    ) -> PlanTimelineApplication | None:
        result = await session.execute(
            select(PlanTimelineRow).where(
                PlanTimelineRow.plan_id == plan_id,
                PlanTimelineRow.engine_version == engine_version,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_application(row)

    async def upsert(
        self,
        session: AsyncSession,
        application: PlanTimelineApplication,
    ) -> PlanTimelineApplication:
        result = await session.execute(
            select(PlanTimelineRow).where(
                PlanTimelineRow.plan_id == application.plan_id,
                PlanTimelineRow.engine_version == application.engine_version,
            ),
        )
        row = result.scalar_one_or_none()
        payload_json = application.model_dump_json()
        now = utc_now_iso()
        if row is None:
            row = PlanTimelineRow(
                id=new_uuid(),
                project_id=application.project_id,
                plan_id=application.plan_id,
                timeline_id=application.timeline_id,
                plan_version=application.plan_version,
                clip_count=application.clip_count,
                duration_ms=application.duration_ms,
                random_seed=0,
                confidence=application.confidence,
                reasoning=application.reasoning,
                engine_version=application.engine_version,
                cache_key=application.cache_key,
                payload_json=payload_json,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.project_id = application.project_id
            row.timeline_id = application.timeline_id
            row.plan_version = application.plan_version
            row.clip_count = application.clip_count
            row.duration_ms = application.duration_ms
            row.confidence = application.confidence
            row.reasoning = application.reasoning
            row.cache_key = application.cache_key
            row.payload_json = payload_json
            row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return self.row_to_application(row)

    async def delete_for_plan(self, session: AsyncSession, plan_id: str) -> None:
        await session.execute(delete(PlanTimelineRow).where(PlanTimelineRow.plan_id == plan_id))
        await session.commit()
