"""Tests for the deterministic Claude SDK stub used by E2E."""

import json

import pytest

from app.core.claude_client import ClaudeClient
from app.core.claude_stub import StubAsyncAnthropic

GRADING_SYSTEM = "あなたは AI 駆動型開発カリキュラムの教育評価者です。…"
CHAT_SYSTEM = "あなたはAI駆動型開発を教える教育AIチューターです。"
NUDGE_SYSTEM = "あなたは学習コーチです。短い1〜2文の次の一歩を返してください。"


def _client() -> ClaudeClient:
    return ClaudeClient(sdk=StubAsyncAnthropic(), model="stub-model")


def _grading_payload(content: str) -> dict:
    return {"role": "user", "content": f"課題: x\n受講者の提出（本文）:\n{content}"}


@pytest.mark.asyncio
async def test_stub_returns_low_score_for_weak_marker():
    text = await _client().complete(GRADING_SYSTEM, [_grading_payload("stub:weak")])
    payload = json.loads(text)
    assert payload["score"] == 55


@pytest.mark.asyncio
async def test_stub_returns_high_score_for_great_marker():
    text = await _client().complete(GRADING_SYSTEM, [_grading_payload("stub:great")])
    assert json.loads(text)["score"] == 92


@pytest.mark.asyncio
async def test_stub_returns_default_score_without_marker():
    text = await _client().complete(GRADING_SYSTEM, [_grading_payload("hello")])
    assert json.loads(text)["score"] == 80


@pytest.mark.asyncio
async def test_stub_chat_reply_is_text():
    text = await _client().complete(
        CHAT_SYSTEM,
        [{"role": "user", "content": "Git の使い方を教えて"}],
    )
    # Not JSON, just a short coaching reply
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    assert "良い質問" in text or "確認" in text


@pytest.mark.asyncio
async def test_stub_nudge_reply_mentions_phase():
    text = await _client().complete(
        NUDGE_SYSTEM,
        [{"role": "user", "content": "今週の弱点を踏まえた助言を一文で。"}],
    )
    assert "Phase" in text or "AI レビュー" in text
