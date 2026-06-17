"""S3 object storage backend for submission uploads (Sprint 27)."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.config import settings
from app.core._file_storage_errors import FileStorageError, FileTooLargeError, MimeMismatchError
from app.core.file_storage import (
    StoredFile,
    _mime_matches_extension,
    detect_mime_type,
    sanitize_filename,
    validate_extension,
)


def _require_bucket() -> str:
    bucket = settings.s3_upload_bucket.strip()
    if not bucket:
        raise FileStorageError("s3_upload_bucket is required when upload_storage_backend=s3")
    return bucket


def _s3_client():
    import boto3

    kwargs = {}
    if settings.s3_upload_region.strip():
        kwargs["region_name"] = settings.s3_upload_region.strip()
    return boto3.client("s3", **kwargs)


def object_prefix(user_id: uuid.UUID | str, submission_id: uuid.UUID | str) -> str:
    parts = [settings.s3_upload_prefix.strip("/"), str(user_id), str(submission_id)]
    return "/".join(p for p in parts if p)


def to_s3_uri(key: str) -> str:
    return f"s3://{_require_bucket()}/{key}"


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise FileStorageError(f"not an s3 uri: {uri}")
    without = uri[5:]
    bucket, _, key = without.partition("/")
    if not bucket or not key:
        raise FileStorageError(f"invalid s3 uri: {uri}")
    return bucket, key


def stored_filename(file_path: str) -> str:
    if file_path.startswith("s3://"):
        _, key = parse_s3_uri(file_path)
        return key.rsplit("/", 1)[-1]
    return Path(file_path).name


def _list_existing_names(client, bucket: str, prefix: str) -> set[str]:
    names: set[str] = set()
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.startswith(prefix):
                names.add(key[len(prefix) :].lstrip("/"))
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return names


def _pick_unique_name(existing: set[str], safe_name: str) -> str:
    if safe_name not in existing:
        return safe_name
    if "." in safe_name:
        stem, _, ext = safe_name.rpartition(".")
        suffix = f".{ext}"
    else:
        stem, suffix = safe_name, ""
    for i in range(1, 100):
        candidate = f"{stem}_{i}{suffix}"
        if candidate not in existing:
            return candidate
    raise FileStorageError("could not find unique filename within 100 attempts")


async def save_upload_s3(
    *,
    user_id: uuid.UUID,
    submission_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> StoredFile:
    if len(content) > settings.max_file_size_bytes:
        raise FileTooLargeError(f"file exceeds {settings.max_file_size_bytes} bytes")
    safe_name = sanitize_filename(filename)
    ext = validate_extension(safe_name)
    mime = detect_mime_type(content)
    if not _mime_matches_extension(mime, ext):
        raise MimeMismatchError(f"content type '{mime}' does not match extension '.{ext}'")

    bucket = _require_bucket()
    prefix = object_prefix(user_id, submission_id) + "/"

    def _write() -> StoredFile:
        client = _s3_client()
        existing = _list_existing_names(client, bucket, prefix)
        unique_name = _pick_unique_name(existing, safe_name)
        key = f"{prefix}{unique_name}"
        client.put_object(Bucket=bucket, Key=key, Body=content, ContentType=mime)
        return StoredFile(
            file_path=to_s3_uri(key),
            mime_type=mime,
            size_bytes=len(content),
        )

    return await asyncio.to_thread(_write)


def read_file_bytes_s3(file_path: str) -> bytes:
    bucket, key = parse_s3_uri(file_path)
    expected = _require_bucket()
    if bucket != expected:
        raise FileStorageError(f"s3 bucket mismatch: {bucket}")
    client = _s3_client()
    resp = client.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def delete_submission_files_s3(user_id: uuid.UUID | str, submission_id: uuid.UUID | str) -> None:
    bucket = _require_bucket()
    prefix = object_prefix(user_id, submission_id) + "/"
    client = _s3_client()
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        contents = resp.get("Contents", [])
        if contents:
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
            )
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
