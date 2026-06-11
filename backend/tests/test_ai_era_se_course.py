"""Sprint 7 follow-up LOW-1 — ai-era-se full syllabus."""

from app.data.courses import get_course


def test_ai_era_se_has_four_phases():
    course = get_course("ai-era-se")
    assert len(course.phases) == 4
    assert [p.phase for p in course.phases] == [1, 2, 3, 4]


def test_ai_era_se_phase_task_counts():
    course = get_course("ai-era-se")
    counts = [len(p.tasks) for p in course.phases]
    assert counts == [8, 10, 8, 5]


def test_each_phase_system_prompt_includes_eval_criteria():
    course = get_course("ai-era-se")
    for p in course.phases:
        assert "評価基準" in p.system_prompt
        assert f"Phase {p.phase}" in p.system_prompt
