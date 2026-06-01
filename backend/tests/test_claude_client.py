from unittest.mock import MagicMock

import pytest

from app.core.claude_client import ClaudeClient


class _StubResponse:
    def __init__(self, text: str) -> None:
        self.content = [MagicMock(text=text)]


def test_complete_returns_assistant_text():
    fake_sdk = MagicMock()
    fake_sdk.messages.create.return_value = _StubResponse("こんにちは、研修生さん")

    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")
    reply = client.complete(
        system_prompt="あなたはAIチューターです",
        history=[{"role": "user", "content": "Gitとは？"}],
    )

    assert reply == "こんにちは、研修生さん"
    fake_sdk.messages.create.assert_called_once()
    kwargs = fake_sdk.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-5"
    assert kwargs["system"] == "あなたはAIチューターです"
    assert kwargs["messages"] == [{"role": "user", "content": "Gitとは？"}]


def test_complete_propagates_sdk_errors():
    fake_sdk = MagicMock()
    fake_sdk.messages.create.side_effect = RuntimeError("rate limited")

    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")

    with pytest.raises(RuntimeError, match="rate limited"):
        client.complete(system_prompt="", history=[])
