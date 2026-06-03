"""Submission API DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SubmissionCreate(BaseModel):
    phase: int = Field(ge=1, le=4)
    task_no: int = Field(ge=1, le=5)
    content: str = Field(min_length=1, max_length=10000)


class SubmissionOut(BaseModel):
    id: uuid.UUID
    phase: int
    task_no: int
    content: str
    ai_feedback: str | None
    score: int | None
    submitted_at: datetime
    graded_at: datetime | None

    model_config = {"from_attributes": True}
