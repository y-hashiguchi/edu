"""Progress DTOs."""

from datetime import datetime

from pydantic import BaseModel


class ProgressOut(BaseModel):
    phase: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ProgressCompleteResponse(BaseModel):
    phase: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    next_unlocked: ProgressOut | None
