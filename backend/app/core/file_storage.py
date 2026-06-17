"""File storage primitives for submission uploads.

All file IO is constrained to a single root directory configured via
`settings.upload_dir`. Filenames are sanitized and MIME types are verified
against the file's actual magic bytes to prevent type spoofing.
"""

import asyncio
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import magic

from app.config import settings
from app.core._file_storage_errors import (
    FileStorageError,
    FileTooLargeError,
    InvalidExtensionError,
    MimeMismatchError,
    PathTraversalError,
)

__all__ = [
    "FileStorageError",
    "FileTooLargeError",
    "InvalidExtensionError",
    "MimeMismatchError",
    "PathTraversalError",
    "StoredFile",
    "delete_submission_files",
    "detect_mime_type",
    "read_file_bytes",
    "sanitize_filename",
    "save_upload",
    "stored_filename",
    "storage_root",
    "submission_dir",
    "validate_extension",
]


# Extension → list of acceptable MIME prefixes returned by libmagic.
_EXTENSION_MIME_PREFIXES: dict[str, tuple[str, ...]] = {
    "py": ("text/", "application/x-python", "application/x-script"),
    "java": ("text/",),
    "js": ("text/", "application/javascript", "application/x-javascript"),
    "ts": ("text/",),
    "txt": ("text/",),
    "md": ("text/",),
    "png": ("image/png",),
    "jpg": ("image/jpeg",),
    "jpeg": ("image/jpeg",),
    "pdf": ("application/pdf",),
}


@dataclass(frozen=True)
class StoredFile:
    file_path: str
    mime_type: str
    size_bytes: int


def storage_root() -> Path:
    return Path(settings.upload_dir).resolve()


def submission_dir(user_id: uuid.UUID | str, submission_id: uuid.UUID | str) -> Path:
    root = storage_root()
    candidate = (root / str(user_id) / str(submission_id)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PathTraversalError(f"target escapes upload root: {candidate}") from exc
    return candidate


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].strip()
    if not base or base in (".", ".."):
        raise FileStorageError("empty or invalid filename")
    cleaned = _SAFE_NAME.sub("_", base)
    cleaned = cleaned.lstrip(".")
    if not cleaned:
        raise FileStorageError("filename became empty after sanitization")
    return cleaned[:120]


def _extension_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def validate_extension(filename: str) -> str:
    ext = _extension_of(filename)
    if not ext or ext not in settings.allowed_upload_extension_set:
        raise InvalidExtensionError(
            f"extension '{ext}' not allowed; permitted: "
            f"{sorted(settings.allowed_upload_extension_set)}"
        )
    return ext


def detect_mime_type(data: bytes) -> str:
    return magic.from_buffer(data[:8192], mime=True) or "application/octet-stream"


def _mime_matches_extension(mime: str, ext: str) -> bool:
    prefixes = _EXTENSION_MIME_PREFIXES.get(ext, ())
    return any(mime.startswith(p) for p in prefixes)


def _unique_target(target_dir: Path, safe_name: str) -> Path:
    """Pick a path under target_dir that does not collide with an existing
    file. Two uploads that sanitize to the same name (e.g. `hello world.png`
    and `hello_world.png`) would otherwise silently overwrite each other and
    leave two SubmissionFile rows pointing at the same bytes. We append a
    numeric suffix (`_1`, `_2`, ...) before the extension to keep both
    distinguishable on disk. The 100-attempt ceiling is a sanity bound — a
    submission directory holding 100 files with the same stem is far past
    any legitimate use.
    """
    target = target_dir / safe_name
    if not target.exists():
        return target
    if "." in safe_name:
        stem, _, ext = safe_name.rpartition(".")
        suffix = f".{ext}"
    else:
        stem, suffix = safe_name, ""
    for i in range(1, 100):
        candidate = target_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileStorageError("could not find unique filename within 100 attempts")


def _use_s3() -> bool:
    return settings.upload_storage_backend == "s3"


def stored_filename(file_path: str) -> str:
    if file_path.startswith("s3://"):
        from app.core.file_storage_s3 import stored_filename as s3_stored_filename

        return s3_stored_filename(file_path)
    return Path(file_path).name


async def save_upload(
    *,
    user_id: uuid.UUID,
    submission_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> StoredFile:
    if _use_s3():
        from app.core.file_storage_s3 import save_upload_s3

        return await save_upload_s3(
            user_id=user_id,
            submission_id=submission_id,
            filename=filename,
            content=content,
        )
    if len(content) > settings.max_file_size_bytes:
        raise FileTooLargeError(f"file exceeds {settings.max_file_size_bytes} bytes")
    safe_name = sanitize_filename(filename)
    ext = validate_extension(safe_name)
    mime = detect_mime_type(content)
    if not _mime_matches_extension(mime, ext):
        raise MimeMismatchError(f"content type '{mime}' does not match extension '.{ext}'")

    target_dir = submission_dir(user_id, submission_id)

    def _write() -> Path:
        target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = _unique_target(target_dir, safe_name)
        target.write_bytes(content)
        return target

    target = await asyncio.to_thread(_write)
    return StoredFile(
        file_path=str(target),
        mime_type=mime,
        size_bytes=len(content),
    )


def delete_submission_files(user_id: uuid.UUID | str, submission_id: uuid.UUID | str) -> None:
    if _use_s3():
        from app.core.file_storage_s3 import delete_submission_files_s3

        delete_submission_files_s3(user_id, submission_id)
        return
    target = submission_dir(user_id, submission_id)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)


def read_file_bytes(file_path: str) -> bytes:
    if file_path.startswith("s3://"):
        from app.core.file_storage_s3 import read_file_bytes_s3

        return read_file_bytes_s3(file_path)
    root = storage_root()
    p = Path(file_path).resolve()
    try:
        p.relative_to(root)
    except ValueError as exc:
        raise PathTraversalError(f"path '{file_path}' is outside upload root") from exc
    return p.read_bytes()
