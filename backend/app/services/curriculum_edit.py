"""Sprint 9 — curriculum edit service.

Routes never touch the ORM directly. They call these helpers and the
service is responsible for:
  - exclude_unset セマンティクス (key in dict / not in dict の判別)
  - publish 時の cache 差し替え
  - エラーハンドリング (PhaseNotFoundError / TaskNotFoundError /
    CourseNotFoundError)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.courses import CourseNotFoundError
from app.models.chat_history import ChatHistory
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask
from app.models.embedding import Embedding
from app.models.enrollment import Enrollment
from app.models.progress import Progress, ProgressStatus
from app.models.submission import Submission
from app.services.curriculum_embeddings import task_embedding_source_ref


class PhaseNotFoundError(Exception):
    def __init__(self, slug: str, phase_no: int) -> None:
        super().__init__(f"phase {phase_no} not found in course {slug!r}")
        self.slug = slug
        self.phase_no = phase_no


class TaskNotFoundError(Exception):
    def __init__(self, slug: str, phase_no: int, task_no: int) -> None:
        super().__init__(
            f"task {task_no} not found in phase {phase_no} of course {slug!r}"
        )
        self.slug = slug
        self.phase_no = phase_no
        self.task_no = task_no


class CannotDeleteLastTaskError(Exception):
    def __init__(self, slug: str, phase_no: int) -> None:
        super().__init__(
            f"cannot delete the last task in phase {phase_no} of course {slug!r}"
        )
        self.slug = slug
        self.phase_no = phase_no


class TaskHasSubmissionsError(Exception):
    def __init__(self, slug: str, phase_no: int, task_no: int) -> None:
        super().__init__(
            f"task {task_no} in phase {phase_no} of course {slug!r} has submissions"
        )
        self.slug = slug
        self.phase_no = phase_no
        self.task_no = task_no


class InvalidTaskMoveError(Exception):
    def __init__(self, slug: str, phase_no: int, task_no: int, to_task_no: int) -> None:
        super().__init__(
            f"invalid move task {task_no} -> {to_task_no} "
            f"in phase {phase_no} of course {slug!r}"
        )
        self.slug = slug
        self.phase_no = phase_no
        self.task_no = task_no
        self.to_task_no = to_task_no


class CannotDeleteLastPhaseError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"cannot delete the last phase in course {slug!r}")
        self.slug = slug


class PhaseHasSubmissionsError(Exception):
    def __init__(self, slug: str, phase_no: int) -> None:
        super().__init__(
            f"phase {phase_no} in course {slug!r} has submissions"
        )
        self.slug = slug
        self.phase_no = phase_no


_TASK_NO_OFFSET = 100_000
_PHASE_NO_OFFSET = 100_000
_DEFAULT_NEW_TASK_TITLE = "新しい Task"
_DEFAULT_NEW_TASK_DESCRIPTION = "説明を入力してください。"
_DEFAULT_NEW_PHASE_TITLE = "新しい Phase"
_DEFAULT_NEW_PHASE_GOAL = "目標を入力してください。"
_DEFAULT_NEW_SYSTEM_PROMPT = (
    "あなたは教育AIチューターです。\n"
    "研修生の質問に3〜5文程度の日本語で答えてください。"
)


@dataclass(frozen=True)
class PublishResult:
    slug: str
    published_phase_count: int
    published_task_count: int
    published_at: datetime
    embedding_source_refs: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


async def _get_course_by_slug(db: AsyncSession, slug: str) -> Course:
    course = (
        await db.execute(select(Course).where(Course.slug == slug))
    ).scalar_one_or_none()
    if course is None:
        raise CourseNotFoundError(slug)
    return course


async def _get_phase_or_raise(
    db: AsyncSession, course_slug: str, course_id, phase_no: int
) -> CurriculumPhase:
    row = (
        await db.execute(
            select(CurriculumPhase).where(
                CurriculumPhase.course_id == course_id,
                CurriculumPhase.phase_no == phase_no,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise PhaseNotFoundError(course_slug, phase_no)
    return row


async def _get_task_or_raise(
    db: AsyncSession,
    course_slug: str,
    phase_no: int,
    phase_id,
    task_no: int,
) -> CurriculumTask:
    row = (
        await db.execute(
            select(CurriculumTask).where(
                CurriculumTask.phase_id == phase_id,
                CurriculumTask.task_no == task_no,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise TaskNotFoundError(course_slug, phase_no, task_no)
    return row


# ---------------------------------------------------------------------------
# Draft write
# ---------------------------------------------------------------------------


_PHASE_DRAFT_FIELDS = ("title", "goal", "system_prompt")
_TASK_DRAFT_FIELDS = (
    "title",
    "description",
    "skill_tags",
    "deliverable",
    "week_label",
)


async def put_phase_draft(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
    payload: Mapping[str, Any],
) -> CurriculumPhase:
    """payload に key があるフィールドだけ draft_* を更新する。

    None 値は「draft をクリア」、明示値は「draft を設定」。key の不在は
    「変更なし」。route は `model_dump(exclude_unset=True)` を渡す。
    """
    course = await _get_course_by_slug(db, course_slug)
    row = await _get_phase_or_raise(db, course_slug, course.id, phase_no)

    for field in _PHASE_DRAFT_FIELDS:
        if field in payload:
            setattr(row, f"draft_{field}", payload[field])
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


async def put_task_draft(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
    task_no: int,
    payload: Mapping[str, Any],
) -> CurriculumTask:
    course = await _get_course_by_slug(db, course_slug)
    phase = await _get_phase_or_raise(db, course_slug, course.id, phase_no)
    row = await _get_task_or_raise(db, course_slug, phase_no, phase.id, task_no)

    for field in _TASK_DRAFT_FIELDS:
        if field in payload:
            setattr(row, f"draft_{field}", payload[field])
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# Publish / discard
# ---------------------------------------------------------------------------


async def publish_course(
    db: AsyncSession, *, course_slug: str
) -> PublishResult:
    """全 draft_* を対応する published 列に COPY、draft_* を NULL に。

    Returns: 影響行数。0 件も idempotent (200 OK)。

    Cache invalidation is the route's responsibility — it must call
    ``runtime.reload_course`` *after* ``db.commit()`` so a commit-time
    failure does not leave the cache holding values the DB rolled back.
    """
    course = await _get_course_by_slug(db, course_slug)

    phases = (await db.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == course.id)
    )).scalars().all()

    published_phase = 0
    for p in phases:
        dirty = False
        if p.draft_title is not None:
            p.title = p.draft_title
            p.draft_title = None
            dirty = True
        if p.draft_goal is not None:
            p.goal = p.draft_goal
            p.draft_goal = None
            dirty = True
        if p.draft_system_prompt is not None:
            p.system_prompt = p.draft_system_prompt
            p.draft_system_prompt = None
            dirty = True
        if dirty:
            published_phase += 1
            p.updated_at = datetime.now(UTC)

    phase_ids = [p.id for p in phases]
    tasks = (await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
    )).scalars().all() if phase_ids else []

    phase_id_to_no = {p.id: p.phase_no for p in phases}
    task_title_published: list[tuple[Any, int]] = []

    published_task = 0
    for t in tasks:
        dirty = False
        title_dirty = t.draft_title is not None
        if t.draft_title is not None:
            t.title = t.draft_title
            t.draft_title = None
            dirty = True
        if t.draft_description is not None:
            t.description = t.draft_description
            t.draft_description = None
            dirty = True
        if t.draft_skill_tags is not None:
            t.skill_tags = t.draft_skill_tags
            t.draft_skill_tags = None
            dirty = True
        if t.draft_deliverable is not None:
            # 空文字 = "明示的に空にしたい"。published 列を NULL に統一する運用。
            t.deliverable = t.draft_deliverable or None
            t.draft_deliverable = None
            dirty = True
        if t.draft_week_label is not None:
            t.week_label = t.draft_week_label or None
            t.draft_week_label = None
            dirty = True
        if dirty:
            published_task += 1
            t.updated_at = datetime.now(UTC)
            if title_dirty:
                task_title_published.append((t.phase_id, t.task_no))

    await db.flush()

    embedding_source_refs: list[str] = []
    if task_title_published:
        tasks_by_phase: dict[Any, list[CurriculumTask]] = {}
        for t in tasks:
            tasks_by_phase.setdefault(t.phase_id, []).append(t)
        published_by_phase: dict[Any, set[int]] = {}
        for phase_id, task_no in task_title_published:
            published_by_phase.setdefault(phase_id, set()).add(task_no)
        for phase_id, phase_tasks in tasks_by_phase.items():
            phase_no = phase_id_to_no[phase_id]
            phase_tasks.sort(key=lambda row: row.task_no)
            published_nos = published_by_phase.get(phase_id, set())
            for i, t in enumerate(phase_tasks):
                if t.task_no in published_nos:
                    embedding_source_refs.append(
                        task_embedding_source_ref(course_slug, phase_no, i)
                    )

    return PublishResult(
        slug=course_slug,
        published_phase_count=published_phase,
        published_task_count=published_task,
        published_at=datetime.now(UTC),
        embedding_source_refs=tuple(embedding_source_refs),
    )


async def discard_drafts(db: AsyncSession, *, course_slug: str) -> None:
    """当該 course 配下の全 draft_* 列を NULL にする。published は変更なし。"""
    course = await _get_course_by_slug(db, course_slug)
    phase_id_rows = (await db.execute(
        select(CurriculumPhase.id).where(CurriculumPhase.course_id == course.id)
    )).all()
    phase_ids = [row[0] for row in phase_id_rows]

    await db.execute(
        update(CurriculumPhase)
        .where(CurriculumPhase.course_id == course.id)
        .values(
            draft_title=None,
            draft_goal=None,
            draft_system_prompt=None,
        )
    )
    if phase_ids:
        await db.execute(
            update(CurriculumTask)
            .where(CurriculumTask.phase_id.in_(phase_ids))
            .values(
                draft_title=None,
                draft_description=None,
                draft_skill_tags=None,
                draft_deliverable=None,
                draft_week_label=None,
            )
        )
    await db.flush()


# ---------------------------------------------------------------------------
# Count drafts (admin 一覧バッジ用)
# ---------------------------------------------------------------------------


async def count_pending_drafts(db: AsyncSession, *, course_slug: str) -> int:
    """draft_* に非 NULL がある field の総数を返す (Phase + Task)。"""
    course = await _get_course_by_slug(db, course_slug)
    phases = (await db.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == course.id)
    )).scalars().all()
    n = 0
    for p in phases:
        n += sum(
            1
            for f in ("draft_title", "draft_goal", "draft_system_prompt")
            if getattr(p, f) is not None
        )
    phase_ids = [p.id for p in phases]
    if phase_ids:
        tasks = (await db.execute(
            select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
        )).scalars().all()
        for t in tasks:
            n += sum(
                1
                for f in (
                    "draft_title",
                    "draft_description",
                    "draft_skill_tags",
                    "draft_deliverable",
                    "draft_week_label",
                )
                if getattr(t, f) is not None
            )
    return n


# ---------------------------------------------------------------------------
# Task structure (Sprint 15 — add / delete / reorder within a phase)
# ---------------------------------------------------------------------------


async def _list_phase_tasks_ordered(
    db: AsyncSession, phase_id
) -> list[CurriculumTask]:
    result = await db.execute(
        select(CurriculumTask)
        .where(CurriculumTask.phase_id == phase_id)
        .order_by(CurriculumTask.task_no)
    )
    return list(result.scalars().all())


async def _remap_task_numbers(
    db: AsyncSession,
    *,
    course_id,
    phase_no: int,
    mapping: dict[int, int],
) -> None:
    """old task_no -> new task_no。UNIQUE 制約回避のため一時オフセット経由。"""
    if not mapping:
        return
    changed_old = set(mapping.keys())
    now = datetime.now(UTC)

    tasks = (
        await db.execute(
            select(CurriculumTask).where(
                CurriculumTask.phase_id.in_(
                    select(CurriculumPhase.id).where(
                        CurriculumPhase.course_id == course_id,
                        CurriculumPhase.phase_no == phase_no,
                    )
                ),
                CurriculumTask.task_no.in_(changed_old),
            )
        )
    ).scalars().all()

    for t in tasks:
        t.task_no = _TASK_NO_OFFSET + t.task_no
    await db.flush()

    for old_no in changed_old:
        await db.execute(
            update(Submission)
            .where(
                Submission.course_id == course_id,
                Submission.phase == phase_no,
                Submission.task_no == old_no,
            )
            .values(task_no=_TASK_NO_OFFSET + old_no)
        )
    await db.flush()

    for t in tasks:
        orig = t.task_no - _TASK_NO_OFFSET
        t.task_no = mapping[orig]
        t.updated_at = now
    await db.flush()

    for old_no, new_no in mapping.items():
        await db.execute(
            update(Submission)
            .where(
                Submission.course_id == course_id,
                Submission.phase == phase_no,
                Submission.task_no == _TASK_NO_OFFSET + old_no,
            )
            .values(task_no=new_no)
        )
    await db.flush()


async def add_task(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
) -> CurriculumTask:
    """Phase 末尾に published task を 1 行追加する。"""
    course = await _get_course_by_slug(db, course_slug)
    phase = await _get_phase_or_raise(db, course_slug, course.id, phase_no)
    tasks = await _list_phase_tasks_ordered(db, phase.id)
    next_no = (max(t.task_no for t in tasks) if tasks else 0) + 1
    row = CurriculumTask(
        phase_id=phase.id,
        task_no=next_no,
        title=_DEFAULT_NEW_TASK_TITLE,
        description=_DEFAULT_NEW_TASK_DESCRIPTION,
        skill_tags=[],
        deliverable=None,
        week_label=None,
    )
    db.add(row)
    await db.flush()
    return row


async def delete_task(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
    task_no: int,
) -> None:
    """Task を削除し、後続 task_no と submission を繰り下げる。"""
    course = await _get_course_by_slug(db, course_slug)
    phase = await _get_phase_or_raise(db, course_slug, course.id, phase_no)
    tasks = await _list_phase_tasks_ordered(db, phase.id)
    if len(tasks) <= 1:
        raise CannotDeleteLastTaskError(course_slug, phase_no)

    row = await _get_task_or_raise(
        db, course_slug, phase_no, phase.id, task_no
    )

    sub_count = (
        await db.execute(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.course_id == course.id,
                Submission.phase == phase_no,
                Submission.task_no == task_no,
            )
        )
    ).scalar_one()
    if sub_count > 0:
        raise TaskHasSubmissionsError(course_slug, phase_no, task_no)

    await db.execute(delete(CurriculumTask).where(CurriculumTask.id == row.id))
    await db.flush()

    mapping = {
        t.task_no: t.task_no - 1 for t in tasks if t.task_no > task_no
    }
    await _remap_task_numbers(
        db,
        course_id=course.id,
        phase_no=phase_no,
        mapping=mapping,
    )


async def move_task(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
    task_no: int,
    to_task_no: int,
) -> CurriculumPhase:
    """task_no の行を to_task_no 位置へ並び替える (1-based)。"""
    course = await _get_course_by_slug(db, course_slug)
    phase = await _get_phase_or_raise(db, course_slug, course.id, phase_no)
    tasks = await _list_phase_tasks_ordered(db, phase.id)
    task_nos = {t.task_no for t in tasks}
    if task_no not in task_nos or to_task_no not in task_nos:
        raise InvalidTaskMoveError(course_slug, phase_no, task_no, to_task_no)
    if task_no == to_task_no:
        return phase

    ordered = list(tasks)
    moving_idx = next(i for i, t in enumerate(ordered) if t.task_no == task_no)
    moving = ordered.pop(moving_idx)
    ordered.insert(to_task_no - 1, moving)

    mapping: dict[int, int] = {}
    for t in tasks:
        new_no = next(i + 1 for i, o in enumerate(ordered) if o.id == t.id)
        if t.task_no != new_no:
            mapping[t.task_no] = new_no

    await _remap_task_numbers(
        db,
        course_id=course.id,
        phase_no=phase_no,
        mapping=mapping,
    )
    phase.updated_at = datetime.now(UTC)
    await db.flush()
    return phase


# ---------------------------------------------------------------------------
# Phase structure (Sprint 17 — add / delete within a course)
# ---------------------------------------------------------------------------


async def _list_phases_ordered(
    db: AsyncSession, course_id
) -> list[CurriculumPhase]:
    result = await db.execute(
        select(CurriculumPhase)
        .where(CurriculumPhase.course_id == course_id)
        .order_by(CurriculumPhase.phase_no)
    )
    return list(result.scalars().all())


async def _remap_phase_numbers(
    db: AsyncSession,
    *,
    course_id,
    mapping: dict[int, int],
) -> None:
    """old phase_no -> new phase_no。UNIQUE 制約回避のため一時オフセット経由。"""
    if not mapping:
        return
    changed_old = set(mapping.keys())
    now = datetime.now(UTC)

    phases = (
        await db.execute(
            select(CurriculumPhase).where(
                CurriculumPhase.course_id == course_id,
                CurriculumPhase.phase_no.in_(changed_old),
            )
        )
    ).scalars().all()

    for p in phases:
        p.phase_no = _PHASE_NO_OFFSET + p.phase_no
    await db.flush()

    for table, col in (
        (Submission, Submission.phase),
        (Progress, Progress.phase),
        (ChatHistory, ChatHistory.phase),
    ):
        for old_no in changed_old:
            await db.execute(
                update(table)
                .where(
                    table.course_id == course_id,
                    col == old_no,
                )
                .values({col.key: _PHASE_NO_OFFSET + old_no})
            )
    for old_no in changed_old:
        await db.execute(
            update(Embedding)
            .where(
                Embedding.course_id == course_id,
                Embedding.phase == old_no,
            )
            .values(phase=_PHASE_NO_OFFSET + old_no)
        )
    await db.flush()

    for p in phases:
        orig = p.phase_no - _PHASE_NO_OFFSET
        p.phase_no = mapping[orig]
        p.updated_at = now
    await db.flush()

    for old_no, new_no in mapping.items():
        offset = _PHASE_NO_OFFSET + old_no
        for table, col in (
            (Submission, Submission.phase),
            (Progress, Progress.phase),
            (ChatHistory, ChatHistory.phase),
        ):
            await db.execute(
                update(table)
                .where(
                    table.course_id == course_id,
                    col == offset,
                )
                .values({col.key: new_no})
            )
        await db.execute(
            update(Embedding)
            .where(
                Embedding.course_id == course_id,
                Embedding.phase == offset,
            )
            .values(phase=new_no)
        )
    await db.flush()


async def _backfill_locked_progress_for_phase(
    db: AsyncSession,
    *,
    course_id,
    phase_no: int,
) -> None:
    """新 Phase 追加時、active enrollment に locked progress 行を追加。"""
    user_ids = (
        await db.execute(
            select(Enrollment.user_id).where(
                Enrollment.course_id == course_id,
                Enrollment.status == "active",
            )
        )
    ).scalars().all()
    if not user_ids:
        return

    existing = set(
        (
            await db.execute(
                select(Progress.user_id).where(
                    Progress.course_id == course_id,
                    Progress.phase == phase_no,
                )
            )
        ).scalars().all()
    )
    for user_id in user_ids:
        if user_id in existing:
            continue
        db.add(
            Progress(
                user_id=user_id,
                course_id=course_id,
                phase=phase_no,
                status=ProgressStatus.LOCKED.value,
            )
        )
    await db.flush()


async def add_phase(
    db: AsyncSession,
    *,
    course_slug: str,
) -> CurriculumPhase:
    """Course 末尾に published phase + 1 task を追加する。"""
    course = await _get_course_by_slug(db, course_slug)
    phases = await _list_phases_ordered(db, course.id)
    next_no = (max(p.phase_no for p in phases) if phases else 0) + 1
    now = datetime.now(UTC)
    row = CurriculumPhase(
        course_id=course.id,
        phase_no=next_no,
        title=f"{_DEFAULT_NEW_PHASE_TITLE} {next_no}",
        goal=_DEFAULT_NEW_PHASE_GOAL,
        system_prompt=_DEFAULT_NEW_SYSTEM_PROMPT,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    db.add(
        CurriculumTask(
            phase_id=row.id,
            task_no=1,
            title=_DEFAULT_NEW_TASK_TITLE,
            description=_DEFAULT_NEW_TASK_DESCRIPTION,
            skill_tags=[],
            deliverable=None,
            week_label=None,
            updated_at=now,
        )
    )
    await _backfill_locked_progress_for_phase(
        db, course_id=course.id, phase_no=next_no
    )
    await db.flush()
    return row


async def delete_phase(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
) -> None:
    """Phase を削除し、後続 phase_no と関連行を繰り下げる。"""
    course = await _get_course_by_slug(db, course_slug)
    phases = await _list_phases_ordered(db, course.id)
    if len(phases) <= 1:
        raise CannotDeleteLastPhaseError(course_slug)

    row = await _get_phase_or_raise(db, course_slug, course.id, phase_no)

    sub_count = (
        await db.execute(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.course_id == course.id,
                Submission.phase == phase_no,
            )
        )
    ).scalar_one()
    if sub_count > 0:
        raise PhaseHasSubmissionsError(course_slug, phase_no)

    await db.execute(delete(CurriculumPhase).where(CurriculumPhase.id == row.id))
    await db.flush()

    await db.execute(
        delete(Progress).where(
            Progress.course_id == course.id,
            Progress.phase == phase_no,
        )
    )
    await db.flush()

    mapping = {
        p.phase_no: p.phase_no - 1 for p in phases if p.phase_no > phase_no
    }
    await _remap_phase_numbers(db, course_id=course.id, mapping=mapping)
