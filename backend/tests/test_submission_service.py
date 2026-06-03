from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.claude_client import ClaudeClient
from app.core.security import hash_password
from app.models.progress import ProgressStatus
from app.models.user import User
from app.services.progress import initialize_progress, list_progress
from app.services.submission import (
    SubmissionTaskInvalidError,
    list_user_submissions,
    upsert_and_grade,
)


async def _user(db) -> User:
    u = User(
        email="alice@example.com", name="A", password_hash=hash_password("password123")
    )
    db.add(u)
    await db.flush()
    await initialize_progress(db, u.id)
    await db.commit()
    return u


def _fake(reply: str) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=reply)])
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")


@pytest.mark.asyncio
async def test_upsert_creates_and_grades(db_session):
    user = await _user(db_session)
    claude = _fake('{"score": 80, "feedback": "良い"}')

    row = await upsert_and_grade(
        db=db_session,
        claude=claude,
        user_id=user.id,
        phase=1,
        task_no=1,
        content="Gitでブランチ切ってPRしました",
    )

    assert row.score == 80
    assert "良い" in row.ai_feedback
    assert row.graded_at is not None


@pytest.mark.asyncio
async def test_upsert_updates_existing(db_session):
    user = await _user(db_session)
    await upsert_and_grade(
        db=db_session,
        claude=_fake('{"score": 70, "feedback": "一回目"}'),
        user_id=user.id,
        phase=1,
        task_no=1,
        content="初回",
    )

    row = await upsert_and_grade(
        db=db_session,
        claude=_fake('{"score": 90, "feedback": "二回目"}'),
        user_id=user.id,
        phase=1,
        task_no=1,
        content="改善版",
    )

    assert row.content == "改善版"
    assert row.score == 90

    listed = await list_user_submissions(db_session, user.id, 1)
    assert len(listed) == 1


@pytest.mark.asyncio
async def test_all_tasks_submitted_promotes_progress(db_session):
    user = await _user(db_session)
    for tno in (1, 2, 3):
        await upsert_and_grade(
            db=db_session,
            claude=_fake('{"score":80,"feedback":"x"}'),
            user_id=user.id,
            phase=1,
            task_no=tno,
            content=f"task {tno}",
        )

    rows = await list_progress(db_session, user.id)
    phase1 = next(r for r in rows if r.phase == 1)
    assert phase1.status == ProgressStatus.SUBMITTED.value


@pytest.mark.asyncio
async def test_partial_submission_keeps_in_progress(db_session):
    user = await _user(db_session)
    await upsert_and_grade(
        db=db_session,
        claude=_fake('{"score":80,"feedback":"x"}'),
        user_id=user.id,
        phase=1,
        task_no=1,
        content="task 1",
    )

    rows = await list_progress(db_session, user.id)
    phase1 = next(r for r in rows if r.phase == 1)
    assert phase1.status == ProgressStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_invalid_task_no_raises(db_session):
    user = await _user(db_session)
    with pytest.raises(SubmissionTaskInvalidError):
        await upsert_and_grade(
            db=db_session,
            claude=_fake('{"score":80,"feedback":"x"}'),
            user_id=user.id,
            phase=1,
            task_no=99,
            content="x",
        )


@pytest.mark.asyncio
async def test_grading_failure_stores_error_message(db_session):
    user = await _user(db_session)
    claude = _fake("これは JSON ではありません")
    row = await upsert_and_grade(
        db=db_session,
        claude=claude,
        user_id=user.id,
        phase=1,
        task_no=1,
        content="提出内容",
    )
    assert row.score is None
    assert row.ai_feedback.startswith("採点エラー")
