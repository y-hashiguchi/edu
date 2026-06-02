from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.claude_client import ClaudeClient


@pytest.mark.asyncio
async def test_complete_returns_assistant_text():
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text="こんにちは、研修生さん")])
    )

    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")
    reply = await client.complete(
        system_prompt="あなたはAIチューターです",
        history=[{"role": "user", "content": "Gitとは？"}],
    )

    assert reply == "こんにちは、研修生さん"
    fake_sdk.messages.create.assert_awaited_once()
    kwargs = fake_sdk.messages.create.await_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-5"
    assert kwargs["system"] == "あなたはAIチューターです"
    assert kwargs["messages"] == [{"role": "user", "content": "Gitとは？"}]


@pytest.mark.asyncio
async def test_complete_propagates_sdk_errors():
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(side_effect=RuntimeError("rate limited"))

    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")

    with pytest.raises(RuntimeError, match="rate limited"):
        await client.complete(system_prompt="", history=[])
