"""Sprint 9 — curriculum_edit service unit tests."""

import pytest
from sqlalchemy import select

from app.data.courses import runtime
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask
from app.models.submission import Submission
from app.services.curriculum_edit import (
    CannotDeleteLastPhaseError,
    CannotDeleteLastTaskError,
    PhaseHasSubmissionsError,
    PhaseNotFoundError,
    TaskHasSubmissionsError,
    add_phase,
    add_task,
    delete_phase,
    delete_task,
    discard_drafts,
    move_phase,
    move_task,
    publish_course,
    put_phase_draft,
    put_task_draft,
)


@pytest.mark.asyncio
async def test_put_phase_draft_sets_specified_fields_only(db_session, seed_curriculum):
    """field 省略 (key not in payload) = 変更なし、明示値 = draft 設定。"""
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": "新しい Phase 1 タイトル"},
    )
    await db_session.commit()

    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    row = (
        await db_session.execute(
            select(CurriculumPhase).where(
                CurriculumPhase.course_id == dev_id,
                CurriculumPhase.phase_no == 1,
            )
        )
    ).scalar_one()
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

    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    row = (
        await db_session.execute(
            select(CurriculumPhase).where(
                CurriculumPhase.course_id == dev_id,
                CurriculumPhase.phase_no == 1,
            )
        )
    ).scalar_one()
    assert row.draft_title is None


@pytest.mark.asyncio
async def test_put_phase_draft_404_on_unknown_phase(db_session, seed_curriculum):
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

    row = (
        await db_session.execute(
            select(CurriculumTask)
            .join(CurriculumPhase, CurriculumTask.phase_id == CurriculumPhase.id)
            .join(Course, CurriculumPhase.course_id == Course.id)
            .where(
                Course.slug == "ai-driven-dev",
                CurriculumPhase.phase_no == 1,
                CurriculumTask.task_no == 1,
            )
        )
    ).scalar_one()
    assert row.draft_skill_tags == ["NEW_TAG"]


@pytest.mark.asyncio
async def test_publish_course_promotes_drafts_and_reloads_cache(db_session, seed_curriculum):
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
    # Sprint 9 review HIGH (code-reviewer): cache refresh moved to the
    # route layer to run after db.commit(). The route is what hits
    # reload_course in production; the service test invokes it directly.
    await runtime.reload_course(db_session, "ai-driven-dev")
    assert result.published_phase_count == 1
    assert result.published_task_count == 1
    assert result.embedding_source_refs == ("course:ai-driven-dev:phase:1:task:0",)

    # cache が新値を返す
    course = runtime.get_cached_course("ai-driven-dev")
    assert course.phases[0].title == "公開対象タイトル"
    assert course.phases[0].tasks[0].title == "新 task 1 title"

    # draft 列はクリアされている
    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    p = (
        await db_session.execute(
            select(CurriculumPhase).where(
                CurriculumPhase.course_id == dev_id,
                CurriculumPhase.phase_no == 1,
            )
        )
    ).scalar_one()
    assert p.draft_title is None
    assert p.title == "公開対象タイトル"


@pytest.mark.asyncio
async def test_publish_course_skips_embedding_refs_when_title_unchanged(
    db_session, seed_curriculum
):
    await put_task_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        task_no=1,
        payload={"skill_tags": ["TAG_ONLY"]},
    )
    await db_session.commit()

    result = await publish_course(db_session, course_slug="ai-driven-dev")
    assert result.published_task_count == 1
    assert result.embedding_source_refs == ()


@pytest.mark.asyncio
async def test_discard_drafts_clears_all_drafts_for_course(db_session, seed_curriculum):
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

    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    p_rows = (
        (
            await db_session.execute(
                select(CurriculumPhase).where(CurriculumPhase.course_id == dev_id)
            )
        )
        .scalars()
        .all()
    )
    assert all(p.draft_title is None for p in p_rows)
    t_rows = (
        (
            await db_session.execute(
                select(CurriculumTask)
                .join(CurriculumPhase, CurriculumTask.phase_id == CurriculumPhase.id)
                .where(CurriculumPhase.course_id == dev_id)
            )
        )
        .scalars()
        .all()
    )
    assert all(t.draft_description is None for t in t_rows)


# ---------------------------------------------------------------------------
# Sprint 15 — task structure (add / delete / reorder)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_task_appends_at_end(db_session, seed_curriculum):
    row = await add_task(db_session, course_slug="ai-driven-dev", phase_no=1)
    await db_session.commit()
    assert row.task_no == 4
    assert row.title == "新しい Task"


@pytest.mark.asyncio
async def test_delete_task_renumbers_following_tasks(db_session, seed_curriculum):
    await add_task(db_session, course_slug="ai-driven-dev", phase_no=1)
    await db_session.commit()
    await delete_task(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        task_no=2,
    )
    await db_session.commit()

    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    tasks = (
        (
            await db_session.execute(
                select(CurriculumTask)
                .join(CurriculumPhase, CurriculumTask.phase_id == CurriculumPhase.id)
                .where(CurriculumPhase.course_id == dev_id, CurriculumPhase.phase_no == 1)
                .order_by(CurriculumTask.task_no)
            )
        )
        .scalars()
        .all()
    )
    assert [t.task_no for t in tasks] == [1, 2, 3]
    assert tasks[1].title != "新しい Task"  # old task 3 became 2


