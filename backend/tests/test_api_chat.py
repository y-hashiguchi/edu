from unittest.mock import AsyncMock, MagicMock

from app.core.claude_client import ClaudeClient, get_claude_client


def _fake_client(*replies: str) -> tuple[ClaudeClient, MagicMock]:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        side_effect=[MagicMock(content=[MagicMock(text=r)]) for r in replies]
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5"), fake_sdk


def test_chat_requires_auth(client, db_session):
    response = client.post("/api/chat", json={"phase": 1, "message": "hi"})
    assert response.status_code == 401


def test_chat_returns_reply_and_persists_history(auth_client):
    from app.main import app

    fake, _ = _fake_client("Gitはバージョン管理ツールです")
    app.dependency_overrides[get_claude_client] = lambda: fake

    try:
        response = auth_client.post(
            "/api/chat", json={"phase": 1, "message": "Gitとは？"}
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


def test_chat_carries_history_across_calls(auth_client):
    from app.main import app

    fake, fake_sdk = _fake_client("一つ目", "二つ目")
    app.dependency_overrides[get_claude_client] = lambda: fake

    try:
        auth_client.post("/api/chat", json={"phase": 1, "message": "Q1"})
        auth_client.post("/api/chat", json={"phase": 1, "message": "Q2"})

        second_call = fake_sdk.messages.create.await_args_list[1]
        roles = [m["role"] for m in second_call.kwargs["messages"]]
        assert roles == ["user", "assistant", "user"]
    finally:
        app.dependency_overrides.clear()


def test_chat_rejects_invalid_phase_via_validation(auth_client):
    response = auth_client.post("/api/chat", json={"phase": 99, "message": "hi"})
    assert response.status_code == 422


def test_chat_rejects_locked_phase_with_403(auth_client):
    from app.main import app

    fake, _ = _fake_client("never reached")
    app.dependency_overrides[get_claude_client] = lambda: fake
    try:
        response = auth_client.post("/api/chat", json={"phase": 2, "message": "hi"})
        assert response.status_code == 403
        assert response.json()["detail"] == "phase 2 is locked"
    finally:
        app.dependency_overrides.clear()


def test_chat_propagates_502_on_claude_error(auth_client):
    from app.main import app

    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(side_effect=RuntimeError("upstream down"))
    fake = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")
    app.dependency_overrides[get_claude_client] = lambda: fake

    try:
        response = auth_client.post("/api/chat", json={"phase": 1, "message": "hi"})
        assert response.status_code == 502
    finally:
        app.dependency_overrides.clear()


def test_chat_does_not_accept_extra_user_id_field(auth_client):
    """user_id を送っても無視される（Pydantic extra='ignore' のデフォルト）。"""
    from app.main import app

    fake, _ = _fake_client("ok")
    app.dependency_overrides[get_claude_client] = lambda: fake
    try:
        response = auth_client.post(
            "/api/chat",
            json={"phase": 1, "message": "hi", "user_id": "spoof"},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
