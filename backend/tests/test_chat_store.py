import pytest

from app.core.security import hash_password
from app.memory.chat_store import SqlChatStore
from app.models.user import User


async def _make_user(db, email: str = "alice@example.com") -> User:
    user = User(email=email, name="A", password_hash=hash_password("password123"))
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_get_history_returns_empty_initially(db_session):
    user = await _make_user(db_session)
    store = SqlChatStore(db_session)
    assert await store.get_history(user.id, 1) == []


@pytest.mark.asyncio
async def test_append_then_get_returns_messages_in_order(db_session):
    user = await _make_user(db_session)
    store = SqlChatStore(db_session)

    await store.append(user.id, 1, "user", "Gitとは？")
    await store.append(user.id, 1, "assistant", "バージョン管理…")
    await db_session.commit()

    history = await store.get_history(user.id, 1)
    assert history == [
        {"role": "user", "content": "Gitとは？"},
        {"role": "assistant", "content": "バージョン管理…"},
    ]


@pytest.mark.asyncio
async def test_history_isolated_per_user(db_session):
    alice = await _make_user(db_session, "alice@example.com")
    bob = await _make_user(db_session, "bob@example.com")
    store = SqlChatStore(db_session)

    await store.append(alice.id, 1, "user", "A")
    await store.append(bob.id, 1, "user", "B")
    await db_session.commit()

    assert await store.get_history(alice.id, 1) == [{"role": "user", "content": "A"}]
    assert await store.get_history(bob.id, 1) == [{"role": "user", "content": "B"}]


@pytest.mark.asyncio
async def test_history_isolated_per_phase(db_session):
    user = await _make_user(db_session)
    store = SqlChatStore(db_session)

    await store.append(user.id, 1, "user", "P1")
    await store.append(user.id, 2, "user", "P2")
    await db_session.commit()

    assert await store.get_history(user.id, 1) == [{"role": "user", "content": "P1"}]
    assert await store.get_history(user.id, 2) == [{"role": "user", "content": "P2"}]


@pytest.mark.asyncio
async def test_history_persists_across_sessions(db_session):
    """別セッションで読み直しても見える。"""
    from app.db.session import SessionLocal

    user = await _make_user(db_session)
    store = SqlChatStore(db_session)
    await store.append(user.id, 1, "user", "永続")
    await db_session.commit()
    user_id = user.id

    async with SessionLocal() as another:
        other = SqlChatStore(another)
        history = await other.get_history(user_id, 1)
        assert history == [{"role": "user", "content": "永続"}]
