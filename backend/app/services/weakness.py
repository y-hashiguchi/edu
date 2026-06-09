"""Sprint 5 weakness service — per-tag score aggregation.

Definition of weakness:
  - Take the latest *graded* attempt for each submission.
  - Group those scores by curriculum skill_tags.
  - Drop tags with fewer than MIN_TAG_SUBMISSIONS supporting samples
    (so a one-off bad grade does not turn into "your weakness").
  - Return the 3 tags with the lowest mean score.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.curriculum import get_task_skill_tags
from app.models.grading_attempt import GradingAttempt
from app.models.submission import Submission

MIN_SUBMISSION_THRESHOLD = 3
"""提出件数がこれを下回るとき、弱点分析を出さずに cold-start UX に切り替える。"""

MIN_TAG_SUBMISSIONS = 2
"""タグ集計に含めるための最小提出数（1 件で「弱点」認定はノイズ）。"""


@dataclass(frozen=True)
class TagAverage:
    tag: str
    average_score: float
    submission_count: int


@dataclass(frozen=True)
class WeaknessResult:
    has_enough_data: bool
    top_weaknesses: list[TagAverage]


async def compute_weakness(
    db: AsyncSession, user_id: uuid.UUID,
) -> WeaknessResult:
    rows = await _latest_graded_scores(db, user_id)
    if len(rows) < MIN_SUBMISSION_THRESHOLD:
        return WeaknessResult(has_enough_data=False, top_weaknesses=[])

    tag_scores: dict[str, list[float]] = defaultdict(list)
    for _sub_id, score, phase, task_no in rows:
        try:
            tags = get_task_skill_tags(phase, task_no)
        except KeyError:
            # Legacy submission whose task no longer exists in the
            # curriculum. Skip the row rather than raise — surfacing
            # a 500 here would suppress weakness analysis for any
            # learner with a single stale submission.
            continue
        for tag in tags:
            tag_scores[tag].append(float(score))

    averages = [
        TagAverage(
            tag=t,
            average_score=round(mean(scores), 2),
            submission_count=len(scores),
        )
        for t, scores in tag_scores.items()
        if len(scores) >= MIN_TAG_SUBMISSIONS
    ]
    # 低スコア順、同点はタグ名でタイブレーク（テストで安定再現可能に）
    averages.sort(key=lambda a: (a.average_score, a.tag))
    return WeaknessResult(has_enough_data=True, top_weaknesses=averages[:3])


async def _latest_graded_scores(
    db: AsyncSession, user_id: uuid.UUID,
) -> list[tuple[uuid.UUID, float, int, int]]:
    """`SELECT DISTINCT ON (s.id)` で submission ごとに最新 graded attempt
    のスコアを返す。phase / task_no は Python 側で curriculum lookup する
    ため一緒に返す。"""
    stmt = (
        select(
            Submission.id,
            GradingAttempt.score,
            Submission.phase,
            Submission.task_no,
        )
        .join(GradingAttempt, GradingAttempt.submission_id == Submission.id)
        .where(
            Submission.user_id == user_id,
            GradingAttempt.status == "graded",
        )
        .order_by(Submission.id, GradingAttempt.created_at.desc())
        .distinct(Submission.id)
    )
    rows = (await db.execute(stmt)).all()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


async def compute_top_weakness_tags_bulk(
    db: AsyncSession, user_ids: list[uuid.UUID],
) -> dict[uuid.UUID, str | None]:
    """1 クエリで全 user の latest graded scores を取得し、user 別に
    タグ平均を計算して上位 1 つを返す。admin users 一覧の column 用。

    Sprint 5 の compute_weakness とは違い、MIN_SUBMISSION_THRESHOLD は
    適用しない: 一覧 column では「データがあるなら出す」方が UX の見える
    機会が増える。MIN_TAG_SUBMISSIONS を満たすタグがあればその中で最低平均
    のタグを返し、無ければ単発タグも含めて最低平均タグを返す（タグ名で
    タイブレーク）。提出 0 件のユーザーのみ None を返す。"""
    if not user_ids:
        return {}

    stmt = (
        select(
            Submission.user_id,
            Submission.id,
            GradingAttempt.score,
            Submission.phase,
            Submission.task_no,
        )
        .join(GradingAttempt, GradingAttempt.submission_id == Submission.id)
        .where(
            Submission.user_id.in_(user_ids),
            GradingAttempt.status == "graded",
        )
        .order_by(
            Submission.user_id,
            Submission.id,
            GradingAttempt.created_at.desc(),
        )
        .distinct(Submission.user_id, Submission.id)
    )
    rows = (await db.execute(stmt)).all()

    by_user: dict[uuid.UUID, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for user_id, _sub_id, score, phase, task_no in rows:
        try:
            tags = get_task_skill_tags(phase, task_no)
        except KeyError:
            continue
        for tag in tags:
            by_user[user_id][tag].append(float(score))

    out: dict[uuid.UUID, str | None] = {}
    for uid in user_ids:
        tag_scores = by_user.get(uid, {})
        if not tag_scores:
            out[uid] = None
            continue
        eligible = {
            t: s for t, s in tag_scores.items()
            if len(s) >= MIN_TAG_SUBMISSIONS
        }
        pool = eligible if eligible else tag_scores
        worst = min(
            pool.items(),
            key=lambda kv: (mean(kv[1]), kv[0]),
        )
        out[uid] = worst[0]
    return out
