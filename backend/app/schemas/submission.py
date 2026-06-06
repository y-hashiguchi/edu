"""Submission API DTOs."""

import uuid
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.schemas.grading import GradingAttemptOut


class SubmissionFileOut(BaseModel):
    id: uuid.UUID
    # Only the sanitized basename is exposed; the absolute server-side path
    # is never sent to clients (would leak the container's WORKDIR / volume
    # mount layout).
    filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_row(cls, row) -> "SubmissionFileOut":
        return cls(
            id=row.id,
            filename=Path(row.file_path).name,
            mime_type=row.mime_type,
            size_bytes=row.size_bytes,
            created_at=row.created_at,
        )


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
