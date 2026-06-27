from __future__ import annotations

import json
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from montage_backend.media.cache import normalize_cache_paths_data
from montage_backend.models.domain.media import (
    ImportStatus,
    MediaCachePaths,
    MediaItem,
    MediaListQuery,
    MediaNotFoundError,
    MediaRole,
    MediaSortField,
    MediaSortOrder,
    MediaType,
    ProcessingStatus,
    StorageMode,
)
from montage_backend.models.db.media_db import MediaItemRow


class MediaRepository:
    def row_to_media(self, row: MediaItemRow) -> MediaItem:
        metadata = json.loads(row.metadata_json) if row.metadata_json else {}
        cache_paths_raw = metadata.get("cache_paths")
        cache_paths = (
            MediaCachePaths.model_validate(normalize_cache_paths_data(cache_paths_raw))
            if cache_paths_raw
            else None
        )
        tags = json.loads(row.tags_json) if row.tags_json else []
        return MediaItem(
            id=row.id,
            project_id=row.project_id,
            file_path=row.file_path,
            file_name=row.file_name,
            source_path=row.source_path,
            media_type=MediaType(row.media_type),
            role=MediaRole(row.role),
            storage_mode=StorageMode(row.storage_mode),
            sha256_hash=row.sha256_hash,
            duration_ms=row.duration_ms,
            width=row.width,
            height=row.height,
            frame_rate=row.frame_rate,
            codec=row.codec,
            frame_count=row.frame_count,
            audio_sample_rate=row.audio_sample_rate,
            bitrate=row.bitrate,
            file_size_bytes=row.file_size_bytes,
            proxy_path=row.proxy_path,
            thumbnail_path=row.thumbnail_path,
            waveform_path=row.waveform_path,
            proxy_status=ProcessingStatus(row.proxy_status),
            waveform_status=ProcessingStatus(row.waveform_status),
            scene_status=ProcessingStatus(row.scene_status),
            tags=tags,
            is_favorite=bool(row.is_favorite),
            import_status=ImportStatus(row.import_status),
            error_message=row.error_message,
            cache_paths=cache_paths,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _apply_row(self, row: MediaItemRow, media: MediaItem) -> None:
        metadata: dict = {}
        if media.cache_paths is not None:
            metadata["cache_paths"] = media.cache_paths.model_dump()

        row.file_path = media.file_path
        row.file_name = media.file_name
        row.source_path = media.source_path
        row.storage_mode = media.storage_mode.value
        row.sha256_hash = media.sha256_hash
        row.duration_ms = media.duration_ms
        row.width = media.width
        row.height = media.height
        row.frame_rate = media.frame_rate
        row.codec = media.codec
        row.frame_count = media.frame_count
        row.audio_sample_rate = media.audio_sample_rate
        row.bitrate = media.bitrate
        row.file_size_bytes = media.file_size_bytes
        row.proxy_path = media.proxy_path
        row.thumbnail_path = media.thumbnail_path
        row.waveform_path = media.waveform_path
        row.proxy_status = media.proxy_status.value
        row.waveform_status = media.waveform_status.value
        row.scene_status = media.scene_status.value
        row.tags_json = json.dumps(media.tags)
        row.is_favorite = 1 if media.is_favorite else 0
        row.import_status = media.import_status.value
        row.error_message = media.error_message
        row.metadata_json = json.dumps(metadata)
        row.updated_at = media.updated_at

    async def get_by_id(self, session: AsyncSession, media_id: str) -> MediaItem | None:
        result = await session.execute(select(MediaItemRow).where(MediaItemRow.id == media_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_media(row)

    async def get_by_sha256(
        self,
        session: AsyncSession,
        project_id: str,
        sha256_hash: str,
    ) -> MediaItem | None:
        result = await session.execute(
            select(MediaItemRow).where(
                MediaItemRow.project_id == project_id,
                MediaItemRow.sha256_hash == sha256_hash,
            ),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self.row_to_media(row)

    async def list_by_project(
        self,
        session: AsyncSession,
        project_id: str,
        query: MediaListQuery | None = None,
    ) -> list[MediaItem]:
        query = query or MediaListQuery()
        result = await session.execute(
            select(MediaItemRow).where(MediaItemRow.project_id == project_id),
        )
        items = [self.row_to_media(row) for row in result.scalars().all()]

        if query.favorites_only:
            items = [item for item in items if item.is_favorite]

        if query.tags:
            tag_set = {tag.lower() for tag in query.tags}
            items = [
                item
                for item in items
                if tag_set.issubset({t.lower() for t in item.tags})
            ]

        if query.search:
            needle = query.search.lower()
            items = [
                item
                for item in items
                if needle in item.file_name.lower()
                or any(needle in tag.lower() for tag in item.tags)
                or (item.codec and needle in item.codec.lower())
            ]

        reverse = query.sort_order == MediaSortOrder.DESC
        if query.sort_by == MediaSortField.NAME:
            items.sort(key=lambda i: i.file_name.lower(), reverse=reverse)
        elif query.sort_by == MediaSortField.DURATION:
            items.sort(key=lambda i: i.duration_ms or 0, reverse=reverse)
        elif query.sort_by == MediaSortField.FAVORITE:
            items.sort(key=lambda i: (i.is_favorite, i.created_at), reverse=reverse)
        else:
            items.sort(key=lambda i: i.created_at, reverse=reverse)

        return items

    async def create(self, session: AsyncSession, media: MediaItem) -> MediaItem:
        metadata: dict = {}
        if media.cache_paths is not None:
            metadata["cache_paths"] = media.cache_paths.model_dump()
        row = MediaItemRow(
            id=media.id,
            project_id=media.project_id,
            file_path=media.file_path,
            file_name=media.file_name,
            source_path=media.source_path,
            media_type=media.media_type.value,
            role=media.role.value,
            storage_mode=media.storage_mode.value,
            sha256_hash=media.sha256_hash,
            duration_ms=media.duration_ms,
            width=media.width,
            height=media.height,
            frame_rate=media.frame_rate,
            codec=media.codec,
            frame_count=media.frame_count,
            audio_sample_rate=media.audio_sample_rate,
            bitrate=media.bitrate,
            file_size_bytes=media.file_size_bytes,
            proxy_path=media.proxy_path,
            thumbnail_path=media.thumbnail_path,
            waveform_path=media.waveform_path,
            proxy_status=media.proxy_status.value,
            waveform_status=media.waveform_status.value,
            scene_status=media.scene_status.value,
            tags_json=json.dumps(media.tags),
            is_favorite=1 if media.is_favorite else 0,
            import_status=media.import_status.value,
            error_message=media.error_message,
            metadata_json=json.dumps(metadata),
            created_at=media.created_at,
            updated_at=media.updated_at,
        )
        session.add(row)
        await session.commit()
        return media

    async def update(self, session: AsyncSession, media: MediaItem) -> MediaItem:
        result = await session.execute(select(MediaItemRow).where(MediaItemRow.id == media.id))
        row = result.scalar_one_or_none()
        if row is None:
            raise MediaNotFoundError(f"Media item not found: {media.id}")
        self._apply_row(row, media)
        await session.commit()
        return media

    async def delete(self, session: AsyncSession, media_id: str) -> None:
        result = await session.execute(select(MediaItemRow).where(MediaItemRow.id == media_id))
        row = result.scalar_one_or_none()
        if row is None:
            raise MediaNotFoundError(f"Media item not found: {media_id}")
        await session.delete(row)
        await session.commit()


def copy_to_originals(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def link_or_copy_source(
    source: Path,
    destination: Path,
    *,
    storage_mode: StorageMode,
) -> Path:
    """Return the path used for processing (copy into project or reference original)."""
    if storage_mode == StorageMode.REFERENCE:
        return source.resolve()
    copy_to_originals(source, destination)
    return destination.resolve()
