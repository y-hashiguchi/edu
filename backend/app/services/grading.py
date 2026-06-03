"""Submission grading via Claude with JSON output."""

import json
import re

from app.core.claude_client import ClaudeClient
from app.schemas.grading import GradingResult


class GradingError(Exception):
    pass


SYSTEM_PROMPT = (
    "あなたは AI 駆動型開発カリキュラムの教育評価者です。\n"
    "受講者の提出物を採点します。以下を守ってください:\n"
    "- 課題の意図に沿っているか、論理性、具体性で評価\n"
    "- 0 〜 100 の整数スコアを必ず付ける\n"
    "- 日本語 2〜4 文の建設的フィードバックを返す\n"
    "- 出力は次の JSON のみ。前置きや後置きを書かない:\n"
    '  {"score": <integer 0-100>, "feedback": "<日本語のコメント>"}'
)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise GradingError(f"No JSON object in response: {text[:200]!r}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise GradingError(f"Invalid JSON: {e}: {text[:200]!r}") from e


async def grade_submission(
    *, claude: ClaudeClient, task_description: str, content: str
) -> GradingResult:
    user_message = (
        f"課題: {task_description}\n\n"
        f"受講者の提出:\n{content}\n\n"
        "上記を採点し、指定された JSON のみで返答してください。"
    )
    reply = await claude.complete(
        system_prompt=SYSTEM_PROMPT,
        history=[{"role": "user", "content": user_message}],
    )

    obj = _extract_json(reply)
    try:
        score_raw = int(obj["score"])
        feedback = str(obj["feedback"])
    except (KeyError, ValueError, TypeError) as e:
        raise GradingError(f"missing or invalid fields: {obj!r}") from e

    score = max(0, min(100, score_raw))
    return GradingResult(score=score, feedback=feedback)
