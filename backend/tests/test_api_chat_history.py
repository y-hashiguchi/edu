from unittest.mock import AsyncMock, MagicMock

from app.core.claude_client import ClaudeClient, get_claude_client


def _fake_client(*replies: str) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        side_effect=[MagicMock(content=[MagicMock(text=r)]) for r in replies]
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")


def test_get_history_returns_empty_array_initially(auth_client):
    response = auth_client.get("/api/chat/history/1")
    assert response.status_code == 200
    assert response.json() == []


def test_get_history_returns_ordered_messages(auth_client):
    from app.main import app

    fake = _fake_client("A1", "A2")
    app.dependency_overrides[get_claude_client] = lambda: fake
    try:
        auth_client.post("/api/chat", json={"phase": 1, "message": "Q1"})
        auth_client.post("/api/chat", json={"phase": 1, "message": "Q2"})
    finally:
        app.dependency_overrides.clear()

    response = auth_client.get("/api/chat/history/1")
    assert response.status_code == 200
    history = response.json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert [m["content"] for m in history] == ["Q1", "A1", "Q2", "A2"]


def test_get_history_requires_auth(client, db_session):
    response = client.get("/api/chat/history/1")
    assert response.status_code == 401


def test_get_history_returns_403_for_locked_phase(auth_client):
    response = auth_client.get("/api/chat/history/2")
    assert response.status_code == 403
    assert response.json()["detail"] == "phase 2 is locked"


def test_get_history_rejects_invalid_phase(auth_client):
    response = auth_client.get("/api/chat/history/99")
    assert response.status_code == 422
