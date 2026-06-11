"""Sprint 8 — async grading enqueue path."""

import pytest

from app.config import settings
from app.services.submission import upsert_and_enqueue


@pytest.mark.asyncio
async def test_upsert_and_enqueue_leaves_submission_ungraded_until_job_runs(
    db_session, auth_user, default_course_id, monkeypatch,
):
    """When async is on, upsert returns before Claude runs."""
    graded_ids: list[str] = []

    async def fake_enqueue(submission_id):
        graded_ids.append(str(submission_id))

    monkeypatch.setattr(settings, "grading_async_enabled", True)
    monkeypatch.setattr(
        "app.services.submission.enqueue_grading",
        fake_enqueue,
    )

    row = await upsert_and_enqueue(
        db=db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        course_slug="ai-driven-dev",
        phase=1,
        task_no=1,
        content="async path test",
        uploads=[],
    )

    assert row.score is None
    assert row.graded_at is None
    assert graded_ids == [str(row.id)]


@pytest.mark.asyncio
async def test_inline_enqueue_grades_when_async_disabled(
    db_session, auth_user, default_course_id, monkeypatch,
):
    """GRADING_ASYNC_ENABLED=false runs grading inline (test default)."""
    from unittest.mock import MagicMock

    from app.core.claude_client import ClaudeClient

    fake_sdk = MagicMock()
    fake_claude = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")

    async def fake_complete_multimodal(self, **kwargs):
        return '{"score": 77, "feedback": "ok"}'

    monkeypatch.setattr(settings, "grading_async_enabled", False)
    monkeypatch.setattr(
        fake_claude, "complete_multimodal", fake_complete_multimodal.__get__(fake_claude)
    )
    monkeypatch.setattr("app.worker.grading_job.get_claude_client", lambda: fake_claude)

    row = await upsert_and_enqueue(
        db=db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        course_slug="ai-driven-dev",
        phase=1,
        task_no=2,
        content="inline grade",
        uploads=[],
    )

    assert row.score == 77
    assert row.graded_at is not None
