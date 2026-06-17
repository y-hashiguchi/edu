"""Tests for the local upload to S3 migration script."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.submission import Submission
from app.models.submission_file import SubmissionFile


async def _submission_with_file(
    db_session,
    *,
    user_id,
    course_id,
    file_path: str,
    mime_type: str = "text/plain",
    task_no: int = 1,
) -> SubmissionFile:
    sub = Submission(
        user_id=user_id,
        course_id=course_id,
        phase=1,
        task_no=task_no,
        content="submission",
    )
    db_session.add(sub)
    await db_session.flush()
    row = SubmissionFile(
        submission_id=sub.id,
        file_path=file_path,
        mime_type=mime_type,
        size_bytes=Path(file_path).stat().st_size if not file_path.startswith("s3://") else 1,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@pytest.fixture
def s3_script_env(monkeypatch):
    import app.core.file_storage_s3 as s3_mod
    from app.config import settings

    monkeypatch.setattr(settings, "s3_upload_bucket", "test-bucket")
    monkeypatch.setattr(settings, "s3_upload_prefix", "uploads")
    monkeypatch.setattr(settings, "s3_upload_region", "")

    put_calls = []
    existing_keys = set()

    class Client:
        def put_object(self, *, Bucket, Key, Body, ContentType):
            existing_keys.add(Key)
            put_calls.append(
                {
                    "Bucket": Bucket,
                    "Key": Key,
                    "Body": Body,
                    "ContentType": ContentType,
                }
            )

        def list_objects_v2(self, *, Bucket, Prefix, ContinuationToken=None):
            return {
                "Contents": [
                    {"Key": key} for key in sorted(existing_keys) if key.startswith(Prefix)
                ],
                "IsTruncated": False,
            }

    monkeypatch.setattr(s3_mod, "_s3_client", lambda: Client())
    return put_calls, existing_keys


@pytest.mark.asyncio
async def test_migrates_local_submission_file_to_s3(
    db_session, auth_user, default_course_id, tmp_path, s3_script_env
):
    from scripts.migrate_uploads_to_s3 import migrate_uploads_to_s3

    local_file = tmp_path / "solution.txt"
    local_file.write_text("hello s3", encoding="utf-8")
    row = await _submission_with_file(
        db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        file_path=str(local_file),
    )

    result = await migrate_uploads_to_s3()

    assert result.scanned == 1
    assert result.migrated == 1
    assert result.skipped == 0
    assert result.errors == 0
    put_calls, _ = s3_script_env
    assert put_calls == [
        {
            "Bucket": "test-bucket",
            "Key": f"uploads/{auth_user.id}/{row.submission_id}/solution.txt",
            "Body": b"hello s3",
            "ContentType": "text/plain",
        }
    ]
    refreshed = (
        await db_session.execute(select(SubmissionFile).where(SubmissionFile.id == row.id))
    ).scalar_one()
    await db_session.refresh(refreshed)
    assert (
        refreshed.file_path
        == f"s3://test-bucket/uploads/{auth_user.id}/{row.submission_id}/solution.txt"
    )


@pytest.mark.asyncio
async def test_dry_run_does_not_upload_or_update_db(
    db_session, auth_user, default_course_id, tmp_path, s3_script_env
):
    from scripts.migrate_uploads_to_s3 import migrate_uploads_to_s3

    local_file = tmp_path / "dry.txt"
    local_file.write_text("dry", encoding="utf-8")
    row = await _submission_with_file(
        db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        file_path=str(local_file),
    )

    result = await migrate_uploads_to_s3(dry_run=True)

    assert result.scanned == 1
    assert result.migrated == 0
    assert result.skipped == 0
    assert result.errors == 0
    put_calls, _ = s3_script_env
    assert put_calls == []
    refreshed = (
        await db_session.execute(select(SubmissionFile).where(SubmissionFile.id == row.id))
    ).scalar_one()
    await db_session.refresh(refreshed)
    assert refreshed.file_path == str(local_file)


@pytest.mark.asyncio
async def test_dry_run_does_not_create_s3_client(
    db_session, auth_user, default_course_id, tmp_path, monkeypatch
):
    import app.core.file_storage_s3 as s3_mod
    from app.config import settings
    from scripts.migrate_uploads_to_s3 import migrate_uploads_to_s3

    monkeypatch.setattr(settings, "s3_upload_bucket", "test-bucket")
    monkeypatch.setattr(settings, "s3_upload_prefix", "uploads")
    monkeypatch.setattr(s3_mod, "_s3_client", lambda: (_ for _ in ()).throw(RuntimeError("aws")))

    local_file = tmp_path / "dry-no-aws.txt"
    local_file.write_text("dry", encoding="utf-8")
    await _submission_with_file(
        db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        file_path=str(local_file),
    )

    result = await migrate_uploads_to_s3(dry_run=True)

    assert result.scanned == 1
    assert result.migrated == 0
    assert result.errors == 0


@pytest.mark.asyncio
async def test_limit_caps_migration_count(
    db_session, auth_user, default_course_id, tmp_path, s3_script_env
):
    from scripts.migrate_uploads_to_s3 import migrate_uploads_to_s3

    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    await _submission_with_file(
        db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        file_path=str(first),
    )
    await _submission_with_file(
        db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        file_path=str(second),
        task_no=2,
    )

    result = await migrate_uploads_to_s3(limit=1)

    assert result.scanned == 1
    assert result.migrated == 1
    put_calls, _ = s3_script_env
    assert len(put_calls) == 1


@pytest.mark.asyncio
async def test_existing_s3_rows_are_skipped(
    db_session, auth_user, default_course_id, tmp_path, s3_script_env
):
    from scripts.migrate_uploads_to_s3 import migrate_uploads_to_s3

    local_file = tmp_path / "local.txt"
    local_file.write_text("local", encoding="utf-8")
    await _submission_with_file(
        db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        file_path="s3://test-bucket/uploads/already.txt",
    )
    await _submission_with_file(
        db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        file_path=str(local_file),
        task_no=2,
    )

    result = await migrate_uploads_to_s3()

    assert result.scanned == 2
    assert result.skipped == 1
    assert result.migrated == 1
    put_calls, _ = s3_script_env
    assert len(put_calls) == 1


@pytest.mark.asyncio
async def test_missing_file_fails_by_default(
    db_session, auth_user, default_course_id, tmp_path, s3_script_env
):
    from scripts.migrate_uploads_to_s3 import migrate_uploads_to_s3

    missing = tmp_path / "missing.txt"
    sub = Submission(
        user_id=auth_user.id,
        course_id=default_course_id,
        phase=1,
        task_no=1,
        content="submission",
    )
    db_session.add(sub)
    await db_session.flush()
    db_session.add(
        SubmissionFile(
            submission_id=sub.id,
            file_path=str(missing),
            mime_type="text/plain",
            size_bytes=10,
        )
    )
    await db_session.commit()

    with pytest.raises(FileNotFoundError):
        await migrate_uploads_to_s3()
    put_calls, _ = s3_script_env
    assert put_calls == []


@pytest.mark.asyncio
async def test_continue_on_error_records_missing_file_and_continues(
    db_session, auth_user, default_course_id, tmp_path, s3_script_env
):
    from scripts.migrate_uploads_to_s3 import migrate_uploads_to_s3

    missing = tmp_path / "missing.txt"
    existing = tmp_path / "existing.txt"
    existing.write_text("ok", encoding="utf-8")
    sub = Submission(
        user_id=auth_user.id,
        course_id=default_course_id,
        phase=1,
        task_no=1,
        content="submission",
    )
    db_session.add(sub)
    await db_session.flush()
    db_session.add(
        SubmissionFile(
            submission_id=sub.id,
            file_path=str(missing),
            mime_type="text/plain",
            size_bytes=10,
        )
    )
    await db_session.commit()
    await _submission_with_file(
        db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        file_path=str(existing),
        task_no=2,
    )

    result = await migrate_uploads_to_s3(continue_on_error=True)

    assert result.scanned == 2
    assert result.errors == 1
    assert result.migrated == 1
    put_calls, _ = s3_script_env
    assert len(put_calls) == 1


@pytest.mark.asyncio
async def test_existing_s3_key_gets_collision_suffix(
    db_session, auth_user, default_course_id, tmp_path, s3_script_env
):
    from scripts.migrate_uploads_to_s3 import migrate_uploads_to_s3

    put_calls, existing_keys = s3_script_env
    local_file = tmp_path / "solution.txt"
    local_file.write_text("new content", encoding="utf-8")
    row = await _submission_with_file(
        db_session,
        user_id=auth_user.id,
        course_id=default_course_id,
        file_path=str(local_file),
    )
    existing_keys.add(f"uploads/{auth_user.id}/{row.submission_id}/solution.txt")

    result = await migrate_uploads_to_s3()

    assert result.migrated == 1
    assert put_calls[0]["Key"] == f"uploads/{auth_user.id}/{row.submission_id}/solution_1.txt"
    refreshed = (
        await db_session.execute(select(SubmissionFile).where(SubmissionFile.id == row.id))
    ).scalar_one()
    await db_session.refresh(refreshed)
    assert refreshed.file_path.endswith("/solution_1.txt")


def test_main_returns_nonzero_for_invalid_limit(capsys):
    from scripts.migrate_uploads_to_s3 import main

    assert main(["--limit", "0"]) == 1
    assert "limit must be greater than zero" in capsys.readouterr().err
