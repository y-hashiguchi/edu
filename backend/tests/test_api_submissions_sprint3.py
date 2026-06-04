"""Sprint 3 API tests: multipart, regrade, history."""

from unittest.mock import AsyncMock, MagicMock

from app.core.claude_client import ClaudeClient, get_claude_client


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?"
        b"\x03\x00\x05\xfe\x02\xfe\xa3rH\x9c\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _fake(reply: str) -> ClaudeClient:
    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=reply)])
    )
    return ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")


def test_multipart_submission_with_file(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 0)

    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":91,"feedback":"good"}'
    )
    try:
        response = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "see attached"},
            files=[("files", ("photo.png", _png_bytes(), "image/png"))],
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["score"] == 91
        assert len(body["files"]) == 1
        assert body["files"][0]["mime_type"] == "image/png"
        assert len(body["grading_history"]) == 1
        assert body["grading_history"][0]["score"] == 91
    finally:
        app.dependency_overrides.clear()


def test_multipart_submission_without_files_still_works(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"ok"}'
    )
    try:
        response = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "text only"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["score"] == 80
        assert body["files"] == []
    finally:
        app.dependency_overrides.clear()


def test_multipart_rejects_bad_extension(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"ok"}'
    )
    try:
        response = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "x"},
            files=[("files", ("evil.exe", b"MZ\x90\x00", "application/octet-stream"))],
        )
        assert response.status_code == 400
        assert "extension" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_multipart_rejects_too_many_files(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_files_per_submission", 2)

    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"ok"}'
    )
    try:
        files = [("files", (f"f{i}.png", _png_bytes(), "image/png")) for i in range(3)]
        response = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "x"},
            files=files,
        )
        assert response.status_code == 400
        assert "files" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_regrade_creates_new_attempt(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 0)

    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":70,"feedback":"first"}'
    )
    try:
        first = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "v"},
        ).json()
        sub_id = first["id"]

        app.dependency_overrides[get_claude_client] = lambda: _fake(
            '{"score":95,"feedback":"second"}'
        )
        regrade = auth_client.post(f"/api/submissions/{sub_id}/regrade")
        assert regrade.status_code == 200, regrade.text
        body = regrade.json()
        assert body["score"] == 95
        assert body["status"] == "graded"

        listed = auth_client.get("/api/submissions/1").json()
        history = listed[0]["grading_history"]
        assert len(history) == 2
        # newest first
        assert history[0]["score"] == 95
        assert history[1]["score"] == 70
    finally:
        app.dependency_overrides.clear()


def test_regrade_cooldown_returns_429(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 60)

    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":70,"feedback":"x"}'
    )
    try:
        first = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "v"},
        ).json()
        sub_id = first["id"]

        regrade = auth_client.post(f"/api/submissions/{sub_id}/regrade")
        assert regrade.status_code == 429
        assert int(regrade.headers["Retry-After"]) > 0
    finally:
        app.dependency_overrides.clear()


async def test_regrade_other_users_submission_returns_404(
    client, db_session, monkeypatch
):
    """A user can't regrade someone else's submission."""
    from app.config import settings
    from app.core.security import create_access_token, hash_password
    from app.main import app
    from app.models.user import User
    from app.services.progress import initialize_progress

    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 0)

    owner = User(
        email="owner@example.com", name="o", password_hash=hash_password("p")
    )
    intruder = User(
        email="intruder@example.com", name="i", password_hash=hash_password("p")
    )
    db_session.add_all([owner, intruder])
    await db_session.flush()
    await initialize_progress(db_session, owner.id)
    await initialize_progress(db_session, intruder.id)
    await db_session.commit()

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"x"}'
    )
    try:
        # Owner submits
        client.headers.update(
            {"Authorization": f"Bearer {create_access_token(subject=str(owner.id))}"}
        )
        first = client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "v"},
        ).json()
        sub_id = first["id"]

        # Intruder regrades
        client.headers.update(
            {"Authorization": f"Bearer {create_access_token(subject=str(intruder.id))}"}
        )
        regrade = client.post(f"/api/submissions/{sub_id}/regrade")
        assert regrade.status_code == 404
    finally:
        app.dependency_overrides.clear()
        client.headers.pop("Authorization", None)
