"""Admin-view DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.grading import GradingAttemptOut
from app.schemas.progress import ProgressOut
from app.schemas.submission import SubmissionFileOut


class AdminUserSummary(BaseModel):
    """One row in the dashboard list."""

    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    is_admin: bool
    completed_phases: int
    in_progress_phases: int
    top_weakness_tag: str | None = None  # Sprint 6: bulk 集計で埋める


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


class AdminCommentOut(BaseModel):
    """A single instructor comment rendered in the admin view.

    Carries `author_name` denormalised so the dashboard can show the
    author without N+1 user lookups."""

    id: uuid.UUID
    submission_id: uuid.UUID
    author_user_id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime
    updated_at: datetime
    parent_id: uuid.UUID | None = None  # Sprint 6: thread structure


class AdminSubmissionSummary(BaseModel):
    """One row in the cross-cohort submissions feed. The denormalised
    user columns let the dashboard render 'who/which-phase' without an
    extra round-trip per row."""

    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_name: str
    phase: int
    task_no: int
    score: int | None
    submitted_at: datetime
    graded_at: datetime | None


class AdminSubmissionListOut(BaseModel):
    items: list[AdminSubmissionSummary]
    total: int
    limit: int
    offset: int


class AdminSubmissionDetail(BaseModel):
    """Detail view that bundles every related piece (files, history,
    comments) so the dashboard renders without a second request."""

    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_name: str
    phase: int
    task_no: int
    content: str
    score: int | None
    ai_feedback: str | None
    submitted_at: datetime
    graded_at: datetime | None
    files: list[SubmissionFileOut]
    grading_history: list[GradingAttemptOut]
    comments: list[AdminCommentOut]
