from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from montage_backend.models.db.base import Base


class MusicSyncRow(Base):
    __tablename__ = "music_sync_analyses"
    __table_args__ = (
        UniqueConstraint("media_id", "sync_version", name="uq_music_sync_media_version"),
        Index("idx_music_sync_project", "project_id"),
        Index("idx_music_sync_tempo", "tempo_bpm"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    media_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    tempo_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    sync_version: Mapped[str] = mapped_column(String, nullable=False)
    cache_key: Mapped[str] = mapped_column(String, nullable=False)
    source_fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
