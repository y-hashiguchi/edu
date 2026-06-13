"""Sprint 9 — admin curriculum editing DTOs."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Output DTOs
# ---------------------------------------------------------------------------


class AdminCurriculumCourseSummary(BaseModel):
    """`/api/admin/curriculum/` (一覧) の 1 row。"""

    slug: str
    title: str
    pending_draft_count: int


class AdminCurriculumCourseList(BaseModel):
    items: list[AdminCurriculumCourseSummary]


class AdminTaskEditOut(BaseModel):
    """1 task 分の published + draft 両状態。"""

    task_no: int
    title: str
    description: str
    skill_tags: list[str]
    deliverable: str | None
    week_label: str | None
    draft_title: str | None
    draft_description: str | None
    draft_skill_tags: list[str] | None
    draft_deliverable: str | None
    draft_week_label: str | None
    updated_at: datetime


class AdminPhaseEditOut(BaseModel):
    """1 phase 分の published + draft 両状態 + tasks."""

    phase_no: int
    title: str
    goal: str
    system_prompt: str
    draft_title: str | None
    draft_goal: str | None
    draft_system_prompt: str | None
    tasks: list[AdminTaskEditOut]
    updated_at: datetime


class AdminCurriculumCourseDetail(BaseModel):
    """`GET /api/admin/curriculum/{slug}` のレスポンス。"""

    slug: str
    title: str
    phases: list[AdminPhaseEditOut]


class AdminCurriculumPublishOut(BaseModel):
    slug: str
    published_phase_count: int
    published_task_count: int
    published_at: datetime


# ---------------------------------------------------------------------------
# Request DTOs — exclude_unset セマンティクス用に全フィールド Optional
# ---------------------------------------------------------------------------


class AdminPhaseUpdateRequest(BaseModel):
    """PUT body — フィールド省略 = 変更なし、明示 None = draft クリア、
    明示値 = draft 設定。route 側で `model_dump(exclude_unset=True)` を取る。
    """

    title: str | None = Field(default=None, max_length=200)
    goal: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, max_length=8000)


class AdminTaskUpdateRequest(BaseModel):
    """PUT body for task draft."""

    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    skill_tags: list[str] | None = Field(default=None, max_length=10)
    deliverable: str | None = Field(default=None, max_length=200)
    week_label: str | None = Field(default=None, max_length=200)

    def normalized_skill_tags(self) -> list[str] | None:
        """順序維持の dedup + 各要素長 50 チェック。

        route が `model_dump(exclude_unset=True)` の後にこれを呼ぶ運用 (タグ
        フィールド省略時は None、明示空 list は []、値ありは dedup 後)。
        """
        if self.skill_tags is None:
            return None
        seen: set[str] = set()
        out: list[str] = []
        for raw in self.skill_tags:
            t = raw.strip()
            if not t or len(t) > 50:
                continue
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out
