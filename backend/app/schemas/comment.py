"""Instructor comment DTOs (Sprint 4).

`AdminCommentOut` lives in `schemas/admin.py` because the admin
submissions detail endpoint already imports it. This module adds the
write-side payload and the learner-facing read DTO. The learner DTO
intentionally drops `author_user_id` — the body of feedback is what the
learner needs; the instructor's internal UUID is operational PII.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    parent_id: uuid.UUID | None = (
        None  # Sprint 6: optional for admin trunk, required for learner reply
    )


class LearnerCommentOut(BaseModel):
    """The learner-facing projection of an instructor comment."""

    id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime
    parent_id: uuid.UUID | None = None  # Sprint 6: thread structure
    # Sprint 6: lets the UI show the reply button on admin-authored
    # comments without exposing author_user_id (intentionally omitted
    # for PII). Frontend's previous duck-type check on author_user_id
    # presence always evaluated false on learner views and silently
    # hid the reply button on every comment.
    is_admin_authored: bool
