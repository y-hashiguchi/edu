import pytest

from app.core.security import hash_password
from app.models.progress import ProgressStatus
from app.models.user import User
from app.services.progress import (
    PhaseLockedError,
    PhaseNotFoundError,
    complete_phase,
    initialize_progress,
    is_phase_unlocked,
    list_progress,
)


async def _make_user(db, email: str = "alice@example.com") -> User:
    user = User(email=email, name="Alice", password_hash=hash_password("password123"))
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_initialize_progress_seeds_four_rows(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    rows = await list_progress(db_session, user.id)
    assert [r.phase for r in rows] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_initialize_phase1_in_progress_others_locked(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    rows = await list_progress(db_session, user.id)
    statuses = [r.status for r in rows]
    assert statuses == [
        ProgressStatus.IN_PROGRESS.value,
        ProgressStatus.LOCKED.value,
        ProgressStatus.LOCKED.value,
        ProgressStatus.LOCKED.value,
    ]
    assert rows[0].started_at is not None
    assert all(r.started_at is None for r in rows[1:])


@pytest.mark.asyncio
async def test_is_phase_unlocked(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    assert await is_phase_unlocked(db_session, user.id, 1) is True
    assert await is_phase_unlocked(db_session, user.id, 2) is False


@pytest.mark.asyncio
async def test_complete_phase_unlocks_next(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()

    current, nxt = await complete_phase(db_session, user.id, 1)
    assert current.status == ProgressStatus.COMPLETED.value
    assert current.completed_at is not None
    assert nxt is not None
    assert nxt.phase == 2
    assert nxt.status == ProgressStatus.IN_PROGRESS.value
    assert nxt.started_at is not None


@pytest.mark.asyncio
async def test_complete_last_phase_returns_no_next(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    for ph in [1, 2, 3]:
        await complete_phase(db_session, user.id, ph)

    current, nxt = await complete_phase(db_session, user.id, 4)
    assert current.phase == 4
    assert current.status == ProgressStatus.COMPLETED.value
    assert nxt is None


@pytest.mark.asyncio
async def test_complete_already_completed_is_idempotent(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()

    await complete_phase(db_session, user.id, 1)
    current, nxt = await complete_phase(db_session, user.id, 1)
    assert current.status == ProgressStatus.COMPLETED.value
    assert nxt is None


@pytest.mark.asyncio
async def test_complete_locked_phase_raises(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    with pytest.raises(PhaseLockedError):
        await complete_phase(db_session, user.id, 2)


@pytest.mark.asyncio
async def test_complete_missing_progress_raises(db_session):
    user = await _make_user(db_session)
    await db_session.commit()
    with pytest.raises(PhaseNotFoundError):
        await complete_phase(db_session, user.id, 1)


@pytest.mark.asyncio
async def test_progress_isolated_per_user(db_session):
    alice = await _make_user(db_session, "alice@example.com")
    bob = await _make_user(db_session, "bob@example.com")
    await initialize_progress(db_session, alice.id)
    await initialize_progress(db_session, bob.id)
    await db_session.commit()

    await complete_phase(db_session, alice.id, 1)

    bob_rows = await list_progress(db_session, bob.id)
    assert bob_rows[0].status == ProgressStatus.IN_PROGRESS.value
    assert bob_rows[1].status == ProgressStatus.LOCKED.value
