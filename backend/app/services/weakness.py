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
        for tag in get_task_skill_tags(phase, task_no):
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
