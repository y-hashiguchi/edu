"""Migrate existing local submission uploads to S3.

Usage:
    uv run python -m scripts.migrate_uploads_to_s3 [--dry-run] [--limit N]

The script uploads local ``submission_files.file_path`` records to the S3
upload bucket configured by ``S3_UPLOAD_BUCKET`` / ``S3_UPLOAD_PREFIX`` and
then rewrites the DB row to the resulting ``s3://`` URI. Local files are not
deleted.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select, update

import app.core.file_storage_s3 as s3_storage
from app.db.session import SessionLocal
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile


@dataclass(frozen=True)
class MigrationResult:
    scanned: int = 0
    migrated: int = 0
    skipped: int = 0
    errors: int = 0


def _with(
    result: MigrationResult,
    *,
    scanned: int = 0,
    migrated: int = 0,
    skipped: int = 0,
    errors: int = 0,
) -> MigrationResult:
    return MigrationResult(
        scanned=result.scanned + scanned,
        migrated=result.migrated + migrated,
        skipped=result.skipped + skipped,
        errors=result.errors + errors,
    )


def _target_key(
    *,
    client=None,
    bucket: str,
    user_id,
    submission_id,
    file_path: str,
) -> str:
    prefix = s3_storage.object_prefix(user_id, submission_id)
    safe_name = Path(file_path).name
    if client is None:
        return f"{prefix}/{safe_name}"
    existing = s3_storage._list_existing_names(client, bucket, f"{prefix}/")
    unique_name = s3_storage._pick_unique_name(existing, safe_name)
    return f"{prefix}/{unique_name}"


async def migrate_uploads_to_s3(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    continue_on_error: bool = False,
) -> MigrationResult:
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than zero")

    result = MigrationResult()
    client = None if dry_run else s3_storage._s3_client()
    bucket = s3_storage._require_bucket()

    async with SessionLocal() as session:
        stmt = (
            select(
                SubmissionFile.id,
                SubmissionFile.submission_id,
                SubmissionFile.file_path,
                SubmissionFile.mime_type,
                Submission.user_id,
            )
            .join(Submission, Submission.id == SubmissionFile.submission_id)
            .order_by(SubmissionFile.created_at, SubmissionFile.id)
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        rows = (await session.execute(stmt)).all()
        for row in rows:
            result = _with(result, scanned=1)
            file_id = row.id
            file_path = row.file_path
            if file_path.startswith("s3://"):
                result = _with(result, skipped=1)
                continue

            try:
                source = Path(file_path)
                content = source.read_bytes()
                key = _target_key(
                    client=client,
                    bucket=bucket,
                    user_id=row.user_id,
                    submission_id=row.submission_id,
                    file_path=file_path,
                )
                target_uri = f"s3://{bucket}/{key}"
                if dry_run:
                    print(f"would migrate {file_id}: {file_path} -> {target_uri}")
                    continue

                assert client is not None
                client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    ContentType=row.mime_type,
                )
                await session.execute(
                    update(SubmissionFile)
                    .where(SubmissionFile.id == file_id)
                    .values(file_path=target_uri)
                )
                await session.commit()
                result = _with(result, migrated=1)
                print(f"migrated {file_id}: {file_path} -> {target_uri}")
            except Exception as exc:
                await session.rollback()
                result = _with(result, errors=1)
                print(f"error {file_id}: {exc}", file=sys.stderr)
                if not continue_on_error:
                    raise

    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate local submission_files uploads to S3.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--continue-on-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = asyncio.run(
            migrate_uploads_to_s3(
                dry_run=args.dry_run,
                limit=args.limit,
                continue_on_error=args.continue_on_error,
            )
        )
    except Exception as exc:
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1

    print(
        "summary: "
        f"scanned={result.scanned} migrated={result.migrated} "
        f"skipped={result.skipped} errors={result.errors}"
    )
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
