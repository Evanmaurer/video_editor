from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from montage_backend.models.db.base import Base


class MediaItemRow(Base):
    __tablename__ = "media_items"
    __table_args__ = (
        Index("idx_media_items_project", "project_id"),
        Index("idx_media_items_status", "import_status"),
        Index("idx_media_items_sha256", "project_id", "sha256_hash"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    source_path: Mapped[str | None] = mapped_column(String, nullable=True)
    media_type: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    storage_mode: Mapped[str] = mapped_column(String, nullable=False, default="copy")
    sha256_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    width: Mapped[int | None] = mapped_column(nullable=True)
    height: Mapped[int | None] = mapped_column(nullable=True)
    frame_rate: Mapped[float | None] = mapped_column(nullable=True)
    codec: Mapped[str | None] = mapped_column(String, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(nullable=True)
    audio_sample_rate: Mapped[int | None] = mapped_column(nullable=True)
    bitrate: Mapped[int | None] = mapped_column(nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    proxy_path: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String, nullable=True)
    waveform_path: Mapped[str | None] = mapped_column(String, nullable=True)
    proxy_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    waveform_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    scene_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_favorite: Mapped[int] = mapped_column(nullable=False, default=0)
    import_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
