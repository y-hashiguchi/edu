"""Submission ORM model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("user_id", "phase", "task_no", name="uq_submissions_user_phase_task"),
        CheckConstraint("phase BETWEEN 1 AND 4", name="ck_submissions_phase"),
        CheckConstraint("task_no BETWEEN 1 AND 5", name="ck_submissions_task_no"),
        CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100", name="ck_submissions_score"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    phase: Mapped[int] = mapped_column(Integer)
    task_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    graded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
