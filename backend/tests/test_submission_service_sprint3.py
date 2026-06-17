"""submission service tests for Sprint 3 (files + regrade + history)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.claude_client import ClaudeClient
from app.core.security import hash_password
from app.models.grading_attempt import GradingAttempt, GradingStatus
from app.models.submission_file import SubmissionFile
from app.models.user import User
from app.services.progress import initialize_progress

_AI_DRIVEN_DEV_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
_AI_DRIVEN_DEV_SLUG = "ai-driven-dev"


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?"
        b"\x03\x00\x05\xfe\x02\xfe\xa3rH\x9c\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _fake_claude(reply_text: str) -> ClaudeClient:
    sdk = MagicMock()
    sdk.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text=reply_text)]))
    return ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")


async def _setup_user(db) -> User:
    user = User(
        email=f"u-{uuid.uuid4()}@example.com",
        name="t",
        password_hash=hash_password("p"),
    )
    db.add(user)
    await db.flush()
    await initialize_progress(db, user.id)
    await db.commit()
    return user


def _reload_chain():
    """Helper for tests that monkeypatch env vars."""
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)
    import app.services.file_storage_service as fss_mod

    reload(fss_mod)
    import app.services.submission as sub_mod

    reload(sub_mod)
    return cfg_mod, fs_mod, fss_mod, sub_mod


@pytest.mark.asyncio
async def test_upsert_with_files_persists_files_and_grading_attempt(
    db_session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    _, _, _, sub_mod = _reload_chain()

    user = await _setup_user(db_session)
    claude = _fake_claude('{"score":92,"feedback":"good"}')

    row = await sub_mod.upsert_and_grade(
        db=db_session,
        claude=claude,
        user_id=user.id,
        phase=1,
        task_no=1,
        content="see attached",
        uploads=[("photo.png", _png_bytes())],
        course_id=_AI_DRIVEN_DEV_ID,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )

    assert row.score == 92
    files = (
        (
            await db_session.execute(
                select(SubmissionFile).where(SubmissionFile.submission_id == row.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(files) == 1
    attempts = (
        (
            await db_session.execute(
                select(GradingAttempt).where(GradingAttempt.submission_id == row.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(attempts) == 1
    assert attempts[0].status == GradingStatus.GRADED


@pytest.mark.asyncio
async def test_resubmit_replaces_old_files(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    _, _, _, sub_mod = _reload_chain()

    user = await _setup_user(db_session)
    claude = _fake_claude('{"score":80,"feedback":"x"}')

    row1 = await sub_mod.upsert_and_grade(
        db=db_session,
        claude=claude,
        user_id=user.id,
        phase=1,
        task_no=1,
        content="v1",
        uploads=[("a.png", _png_bytes())],
        course_id=_AI_DRIVEN_DEV_ID,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )

    row2 = await sub_mod.upsert_and_grade(
        db=db_session,
        claude=claude,
        user_id=user.id,
        phase=1,
        task_no=1,
        content="v2",
        uploads=[("b.png", _png_bytes())],
        course_id=_AI_DRIVEN_DEV_ID,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )

    assert row1.id == row2.id
    files = (
        (
            await db_session.execute(
                select(SubmissionFile).where(SubmissionFile.submission_id == row2.id)
            )
        )
        .scalars()
        .all()
    )
    assert [f.file_path.endswith("b.png") for f in files] == [True]
    attempts = (
        (
            await db_session.execute(
                select(GradingAttempt).where(GradingAttempt.submission_id == row2.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_regrade_appends_attempt(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("REGRADE_COOLDOWN_SECONDS", "0")
    _, _, _, sub_mod = _reload_chain()

    user = await _setup_user(db_session)
    claude = _fake_claude('{"score":70,"feedback":"first"}')

    row = await sub_mod.upsert_and_grade(
        db=db_session,
        claude=claude,
        user_id=user.id,
        phase=1,
        task_no=1,
        content="v1",
        uploads=[],
        course_id=_AI_DRIVEN_DEV_ID,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )

    claude2 = _fake_claude('{"score":95,"feedback":"better"}')
    attempt = await sub_mod.regrade_submission(
        db=db_session,
        claude=claude2,
        user_id=user.id,
        submission_id=row.id,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )

    assert attempt.score == 95
    await db_session.refresh(row)
    assert row.score == 95
    attempts = (
        (
            await db_session.execute(
                select(GradingAttempt).where(GradingAttempt.submission_id == row.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_regrade_enforces_cooldown(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("REGRADE_COOLDOWN_SECONDS", "60")
    _, _, _, sub_mod = _reload_chain()

    user = await _setup_user(db_session)
    claude = _fake_claude('{"score":70,"feedback":"first"}')

    row = await sub_mod.upsert_and_grade(
        db=db_session,
        claude=claude,
        user_id=user.id,
        phase=1,
        task_no=1,
        content="v1",
        uploads=[],
        course_id=_AI_DRIVEN_DEV_ID,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )

    with pytest.raises(sub_mod.RegradeCooldownError) as exc:
        await sub_mod.regrade_submission(
            db=db_session,
            claude=claude,
            user_id=user.id,
            submission_id=row.id,
            course_slug=_AI_DRIVEN_DEV_SLUG,
        )
    assert exc.value.retry_after_seconds > 0


@pytest.mark.asyncio
async def test_failed_attempts_do_not_count_toward_cooldown(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("REGRADE_COOLDOWN_SECONDS", "60")
    _, _, _, sub_mod = _reload_chain()

    user = await _setup_user(db_session)

    # First call fails (bad JSON)
    bad_claude = _fake_claude("not json")
    row = await sub_mod.upsert_and_grade(
        db=db_session,
        claude=bad_claude,
        user_id=user.id,
        phase=1,
        task_no=1,
        content="v1",
        uploads=[],
        course_id=_AI_DRIVEN_DEV_ID,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )
    assert row.score is None

    # Immediate retry must be allowed because last attempt was 'failed'.
    good_claude = _fake_claude('{"score":80,"feedback":"good"}')
    attempt = await sub_mod.regrade_submission(
        db=db_session,
        claude=good_claude,
        user_id=user.id,
        submission_id=row.id,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )
    assert attempt.status == GradingStatus.GRADED


@pytest.mark.asyncio
async def test_concurrent_regrade_serialised_by_row_lock(db_session, tmp_path, monkeypatch):
    """Two parallel regrade calls cannot both bypass the cooldown.

    Reproduces the pre-fix race where both sessions read the same "cooldown
    just expired" state, both call Claude, and both insert new graded
    attempts. With SELECT FOR UPDATE on the submission row, the second
    session blocks until the first commits, then observes the freshly
    inserted attempt and is rejected with RegradeCooldownError.
    """
    import asyncio
    from datetime import UTC, datetime, timedelta

    from app.config import settings
    from app.db.session import SessionLocal
    from app.services import submission as sub_mod

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "regrade_cooldown_seconds", 60)

    user = await _setup_user(db_session)
    claude = _fake_claude('{"score":70,"feedback":"first"}')
    row = await sub_mod.upsert_and_grade(
        db=db_session,
        claude=claude,
        user_id=user.id,
        phase=1,
        task_no=1,
        content="v",
        uploads=[],
        course_id=_AI_DRIVEN_DEV_ID,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )

    # Push the only graded attempt 61 s into the past so the cooldown has
    # just barely elapsed — without the lock both racers would observe
    # `remaining <= 0` and both proceed.
    attempt = (
        await db_session.execute(
            select(GradingAttempt).where(GradingAttempt.submission_id == row.id)
        )
    ).scalar_one()
    attempt.created_at = datetime.now(UTC) - timedelta(seconds=61)
    await db_session.commit()

    submission_id = row.id
    user_id = user.id

    # Hold the Claude call long enough for the second task to observe the
    # lock contention rather than racing past it on a tight CPU schedule.
    async def slow_create(**_kwargs):
        await asyncio.sleep(0.3)
        return MagicMock(content=[MagicMock(text='{"score":99,"feedback":"x"}')])

    slow_sdk = MagicMock()
    slow_sdk.messages.create = slow_create
    slow_claude = ClaudeClient(sdk=slow_sdk, model="claude-sonnet-4-5")

    async def attempt_regrade():
        async with SessionLocal() as session:
            try:
                return await sub_mod.regrade_submission(
                    db=session,
                    claude=slow_claude,
                    user_id=user_id,
                    submission_id=submission_id,
                    course_slug=_AI_DRIVEN_DEV_SLUG,
                )
            except sub_mod.RegradeCooldownError as e:
                return e

    results = await asyncio.gather(attempt_regrade(), attempt_regrade())
    successes = [r for r in results if not isinstance(r, sub_mod.RegradeCooldownError)]
    cooldowns = [r for r in results if isinstance(r, sub_mod.RegradeCooldownError)]
    assert len(successes) == 1, f"expected exactly one success, got {results!r}"
    assert len(cooldowns) == 1


@pytest.mark.asyncio
async def test_regrade_rejects_other_users_submission(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("REGRADE_COOLDOWN_SECONDS", "0")
    _, _, _, sub_mod = _reload_chain()

    owner = await _setup_user(db_session)
    intruder = await _setup_user(db_session)
    claude = _fake_claude('{"score":80,"feedback":"x"}')

    row = await sub_mod.upsert_and_grade(
        db=db_session,
        claude=claude,
        user_id=owner.id,
        phase=1,
        task_no=1,
        content="v",
        uploads=[],
        course_id=_AI_DRIVEN_DEV_ID,
        course_slug=_AI_DRIVEN_DEV_SLUG,
    )

    with pytest.raises(sub_mod.SubmissionNotFoundError):
        await sub_mod.regrade_submission(
            db=db_session,
            claude=claude,
            user_id=intruder.id,
            submission_id=row.id,
            course_slug=_AI_DRIVEN_DEV_SLUG,
        )
