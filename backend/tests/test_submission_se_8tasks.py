"""Sprint 7 — submissions: task_no upper bound is per-course."""

import pytest
from sqlalchemy import select

from app.models.course import Course
from app.models.enrollment import Enrollment


@pytest.mark.asyncio
async def test_ai_era_se_accepts_task_no_8(
    client, auth_user, auth_token, db_session
):
    se = (await db_session.execute(
        select(Course).where(Course.slug == "ai-era-se")
    )).scalar_one()
    db_session.add(
        Enrollment(user_id=auth_user.id, course_id=se.id, status="active")
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.post(
        "/api/submissions?course=ai-era-se",
        data={"phase": "1", "task_no": "8", "content": "essay"},
    )
    assert res.status_code in (200, 201)


@pytest.mark.asyncio
async def test_ai_era_se_rejects_task_no_9(
    client, auth_user, auth_token, db_session
):
    se = (await db_session.execute(
        select(Course).where(Course.slug == "ai-era-se")
    )).scalar_one()
    db_session.add(
        Enrollment(user_id=auth_user.id, course_id=se.id, status="active")
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.post(
        "/api/submissions?course=ai-era-se",
        data={"phase": "1", "task_no": "9", "content": "essay"},
    )
    assert res.status_code == 422
