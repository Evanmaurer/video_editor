from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.plan_pacing import PACING_ENGINE_VERSION, PlanPacingAnalysis
from montage_backend.models.db.plan_pacing_db import PlanPacingRow


class PlanPacingRepository:
    def row_to_analysis(self, row: PlanPacingRow) -> PlanPacingAnalysis:
        payload = json.loads(row.payload_json) if row.payload_json else {}
        return PlanPacingAnalysis.model_validate(payload)

    async def get_for_plan(
        self,
        session: AsyncSession,
        plan_id: str,
        *,
        engine_version: str = PACING_ENGINE_VERSION,
    ) -> PlanPacingAnalysis | None:
        result = await session.execute(
            select(PlanPacingRow).where(
                PlanPacingRow.plan_id == plan_id,
                PlanPacingRow.engine_version == engine_version,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_analysis(row)

    async def upsert(
        self,
        session: AsyncSession,
        analysis: PlanPacingAnalysis,
    ) -> PlanPacingAnalysis:
        result = await session.execute(
            select(PlanPacingRow).where(
                PlanPacingRow.plan_id == analysis.plan_id,
                PlanPacingRow.engine_version == analysis.engine_version,
            ),
        )
        row = result.scalar_one_or_none()
        payload_json = analysis.model_dump_json()
        now = utc_now_iso()
        if row is None:
            row = PlanPacingRow(
                id=new_uuid(),
                project_id=analysis.project_id,
                plan_id=analysis.plan_id,
                pacing_profile=analysis.pacing_profile,
                target_duration_ms=analysis.target_duration_ms,
                total_duration_ms=analysis.total_duration_ms,
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
            row.pacing_profile = analysis.pacing_profile
            row.target_duration_ms = analysis.target_duration_ms
            row.total_duration_ms = analysis.total_duration_ms
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
        await session.execute(delete(PlanPacingRow).where(PlanPacingRow.plan_id == plan_id))
        await session.commit()
