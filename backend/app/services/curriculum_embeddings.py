"""Seed curriculum task embeddings from the runtime cache (Sprint 18).

Replaces the legacy ``COURSE_REGISTRY``-only path in ``scripts/seed_embeddings.py``
so dynamically added courses and phases get RAG coverage without a manual script run.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding_client import EmbeddingClient
from app.data.courses import CourseNotFoundError, get_course, runtime
from app.data.curriculum import CURRICULUM
from app.models.course import Course
from app.models.embedding import Embedding
from app.services.embedding import upsert_embeddings

logger = logging.getLogger(__name__)

_CURRICULUM_SOURCE_TYPES = ("curriculum_task", "curriculum_skill")


def task_embedding_source_ref(course_slug: str, phase_no: int, task_index: int) -> str:
    return f"course:{course_slug}:phase:{phase_no}:task:{task_index}"


def build_embedding_items(course_slug: str) -> list[tuple[str, str, int | None, str]]:
    """Return (source_type, source_ref, phase, content) tuples for one course."""
    course_data = get_course(course_slug)
    items: list[tuple[str, str, int | None, str]] = []

    if course_slug == "ai-driven-dev":
        for phase_no, phase in CURRICULUM.items():
            for i, skill in enumerate(phase["skills"]):
                items.append(
                    (
                        "curriculum_skill",
                        f"course:{course_slug}:phase:{phase_no}:skill:{i}",
                        phase_no,
                        skill,
                    )
                )

    for phase in course_data.phases:
        for i, task in enumerate(phase.tasks):
            items.append(
                (
                    "curriculum_task",
                    task_embedding_source_ref(course_slug, phase.phase, i),
                    phase.phase,
                    task.title,
                )
            )
    return items


async def seed_course_embeddings_refs(
    db: AsyncSession,
    course_slug: str,
    source_refs: list[str],
    *,
    client: EmbeddingClient | None = None,
) -> int:
    """Re-embed only the given source_ref rows (publish diff path)."""
    if not source_refs:
        return 0
    ref_set = set(source_refs)
    if client is None:
        client = EmbeddingClient()
    course_row = (
        await db.execute(select(Course).where(Course.slug == course_slug))
    ).scalar_one_or_none()
    if course_row is None:
        return 0
    try:
        items = build_embedding_items(course_slug)
    except CourseNotFoundError:
        await runtime.reload_course(db, course_slug)
        items = build_embedding_items(course_slug)
    filtered = [it for it in items if it[1] in ref_set]
    if not filtered:
        return 0
    await upsert_embeddings(
        db,
        client,
        user_id=None,
        course_id=course_row.id,
        items=filtered,
    )
    return len(filtered)


async def seed_course_embeddings(
    db: AsyncSession,
    course_slug: str,
    *,
    client: EmbeddingClient | None = None,
) -> int:
    """Embed curriculum content for one course. Returns row count (0 if cache miss)."""
    if client is None:
        client = EmbeddingClient()
    course_row = (
        await db.execute(select(Course).where(Course.slug == course_slug))
    ).scalar_one_or_none()
    if course_row is None:
        return 0
    try:
        items = build_embedding_items(course_slug)
    except CourseNotFoundError:
        await runtime.reload_course(db, course_slug)
        items = build_embedding_items(course_slug)
    if not items:
        return 0
    await upsert_embeddings(
        db,
        client,
        user_id=None,
        course_id=course_row.id,
        items=items,
    )
    return len(items)


async def prune_orphan_course_embeddings(
    db: AsyncSession,
    course_slug: str,
) -> int:
    """Remove curriculum_task/skill rows whose source_ref no longer exists."""
    course_row = (
        await db.execute(select(Course).where(Course.slug == course_slug))
    ).scalar_one_or_none()
    if course_row is None:
        return 0
    try:
        items = build_embedding_items(course_slug)
    except CourseNotFoundError:
        await runtime.reload_course(db, course_slug)
        items = build_embedding_items(course_slug)
    valid_refs = {it[1] for it in items if it[0] in _CURRICULUM_SOURCE_TYPES}
    stmt = delete(Embedding).where(
        Embedding.course_id == course_row.id,
        Embedding.source_type.in_(_CURRICULUM_SOURCE_TYPES),
    )
    if valid_refs:
        stmt = stmt.where(Embedding.source_ref.notin_(valid_refs))
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount or 0


async def seed_all_course_embeddings(
    db: AsyncSession,
    *,
    client: EmbeddingClient | None = None,
) -> int:
    """Reload cache from DB and seed embeddings for every course."""
    await runtime.reload_from_db(db)
    courses = list((await db.execute(select(Course))).scalars().all())
    total = 0
    for course in courses:
        total += await seed_course_embeddings(db, course.slug, client=client)
    return total
