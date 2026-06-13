"""Sprint 9 — process-local curriculum cache tests."""

import uuid

import pytest

from app.data.courses import runtime
from app.data.courses.types import CourseData, PhaseData, TaskItem


@pytest.mark.asyncio
async def test_reload_from_db_populates_cache(db_session, seed_curriculum):
    """seed_curriculum fixture (Task 10 で追加) が curriculum_phases /
    curriculum_tasks を埋めた後、reload_from_db で cache が満たされる。"""
    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    course = runtime.get_cached_course("ai-driven-dev")
    assert isinstance(course, CourseData)
    assert course.slug == "ai-driven-dev"
    assert len(course.phases) == 4
    p1 = course.phases[0]
    assert isinstance(p1, PhaseData)
    assert p1.phase == 1
    assert len(p1.tasks) == 3
    t1 = p1.tasks[0]
    assert isinstance(t1, TaskItem)
    assert "Git" in t1.title


@pytest.mark.asyncio
async def test_get_cached_course_raises_on_unknown_slug(
    db_session, seed_curriculum
):
    from app.data.courses import CourseNotFoundError

    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    with pytest.raises(CourseNotFoundError):
        runtime.get_cached_course("nope")


@pytest.mark.asyncio
async def test_reload_course_updates_single_course_only(
    db_session, seed_curriculum
):
    """publish 後の差し替え: 1 course だけ rebuild、他は不変。"""
    from app.models.curriculum_phase import CurriculumPhase
    from sqlalchemy import select, update
    from app.models.course import Course

    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    before_se = runtime.get_cached_course("ai-era-se")

    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    stmt = update(CurriculumPhase).where(
        CurriculumPhase.course_id == dev_id, CurriculumPhase.phase_no == 1
    ).values(title="X 更新後")
    await db_session.execute(stmt)
    await db_session.commit()

    await runtime.reload_course(db_session, "ai-driven-dev")
    after_dev = runtime.get_cached_course("ai-driven-dev")
    after_se = runtime.get_cached_course("ai-era-se")
    assert after_dev.phases[0].title == "X 更新後"
    assert after_se is before_se  # same object → unchanged


@pytest.mark.asyncio
async def test_cache_returns_published_not_draft(db_session, seed_curriculum):
    """draft_title が入っていても、cache (= runtime) は published 値を返す。"""
    from app.models.curriculum_phase import CurriculumPhase
    from sqlalchemy import select, update
    from app.models.course import Course

    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    await db_session.execute(
        update(CurriculumPhase).where(
            CurriculumPhase.course_id == dev_id,
            CurriculumPhase.phase_no == 1,
        ).values(draft_title="DRAFT ONLY")
    )
    await db_session.commit()

    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    course = runtime.get_cached_course("ai-driven-dev")
    assert course.phases[0].title != "DRAFT ONLY"


@pytest.mark.asyncio
async def test_reload_from_db_on_empty_table_raises(db_session):
    """0 行検出時はエラー (silent fallback ではなく、明示的に起動失敗)。"""
    from sqlalchemy import delete
    from app.models.curriculum_phase import CurriculumPhase
    from app.models.curriculum_task import CurriculumTask

    await db_session.execute(delete(CurriculumTask))
    await db_session.execute(delete(CurriculumPhase))
    await db_session.commit()

    runtime._CACHE.clear()
    with pytest.raises(RuntimeError, match="curriculum_phases is empty"):
        await runtime.reload_from_db(db_session)
