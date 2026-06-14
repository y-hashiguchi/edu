"""Tests for the promote_admin operator CLI."""

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.user import User


@pytest.mark.asyncio
async def test_promote_flips_is_admin(db_session, capsys):
    """Happy path: an existing non-admin user becomes admin and the
    change is persisted (not just printed)."""
    from scripts.promote_admin import promote

    user = User(
        email="newadmin@example.com",
        name="N",
        password_hash=hash_password("p"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.is_admin is False
    target_id = user.id

    rc = await promote("newadmin@example.com")
    assert rc == 0
    assert "promoted" in capsys.readouterr().out

    # Re-fetch through a fresh statement to confirm the DB write — relying
    # on the cached `user.is_admin` would mask a missing commit.
    refreshed = (
        await db_session.execute(select(User).where(User.id == target_id))
    ).scalar_one()
    await db_session.refresh(refreshed)
    assert refreshed.is_admin is True


@pytest.mark.asyncio
async def test_promote_is_idempotent(db_session, capsys):
    """Running promote against a user that is already admin is a no-op
    success, not an error. Ops people will re-run it after seeding."""
    from scripts.promote_admin import promote

    user = User(
        email="alreadyadmin@example.com",
        name="A",
        password_hash=hash_password("p"),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()

    rc = await promote("alreadyadmin@example.com")
    assert rc == 0
    assert "already admin" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_promote_unknown_email_returns_nonzero(capsys):
    from scripts.promote_admin import promote

    rc = await promote("nobody@example.com")
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_main_rejects_wrong_arg_count(capsys):
    from scripts.promote_admin import main

    assert main([]) == 2
    assert main(["a@b.com", "extra"]) == 2
    err = capsys.readouterr().err
    assert "usage" in err.lower()


def test_mask_email_keeps_domain_but_redacts_local_part():
    """MED-2 (sprint-4 security follow-up): operator scripts feed stdout
    and stderr into CloudWatch/Datadog, which has a wider read-audience
    than the DB. The raw learner email is PII — the CLI must mask the
    local part before printing."""
    from app.core.email_mask import mask_email

    assert mask_email("alice@example.com") == "a***@example.com"
    assert mask_email("ab@x.com") == "a***@x.com"
    assert mask_email("a@example.com") == "a***@example.com"
    assert mask_email("garbage") == "***"


@pytest.mark.asyncio
async def test_promote_logs_masked_email_only(db_session, capsys):
    """End-to-end check: the success log line keeps the domain but
    strips the local part below the first two chars. Validates the
    mask hits the actual print path, not only the helper."""
    from scripts.promote_admin import promote

    user = User(
        email="bob.alice@corp.example",
        name="B",
        password_hash=hash_password("p"),
    )
    db_session.add(user)
    await db_session.commit()

    rc = await promote("bob.alice@corp.example")
    assert rc == 0
    out = capsys.readouterr().out
    assert "b***@corp.example" in out
    # Raw local part must not leak.
    assert "bob.alice" not in out
