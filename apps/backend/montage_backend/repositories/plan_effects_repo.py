from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.plan_effects import EFFECTS_ENGINE_VERSION, PlanEffectsAnalysis
from montage_backend.models.db.plan_effects_db import PlanEffectsRow


class PlanEffectsRepository:
    def row_to_analysis(self, row: PlanEffectsRow) -> PlanEffectsAnalysis:
        payload = json.loads(row.payload_json) if row.payload_json else {}
        return PlanEffectsAnalysis.model_validate(payload)

    async def get_for_plan(
        self,
        session: AsyncSession,
        plan_id: str,
        *,
        engine_version: str = EFFECTS_ENGINE_VERSION,
    ) -> PlanEffectsAnalysis | None:
        result = await session.execute(
            select(PlanEffectsRow).where(
                PlanEffectsRow.plan_id == plan_id,
                PlanEffectsRow.engine_version == engine_version,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_analysis(row)

    async def upsert(
        self,
        session: AsyncSession,
        analysis: PlanEffectsAnalysis,
    ) -> PlanEffectsAnalysis:
        result = await session.execute(
            select(PlanEffectsRow).where(
                PlanEffectsRow.plan_id == analysis.plan_id,
                PlanEffectsRow.engine_version == analysis.engine_version,
            ),
        )
        row = result.scalar_one_or_none()
        payload_json = analysis.model_dump_json()
        now = utc_now_iso()
        if row is None:
            row = PlanEffectsRow(
                id=new_uuid(),
                project_id=analysis.project_id,
                plan_id=analysis.plan_id,
                clip_count=analysis.clip_count,
                random_seed=analysis.random_seed,
                confidence=analysis.confidence,
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
            row.clip_count = analysis.clip_count
            row.random_seed = analysis.random_seed
            row.confidence = analysis.confidence
            row.reasoning = analysis.reasoning
            row.cache_key = analysis.cache_key
            row.payload_json = payload_json
            row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return self.row_to_analysis(row)

    async def delete_for_plan(self, session: AsyncSession, plan_id: str) -> None:
        await session.execute(delete(PlanEffectsRow).where(PlanEffectsRow.plan_id == plan_id))
        await session.commit()
