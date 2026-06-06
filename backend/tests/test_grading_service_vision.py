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
async def test_grade_submission_with_image_uses_multimodal(tmp_path):
    from app.models.submission_file import SubmissionFile
    from app.services.grading import grade_submission

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
async def test_grade_submission_truncates_long_text_attachments(tmp_path):
    """HIGH-2: inline text bodies are truncated before being added to the prompt.

    A 5 MB plain-text attachment would otherwise expand the user message far
    beyond what's safe (token cost + context-window blowup).
    """
    from app.models.submission_file import SubmissionFile
    from app.services import grading
    from app.services.grading import (
        _MAX_INLINE_CHARS_PER_FILE,
        _TRUNCATION_MARKER,
    )

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
async def test_grade_submission_returns_failed_on_claude_error():
    from app.services.grading import grade_submission

    sdk = MagicMock()
    sdk.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
    claude = ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    result = await grade_submission(
        claude=claude, task_description="x", content="y", files=[]
    )
    assert result.status == GradingResultStatus.FAILED
    assert result.error_message and "boom" in result.error_message


@pytest.mark.asyncio
async def test_grade_submission_returns_failed_on_bad_json():
    from app.services.grading import grade_submission

    claude = _fake_claude("not json at all")
    result = await grade_submission(
        claude=claude, task_description="x", content="y", files=[]
    )
    assert result.status == GradingResultStatus.FAILED
    assert result.error_message is not None
