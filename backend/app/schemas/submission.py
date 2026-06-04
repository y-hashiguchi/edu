"""Submission API DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.grading import GradingAttemptOut


class SubmissionFileOut(BaseModel):
    id: uuid.UUID
    file_path: str
    mime_type: str
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @property
    def filename(self) -> str:
        from pathlib import Path

        return Path(self.file_path).name


class SubmissionCreate(BaseModel):
    """Used only by tests that still post JSON; the live API uses multipart."""

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
    files: list[SubmissionFileOut] = []
    grading_history: list[GradingAttemptOut] = []

    model_config = {"from_attributes": True}
