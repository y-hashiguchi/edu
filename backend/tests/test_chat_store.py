import pytest

from app.memory.chat_store import InMemoryChatStore


@pytest.mark.asyncio
async def test_new_store_returns_empty_history():
    store = InMemoryChatStore()
    assert await store.get_history(user_id="u1", phase=1) == []


@pytest.mark.asyncio
async def test_append_then_get_returns_messages_in_order():
    store = InMemoryChatStore()
    await store.append(user_id="u1", phase=1, role="user", content="Git とは？")
    await store.append(user_id="u1", phase=1, role="assistant", content="バージョン管理…")

    history = await store.get_history(user_id="u1", phase=1)
    assert history == [
        {"role": "user", "content": "Git とは？"},
        {"role": "assistant", "content": "バージョン管理…"},
    ]


@pytest.mark.asyncio
async def test_history_is_scoped_per_user_and_phase():
    store = InMemoryChatStore()
    await store.append(user_id="u1", phase=1, role="user", content="A")
    await store.append(user_id="u1", phase=2, role="user", content="B")
    await store.append(user_id="u2", phase=1, role="user", content="C")

    assert await store.get_history("u1", 1) == [{"role": "user", "content": "A"}]
    assert await store.get_history("u1", 2) == [{"role": "user", "content": "B"}]
    assert await store.get_history("u2", 1) == [{"role": "user", "content": "C"}]


@pytest.mark.asyncio
async def test_clear_removes_only_targeted_thread():
    store = InMemoryChatStore()
    await store.append("u1", 1, "user", "A")
    await store.append("u1", 2, "user", "B")

    await store.clear("u1", 1)

    assert await store.get_history("u1", 1) == []
    assert await store.get_history("u1", 2) == [{"role": "user", "content": "B"}]
