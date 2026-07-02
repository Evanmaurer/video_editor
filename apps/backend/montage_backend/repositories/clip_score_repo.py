from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.clip_score import CLIP_SCORER_VERSION, ClipScore
from montage_backend.models.db.clip_score_db import ClipScoreRow


class ClipScoreRepository:
    def row_to_score(self, row: ClipScoreRow) -> ClipScore:
        payload = json.loads(row.payload_json) if row.payload_json else {}
        return ClipScore.model_validate(payload)

    async def get_for_media(
        self,
        session: AsyncSession,
        media_id: str,
        *,
        scorer_version: str = CLIP_SCORER_VERSION,
    ) -> ClipScore | None:
        result = await session.execute(
            select(ClipScoreRow).where(
                ClipScoreRow.media_id == media_id,
                ClipScoreRow.scorer_version == scorer_version,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_score(row)

    async def list_for_project(
        self,
        session: AsyncSession,
        project_id: str,
        *,
        scorer_version: str = CLIP_SCORER_VERSION,
        limit: int = 500,
    ) -> list[ClipScore]:
        result = await session.execute(
            select(ClipScoreRow)
            .where(
                ClipScoreRow.project_id == project_id,
                ClipScoreRow.scorer_version == scorer_version,
            )
            .order_by(ClipScoreRow.montage_score.desc())
            .limit(limit),
        )
        return [self.row_to_score(row) for row in result.scalars().all()]

    async def upsert(
        self,
        session: AsyncSession,
        score: ClipScore,
    ) -> ClipScore:
        result = await session.execute(
            select(ClipScoreRow).where(
                ClipScoreRow.media_id == score.media_id,
                ClipScoreRow.scorer_version == score.scorer_version,
            ),
        )
        row = result.scalar_one_or_none()
        payload_json = score.model_dump_json()
        now = utc_now_iso()
        if row is None:
            row = ClipScoreRow(
                id=new_uuid(),
                project_id=score.project_id,
                media_id=score.media_id,
                montage_score=score.montage_score,
                confidence=score.confidence,
                reasoning=score.reasoning,
                breakdown_json=score.breakdown.model_dump_json(),
                scorer_version=score.scorer_version,
                cache_key=score.cache_key,
                source_fingerprint=score.source_fingerprint,
                payload_json=payload_json,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.project_id = score.project_id
            row.montage_score = score.montage_score
            row.confidence = score.confidence
            row.reasoning = score.reasoning
            row.breakdown_json = score.breakdown.model_dump_json()
            row.cache_key = score.cache_key
            row.source_fingerprint = score.source_fingerprint
            row.payload_json = payload_json
            row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return self.row_to_score(row)

    async def delete_for_media(self, session: AsyncSession, media_id: str) -> None:
        await session.execute(delete(ClipScoreRow).where(ClipScoreRow.media_id == media_id))
        await session.commit()
