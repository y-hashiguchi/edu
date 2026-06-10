"""Sprint 5 nudge cache, Sprint 7 scoped per course.

PK is composite (user_id, course_id) so a learner enrolled in multiple
courses gets one nudge per course instead of one global nudge
contaminated with cross-course state. input_signature still drives
sub-24h invalidation."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNudge(Base):
    __tablename__ = "user_nudges"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), primary_key=True
    )
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    input_signature: Mapped[str] = mapped_column(String(16), nullable=False)
