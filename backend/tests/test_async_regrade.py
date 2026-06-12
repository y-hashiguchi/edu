"""Sprint 8 follow-up — POST /api/submissions/{id}/regrade async path
and GET /api/me/submissions/{id} polling endpoint."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.claude_client import ClaudeClient, get_claude_client
from app.main import app


def _fake_claude(reply: str = '{"score": 80, "feedback": "ok"}') -> ClaudeClient:
    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=reply)])
    )
    return ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")


async def _create_graded_submission(
    auth_client, auth_user, db_session
) -> dict:
    app.dependency_overrides[get_claude_client] = lambda: _fake_claude(
        '{"score": 80, "feedback": "first"}'
    )
    try:
        res = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "essay"},
        )
        assert res.status_code in (200, 201), res.text
        return res.json()
    finally:
        app.dependency_overrides.pop(get_claude_client, None)


@pytest.mark.asyncio
async def test_get_my_submission_returns_full_shape(
    auth_client, auth_user, db_session, monkeypatch
):
    from app.config import settings

    monkeypatch.setattr(settings, "grading_async_enabled", False)
    submission = await _create_graded_submission(auth_client, auth_user, db_session)
    sub_id = submission["id"]

    res = auth_client.get(f"/api/me/submissions/{sub_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == sub_id
    assert body["phase"] == 1
    assert body["task_no"] == 1
    assert body["score"] == 80
    assert body["graded_at"] is not None
    # grading_history is most-recent-first
    assert len(body["grading_history"]) >= 1
    assert body["grading_history"][0]["status"] == "graded"


@pytest.mark.asyncio
async def test_get_my_submission_404_for_other_users_submission(
    client, auth_user, admin_user, admin_token, db_session, monkeypatch
):
    """BOLA boundary: an admin (or any other learner) calling /api/me/
    cannot read another user's submission. /api/me/ pins user_id."""
    from app.config import settings
    from app.core.security import create_access_token

    monkeypatch.setattr(settings, "grading_async_enabled", False)

    # Owner creates a submission.
    owner_token = create_access_token(subject=str(auth_user.id))
    client.headers.update({"Authorization": f"Bearer {owner_token}"})
    submission = await _create_graded_submission(client, auth_user, db_session)
    sub_id = submission["id"]

    # Admin tries to read it via /api/me/.
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get(f"/api/me/submissions/{sub_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_my_submission_404_for_unknown_id(auth_client):
    res = auth_client.get(f"/api/me/submissions/{uuid.uuid4()}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_async_regrade_returns_pending_and_resets_graded_at(
    auth_client, auth_user, db_session, monkeypatch
):
    """In async mode, regrade returns a synthetic PENDING attempt and
    clears graded_at so the frontend knows to poll."""
    from app.config import settings

    # Seed a sync-graded submission first.
    monkeypatch.setattr(settings, "grading_async_enabled", False)
    submission = await _create_graded_submission(auth_client, auth_user, db_session)
    sub_id = submission["id"]
    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 0)

    # Switch to async + stub enqueue_grading so we don't hit Redis.
    monkeypatch.setattr(settings, "grading_async_enabled", True)
    with patch(
        "app.services.submission.enqueue_grading", new=AsyncMock(return_value=None)
    ) as enqueue_mock:
        res = auth_client.post(f"/api/submissions/{sub_id}/regrade")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "pending"
    assert body["score"] is None
    assert body["feedback"] is None
    assert body["model_name"] == "(pending)"
    enqueue_mock.assert_awaited_once()

    # The submission's graded_at is now None (poll trigger).
    poll = auth_client.get(f"/api/me/submissions/{sub_id}")
    assert poll.status_code == 200
    assert poll.json()["graded_at"] is None


@pytest.mark.asyncio
async def test_async_regrade_honours_cooldown(
    auth_client, auth_user, db_session, monkeypatch
):
    """Cooldown applies in async mode just like sync mode — the
    pre-flight check runs in the route before enqueue."""
    from app.config import settings

    monkeypatch.setattr(settings, "grading_async_enabled", False)
    submission = await _create_graded_submission(auth_client, auth_user, db_session)
    sub_id = submission["id"]
    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 60)
    monkeypatch.setattr(settings, "grading_async_enabled", True)

    with patch(
        "app.services.submission.enqueue_grading", new=AsyncMock(return_value=None)
    ) as enqueue_mock:
        res = auth_client.post(f"/api/submissions/{sub_id}/regrade")

    assert res.status_code == 429
    assert "Retry-After" in res.headers
    enqueue_mock.assert_not_awaited()
