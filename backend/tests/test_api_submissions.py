from unittest.mock import AsyncMock, MagicMock

from app.core.claude_client import ClaudeClient, get_claude_client


def _fake(reply: str) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=reply)])
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")


def test_submit_requires_auth(client, db_session):
    response = client.post(
        "/api/submissions", json={"phase": 1, "task_no": 1, "content": "x"}
    )
    assert response.status_code == 401


def test_submit_creates_and_returns_grade(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":88,"feedback":"good"}'
    )
    try:
        response = auth_client.post(
            "/api/submissions",
            json={"phase": 1, "task_no": 1, "content": "Gitでブランチ切りました"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["score"] == 88
        assert "good" in body["ai_feedback"]
    finally:
        app.dependency_overrides.clear()


def test_submit_locked_phase_returns_403(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"x"}'
    )
    try:
        response = auth_client.post(
            "/api/submissions", json={"phase": 2, "task_no": 1, "content": "x"}
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_submit_invalid_task_returns_422(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"x"}'
    )
    try:
        response = auth_client.post(
            "/api/submissions", json={"phase": 1, "task_no": 99, "content": "x"}
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_list_returns_submissions(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"x"}'
    )
    try:
        auth_client.post(
            "/api/submissions", json={"phase": 1, "task_no": 1, "content": "A"}
        )
        auth_client.post(
            "/api/submissions", json={"phase": 1, "task_no": 2, "content": "B"}
        )
        response = auth_client.get("/api/submissions/1")
        assert response.status_code == 200
        data = response.json()
        assert [r["task_no"] for r in data] == [1, 2]
    finally:
        app.dependency_overrides.clear()


def test_list_requires_auth(client, db_session):
    response = client.get("/api/submissions/1")
    assert response.status_code == 401


def test_all_submissions_promote_progress_to_submitted(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"x"}'
    )
    try:
        for tno in (1, 2, 3):
            auth_client.post(
                "/api/submissions",
                json={"phase": 1, "task_no": tno, "content": f"task {tno}"},
            )
        resp = auth_client.get("/api/progress")
        phases = {r["phase"]: r["status"] for r in resp.json()}
        assert phases[1] == "submitted"
    finally:
        app.dependency_overrides.clear()
