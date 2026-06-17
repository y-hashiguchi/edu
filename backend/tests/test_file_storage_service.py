"""file_storage_service unit tests."""

import uuid

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.user import User


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?"
        b"\x03\x00\x05\xfe\x02\xfe\xa3rH\x9c\x00\x00\x00\x00IEND\xaeB`\x82"
    )


async def _make_user_and_submission(db, course_id) -> tuple[User, Submission]:
    user = User(
        email=f"u-{uuid.uuid4()}@example.com",
        name="t",
        password_hash=hash_password("p"),
    )
    db.add(user)
    await db.flush()
    sub = Submission(user_id=user.id, course_id=course_id, phase=1, task_no=1, content="x")
    db.add(sub)
    await db.flush()
    return user, sub


@pytest.mark.asyncio
async def test_persist_uploads_creates_db_rows_and_files(
    db_session, tmp_path, monkeypatch, default_course_id
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)
    import app.services.file_storage_service as svc_mod

    reload(svc_mod)

    user, sub = await _make_user_and_submission(db_session, default_course_id)

    files = await svc_mod.persist_uploads(
        db=db_session,
        user_id=user.id,
        submission_id=sub.id,
        uploads=[("photo.png", _png_bytes())],
    )

    await db_session.commit()
    assert len(files) == 1
    rows = (
        (
            await db_session.execute(
                select(SubmissionFile).where(SubmissionFile.submission_id == sub.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_persist_uploads_rejects_too_many_files(
    db_session, tmp_path, monkeypatch, default_course_id
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_FILES_PER_SUBMISSION", "2")
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)
    import app.services.file_storage_service as svc_mod

    reload(svc_mod)

    user, sub = await _make_user_and_submission(db_session, default_course_id)

    with pytest.raises(svc_mod.TooManyFilesError):
        await svc_mod.persist_uploads(
            db=db_session,
            user_id=user.id,
            submission_id=sub.id,
            uploads=[
                ("a.png", _png_bytes()),
                ("b.png", _png_bytes()),
                ("c.png", _png_bytes()),
            ],
        )


@pytest.mark.asyncio
async def test_clear_existing_files_drops_db_and_disk(
    db_session, tmp_path, monkeypatch, default_course_id
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)
    import app.services.file_storage_service as svc_mod

    reload(svc_mod)

    user, sub = await _make_user_and_submission(db_session, default_course_id)
    await svc_mod.persist_uploads(
        db=db_session,
        user_id=user.id,
        submission_id=sub.id,
        uploads=[("photo.png", _png_bytes())],
    )
    await db_session.commit()

    await svc_mod.clear_existing_files(db=db_session, user_id=user.id, submission_id=sub.id)
    await db_session.commit()

    remaining = (
        (
            await db_session.execute(
                select(SubmissionFile).where(SubmissionFile.submission_id == sub.id)
            )
        )
        .scalars()
        .all()
    )
    assert remaining == []
    assert not fs_mod.submission_dir(user.id, sub.id).exists()


@pytest.mark.asyncio
async def test_persist_uploads_rolls_back_disk_on_mid_loop_failure(
    db_session, tmp_path, monkeypatch, default_course_id
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)
    import app.services.file_storage_service as svc_mod

    reload(svc_mod)

    user, sub = await _make_user_and_submission(db_session, default_course_id)

    # First upload valid PNG, second triggers MimeMismatchError (PNG content with .py extension).
    uploads = [
        ("good.png", _png_bytes()),
        ("bad.py", _png_bytes()),  # mime/ext mismatch → raises mid-loop
    ]

    with pytest.raises(fs_mod.MimeMismatchError):
        await svc_mod.persist_uploads(
            db=db_session,
            user_id=user.id,
            submission_id=sub.id,
            uploads=uploads,
        )

    # Cleanup should have removed the partially-written first file and its dir.
    assert not fs_mod.submission_dir(user.id, sub.id).exists()
