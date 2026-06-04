"""Orchestrates upload validation, disk writes, and DB row creation."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import file_storage
from app.models.submission_file import SubmissionFile


class TooManyFilesError(Exception):
    pass


async def persist_uploads(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    submission_id: uuid.UUID,
    uploads: list[tuple[str, bytes]],
) -> list[SubmissionFile]:
    if len(uploads) > settings.max_files_per_submission:
        raise TooManyFilesError(
            f"{len(uploads)} files exceeds limit "
            f"{settings.max_files_per_submission}"
        )

    saved: list[SubmissionFile] = []
    for filename, content in uploads:
        stored = await file_storage.save_upload(
            user_id=user_id,
            submission_id=submission_id,
            filename=filename,
            content=content,
        )
        row = SubmissionFile(
            submission_id=submission_id,
            file_path=stored.file_path,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
        )
        db.add(row)
        saved.append(row)

    await db.flush()
    return saved


async def clear_existing_files(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    submission_id: uuid.UUID,
) -> None:
    await db.execute(
        delete(SubmissionFile).where(SubmissionFile.submission_id == submission_id)
    )
    file_storage.delete_submission_files(user_id, submission_id)


async def list_submission_files(
    db: AsyncSession, submission_id: uuid.UUID
) -> list[SubmissionFile]:
    rows = (
        await db.execute(
            select(SubmissionFile)
            .where(SubmissionFile.submission_id == submission_id)
            .order_by(SubmissionFile.created_at)
        )
    ).scalars().all()
    return list(rows)
