"""Sprint 4 model tests: is_admin, instructor_comments, notifications."""

import pytest

from app.core.security import hash_password
from app.models.user import User


@pytest.mark.asyncio
async def test_user_is_admin_default_false(db_session):
    """A freshly inserted user is NOT an admin unless the row says so.

    This is the load-bearing default for the whole RBAC story: the
    `get_current_admin` dependency, the alembic migration's
    server_default, and every existing pre-Sprint-4 user all rely on
    `is_admin` reading False by default.
    """
    user = User(
        email="reg@example.com",
        name="r",
        password_hash=hash_password("p"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.is_admin is False


@pytest.mark.asyncio
async def test_user_is_admin_can_be_true(db_session):
    """Explicitly opting a user in to admin status round-trips through
    the DB as True (not 1, not 't', not 'true' string)."""
    user = User(
        email="adm@example.com",
        name="a",
        password_hash=hash_password("p"),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.is_admin is True
