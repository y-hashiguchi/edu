"""Sprint 7 — submissions: task_no upper bound is per-course."""

import pytest
from sqlalchemy import select

from app.data.courses import get_course
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.services.progress import initialize_progress_for_course


async def _enroll_in_se(db_session, auth_user):
    se = (await db_session.execute(select(Course).where(Course.slug == "ai-era-se"))).scalar_one()
    db_session.add(Enrollment(user_id=auth_user.id, course_id=se.id, status="active"))
    course_data = get_course("ai-era-se")
    await initialize_progress_for_course(
        db_session,
        auth_user.id,
        se.id,
        [p.phase for p in course_data.phases],
    )
    await db_session.commit()
    return se


@pytest.mark.asyncio
async def test_ai_era_se_accepts_task_no_8(client, auth_user, auth_token, db_session):
    await _enroll_in_se(db_session, auth_user)

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.post(
        "/api/submissions?course=ai-era-se",
        data={"phase": "1", "task_no": "8", "content": "essay"},
    )
    assert res.status_code in (200, 201)


@pytest.mark.asyncio
async def test_ai_era_se_rejects_task_no_9(client, auth_user, auth_token, db_session):
    await _enroll_in_se(db_session, auth_user)

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.post(
        "/api/submissions?course=ai-era-se",
        data={"phase": "1", "task_no": "9", "content": "essay"},
    )
    assert res.status_code == 422
