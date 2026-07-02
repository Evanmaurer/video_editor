from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.plan_feedback import (
    FEEDBACK_ENGINE_VERSION,
    PlanFeedbackEvent,
    PlanQualityAnalysis,
)
from montage_backend.models.db.plan_feedback_db import PlanFeedbackEventRow, PlanQualityRow


class PlanQualityRepository:
    def row_to_analysis(self, row: PlanQualityRow) -> PlanQualityAnalysis:
        payload = json.loads(row.payload_json) if row.payload_json else {}
        return PlanQualityAnalysis.model_validate(payload)

    async def get_for_plan(
        self,
        session: AsyncSession,
        plan_id: str,
        *,
        engine_version: str = FEEDBACK_ENGINE_VERSION,
    ) -> PlanQualityAnalysis | None:
        result = await session.execute(
            select(PlanQualityRow).where(
                PlanQualityRow.plan_id == plan_id,
                PlanQualityRow.engine_version == engine_version,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_analysis(row)

    async def upsert(
        self,
        session: AsyncSession,
        analysis: PlanQualityAnalysis,
    ) -> PlanQualityAnalysis:
        result = await session.execute(
            select(PlanQualityRow).where(
                PlanQualityRow.plan_id == analysis.plan_id,
                PlanQualityRow.engine_version == analysis.engine_version,
            ),
        )
        row = result.scalar_one_or_none()
        payload_json = analysis.model_dump_json()
        now = utc_now_iso()
        if row is None:
            row = PlanQualityRow(
                id=new_uuid(),
                project_id=analysis.project_id,
                plan_id=analysis.plan_id,
                plan_version=analysis.plan_version,
                overall_score=analysis.overall_score,
                confidence=analysis.overall_confidence,
                reasoning=analysis.reasoning,
                engine_version=analysis.engine_version,
                cache_key=analysis.cache_key,
                payload_json=payload_json,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.project_id = analysis.project_id
            row.plan_version = analysis.plan_version
            row.overall_score = analysis.overall_score
            row.confidence = analysis.overall_confidence
            row.reasoning = analysis.reasoning
            row.cache_key = analysis.cache_key
            row.payload_json = payload_json
            row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return self.row_to_analysis(row)

    async def delete_for_plan(self, session: AsyncSession, plan_id: str) -> None:
        await session.execute(delete(PlanQualityRow).where(PlanQualityRow.plan_id == plan_id))
        await session.commit()


class PlanFeedbackRepository:
    def row_to_event(self, row: PlanFeedbackEventRow) -> PlanFeedbackEvent:
        applied_changes = json.loads(row.applied_changes_json) if row.applied_changes_json else {}
        return PlanFeedbackEvent(
            id=row.id,
            plan_id=row.plan_id,
            project_id=row.project_id,
            action=row.action,
            comment=row.comment,
            applied_changes=applied_changes,
            created_at=row.created_at,
        )

    async def list_for_plan(self, session: AsyncSession, plan_id: str) -> list[PlanFeedbackEvent]:
        result = await session.execute(
            select(PlanFeedbackEventRow)
            .where(PlanFeedbackEventRow.plan_id == plan_id)
            .order_by(PlanFeedbackEventRow.created_at.asc()),
        )
        return [self.row_to_event(row) for row in result.scalars().all()]

    async def create(self, session: AsyncSession, event: PlanFeedbackEvent) -> PlanFeedbackEvent:
        row = PlanFeedbackEventRow(
            id=event.id,
            project_id=event.project_id,
            plan_id=event.plan_id,
            action=event.action.value if hasattr(event.action, "value") else str(event.action),
            comment=event.comment,
            applied_changes_json=json.dumps(event.applied_changes),
            created_at=event.created_at,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return self.row_to_event(row)

    async def delete_for_plan(self, session: AsyncSession, plan_id: str) -> None:
        await session.execute(delete(PlanFeedbackEventRow).where(PlanFeedbackEventRow.plan_id == plan_id))
        await session.commit()