@pytest.mark.asyncio
async def test_delete_last_task_in_phase_raises(db_session, seed_curriculum):
    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    phase_id = (
        await db_session.execute(
            select(CurriculumPhase.id).where(
                CurriculumPhase.course_id == dev_id,
                CurriculumPhase.phase_no == 1,
            )
        )
    ).scalar_one()

    while True:
        tasks = (
            (
                await db_session.execute(
                    select(CurriculumTask).where(CurriculumTask.phase_id == phase_id)
                )
            )
            .scalars()
            .all()
        )
        if len(tasks) <= 1:
            break
        last_no = max(t.task_no for t in tasks)
        await delete_task(
            db_session,
            course_slug="ai-driven-dev",
            phase_no=1,
            task_no=last_no,
        )
        await db_session.flush()

    with pytest.raises(CannotDeleteLastTaskError):
        await delete_task(
            db_session,
            course_slug="ai-driven-dev",
            phase_no=1,
            task_no=1,
        )


@pytest.mark.asyncio
async def test_delete_task_with_submissions_raises(
    db_session, seed_curriculum, auth_user, default_course_id
):
    db_session.add(
        Submission(
            user_id=auth_user.id,
            course_id=default_course_id,
            phase=1,
            task_no=1,
            content="hello",
        )
    )
    await db_session.commit()

    with pytest.raises(TaskHasSubmissionsError):
        await delete_task(
            db_session,
            course_slug="ai-driven-dev",
            phase_no=1,
            task_no=1,
        )


@pytest.mark.asyncio
async def test_move_task_reorders_and_updates_submissions(
    db_session, seed_curriculum, auth_user, default_course_id
):
    db_session.add(
        Submission(
            user_id=auth_user.id,
            course_id=default_course_id,
            phase=1,
            task_no=3,
            content="task3",
        )
    )
    await db_session.commit()

    await move_task(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        task_no=3,
        to_task_no=1,
    )
    await db_session.commit()

    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    tasks = (
        (
            await db_session.execute(
                select(CurriculumTask)
                .join(CurriculumPhase, CurriculumTask.phase_id == CurriculumPhase.id)
                .where(CurriculumPhase.course_id == dev_id, CurriculumPhase.phase_no == 1)
                .order_by(CurriculumTask.task_no)
            )
        )
        .scalars()
        .all()
    )
    assert len(tasks) == 3
    assert tasks[0].task_no == 1

    sub = (
        await db_session.execute(
            select(Submission).where(
                Submission.user_id == auth_user.id,
                Submission.phase == 1,
            )
        )
    ).scalar_one()
    assert sub.task_no == 1
    assert sub.content == "task3"


@pytest.mark.asyncio
async def test_move_phase_reorders_and_updates_submissions(
    db_session, seed_curriculum, auth_user, default_course_id
):
    db_session.add(
        Submission(
            user_id=auth_user.id,
            course_id=default_course_id,
            phase=4,
            task_no=1,
            content="phase4",
        )
    )
    await db_session.commit()

    await move_phase(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=4,
        to_phase_no=1,
    )
    await db_session.commit()

    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    phases = (
        (
            await db_session.execute(
                select(CurriculumPhase)
                .where(CurriculumPhase.course_id == dev_id)
                .order_by(CurriculumPhase.phase_no)
            )
        )
        .scalars()
        .all()
    )
    assert len(phases) == 4
    assert phases[0].phase_no == 1

    sub = (
        await db_session.execute(
            select(Submission).where(
                Submission.user_id == auth_user.id,
                Submission.content == "phase4",
            )
        )
    ).scalar_one()
    assert sub.phase == 1


@pytest.mark.asyncio
async def test_add_phase_appends_with_one_task(db_session, seed_curriculum):
    row = await add_phase(db_session, course_slug="ai-driven-dev")
    await db_session.commit()
    await runtime.reload_course(db_session, "ai-driven-dev")

    assert row.phase_no == 5
    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    tasks = (
        (
            await db_session.execute(
                select(CurriculumTask)
                .join(CurriculumPhase, CurriculumTask.phase_id == CurriculumPhase.id)
                .where(CurriculumPhase.course_id == dev_id, CurriculumPhase.phase_no == 5)
            )
        )
        .scalars()
        .all()
    )
    assert len(tasks) == 1


@pytest.mark.asyncio
async def test_delete_phase_renumbers(db_session, seed_curriculum):
    await add_phase(db_session, course_slug="ai-driven-dev")
    await db_session.commit()
    await delete_phase(db_session, course_slug="ai-driven-dev", phase_no=5)
    await db_session.commit()

    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    phases = (
        (
            await db_session.execute(
                select(CurriculumPhase)
                .where(CurriculumPhase.course_id == dev_id)
                .order_by(CurriculumPhase.phase_no)
            )
        )
        .scalars()
        .all()
    )
    assert len(phases) == 4
    assert [p.phase_no for p in phases] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_delete_phase_with_submissions_raises(
    db_session, seed_curriculum, auth_user, default_course_id
):
    db_session.add(
        Submission(
            user_id=auth_user.id,
            course_id=default_course_id,
            phase=2,
            task_no=1,
            content="x",
        )
    )
    await db_session.commit()

    with pytest.raises(PhaseHasSubmissionsError):
        await delete_phase(db_session, course_slug="ai-driven-dev", phase_no=2)


@pytest.mark.asyncio
async def test_cannot_delete_last_phase(db_session, seed_curriculum):
    dev_id = (
        await db_session.execute(select(Course.id).where(Course.slug == "ai-driven-dev"))
    ).scalar_one()
    phases = (
        (
            await db_session.execute(
                select(CurriculumPhase).where(CurriculumPhase.course_id == dev_id)
            )
        )
        .scalars()
        .all()
    )
    for p in phases[1:]:
        await delete_phase(db_session, course_slug="ai-driven-dev", phase_no=p.phase_no)
        await db_session.commit()

    with pytest.raises(CannotDeleteLastPhaseError):
        await delete_phase(db_session, course_slug="ai-driven-dev", phase_no=1)
