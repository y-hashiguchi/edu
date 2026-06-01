from app.memory.chat_store import InMemoryChatStore


def test_new_store_returns_empty_history():
    store = InMemoryChatStore()
    assert store.get_history(user_id="u1", phase=1) == []


def test_append_then_get_returns_messages_in_order():
    store = InMemoryChatStore()
    store.append(user_id="u1", phase=1, role="user", content="Git とは？")
    store.append(user_id="u1", phase=1, role="assistant", content="バージョン管理…")

    history = store.get_history(user_id="u1", phase=1)
    assert history == [
        {"role": "user", "content": "Git とは？"},
        {"role": "assistant", "content": "バージョン管理…"},
    ]


def test_history_is_scoped_per_user_and_phase():
    store = InMemoryChatStore()
    store.append(user_id="u1", phase=1, role="user", content="A")
    store.append(user_id="u1", phase=2, role="user", content="B")
    store.append(user_id="u2", phase=1, role="user", content="C")

    assert store.get_history("u1", 1) == [{"role": "user", "content": "A"}]
    assert store.get_history("u1", 2) == [{"role": "user", "content": "B"}]
    assert store.get_history("u2", 1) == [{"role": "user", "content": "C"}]


def test_clear_removes_only_targeted_thread():
    store = InMemoryChatStore()
    store.append("u1", 1, "user", "A")
    store.append("u1", 2, "user", "B")

    store.clear("u1", 1)

    assert store.get_history("u1", 1) == []
    assert store.get_history("u1", 2) == [{"role": "user", "content": "B"}]
