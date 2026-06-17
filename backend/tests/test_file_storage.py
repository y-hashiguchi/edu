"""file_storage core module tests."""

import uuid
from pathlib import Path

import pytest

from app.core.file_storage import (
    FileStorageError,
    FileTooLargeError,
    InvalidExtensionError,
    MimeMismatchError,
    PathTraversalError,
    detect_mime_type,
    sanitize_filename,
    validate_extension,
)

# ----------- helpers -----------


def _png_bytes() -> bytes:
    # 1x1 transparent PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?"
        b"\x03\x00\x05\xfe\x02\xfe\xa3rH\x9c\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n%%EOF\n"


# ----------- sanitize_filename -----------


def test_sanitize_filename_removes_path_separators():
    assert sanitize_filename("../../etc/passwd") == "passwd"


def test_sanitize_filename_keeps_basic_chars():
    assert sanitize_filename("my code.py") == "my_code.py"


def test_sanitize_filename_rejects_empty(tmp_path):
    with pytest.raises(FileStorageError):
        sanitize_filename("")


# ----------- validate_extension -----------


def test_validate_extension_accepts_whitelisted():
    validate_extension("solution.py")


def test_validate_extension_rejects_exe():
    with pytest.raises(InvalidExtensionError):
        validate_extension("evil.exe")


def test_validate_extension_case_insensitive():
    validate_extension("photo.JPG")


# ----------- submission_dir + path traversal -----------


def test_submission_dir_resolves_under_root(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)

    user_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    target = fs_mod.submission_dir(user_id, sub_id)
    assert str(target).startswith(str(tmp_path.resolve()))


def test_path_traversal_via_user_id_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)

    with pytest.raises(PathTraversalError):
        fs_mod.submission_dir("..", "x")  # type: ignore[arg-type]


# ----------- detect_mime_type -----------


def test_detect_mime_type_png():
    assert detect_mime_type(_png_bytes()).startswith("image/png")


def test_detect_mime_type_pdf():
    assert detect_mime_type(_pdf_bytes()) == "application/pdf"


# ----------- save_upload -----------


@pytest.mark.asyncio
async def test_save_upload_writes_file_and_returns_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)

    user_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    data = _png_bytes()
    meta = await fs_mod.save_upload(
        user_id=user_id,
        submission_id=sub_id,
        filename="hello.png",
        content=data,
    )

    assert meta.size_bytes == len(data)
    assert meta.mime_type.startswith("image/png")
    # file_path is stored relative-to-cwd; check the file actually exists.
    assert Path(meta.file_path).exists()


@pytest.mark.asyncio
async def test_save_upload_rejects_oversized(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_FILE_SIZE_BYTES", "10")
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)

    with pytest.raises(FileTooLargeError):
        await fs_mod.save_upload(
            user_id=uuid.uuid4(),
            submission_id=uuid.uuid4(),
            filename="big.txt",
            content=b"more than ten bytes here",
        )


@pytest.mark.asyncio
async def test_save_upload_rejects_mime_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)

    # PNG bytes with .py extension
    with pytest.raises(MimeMismatchError):
        await fs_mod.save_upload(
            user_id=uuid.uuid4(),
            submission_id=uuid.uuid4(),
            filename="fake.py",
            content=_png_bytes(),
        )


@pytest.mark.asyncio
async def test_save_upload_suffixes_collisions(tmp_path, monkeypatch):
    """MED-4: A second upload with the same sanitized name must not overwrite."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)

    user_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    a = await fs_mod.save_upload(
        user_id=user_id,
        submission_id=sub_id,
        filename="img.png",
        content=_png_bytes(),
    )
    b = await fs_mod.save_upload(
        user_id=user_id,
        submission_id=sub_id,
        filename="img.png",
        content=_png_bytes(),
    )
    assert a.file_path != b.file_path
    assert Path(a.file_path).exists()
    assert Path(b.file_path).exists()
    # Suffix should match the convention _N.ext
    assert Path(b.file_path).name == "img_1.png"


@pytest.mark.asyncio
async def test_save_upload_suffix_handles_extensionless_name(tmp_path, monkeypatch):
    """Filenames without an extension still get a unique suffix."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("ALLOWED_UPLOAD_EXTENSIONS", "py,txt,bin")
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)

    # We need a filename without dot but allowed_extensions requires one — use
    # ".txt" path so it survives validate_extension but the collision suffix
    # logic still has to deal with the dotted form correctly.
    user_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    a = await fs_mod.save_upload(
        user_id=user_id,
        submission_id=sub_id,
        filename="notes.txt",
        content=b"hello world",
    )
    b = await fs_mod.save_upload(
        user_id=user_id,
        submission_id=sub_id,
        filename="notes.txt",
        content=b"different content",
    )
    assert Path(b.file_path).name == "notes_1.txt"
    assert Path(a.file_path).read_bytes() == b"hello world"
    assert Path(b.file_path).read_bytes() == b"different content"


@pytest.mark.asyncio
async def test_delete_files_removes_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from importlib import reload

    import app.config as cfg_mod

    reload(cfg_mod)
    import app.core.file_storage as fs_mod

    reload(fs_mod)

    user_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    await fs_mod.save_upload(
        user_id=user_id, submission_id=sub_id, filename="a.txt", content=b"hello"
    )
    target = fs_mod.submission_dir(user_id, sub_id)
    assert target.exists()
    fs_mod.delete_submission_files(user_id, sub_id)
    assert not target.exists()
