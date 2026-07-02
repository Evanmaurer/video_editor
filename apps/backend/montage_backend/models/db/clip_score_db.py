from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from montage_backend.models.db.base import Base


class ClipScoreRow(Base):
    __tablename__ = "clip_scores"
    __table_args__ = (
        UniqueConstraint("media_id", "scorer_version", name="uq_clip_scores_media_scorer"),
        Index("idx_clip_scores_project", "project_id"),
        Index("idx_clip_scores_score", "montage_score"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    media_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    montage_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    scorer_version: Mapped[str] = mapped_column(String, nullable=False)
    cache_key: Mapped[str] = mapped_column(String, nullable=False)
    source_fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
