"""Sprint 9 — editable per-phase curriculum row (published + draft)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CurriculumPhase(Base):
    """Curriculum の Phase 1 行。published 列と draft_* 列の二段保持。

    Sprint 9: ai-driven-dev / ai-era-se の Python レジストリは初回 seed として
    Alembic migration 内で写し込まれる。以後の編集はこのテーブル経由のみ。
    `draft_*` 列は NULL = 未編集、非 NULL = 次 publish 候補。
    """

    __tablename__ = "curriculum_phases"
    __table_args__ = (
        UniqueConstraint("course_id", "phase_no", name="uq_curriculum_phases_course_phase_no"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    phase_no: Mapped[int] = mapped_column(Integer, nullable=False)

    # Published values (runtime cache が読む値)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Draft overlay (NULL = 未編集)
    draft_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
