"""Sprint 5 model tests — UserNudge cache row."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.user import User
from app.models.user_nudge import UserNudge


async def _make_user(db_session, email="u@e.com"):
    user = User(email=email, name="U", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_user_nudge_round_trip(db_session, default_course_id):
    user = await _make_user(db_session)
    nudge = UserNudge(
        user_id=user.id,
        course_id=default_course_id,
        body="今日は データ構造 を伸ばすチャンスです。",
        generated_at=datetime.now(UTC),
        input_signature="abc1234567890def",
    )
    db_session.add(nudge)
    await db_session.commit()
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).scalar_one()
    assert row.body.startswith("今日は")


@pytest.mark.asyncio
async def test_user_nudge_pk_is_user_id(db_session, default_course_id):
    """1 user = 1 row, so a second insert with the same user_id must fail."""
    user = await _make_user(db_session)
    db_session.add(UserNudge(
        user_id=user.id, course_id=default_course_id, body="a",
        generated_at=datetime.now(UTC),
        input_signature="x" * 16,
    ))
    await db_session.commit()

    db_session.add(UserNudge(
        user_id=user.id, course_id=default_course_id, body="b",
        generated_at=datetime.now(UTC),
        input_signature="y" * 16,
    ))
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_nudge_cascades_on_user_delete(db_session, default_course_id):
    user = await _make_user(db_session)
    db_session.add(UserNudge(
        user_id=user.id, course_id=default_course_id, body="a",
        generated_at=datetime.now(UTC),
        input_signature="x" * 16,
    ))
    await db_session.commit()

    await db_session.delete(user)
    await db_session.commit()
    leftover = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).first()
    assert leftover is None
