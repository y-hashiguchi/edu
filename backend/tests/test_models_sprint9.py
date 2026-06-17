"""Sprint 9 model tests — CurriculumPhase / CurriculumTask."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask


@pytest.mark.asyncio
async def test_curriculum_phase_unique_course_phase_no(db_session):
    c = Course(slug="x", title="X", sort_order=0)
    db_session.add(c)
    await db_session.flush()

    p = CurriculumPhase(
        course_id=c.id,
        phase_no=1,
        title="t",
        goal="g",
        system_prompt="s",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    assert p.id is not None

    dup = CurriculumPhase(
        course_id=c.id,
        phase_no=1,
        title="t2",
        goal="g2",
        system_prompt="s2",
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_curriculum_task_unique_phase_task_no(db_session):
    c = Course(slug="x", title="X", sort_order=0)
    db_session.add(c)
    await db_session.flush()
    p = CurriculumPhase(
        course_id=c.id,
        phase_no=1,
        title="t",
        goal="g",
        system_prompt="s",
    )
    db_session.add(p)
    await db_session.flush()

    t = CurriculumTask(
        phase_id=p.id,
        task_no=1,
        title="task",
        description="d",
        skill_tags=["A"],
    )
    db_session.add(t)
    await db_session.commit()

    dup = CurriculumTask(
        phase_id=p.id,
        task_no=1,
        title="task2",
        description="d2",
        skill_tags=["B"],
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_phase_delete_cascades_tasks(db_session):
    """ON DELETE CASCADE: phase が消えたら tasks も消える。"""
    c = Course(slug="x", title="X", sort_order=0)
    db_session.add(c)
    await db_session.flush()
    p = CurriculumPhase(
        course_id=c.id,
        phase_no=1,
        title="t",
        goal="g",
        system_prompt="s",
    )
    db_session.add(p)
    await db_session.flush()
    db_session.add(
        CurriculumTask(
            phase_id=p.id,
            task_no=1,
            title="task",
            description="d",
            skill_tags=[],
        )
    )
    await db_session.commit()

    task_id = (
        await db_session.execute(select(CurriculumTask.id).where(CurriculumTask.phase_id == p.id))
    ).scalar_one()
    await db_session.delete(p)
    await db_session.commit()
    # Sprint 9 conftest pre-seeds CurriculumTask rows from COURSE_REGISTRY,
    # so a global SELECT no longer reflects only this test's row. Assert
    # via primary key instead.
    assert await db_session.get(CurriculumTask, task_id) is None


@pytest.mark.asyncio
async def test_curriculum_task_skill_tags_stores_list(db_session):
    """skill_tags は JSONB で list[str] のラウンドトリップが効くこと。"""
    c = Course(slug="x", title="X", sort_order=0)
    db_session.add(c)
    await db_session.flush()
    p = CurriculumPhase(
        course_id=c.id,
        phase_no=1,
        title="t",
        goal="g",
        system_prompt="s",
    )
    db_session.add(p)
    await db_session.flush()

    t = CurriculumTask(
        phase_id=p.id,
        task_no=1,
        title="task",
        description="d",
        skill_tags=["Git/GitHub", "API基礎"],
        deliverable="report.md",
        week_label="第1週",
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    assert t.skill_tags == ["Git/GitHub", "API基礎"]
    assert t.deliverable == "report.md"
    assert t.week_label == "第1週"
