"""Sprint 9 — curriculum_edit service unit tests."""

import pytest
from sqlalchemy import select

from app.data.courses import runtime
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask
from app.services.curriculum_edit import (
    PhaseNotFoundError,
    TaskNotFoundError,
    discard_drafts,
    publish_course,
    put_phase_draft,
    put_task_draft,
)


@pytest.mark.asyncio
async def test_put_phase_draft_sets_specified_fields_only(
    db_session, seed_curriculum
):
    """field 省略 (key not in payload) = 変更なし、明示値 = draft 設定。"""
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": "新しい Phase 1 タイトル"},
    )
    await db_session.commit()

    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    row = (await db_session.execute(
        select(CurriculumPhase).where(
            CurriculumPhase.course_id == dev_id,
            CurriculumPhase.phase_no == 1,
        )
    )).scalar_one()
    assert row.draft_title == "新しい Phase 1 タイトル"
    assert row.draft_goal is None  # 省略 → 変更なし


@pytest.mark.asyncio
async def test_put_phase_draft_none_clears_draft(db_session, seed_curriculum):
    """payload に明示 None を入れると draft をクリア。"""
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": "draft"},
    )
    await db_session.commit()
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": None},
    )
    await db_session.commit()

    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    row = (await db_session.execute(
        select(CurriculumPhase).where(
            CurriculumPhase.course_id == dev_id,
            CurriculumPhase.phase_no == 1,
        )
    )).scalar_one()
    assert row.draft_title is None


@pytest.mark.asyncio
async def test_put_phase_draft_404_on_unknown_phase(
    db_session, seed_curriculum
):
    with pytest.raises(PhaseNotFoundError):
        await put_phase_draft(
            db_session,
            course_slug="ai-driven-dev",
            phase_no=99,
            payload={"title": "x"},
        )


@pytest.mark.asyncio
async def test_put_task_draft_handles_skill_tags(db_session, seed_curriculum):
    await put_task_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        task_no=1,
        payload={"skill_tags": ["NEW_TAG"]},
    )
    await db_session.commit()

    row = (await db_session.execute(
        select(CurriculumTask)
        .join(CurriculumPhase, CurriculumTask.phase_id == CurriculumPhase.id)
        .join(Course, CurriculumPhase.course_id == Course.id)
        .where(
            Course.slug == "ai-driven-dev",
            CurriculumPhase.phase_no == 1,
            CurriculumTask.task_no == 1,
        )
    )).scalar_one()
    assert row.draft_skill_tags == ["NEW_TAG"]


@pytest.mark.asyncio
async def test_publish_course_promotes_drafts_and_reloads_cache(
    db_session, seed_curriculum
):
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": "公開対象タイトル"},
    )
    await put_task_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        task_no=1,
        payload={"title": "新 task 1 title"},
    )
    await db_session.commit()

    result = await publish_course(db_session, course_slug="ai-driven-dev")
    await db_session.commit()
    assert result.published_phase_count == 1
    assert result.published_task_count == 1

    # cache が新値を返す
    course = runtime.get_cached_course("ai-driven-dev")
    assert course.phases[0].title == "公開対象タイトル"
    assert course.phases[0].tasks[0].title == "新 task 1 title"

    # draft 列はクリアされている
    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    p = (await db_session.execute(
        select(CurriculumPhase).where(
            CurriculumPhase.course_id == dev_id,
            CurriculumPhase.phase_no == 1,
        )
    )).scalar_one()
    assert p.draft_title is None
    assert p.title == "公開対象タイトル"


@pytest.mark.asyncio
async def test_discard_drafts_clears_all_drafts_for_course(
    db_session, seed_curriculum
):
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": "discard me"},
    )
    await put_task_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        task_no=1,
        payload={"description": "discard me too"},
    )
    await db_session.commit()

    await discard_drafts(db_session, course_slug="ai-driven-dev")
    await db_session.commit()

    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    p_rows = (await db_session.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == dev_id)
    )).scalars().all()
    assert all(p.draft_title is None for p in p_rows)
    t_rows = (await db_session.execute(
        select(CurriculumTask)
        .join(CurriculumPhase, CurriculumTask.phase_id == CurriculumPhase.id)
        .where(CurriculumPhase.course_id == dev_id)
    )).scalars().all()
    assert all(t.draft_description is None for t in t_rows)
