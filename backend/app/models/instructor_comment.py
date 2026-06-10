"""Instructor comment on a learner submission (Sprint 4)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InstructorComment(Base):
    __tablename__ = "instructor_comments"
    __table_args__ = (
        # MED-1 (sprint-6 follow-up): direct self-loop guard. Catches the
        # simplest invalid state at write time so the recursive CTEs in
        # services/comment.py only have to defend against depth (via
        # MAX_THREAD_DEPTH).
        CheckConstraint(
            "parent_id IS NULL OR parent_id != id",
            name="ck_instructor_comments_no_self_parent",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ondelete=RESTRICT on the author: deleting an instructor account must
    # not silently strip their feedback off learner records. Operations
    # should anonymise first if a hard delete is ever required.
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("instructor_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
