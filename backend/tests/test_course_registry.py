"""Sprint 7 — course registry contract tests."""

import uuid

import pytest

from app.data.courses import (
    COURSE_REGISTRY,
    DEFAULT_COURSE_SLUG,
    get_course,
    get_phase,
    get_phases,
)
from app.data.courses.types import CourseData, PhaseData, TaskItem


def test_default_course_is_ai_driven_dev():
    assert DEFAULT_COURSE_SLUG == "ai-driven-dev"
    assert DEFAULT_COURSE_SLUG in COURSE_REGISTRY


def test_ai_driven_dev_course_shape():
    c = get_course("ai-driven-dev")
    assert isinstance(c, CourseData)
    assert c.slug == "ai-driven-dev"
    assert c.id == uuid.UUID("00000000-0000-4000-8000-000000000001")
    assert len(c.phases) == 4
    for p in c.phases:
        assert isinstance(p, PhaseData)
        assert len(p.tasks) >= 1
        for t in p.tasks:
            assert isinstance(t, TaskItem)


def test_get_phases_returns_tuple():
    phases = get_phases("ai-driven-dev")
    assert isinstance(phases, tuple)
    assert len(phases) == 4


def test_get_phase_picks_one_by_number():
    p = get_phase("ai-driven-dev", 1)
    assert p.phase == 1
    assert "開発環境" in p.title


def test_get_course_raises_on_unknown_slug():
    from app.data.courses import CourseNotFoundError

    with pytest.raises(CourseNotFoundError):
        get_course("does-not-exist")


def test_get_phase_raises_on_unknown_phase():
    from app.data.courses import PhaseNotFoundError

    with pytest.raises(PhaseNotFoundError):
        get_phase("ai-driven-dev", 99)


def test_course_data_is_frozen():
    c = get_course("ai-driven-dev")
    with pytest.raises(Exception):
        c.title = "mutated"  # type: ignore[misc]
