from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from montage_backend.models.db.base import Base


class ClipHighlightRow(Base):
    __tablename__ = "clip_highlights"
    __table_args__ = (
        UniqueConstraint("media_id", "detector_version", name="uq_clip_highlights_media_detector"),
        Index("idx_clip_highlights_project", "project_id"),
        Index("idx_clip_highlights_count", "highlight_count"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    media_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    highlight_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detector_version: Mapped[str] = mapped_column(String, nullable=False)
    cache_key: Mapped[str] = mapped_column(String, nullable=False)
    source_fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    highlights_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
