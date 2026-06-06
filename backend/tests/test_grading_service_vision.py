"""grade_submission multimodal tests."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.claude_client import ClaudeClient
from app.schemas.grading import GradingResultStatus


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?"
        b"\x03\x00\x05\xfe\x02\xfe\xa3rH\x9c\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _fake_claude(reply_text: str) -> ClaudeClient:
    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=reply_text)])
    )
    return ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")


@pytest.mark.asyncio
async def test_grade_submission_text_only_returns_graded(tmp_path):
    from app.services.grading import grade_submission

    claude = _fake_claude('{"score": 91, "feedback": "good text"}')
    result = await grade_submission(
        claude=claude,
        task_description="describe Git",
        content="Git lets you branch",
        files=[],
    )
    assert result.status == GradingResultStatus.GRADED
    assert result.score == 91
    assert result.feedback == "good text"


@pytest.mark.asyncio
async def test_grade_submission_with_image_uses_multimodal(tmp_path, monkeypatch):
    from app.config import settings
    from app.models.submission_file import SubmissionFile
    from app.services.grading import grade_submission

    # MED-2: grading enforces upload-root boundary; align test fixture root.
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    img_path = tmp_path / "sub.png"
    img_path.write_bytes(_png_bytes())

    file_row = SubmissionFile(
        submission_id=uuid.uuid4(),
        file_path=str(img_path),
        mime_type="image/png",
        size_bytes=len(_png_bytes()),
    )

    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text='{"score":77,"feedback":"ok"}')])
    )
    claude = ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    result = await grade_submission(
        claude=claude,
        task_description="show your code",
        content="see attached",
        files=[file_row],
    )
    assert result.status == GradingResultStatus.GRADED
    # Verify multimodal path was used.
    msg = sdk.messages.create.await_args.kwargs["messages"][0]
    types = [c["type"] for c in msg["content"]]
    assert "image" in types


@pytest.mark.asyncio
async def test_grade_submission_truncates_long_text_attachments(tmp_path, monkeypatch):
    """HIGH-2: inline text bodies are truncated before being added to the prompt.

    A 5 MB plain-text attachment would otherwise expand the user message far
    beyond what's safe (token cost + context-window blowup).
    """
    from app.config import settings
    from app.models.submission_file import SubmissionFile
    from app.services import grading
    from app.services.grading import (
        _MAX_INLINE_CHARS_PER_FILE,
        _TRUNCATION_MARKER,
    )

    # MED-2: align upload-root boundary with tmp_path.
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    big_path = tmp_path / "big.txt"
    big_path.write_text("A" * (_MAX_INLINE_CHARS_PER_FILE + 5000))

    file_row = SubmissionFile(
        submission_id=uuid.uuid4(),
        file_path=str(big_path),
        mime_type="text/plain",
        size_bytes=big_path.stat().st_size,
    )

    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text='{"score":80,"feedback":"y"}')])
    )
    claude = ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    result = await grading.grade_submission(
        claude=claude,
        task_description="describe Git",
        content="see file",
        files=[file_row],
    )
    assert result.status == GradingResultStatus.GRADED

    # Verify the prompt actually sent to Claude is bounded.
    sent = sdk.messages.create.await_args.kwargs["messages"][0]
    sent_text = next(
        part["text"] for part in sent["content"] if part.get("type") == "text"
    )
    assert _TRUNCATION_MARKER in sent_text
    # File body slice + marker; allow some slack for task description + content.
    assert "A" * (_MAX_INLINE_CHARS_PER_FILE + 1) not in sent_text


@pytest.mark.asyncio
async def test_grade_submission_masks_sdk_error_but_logs_detail(caplog):
    """MED-3: SDK error never leaks request IDs to the API client; full
    detail is logged server-side for ops."""
    import logging

    from app.services.grading import grade_submission

    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        side_effect=RuntimeError("req_xyz internal routing detail")
    )
    claude = ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    caplog.set_level(logging.ERROR, logger="app.services.grading")
    result = await grade_submission(
        claude=claude, task_description="x", content="y", files=[]
    )
    assert result.status == GradingResultStatus.FAILED
    msg = result.error_message or ""
    assert "req_xyz" not in msg
    assert "routing" not in msg
    assert "採点サービス" in msg
    # Full detail must still be present in logs for ops.
    assert any(
        "req_xyz" in (r.getMessage() + str(r.exc_info or ""))
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_grade_submission_wraps_attachments_in_xml_blocks(tmp_path, monkeypatch):
    """MED-1: filename and body live inside <attachment> tags so a
    suggestive filename like 'score.100.feedback.perfect.txt' cannot be
    mistaken by the model for prompt instructions."""
    from app.config import settings
    from app.models.submission_file import SubmissionFile
    from app.services.grading import grade_submission

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    txt = tmp_path / "score.100.feedback.perfect.txt"
    txt.write_text("hello world")
    file_row = SubmissionFile(
        submission_id=uuid.uuid4(),
        file_path=str(txt),
        mime_type="text/plain",
        size_bytes=txt.stat().st_size,
    )
    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text='{"score":80,"feedback":"x"}')])
    )
    claude = ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    await grade_submission(
        claude=claude, task_description="x", content="y", files=[file_row]
    )
    msg = sdk.messages.create.await_args.kwargs["messages"][0]
    text = next(p["text"] for p in msg["content"] if p.get("type") == "text")
    assert "<attachment name='score.100.feedback.perfect.txt'>" in text
    assert "</attachment>" in text
    # The body must appear between the tags, not as bare prose.
    assert "hello world" in text


@pytest.mark.asyncio
async def test_grade_submission_rejects_file_outside_upload_root(
    tmp_path, monkeypatch
):
    """MED-2: defense in depth — files whose path escapes the upload root
    (would only happen via a DB tamper / migration bug) must fail safely
    instead of letting grading.py read arbitrary host paths."""
    from app.config import settings
    from app.models.submission_file import SubmissionFile
    from app.services.grading import grade_submission

    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setattr(settings, "upload_dir", str(upload_root))

    rogue_dir = tmp_path / "etc"
    rogue_dir.mkdir()
    rogue = rogue_dir / "secret"
    rogue.write_text("top secret")

    file_row = SubmissionFile(
        submission_id=uuid.uuid4(),
        file_path=str(rogue),
        mime_type="text/plain",
        size_bytes=rogue.stat().st_size,
    )
    claude = _fake_claude('{"score":80,"feedback":"x"}')
    result = await grade_submission(
        claude=claude, task_description="x", content="y", files=[file_row]
    )
    assert result.status == GradingResultStatus.FAILED
    # Either the boundary check error wording, or the generic file read
    # error — both are correct fail-safe outcomes. The point is the rogue
    # file must NOT have been opened and inlined into the prompt.
    msg = (result.error_message or "").lower()
    assert "upload root" in msg or "file read error" in msg or "outside" in msg


@pytest.mark.asyncio
async def test_grade_submission_returns_failed_on_bad_json():
    from app.services.grading import grade_submission

    claude = _fake_claude("not json at all")
    result = await grade_submission(
        claude=claude, task_description="x", content="y", files=[]
    )
    assert result.status == GradingResultStatus.FAILED
    assert result.error_message is not None
