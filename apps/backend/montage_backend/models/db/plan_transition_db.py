from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from montage_backend.models.db.base import Base


class PlanTransitionRow(Base):
    __tablename__ = "plan_transition_analyses"
    __table_args__ = (
        UniqueConstraint("plan_id", "engine_version", name="uq_plan_transitions_plan_engine"),
        Index("idx_plan_transitions_project", "project_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False)
    plan_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("montage_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    junction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    engine_version: Mapped[str] = mapped_column(String, nullable=False)
    cache_key: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
