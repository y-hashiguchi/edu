"""Deterministic Claude SDK stub for end-to-end testing.

Activated when ``settings.claude_stub_mode`` is true. The stub mimics the
shape of ``anthropic.AsyncAnthropic`` so ``ClaudeClient`` can use it
unchanged. Responses are derived from textual markers inside the user
message so an E2E test can control the score / weakness profile.

Recognized markers (in the user message body):

* ``stub:weak``   → grading JSON with score 55
* ``stub:ok``     → grading JSON with score 75
* ``stub:great``  → grading JSON with score 92
* (no marker)     → grading JSON with score 80

For non-grading prompts (chat / nudge) a short canned text reply is
returned so the integration still surfaces something to the user.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_GRADING_PROMPT_MARKER = "教育評価者"
_GRADING_SCORE_CASES: tuple[tuple[str, int, str], ...] = (
    ("stub:weak", 55, "もう少し具体例を増やしましょう。"),
    ("stub:ok", 75, "概ね良好です。あと一歩深掘りを。"),
    ("stub:great", 92, "素晴らしい考察です。"),
)
_DEFAULT_STUB_SCORE = 80
_DEFAULT_STUB_FEEDBACK = "標準的な内容です。"

_NUDGE_REPLY = "Phase 1 を着実に進めましょう。次のタスクで AI レビューに挑戦してみてください。"
_CHAT_REPLY = "良い質問ですね。まずは公式ドキュメントを確認し、小さな例で動かしてみましょう。"


@dataclass(frozen=True)
class _StubContentBlock:
    text: str


@dataclass(frozen=True)
class _StubResponse:
    content: list[_StubContentBlock]


def _pick_grading_payload(user_text: str) -> dict[str, Any]:
    for marker, score, feedback in _GRADING_SCORE_CASES:
        if marker in user_text:
            return {"score": score, "feedback": feedback}
    return {"score": _DEFAULT_STUB_SCORE, "feedback": _DEFAULT_STUB_FEEDBACK}


def _extract_user_text(messages: list[dict[str, Any]]) -> str:
    """Flatten the most recent user message into a string for marker scanning."""
    for entry in reversed(messages):
        if entry.get("role") != "user":
            continue
        content = entry.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
            return "\n".join(chunks)
    return ""


def _build_reply(*, system: str, messages: list[dict[str, Any]]) -> str:
    user_text = _extract_user_text(messages)
    if _GRADING_PROMPT_MARKER in (system or ""):
        return json.dumps(_pick_grading_payload(user_text), ensure_ascii=False)
    # Heuristic: nudge prompts are short and reference Phase / 弱点; treat
    # the chat default as covering everything else (chat, nudge fallback).
    if "弱点" in user_text or "次の一歩" in (system or "") or "短い" in (system or ""):
        return _NUDGE_REPLY
    return _CHAT_REPLY


class _StubMessages:
    async def create(
        self,
        *,
        model: str,  # noqa: ARG002 — kept to mirror the SDK signature
        max_tokens: int,  # noqa: ARG002
        system: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,  # noqa: ARG002
    ) -> _StubResponse:
        text = _build_reply(system=system, messages=messages)
        return _StubResponse(content=[_StubContentBlock(text=text)])


class StubAsyncAnthropic:
    """Drop-in replacement for ``anthropic.AsyncAnthropic`` in E2E runs.

    Only the ``.messages.create`` surface used by :class:`ClaudeClient` is
    implemented. The signature matches the real SDK so ``ClaudeClient``
    needs no changes.
    """

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.messages = _StubMessages()
