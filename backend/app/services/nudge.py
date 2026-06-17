"""Sprint 5 AI nudge service.

Lazy generation + 24h cache. The cache key is (user_id), the freshness
check is (within TTL) AND (input_signature unchanged). On Claude
failure we degrade rather than 500 — stale row if we have one,
generic static fallback otherwise. Cold-start users (submissions < 3)
never hit the LLM and never persist a row, so re-evaluating their
state after they start submitting is cheap.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user_nudge import UserNudge
from app.services.weakness import MIN_SUBMISSION_THRESHOLD

logger = logging.getLogger(__name__)


COLD_START_BODY = (
    "まずは Phase 1 のタスクから始めてみましょう。"
    "3 件提出するとあなた専用のアドバイスが出るようになります。"
)
"""Submission count < MIN_SUBMISSION_THRESHOLD のとき出す固定文。"""

TRANSITIONAL_BODY = (
    "提出が貯まり始めましたね。"
    "同じタグのタスクを 2 件以上こなすと、あなた専用の分析が始まります。"
    "まずは Phase 1 を進めてみましょう。"
)
"""MED-2 (sprint-5 follow-up): submission_count >= threshold だが
weakness も recommendations も空の transitional state で出す固定文。
LLM を呼ぶとコンテキスト不足で curriculum-irrelevant な内容を
ハルシネートするため (ローカル検証で実害確認)、ここで短絡する。"""

LLM_FAILURE_FALLBACK = "今日も学習を続けましょう。提出を 1 件積むごとに、次の一歩が見えてきます。"
"""LLM が落ちていて、過去の nudge も存在しないときの最終フォールバック。"""


@dataclass(frozen=True)
class NudgeResult:
    body: str
    generated_at: datetime
    is_fresh: bool


def _build_signature(
    course_id: uuid.UUID,
    weakness_tags: list[str],
    top_recommendation_key: str | None,
    submission_count: int,
) -> str:
    """16 char SHA-256 prefix. Identical inputs → identical signature.
    A change in top-3 weakness order, in the primary recommendation, or
    in the total submission count breaks the cache deliberately.

    Sprint 7: course_id is folded into the payload so a learner who
    switches courses (and whose UserNudge PK now includes course_id)
    sees a clean cache miss instead of a stale signature collision
    if two courses ever happen to produce the same weakness/rec/count
    triple within the TTL window.

    LOW-4 (sprint-5 follow-up): `weakness_tags[:3]` is a defensive
    duplicate cap. `compute_weakness` already returns at most 3 tags
    (`averages[:3]`), so this slice is redundant in current code. The
    safeguard is kept on purpose: signatures are derived data and we
    want this function to remain a pure SHA-256 wrapper independent of
    the upstream invariant. A future change that lifts the top-3 cap
    in weakness service would otherwise silently break cache stability
    here."""
    payload = (
        f"{course_id}|{','.join(weakness_tags[:3])}|"
        f"{top_recommendation_key or ''}|{submission_count}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _build_prompt(
    weakness_tags: list[str],
    recommendation_titles: list[str],
    progress_text: str,
) -> tuple[str, str]:
    """Return (system_prompt, user_message).

    XML wrapper around learner data mirrors Sprint 4 MED-1's defensive
    pattern — even if a recommendation title later contains an injection
    payload, it never escapes the <recommendations> block."""
    system = (
        "あなたは個別最適化されたアドバイザーです。\n"
        "受講者の弱点と進捗を踏まえて、次の一歩を 80 文字以内・1 文で示してください。\n"
        "励ましの言葉は不要。具体的なタスク名や数値を含めてください。"
    )
    weakness_block = (
        "\n".join(f"{i + 1}. {t}" for i, t in enumerate(weakness_tags[:3]))
        or "（まだ十分なデータがありません）"
    )
    rec_block = "\n".join(f"- {title}" for title in recommendation_titles[:3]) or "- （該当なし）"
    user = (
        f"<progress>{progress_text}</progress>\n"
        f"<weakness>\n{weakness_block}\n</weakness>\n"
        f"<recommendations>\n{rec_block}\n</recommendations>"
    )
    return system, user


async def get_or_generate(
    db: AsyncSession,
    *,
    claude,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    weakness_tags: list[str],
    top_recommendation_key: str | None,
    submission_count: int,
    recommendation_titles: list[str] | None = None,
    progress_text: str = "",
) -> NudgeResult:
    # Cold start: skip LLM entirely.
    if submission_count < MIN_SUBMISSION_THRESHOLD:
        return NudgeResult(
            body=COLD_START_BODY,
            generated_at=datetime.now(UTC),
            is_fresh=True,
        )

    # MED-2 (sprint-5 follow-up): transitional state past cold-start but
    # before any tag has hit MIN_TAG_SUBMISSIONS. Empty weakness AND empty
    # recommendations means the XML prompt has no real context for the
    # LLM to ground on — Haiku then hallucinates curriculum-irrelevant
    # tasks. Skip the LLM, return the transitional text, do NOT persist
    # so the next state transition gets a real cache miss.
    if not weakness_tags and not (recommendation_titles or []):
        return NudgeResult(
            body=TRANSITIONAL_BODY,
            generated_at=datetime.now(UTC),
            is_fresh=True,
        )

    signature = _build_signature(
        course_id,
        weakness_tags,
        top_recommendation_key,
        submission_count,
    )

    # HIGH-2 (sprint-5 security review): skip_locked=True turns a
    # concurrent caller into a cache miss instead of a blocking lock
    # holder. The worst outcome is one redundant LLM call; the
    # subsequent ON CONFLICT DO UPDATE keeps the final state coherent.
    # Blocking would tie up a DB connection for the entire LLM round
    # trip and chain into pool exhaustion at scale.
    existing = (
        await db.execute(
            select(UserNudge)
            .where(
                UserNudge.user_id == user_id,
                UserNudge.course_id == course_id,
            )
            .with_for_update(skip_locked=True)
        )
    ).scalar_one_or_none()

    ttl = timedelta(hours=settings.nudge_cache_ttl_hours)
    if (
        existing is not None
        and (datetime.now(UTC) - existing.generated_at) < ttl
        and existing.input_signature == signature
    ):
        return NudgeResult(
            body=existing.body,
            generated_at=existing.generated_at,
            is_fresh=True,
        )

    # Cache miss / stale / signature changed → regenerate.
    system_prompt, user_message = _build_prompt(
        weakness_tags,
        recommendation_titles or [],
        progress_text,
    )
    try:
        reply = await claude.complete(
            system_prompt=system_prompt,
            history=[{"role": "user", "content": user_message}],
            max_tokens=settings.nudge_max_output_tokens,
            temperature=settings.nudge_temperature,
        )
    except Exception:
        logger.exception("Nudge LLM call failed; degrading gracefully")
        if existing is not None:
            return NudgeResult(
                body=existing.body,
                generated_at=existing.generated_at,
                is_fresh=False,
            )
        return NudgeResult(
            body=LLM_FAILURE_FALLBACK,
            generated_at=datetime.now(UTC),
            is_fresh=False,
        )

    body = (reply or "").strip()[:500]
    if not body:
        if existing is not None:
            return NudgeResult(
                body=existing.body,
                generated_at=existing.generated_at,
                is_fresh=False,
            )
        return NudgeResult(
            body=LLM_FAILURE_FALLBACK,
            generated_at=datetime.now(UTC),
            is_fresh=False,
        )

    now = datetime.now(UTC)
    stmt = pg_insert(UserNudge.__table__).values(
        user_id=user_id,
        course_id=course_id,
        body=body,
        generated_at=now,
        input_signature=signature,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "course_id"],
        set_={"body": body, "generated_at": now, "input_signature": signature},
    )
    await db.execute(stmt)
    await db.commit()

    return NudgeResult(body=body, generated_at=now, is_fresh=True)
