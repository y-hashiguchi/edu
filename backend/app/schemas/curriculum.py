"""API応答用のpydanticスキーマ。"""

from pydantic import BaseModel, ConfigDict


class PhaseSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    phase: int
    title: str
    goal: str
    duration: str
    skills: list[str]
    tasks: list[str]
    locked: bool
    status: str
