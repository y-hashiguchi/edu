"""API応答用のpydanticスキーマ。"""

from pydantic import BaseModel


class PhaseSummary(BaseModel):
    phase: int
    title: str
    goal: str
    duration: str
    skills: list[str]
    tasks: list[str]
