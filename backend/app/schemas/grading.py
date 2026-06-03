"""Grading DTOs."""

from pydantic import BaseModel, Field


class GradingResult(BaseModel):
    score: int = Field(ge=0, le=100)
    feedback: str
