from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from montage_backend.models.db.base import Base


class MediaMetadataFeatureRow(Base):
    __tablename__ = "media_metadata_features"
    __table_args__ = (
        UniqueConstraint("media_id", "feature_key", name="uq_media_metadata_feature"),
        Index("idx_media_metadata_media", "media_id"),
        Index("idx_media_metadata_status", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    media_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("media_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_key: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
