from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from montage_backend.models.db.base import Base


class ClipAnalysisSnapshotRow(Base):
    __tablename__ = "clip_analysis_snapshots"
    __table_args__ = (
        UniqueConstraint("media_id", name="uq_clip_analysis_snapshot_media"),
        Index("idx_clip_analysis_project", "project_id"),
        Index("idx_clip_analysis_status", "overall_status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    media_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    overall_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    readiness: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
