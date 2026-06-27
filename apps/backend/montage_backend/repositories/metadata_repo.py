from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.domain.media import ProcessingStatus
from montage_backend.models.domain.metadata import (
    METADATA_SCHEMA_VERSION,
    MetadataFeatureKey,
    MetadataFeatureRecord,
)
from montage_backend.models.db.metadata_db import MediaMetadataFeatureRow


class MetadataRepository:
    def row_to_record(self, row: MediaMetadataFeatureRow) -> MetadataFeatureRecord:
        return MetadataFeatureRecord(
            media_id=row.media_id,
            feature_key=MetadataFeatureKey(row.feature_key),
            status=ProcessingStatus(row.status),
            payload=json.loads(row.payload_json) if row.payload_json else {},
            confidence=row.confidence,
            reasoning=row.reasoning,
            source_fingerprint=row.source_fingerprint,
            schema_version=row.schema_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_for_media(
        self,
        session: AsyncSession,
        media_id: str,
    ) -> list[MetadataFeatureRecord]:
        result = await session.execute(
            select(MediaMetadataFeatureRow)
            .where(MediaMetadataFeatureRow.media_id == media_id)
            .order_by(MediaMetadataFeatureRow.feature_key),
        )
        return [self.row_to_record(row) for row in result.scalars().all()]

    async def get_feature(
        self,
        session: AsyncSession,
        media_id: str,
        feature_key: MetadataFeatureKey,
    ) -> MetadataFeatureRecord | None:
        result = await session.execute(
            select(MediaMetadataFeatureRow).where(
                MediaMetadataFeatureRow.media_id == media_id,
                MediaMetadataFeatureRow.feature_key == feature_key.value,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_record(row)

    async def upsert_feature(
        self,
        session: AsyncSession,
        *,
        media_id: str,
        feature_key: MetadataFeatureKey,
        status: ProcessingStatus,
        payload: dict,
        source_fingerprint: str | None = None,
        confidence: float | None = None,
        reasoning: str | None = None,
    ) -> MetadataFeatureRecord:
        result = await session.execute(
            select(MediaMetadataFeatureRow).where(
                MediaMetadataFeatureRow.media_id == media_id,
                MediaMetadataFeatureRow.feature_key == feature_key.value,
            ),
        )
        row = result.scalar_one_or_none()
        now = utc_now_iso()
        if row is None:
            row = MediaMetadataFeatureRow(
                id=new_uuid(),
                media_id=media_id,
                feature_key=feature_key.value,
                status=status.value,
                payload_json=json.dumps(payload),
                confidence=confidence,
                reasoning=reasoning,
                source_fingerprint=source_fingerprint,
                schema_version=METADATA_SCHEMA_VERSION,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.status = status.value
            row.payload_json = json.dumps(payload)
            row.confidence = confidence
            row.reasoning = reasoning
            row.source_fingerprint = source_fingerprint
            row.schema_version = METADATA_SCHEMA_VERSION
            row.updated_at = now
        await session.commit()
        return self.row_to_record(row)

    async def delete_for_media(self, session: AsyncSession, media_id: str) -> None:
        await session.execute(
            delete(MediaMetadataFeatureRow).where(MediaMetadataFeatureRow.media_id == media_id),
        )
        await session.commit()
