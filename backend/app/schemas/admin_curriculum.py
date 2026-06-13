"""Sprint 9 — admin curriculum editing DTOs."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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

    Sprint 9 follow-up MED-1: ``min_length=1`` を付与し、空文字 draft が
    published 列に COPY されて NOT NULL 仕様を実質破ることを防ぐ。
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    goal: str | None = Field(default=None, min_length=1, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=8000)


class AdminTaskUpdateRequest(BaseModel):
    """PUT body for task draft.

    Sprint 9 follow-up MED-1: title / description は ``min_length=1`` 必須。
    ``deliverable`` / ``week_label`` は「空文字 = 明示的に空にする」のセン
    チネル運用なので min_length は付けない。
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    skill_tags: list[str] | None = Field(default=None, max_length=10)
    deliverable: str | None = Field(default=None, max_length=200)
    week_label: str | None = Field(default=None, max_length=200)

    @field_validator("skill_tags")
    @classmethod
    def _validate_skill_tag_lengths(
        cls, v: list[str] | None
    ) -> list[str] | None:
        """Sprint 9 follow-up MED-2: 50 字超のタグは silent drop ではなく
        422 で reject する。UI が「入力したのに消えた」状態を作らない。
        """
        if v is None:
            return v
        for raw in v:
            if len(raw.strip()) > 50:
                raise ValueError(
                    f"skill_tag exceeds 50 chars: {raw[:20]!r}..."
                )
        return v

    def normalized_skill_tags(self) -> list[str] | None:
        """順序維持の dedup + 空文字 strip。長さ検査は field_validator が
        担当するためここでは silent drop しない。
        """
        if self.skill_tags is None:
            return None
        seen: set[str] = set()
        out: list[str] = []
        for raw in self.skill_tags:
            t = raw.strip()
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out
