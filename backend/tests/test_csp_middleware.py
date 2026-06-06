"""CSP middleware test (MED-5).

The API does not render HTML, but a restrictive default-src policy on the
API origin acts as a tripwire — any accidental future inline rendering bug
would be sandboxed by the browser instead of executing.
"""

from unittest.mock import AsyncMock, MagicMock


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?"
        b"\x03\x00\x05\xfe\x02\xfe\xa3rH\x9c\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_csp_header_present_on_health_endpoint(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    csp = r.headers.get("content-security-policy", "")
    assert csp.startswith("default-src 'none'")
    assert "frame-ancestors 'none'" in csp
    assert "base-uri 'none'" in csp


def test_csp_header_present_on_404(client):
    """The middleware must attach the header even on 404 / 401, not just
    on happy-path responses."""
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.headers.get("content-security-policy", "").startswith("default-src")


def test_csp_header_present_on_file_download(auth_client, tmp_path, monkeypatch):
    """File downloads carry binary bodies and already get
    X-Content-Type-Options: nosniff. The CSP header must coexist with both."""
    from app.config import settings
    from app.core.claude_client import ClaudeClient, get_claude_client
    from app.main import app

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 0)

    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text='{"score":80,"feedback":"x"}')])
    )
    app.dependency_overrides[get_claude_client] = lambda: ClaudeClient(
        sdk=sdk, model="claude-sonnet-4-5"
    )
    try:
        created = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "see attached"},
            files=[("files", ("photo.png", _png_bytes(), "image/png"))],
        ).json()
        sub_id = created["id"]
        file_id = created["files"][0]["id"]

        r = auth_client.get(f"/api/submissions/{sub_id}/files/{file_id}")
        assert r.status_code == 200
        assert r.headers["content-security-policy"].startswith("default-src")
        # The pre-existing security header must still be present.
        assert r.headers["X-Content-Type-Options"] == "nosniff"
    finally:
        app.dependency_overrides.clear()
