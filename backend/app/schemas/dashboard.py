"""Sprint 5 dashboard API response schemas.

Single envelope: 4 fixed top-level sections. The names mirror the
service-side dataclass fields so the API layer's job stays mechanical."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProgressSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    completed_tasks: int
    total_tasks: int
    submission_count: int
    average_score: float | None


class TagAverageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tag: str
    average_score: float
    submission_count: int


class WeaknessOut(BaseModel):
    has_enough_data: bool
    top_weaknesses: list[TagAverageOut]


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    phase: int
    task_no: int
    title: str
    skill_tags: list[str]
    match_tag: str | None
    rag_score: float


class RecommendationsBlock(BaseModel):
    items: list[RecommendationOut]


class NudgeOut(BaseModel):
    body: str
    generated_at: datetime
    is_fresh: bool


class DashboardResponse(BaseModel):
    progress_summary: ProgressSummaryOut
    weakness: WeaknessOut
    recommendations: RecommendationsBlock
    nudge: NudgeOut
