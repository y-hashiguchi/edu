from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.claude_client import ClaudeClient
from app.services.grading import GradingError, grade_submission


def _fake(reply: str) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=reply)])
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")


@pytest.mark.asyncio
async def test_grade_parses_json_object():
    claude = _fake('{"score": 85, "feedback": "良い回答です。"}')
    result = await grade_submission(
        claude=claude, task_description="Gitとは", content="Gitはバージョン管理"
    )
    assert result.score == 85
    assert "良い" in result.feedback


@pytest.mark.asyncio
async def test_grade_handles_wrapped_json():
    text = '評価結果は以下です:\n{"score": 60, "feedback": "もう少し具体例を"}\nです。'
    claude = _fake(text)
    result = await grade_submission(
        claude=claude, task_description="x", content="y"
    )
    assert result.score == 60


@pytest.mark.asyncio
async def test_grade_clamps_out_of_range_score():
    claude = _fake('{"score": 150, "feedback": "x"}')
    result = await grade_submission(claude=claude, task_description="x", content="y")
    assert result.score == 100


@pytest.mark.asyncio
async def test_grade_raises_on_unparseable():
    claude = _fake("これは JSON ではありません")
    with pytest.raises(GradingError):
        await grade_submission(claude=claude, task_description="x", content="y")
