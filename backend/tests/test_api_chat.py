from unittest.mock import MagicMock

from app.core.claude_client import ClaudeClient, get_claude_client
from app.memory.chat_store import InMemoryChatStore, get_chat_store


def _fake_client(*replies: str) -> tuple[ClaudeClient, MagicMock]:
    fake_sdk = MagicMock()
    fake_sdk.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text=r)]) for r in replies
    ]
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5"), fake_sdk


def test_chat_returns_reply_and_persists_history(client):
    from app.main import app

    fake, _ = _fake_client("Gitはバージョン管理ツールです")
    store = InMemoryChatStore()
    app.dependency_overrides[get_claude_client] = lambda: fake
    app.dependency_overrides[get_chat_store] = lambda: store

    try:
        response = client.post(
            "/api/chat",
            json={"user_id": "u1", "phase": 1, "message": "Gitとは？"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "Gitはバージョン管理ツールです"
        assert data["history"] == [
            {"role": "user", "content": "Gitとは？"},
            {"role": "assistant", "content": "Gitはバージョン管理ツールです"},
        ]
    finally:
        app.dependency_overrides.clear()


def test_chat_carries_history_across_calls(client):
    from app.main import app

    fake, fake_sdk = _fake_client("一つ目", "二つ目")
    store = InMemoryChatStore()
    app.dependency_overrides[get_claude_client] = lambda: fake
    app.dependency_overrides[get_chat_store] = lambda: store

    try:
        client.post("/api/chat", json={"user_id": "u1", "phase": 1, "message": "Q1"})
        client.post("/api/chat", json={"user_id": "u1", "phase": 1, "message": "Q2"})

        second_call_messages = fake_sdk.messages.create.call_args_list[1].kwargs["messages"]
        roles = [m["role"] for m in second_call_messages]
        assert roles == ["user", "assistant", "user"]
    finally:
        app.dependency_overrides.clear()


def test_chat_rejects_invalid_phase(client):
    response = client.post(
        "/api/chat",
        json={"user_id": "u1", "phase": 99, "message": "hi"},
    )
    assert response.status_code == 422
