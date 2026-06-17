"""S3 upload storage backend tests (Sprint 27)."""

import uuid
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def s3_env(monkeypatch):
    monkeypatch.setenv("UPLOAD_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_UPLOAD_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_UPLOAD_PREFIX", "uploads")
    from importlib import reload

    import app.config as cfg_mod
    import app.core.file_storage as fs_mod
    import app.core.file_storage_s3 as s3_mod

    reload(cfg_mod)
    reload(fs_mod)
    reload(s3_mod)

    store: dict[str, bytes] = {}

    client = MagicMock()

    def put_object(*, Bucket, Key, Body, ContentType):
        store[f"{Bucket}/{Key}"] = Body

    def get_object(*, Bucket, Key):
        body = store[f"{Bucket}/{Key}"]
        return {"Body": MagicMock(read=lambda: body)}

    def list_objects_v2(*, Bucket, Prefix, ContinuationToken=None):
        contents = []
        for full_key in store:
            if not full_key.startswith(f"{Bucket}/"):
                continue
            key = full_key.split("/", 1)[1]
            if key.startswith(Prefix):
                contents.append({"Key": key})
        return {"Contents": contents, "IsTruncated": False}

    def delete_objects(*, Bucket, Delete):
        for obj in Delete["Objects"]:
            store.pop(f"{Bucket}/{obj['Key']}", None)

    client.put_object = put_object
    client.get_object = get_object
    client.list_objects_v2 = list_objects_v2
    client.delete_objects = delete_objects

    s3_mod._s3_client = lambda: client
    return fs_mod, s3_mod, store


@pytest.mark.asyncio
async def test_save_upload_s3_stores_and_reads(s3_env):
    fs_mod, _, store = s3_env
    user_id = uuid.uuid4()
    submission_id = uuid.uuid4()
    meta = await fs_mod.save_upload(
        user_id=user_id,
        submission_id=submission_id,
        filename="notes.txt",
        content=b"hello s3",
    )
    assert meta.file_path.startswith("s3://test-bucket/")
    assert fs_mod.stored_filename(meta.file_path) == "notes.txt"
    assert fs_mod.read_file_bytes(meta.file_path) == b"hello s3"
    assert any(k.endswith("notes.txt") for k in store)


@pytest.mark.asyncio
async def test_save_upload_s3_unique_collision(s3_env):
    fs_mod, _, _ = s3_env
    user_id = uuid.uuid4()
    submission_id = uuid.uuid4()
    a = await fs_mod.save_upload(
        user_id=user_id,
        submission_id=submission_id,
        filename="dup.txt",
        content=b"one",
    )
    b = await fs_mod.save_upload(
        user_id=user_id,
        submission_id=submission_id,
        filename="dup.txt",
        content=b"two",
    )
    assert fs_mod.stored_filename(a.file_path) == "dup.txt"
    assert fs_mod.stored_filename(b.file_path) == "dup_1.txt"


def test_delete_submission_files_s3(s3_env):
    _, s3_mod, store = s3_env
    user_id = uuid.uuid4()
    submission_id = uuid.uuid4()
    key = f"uploads/{user_id}/{submission_id}/x.txt"
    store[f"test-bucket/{key}"] = b"x"
    s3_mod.delete_submission_files_s3(user_id, submission_id)
    assert not any(k.endswith("x.txt") for k in store)


def test_parse_s3_uri(s3_env):
    _, s3_mod, _ = s3_env
    bucket, key = s3_mod.parse_s3_uri("s3://bkt/uploads/u/s/file.py")
    assert bucket == "bkt"
    assert key == "uploads/u/s/file.py"
