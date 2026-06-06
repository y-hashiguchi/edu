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


def test_create_submission_rejects_overlong_content(auth_client, tmp_path, monkeypatch):
    """HIGH-1: server enforces max_length on the content form field."""
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"x"}'
    )
    try:
        response = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "x" * 10_001},
        )
        # Pydantic validation runs before any business logic.
        assert response.status_code == 422, response.text
    finally:
        app.dependency_overrides.clear()


def test_rate_limit_blocks_burst_create_submission(
    auth_client, tmp_path, monkeypatch
):
    """HIGH-5: more than `submission_rate_limit` POSTs in a short window 429."""
    from app.config import settings
    from app.core.limiter import limiter

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(limiter, "enabled", True)
    # `limits` MemoryStorage is keyed by (route, IP). TestClient always uses
    # 127.0.0.1, so a previous suite run could leave residue. Reset to ensure
    # the bucket starts empty.
    try:
        limiter._storage.reset()
    except Exception:  # pragma: no cover - storage backends differ
        pass

    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"x"}'
    )
    try:
        statuses = []
        for i in range(11):
            r = auth_client.post(
                "/api/submissions",
                data={
                    "phase": "1",
                    "task_no": str((i % 5) + 1),
                    "content": f"burst-{i}",
                },
            )
            statuses.append(r.status_code)
        assert 429 in statuses, statuses
    finally:
        app.dependency_overrides.clear()


def test_limit_upload_size_middleware_rejects_oversized_body():
    """CRITICAL-2: middleware rejects on content-length without reading body."""
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient as StarletteTestClient

    from app.main import LimitUploadSize

    async def echo(_request):
        return PlainTextResponse("ok")

    sub_app = Starlette(routes=[Route("/echo", echo, methods=["POST"])])
    sub_app.add_middleware(LimitUploadSize, max_body_bytes=1024)
    sub_client = StarletteTestClient(sub_app)

    body_within = b"x" * 512
    body_over = b"x" * 2048
    assert sub_client.post("/echo", content=body_within).status_code == 200
    over_response = sub_client.post("/echo", content=body_over)
    assert over_response.status_code == 413
    assert "too large" in over_response.json()["detail"]


def test_files_dto_exposes_only_filename(auth_client, tmp_path, monkeypatch):
    """HIGH-3: SubmissionFileOut must not leak the absolute server path."""
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"x"}'
    )
    try:
        response = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "v"},
            files=[("files", ("photo.png", _png_bytes(), "image/png"))],
        )
        assert response.status_code == 201, response.text
        body = response.json()
        f = body["files"][0]
        assert f["filename"] == "photo.png"
        assert "file_path" not in f
    finally:
        app.dependency_overrides.clear()


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


def test_download_file_returns_content(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 0)

    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake(
        '{"score":80,"feedback":"x"}'
    )
    try:
        first = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "v"},
            files=[("files", ("photo.png", _png_bytes(), "image/png"))],
        ).json()
        sub_id = first["id"]
        file_id = first["files"][0]["id"]

        resp = auth_client.get(f"/api/submissions/{sub_id}/files/{file_id}")
        assert resp.status_code == 200, resp.text
        assert resp.content.startswith(b"\x89PNG")
        assert resp.headers["content-disposition"].startswith("attachment;")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
    finally:
        app.dependency_overrides.clear()


async def test_download_other_users_file_returns_404(
    client, db_session, tmp_path, monkeypatch
):
    from app.config import settings
    from app.core.security import create_access_token, hash_password
    from app.main import app
    from app.models.user import User
    from app.services.progress import initialize_progress

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 0)

    owner = User(
        email="own@example.com", name="o", password_hash=hash_password("p")
    )
    intruder = User(
        email="int@example.com", name="i", password_hash=hash_password("p")
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
        client.headers.update(
            {"Authorization": f"Bearer {create_access_token(subject=str(owner.id))}"}
        )
        first = client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "v"},
            files=[("files", ("photo.png", _png_bytes(), "image/png"))],
        ).json()
        sub_id = first["id"]
        file_id = first["files"][0]["id"]

        client.headers.update(
            {"Authorization": f"Bearer {create_access_token(subject=str(intruder.id))}"}
        )
        resp = client.get(f"/api/submissions/{sub_id}/files/{file_id}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
        client.headers.pop("Authorization", None)
