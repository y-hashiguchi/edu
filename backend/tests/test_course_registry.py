"""Sprint 7 — course registry contract tests."""

import uuid
from dataclasses import FrozenInstanceError

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
    with pytest.raises(FrozenInstanceError):
        c.title = "mutated"  # type: ignore[misc]


def test_ai_era_se_course_present():
    c = get_course("ai-era-se")
    assert c.slug == "ai-era-se"
    assert c.id == uuid.UUID("00000000-0000-4000-8000-000000000002")
    assert c.sort_order == 1
    # Full syllabus: 4 phases (LOW-1 follow-up)
    assert len(c.phases) == 4
    assert [p.phase for p in c.phases] == [1, 2, 3, 4]
    assert len(c.phases[0].tasks) == 8


def test_ai_era_se_phase1_system_prompt_contains_ai_usage_rules():
    p = get_phase("ai-era-se", 1)
    # 5 rules, literal text from syllabus
    assert "コピペ禁止" in p.system_prompt
    assert "動けばOKは禁止" in p.system_prompt
    assert "プロンプトはバージョン管理" in p.system_prompt
    assert "AIが見逃した問題" in p.system_prompt
    assert "毎週の作業ログ" in p.system_prompt


def test_ai_era_se_phase1_task_titles_match_syllabus():
    p = get_phase("ai-era-se", 1)
    titles = [t.title for t in p.tasks]
    assert "Git・ターミナル・VS Code 基礎" in titles[0]
    assert "PHPフレームワーク比較" in titles[1]
    assert "HTTP・API・DB" in titles[2]
    assert "業務DB読解" in titles[3]
    assert "Docker・ローカル環境構築" in titles[4]
    assert "AWSインフラ概念" in titles[5]
    assert "SQL実践" in titles[6]
    assert "フェーズ1振り返り" in titles[7]
