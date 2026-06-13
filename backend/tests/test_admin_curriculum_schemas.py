"""Sprint 9 follow-up MED-1 / MED-2 — admin curriculum schema validation."""

import pytest
from pydantic import ValidationError

from app.schemas.admin_curriculum import (
    AdminPhaseUpdateRequest,
    AdminTaskUpdateRequest,
)


def test_phase_title_rejects_empty_string():
    """MED-1: 空文字 draft は 422。明示 None (draft クリア) は OK。"""
    with pytest.raises(ValidationError):
        AdminPhaseUpdateRequest(title="")

    # None は draft クリアセマンティクスなので validation を通る
    AdminPhaseUpdateRequest(title=None)


def test_phase_system_prompt_rejects_empty_string():
    with pytest.raises(ValidationError):
        AdminPhaseUpdateRequest(system_prompt="")


def test_task_title_rejects_empty_string():
    with pytest.raises(ValidationError):
        AdminTaskUpdateRequest(title="")


def test_task_description_rejects_empty_string():
    with pytest.raises(ValidationError):
        AdminTaskUpdateRequest(description="")


def test_task_deliverable_allows_empty_string_sentinel():
    """deliverable は「空文字 = 明示的に空にする」を保つので OK。"""
    req = AdminTaskUpdateRequest(deliverable="")
    assert req.deliverable == ""


def test_task_week_label_allows_empty_string_sentinel():
    req = AdminTaskUpdateRequest(week_label="")
    assert req.week_label == ""


def test_skill_tag_too_long_returns_422():
    """MED-2: 50 字超のタグは silent drop ではなく ValidationError。"""
    too_long = "x" * 51
    with pytest.raises(ValidationError):
        AdminTaskUpdateRequest(skill_tags=["ok", too_long])


def test_skill_tag_exactly_50_chars_is_accepted():
    fifty = "x" * 50
    req = AdminTaskUpdateRequest(skill_tags=[fifty])
    assert req.skill_tags == [fifty]


def test_normalized_skill_tags_dedup_and_strip():
    """normalized_skill_tags は dedup + strip のみ担当する。"""
    req = AdminTaskUpdateRequest(
        skill_tags=["  Git  ", "Git", "GitHub", ""]
    )
    assert req.normalized_skill_tags() == ["Git", "GitHub"]


def test_normalized_skill_tags_returns_none_when_unset():
    req = AdminTaskUpdateRequest()
    assert req.normalized_skill_tags() is None


def test_normalized_skill_tags_returns_empty_list_when_explicit():
    """明示空 list は []。draft_skill_tags = [] として扱われる。"""
    req = AdminTaskUpdateRequest(skill_tags=[])
    assert req.normalized_skill_tags() == []
