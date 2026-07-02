from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import utc_now_iso
from montage_backend.models.domain.montage_plan import MontagePlan, MontagePlanStatus
from montage_backend.models.db.montage_plan_db import MontagePlanRow


class MontagePlanRepository:
    def plan_to_row(self, plan: MontagePlan) -> MontagePlanRow:
        payload = plan.model_dump(mode="json")
        return MontagePlanRow(
            id=plan.id,
            project_id=plan.project_id,
            name=plan.name,
            status=plan.status.value,
            version=plan.version,
            random_seed=plan.metadata.random_seed,
            generator_id=plan.metadata.generator_id,
            generator_version=plan.metadata.generator_version,
            overall_confidence=plan.overall_confidence,
            duration_ms=plan.duration_ms,
            payload_json=json.dumps(payload),
            applied_timeline_id=plan.applied_timeline_id,
            schema_version=plan.metadata.schema_version,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )

    def row_to_plan(self, row: MontagePlanRow) -> MontagePlan:
        return MontagePlan.model_validate(json.loads(row.payload_json))

    async def create(self, session: AsyncSession, plan: MontagePlan) -> MontagePlan:
        row = self.plan_to_row(plan)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return self.row_to_plan(row)

    async def get(self, session: AsyncSession, plan_id: str) -> MontagePlan | None:
        result = await session.execute(select(MontagePlanRow).where(MontagePlanRow.id == plan_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_plan(row)

    async def list_for_project(
        self,
        session: AsyncSession,
        project_id: str,
        *,
        limit: int = 100,
    ) -> list[MontagePlan]:
        result = await session.execute(
            select(MontagePlanRow)
            .where(MontagePlanRow.project_id == project_id)
            .order_by(MontagePlanRow.updated_at.desc())
            .limit(limit),
        )
        return [self.row_to_plan(row) for row in result.scalars().all()]

    async def update(self, session: AsyncSession, plan: MontagePlan) -> MontagePlan:
        result = await session.execute(select(MontagePlanRow).where(MontagePlanRow.id == plan.id))
        row = result.scalar_one_or_none()
        if row is None:
            return plan
        updated = self.plan_to_row(plan)
        row.name = updated.name
        row.status = updated.status
        row.version = updated.version
        row.random_seed = updated.random_seed
        row.generator_id = updated.generator_id
        row.generator_version = updated.generator_version
        row.overall_confidence = updated.overall_confidence
        row.duration_ms = updated.duration_ms
        row.payload_json = updated.payload_json
        row.applied_timeline_id = updated.applied_timeline_id
        row.schema_version = updated.schema_version
        row.updated_at = utc_now_iso()
        await session.commit()
        await session.refresh(row)
        return self.row_to_plan(row)

    async def delete(self, session: AsyncSession, plan_id: str) -> None:
        await session.execute(delete(MontagePlanRow).where(MontagePlanRow.id == plan_id))
        await session.commit()

    async def get_by_status(
        self,
        session: AsyncSession,
        project_id: str,
        status: MontagePlanStatus,
    ) -> list[MontagePlan]:
        result = await session.execute(
            select(MontagePlanRow).where(
                MontagePlanRow.project_id == project_id,
                MontagePlanRow.status == status.value,
            ),
        )
        return [self.row_to_plan(row) for row in result.scalars().all()]
