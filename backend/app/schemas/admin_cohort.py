"""Sprint 10 — admin cohort summary DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StuckLearnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    display_name: str
    email_masked: str
    last_activity_at: datetime | None
    current_phase: int
    submission_count: int
    reason: str = Field(description="no_submissions | inactive_7d")


class TagHeatmapEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tag: str
    average_score: float
    submission_count: int


class AdminCohortSummaryOut(BaseModel):
    course_slug: str
    course_title: str
    enrolled_count: int
    average_score: float | None
    completion_rate: float
    stuck_learners: list[StuckLearnerOut]
    tag_heatmap: list[TagHeatmapEntryOut]
