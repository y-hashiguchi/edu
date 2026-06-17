"""ClaudeClient multimodal completion tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.claude_client import ClaudeClient


@pytest.mark.asyncio
async def test_complete_multimodal_sends_text_and_image_blocks():
    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text='{"score":90,"feedback":"x"}')])
    )
    client = ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    reply = await client.complete_multimodal(
        system_prompt="sys",
        text="hello",
        attachments=[
            {"media_type": "image/png", "data": "<base64>"},
            {"media_type": "application/pdf", "data": "<base64>"},
        ],
    )

    assert reply.startswith("{")
    sdk.messages.create.assert_awaited_once()
    kwargs = sdk.messages.create.await_args.kwargs
    msg = kwargs["messages"][0]
    assert msg["role"] == "user"
    content_types = [b["type"] for b in msg["content"]]
    assert "text" in content_types
    assert content_types.count("image") == 1
    assert content_types.count("document") == 1


@pytest.mark.asyncio
async def test_complete_multimodal_without_attachments_falls_back_to_text():
    sdk = MagicMock()
    sdk.messages.create = AsyncMock(return_value=MagicMock(content=[MagicMock(text="ok")]))
    client = ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    reply = await client.complete_multimodal(system_prompt="sys", text="only text", attachments=[])

    assert reply == "ok"
    kwargs = sdk.messages.create.await_args.kwargs
    msg = kwargs["messages"][0]
    assert msg["content"][0]["type"] == "text"
    assert len(msg["content"]) == 1
