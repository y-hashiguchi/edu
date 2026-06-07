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


class LearnerCommentOut(BaseModel):
    """The learner-facing projection of an instructor comment."""

    id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime
