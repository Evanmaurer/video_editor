from __future__ import annotations

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from montage_backend.models.db.base import Base


class MontagePlanRow(Base):
    __tablename__ = "montage_plans"
    __table_args__ = (
        Index("idx_montage_plans_project", "project_id"),
        Index("idx_montage_plans_status", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generator_id: Mapped[str] = mapped_column(String, nullable=False, default="montage-plan-framework")
    generator_version: Mapped[str] = mapped_column(String, nullable=False, default="1.0.0")
    overall_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    applied_timeline_id: Mapped[str | None] = mapped_column(String, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
