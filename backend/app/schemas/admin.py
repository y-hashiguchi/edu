"""Admin-view DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.progress import ProgressOut


class AdminUserSummary(BaseModel):
    """One row in the dashboard list."""

    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    is_admin: bool
    completed_phases: int
    in_progress_phases: int


class AdminUserListOut(BaseModel):
    items: list[AdminUserSummary]
    total: int
    limit: int
    offset: int


class AdminUserDetail(BaseModel):
    """Single-learner drill-down. Keys of `latest_scores` are phase
    numbers serialised as strings (JSON object keys cannot be ints) —
    consumers should `int(k)` if they need numeric keys."""

    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    is_admin: bool
    progress: list[ProgressOut]
    latest_scores: dict[int, int | None]
