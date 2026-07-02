from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.clip_highlight import HIGHLIGHT_DETECTOR_VERSION, ClipHighlights
from montage_backend.models.db.clip_highlight_db import ClipHighlightRow


class ClipHighlightRepository:
    def row_to_highlights(self, row: ClipHighlightRow) -> ClipHighlights:
        payload = json.loads(row.payload_json) if row.payload_json else {}
        return ClipHighlights.model_validate(payload)

    async def get_for_media(
        self,
        session: AsyncSession,
        media_id: str,
        *,
        detector_version: str = HIGHLIGHT_DETECTOR_VERSION,
    ) -> ClipHighlights | None:
        result = await session.execute(
            select(ClipHighlightRow).where(
                ClipHighlightRow.media_id == media_id,
                ClipHighlightRow.detector_version == detector_version,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_highlights(row)

    async def list_for_project(
        self,
        session: AsyncSession,
        project_id: str,
        *,
        detector_version: str = HIGHLIGHT_DETECTOR_VERSION,
        limit: int = 500,
    ) -> list[ClipHighlights]:
        result = await session.execute(
            select(ClipHighlightRow)
            .where(
                ClipHighlightRow.project_id == project_id,
                ClipHighlightRow.detector_version == detector_version,
            )
            .order_by(ClipHighlightRow.highlight_count.desc())
            .limit(limit),
        )
        return [self.row_to_highlights(row) for row in result.scalars().all()]

    async def upsert(
        self,
        session: AsyncSession,
        highlights: ClipHighlights,
    ) -> ClipHighlights:
        result = await session.execute(
            select(ClipHighlightRow).where(
                ClipHighlightRow.media_id == highlights.media_id,
                ClipHighlightRow.detector_version == highlights.detector_version,
            ),
        )
        row = result.scalar_one_or_none()
        payload_json = highlights.model_dump_json()
        highlights_json = json.dumps([item.model_dump(mode="json") for item in highlights.highlights])
        now = utc_now_iso()
        if row is None:
            row = ClipHighlightRow(
                id=new_uuid(),
                project_id=highlights.project_id,
                media_id=highlights.media_id,
                highlight_count=highlights.highlight_count,
                detector_version=highlights.detector_version,
                cache_key=highlights.cache_key,
                source_fingerprint=highlights.source_fingerprint,
                highlights_json=highlights_json,
                payload_json=payload_json,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.project_id = highlights.project_id
            row.highlight_count = highlights.highlight_count
            row.cache_key = highlights.cache_key
            row.source_fingerprint = highlights.source_fingerprint
            row.highlights_json = highlights_json
            row.payload_json = payload_json
            row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return self.row_to_highlights(row)

    async def delete_for_media(self, session: AsyncSession, media_id: str) -> None:
        await session.execute(delete(ClipHighlightRow).where(ClipHighlightRow.media_id == media_id))
        await session.commit()
