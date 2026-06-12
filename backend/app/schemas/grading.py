"""Grading DTOs."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class GradingResultStatus(StrEnum):
    GRADED = "graded"
    FAILED = "failed"
    # Sprint 8 follow-up: ephemeral wire status used by async regrade.
    # Never persisted (the DB CHECK constraint only allows graded/failed).
    # The route hands the client a synthetic PENDING attempt so the
    # frontend knows to start polling.
    PENDING = "pending"


class GradingResult(BaseModel):
    status: GradingResultStatus
    score: int | None = Field(default=None, ge=0, le=100)
    feedback: str | None = None
    error_message: str | None = None
    model_name: str


class GradingAttemptOut(BaseModel):
    id: UUID
    status: GradingResultStatus
    score: int | None
    feedback: str | None
    error_message: str | None
    model_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
