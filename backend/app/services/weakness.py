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

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.curriculum import get_task_skill_tags
from app.models.grading_attempt import GradingAttempt
from app.models.submission import Submission

MIN_SUBMISSION_THRESHOLD = 3
"""提出件数がこれを下回るとき、弱点分析を出さずに cold-start UX に切り替える。"""

MIN_TAG_SUBMISSIONS = 2
"""タグ集計に含めるための最小提出数（1 件で「弱点」認定はノイズ）。"""

BULK_MIN_TAG_SUBMISSIONS = MIN_TAG_SUBMISSIONS
"""admin 一覧 bulk 弱点でも learner dashboard と同じタグ最小件数を適用する。
1 件タグへの fallback は行わない（Sprint 6 MED-2）。"""


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
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> WeaknessResult:
    rows = await _latest_graded_scores(db, user_id, course_id)
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
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
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
            Submission.course_id == course_id,
            GradingAttempt.status == "graded",
        )
        .order_by(Submission.id, GradingAttempt.created_at.desc())
        .distinct(Submission.id)
    )
    rows = (await db.execute(stmt)).all()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


async def compute_top_weakness_tags_bulk(
    db: AsyncSession,
    user_course_pairs: list[tuple[uuid.UUID, uuid.UUID]],
) -> dict[uuid.UUID, str | None]:
    """1 クエリで全 (user, course) の latest graded scores を取得し、
    user 別にタグ平均を計算して上位 1 つを返す。admin users 一覧の
    column 用。Sprint 7 で course-scoped に拡張。

    Sprint 5 の compute_weakness とは違い、MIN_SUBMISSION_THRESHOLD は
    適用しない: 一覧 column では「データがあるなら出す」方が UX の見える
    機会が増える。タグは BULK_MIN_TAG_SUBMISSIONS（= MIN_TAG_SUBMISSIONS）
    を満たすものだけを対象とし、該当タグが無ければ None を返す。
    learner dashboard の弱点分析と同じタグ閾値で一貫させる（Sprint 6 MED-2）。
    提出 0 件のユーザーのみ None を返す。

    Sprint 7: input は (user_id, course_id) のタプル列。同じ user が
    複数 course を持つケースは admin 一覧では想定しない（admin 側で
    course を 1 つに固定して呼ぶ）。戻り値は user_id でキー付けする。

    Sprint 7 MED-4 (follow-up): 同一 user_id を複数 (uid, cid) ペアで
    渡すと "後勝ち" になりサイレントなデータロスを起こすため、
    duplicate user_id を検出した時点で ValueError を投げる。複数
    course を分析したい呼び出し側は (uid, cid) キー版（未実装、
    Sprint 8 候補）へ移行すること。"""
    if not user_course_pairs:
        return {}

    user_ids = [u for u, _ in user_course_pairs]
    seen: set[uuid.UUID] = set()
    for uid in user_ids:
        if uid in seen:
            raise ValueError(
                f"compute_top_weakness_tags_bulk: duplicate user_id {uid} "
                "in user_course_pairs. The return dict is keyed by user_id "
                "and cannot safely carry multiple courses for the same "
                "user. Either deduplicate at the call site or migrate to "
                "a (user_id, course_id)-keyed variant."
            )
        seen.add(uid)
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
            tuple_(Submission.user_id, Submission.course_id).in_(user_course_pairs),
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

    by_user: dict[uuid.UUID, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
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
        eligible = {t: s for t, s in tag_scores.items() if len(s) >= BULK_MIN_TAG_SUBMISSIONS}
        if not eligible:
            out[uid] = None
            continue
        worst = min(
            eligible.items(),
            key=lambda kv: (mean(kv[1]), kv[0]),
        )
        out[uid] = worst[0]
    return out
