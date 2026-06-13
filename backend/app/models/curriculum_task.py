"""Sprint 9 — editable per-task curriculum row (published + draft)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CurriculumTask(Base):
    """Curriculum の Task 1 行。published 列と draft_* 列の二段保持。

    Sprint 9: `skill_tags` は JSONB の `list[str]` で永続化。`deliverable`
    と `week_label` は NULL 可。`draft_deliverable=""` / `draft_week_label=""`
    は「明示的に空にしたい」を表すための sentinel として運用 (NULL は
    "未編集" の意味で予約)。
    """

    __tablename__ = "curriculum_tasks"
    __table_args__ = (
        UniqueConstraint(
            "phase_id", "task_no", name="uq_curriculum_tasks_phase_task_no"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    phase_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_phases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_no: Mapped[int] = mapped_column(Integer, nullable=False)

    # Published values
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    skill_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    deliverable: Mapped[str | None] = mapped_column(Text, nullable=True)
    week_label: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Draft overlay
    draft_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_skill_tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    draft_deliverable: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_week_label: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
