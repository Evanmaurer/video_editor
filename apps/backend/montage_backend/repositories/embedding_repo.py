from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.analysis.embedding_analysis import (
    EmbeddingMatch,
    EmbeddingScopeType,
    EmbeddingVectorRecord,
    cosine_similarity,
)
from montage_backend.models.domain import new_uuid, utc_now_iso
from montage_backend.models.db.embedding_db import AnalysisEmbeddingRow


class EmbeddingRepository:
    def row_to_record(self, row: AnalysisEmbeddingRow) -> EmbeddingVectorRecord:
        return EmbeddingVectorRecord(
            id=row.id,
            scope_type=EmbeddingScopeType(row.scope_type),
            scope_id=row.scope_id,
            timestamp_ms=row.timestamp_ms,
            start_ms=row.start_ms,
            end_ms=row.end_ms,
            vector=json.loads(row.embedding_json),
            dimensions=row.dimensions,
        )

    async def delete_for_media(
        self,
        session: AsyncSession,
        media_id: str,
        *,
        model_id: str | None = None,
    ) -> None:
        stmt = delete(AnalysisEmbeddingRow).where(AnalysisEmbeddingRow.media_id == media_id)
        if model_id is not None:
            stmt = stmt.where(AnalysisEmbeddingRow.model_id == model_id)
        await session.execute(stmt)
        await session.commit()

    async def upsert_records(
        self,
        session: AsyncSession,
        *,
        project_id: str,
        media_id: str,
        model_id: str,
        source_fingerprint: str | None,
        records: list[EmbeddingVectorRecord],
    ) -> None:
        await self.delete_for_media(session, media_id, model_id=model_id)
        now = utc_now_iso()
        for record in records:
            session.add(
                AnalysisEmbeddingRow(
                    id=record.id,
                    project_id=project_id,
                    media_id=media_id,
                    scope_type=record.scope_type.value,
                    scope_id=record.scope_id,
                    model_id=model_id,
                    dimensions=record.dimensions,
                    embedding_json=json.dumps(record.vector),
                    timestamp_ms=record.timestamp_ms,
                    start_ms=record.start_ms,
                    end_ms=record.end_ms,
                    source_fingerprint=source_fingerprint,
                    created_at=now,
                ),
            )
        await session.commit()

    async def count_for_media(self, session: AsyncSession, media_id: str) -> int:
        result = await session.execute(
            select(AnalysisEmbeddingRow).where(AnalysisEmbeddingRow.media_id == media_id),
        )
        return len(result.scalars().all())

    async def get_clip_embedding(
        self,
        session: AsyncSession,
        media_id: str,
        *,
        model_id: str | None = None,
    ) -> EmbeddingVectorRecord | None:
        stmt = select(AnalysisEmbeddingRow).where(
            AnalysisEmbeddingRow.media_id == media_id,
            AnalysisEmbeddingRow.scope_type == EmbeddingScopeType.CLIP.value,
        )
        if model_id is not None:
            stmt = stmt.where(AnalysisEmbeddingRow.model_id == model_id)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_record(row)

    async def get_scene_embedding(
        self,
        session: AsyncSession,
        media_id: str,
        scope_id: str,
    ) -> EmbeddingVectorRecord | None:
        result = await session.execute(
            select(AnalysisEmbeddingRow).where(
                AnalysisEmbeddingRow.media_id == media_id,
                AnalysisEmbeddingRow.scope_type == EmbeddingScopeType.SCENE.value,
                AnalysisEmbeddingRow.scope_id == scope_id,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_record(row)

    async def list_project_embeddings(
        self,
        session: AsyncSession,
        project_id: str,
        *,
        scope_type: EmbeddingScopeType | None = None,
    ) -> list[tuple[AnalysisEmbeddingRow, list[float]]]:
        stmt = select(AnalysisEmbeddingRow).where(AnalysisEmbeddingRow.project_id == project_id)
        if scope_type is not None:
            stmt = stmt.where(AnalysisEmbeddingRow.scope_type == scope_type.value)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [(row, json.loads(row.embedding_json)) for row in rows]

    async def search_similar(
        self,
        session: AsyncSession,
        project_id: str,
        query_vector: list[float],
        *,
        scope_type: EmbeddingScopeType,
        top_k: int = 10,
        exclude_media_id: str | None = None,
    ) -> list[EmbeddingMatch]:
        candidates = await self.list_project_embeddings(session, project_id, scope_type=scope_type)
        matches: list[EmbeddingMatch] = []
        for row, vector in candidates:
            if exclude_media_id is not None and row.media_id == exclude_media_id:
                continue
            similarity = cosine_similarity(query_vector, vector)
            matches.append(
                EmbeddingMatch(
                    embedding_id=row.id,
                    media_id=row.media_id,
                    scope_type=EmbeddingScopeType(row.scope_type),
                    scope_id=row.scope_id,
                    similarity=similarity,
                    timestamp_ms=row.timestamp_ms,
                    start_ms=row.start_ms,
                    end_ms=row.end_ms,
                ),
            )
        matches.sort(key=lambda match: match.similarity, reverse=True)
        return matches[:top_k]

    async def find_duplicates(
        self,
        session: AsyncSession,
        project_id: str,
        media_id: str,
        *,
        threshold: float = 0.95,
    ) -> list[EmbeddingMatch]:
        clip = await self.get_clip_embedding(session, media_id)
        if clip is None:
            return []
        matches = await self.search_similar(
            session,
            project_id,
            clip.vector,
            scope_type=EmbeddingScopeType.CLIP,
            top_k=100,
            exclude_media_id=media_id,
        )
        return [match for match in matches if match.similarity >= threshold]

    def new_record_id(self) -> str:
        return new_uuid()
