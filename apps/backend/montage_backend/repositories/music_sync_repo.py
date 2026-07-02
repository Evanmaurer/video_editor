from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.music_sync import MUSIC_SYNC_VERSION, MusicSyncAnalysis
from montage_backend.models.db.music_sync_db import MusicSyncRow


class MusicSyncRepository:
    def row_to_analysis(self, row: MusicSyncRow) -> MusicSyncAnalysis:
        payload = json.loads(row.payload_json) if row.payload_json else {}
        return MusicSyncAnalysis.model_validate(payload)

    async def get_for_media(
        self,
        session: AsyncSession,
        media_id: str,
        *,
        sync_version: str = MUSIC_SYNC_VERSION,
    ) -> MusicSyncAnalysis | None:
        result = await session.execute(
            select(MusicSyncRow).where(
                MusicSyncRow.media_id == media_id,
                MusicSyncRow.sync_version == sync_version,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_analysis(row)

    async def list_for_project(
        self,
        session: AsyncSession,
        project_id: str,
        *,
        sync_version: str = MUSIC_SYNC_VERSION,
        limit: int = 100,
    ) -> list[MusicSyncAnalysis]:
        result = await session.execute(
            select(MusicSyncRow)
            .where(
                MusicSyncRow.project_id == project_id,
                MusicSyncRow.sync_version == sync_version,
            )
            .order_by(MusicSyncRow.tempo_bpm.desc())
            .limit(limit),
        )
        return [self.row_to_analysis(row) for row in result.scalars().all()]

    async def upsert(
        self,
        session: AsyncSession,
        analysis: MusicSyncAnalysis,
    ) -> MusicSyncAnalysis:
        result = await session.execute(
            select(MusicSyncRow).where(
                MusicSyncRow.media_id == analysis.media_id,
                MusicSyncRow.sync_version == analysis.sync_version,
            ),
        )
        row = result.scalar_one_or_none()
        payload_json = analysis.model_dump_json()
        now = utc_now_iso()
        if row is None:
            row = MusicSyncRow(
                id=new_uuid(),
                project_id=analysis.project_id,
                media_id=analysis.media_id,
                tempo_bpm=analysis.tempo_bpm,
                confidence=analysis.confidence,
                reasoning=analysis.reasoning,
                sync_version=analysis.sync_version,
                cache_key=analysis.cache_key,
                source_fingerprint=analysis.source_fingerprint,
                payload_json=payload_json,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.project_id = analysis.project_id
            row.tempo_bpm = analysis.tempo_bpm
            row.confidence = analysis.confidence
            row.reasoning = analysis.reasoning
            row.cache_key = analysis.cache_key
            row.source_fingerprint = analysis.source_fingerprint
            row.payload_json = payload_json
            row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return self.row_to_analysis(row)

    async def delete_for_media(self, session: AsyncSession, media_id: str) -> None:
        await session.execute(delete(MusicSyncRow).where(MusicSyncRow.media_id == media_id))
        await session.commit()
