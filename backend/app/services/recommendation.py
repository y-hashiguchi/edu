"""Sprint 5 recommendation service.

Couples "what hasn't this learner tried yet" with "what looks like
their weakness" via the curriculum-task RAG helper. Returns at most
3 hits; fewer is OK and signals to the UI to show a softer CTA.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding_client import EmbeddingClient
from app.data.courses import get_course
from app.models.submission import Submission
from app.services.rag import CurriculumTaskHit, search_curriculum_tasks


@dataclass(frozen=True)
class Recommendation:
    phase: int
    task_no: int
    title: str
    skill_tags: list[str]
    match_tag: str | None
    rag_score: float


async def compute_recommendations(
    db: AsyncSession,
    client: EmbeddingClient,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_slug: str,
    top_weakness_tags: list[str],
) -> list[Recommendation]:
    if not top_weakness_tags:
        return []

    submitted = await _user_submitted_phase_task_pairs(db, user_id, course_id)
    course = get_course(course_slug)
    course_task_lookup: dict[tuple[int, int], tuple[str, list[str]]] = {
        (p.phase, t.task_no): (t.title, list(t.skill_tags))
        for p in course.phases
        for t in p.tasks
    }
    unsubmitted_keys: set[tuple[int, int]] = {
        key for key in course_task_lookup if key not in submitted
    }
    if not unsubmitted_keys:
        return []

    primary = top_weakness_tags[0]
    # Sprint 7 MED-2: filter Embedding rows by course at the SQL layer
    # so cross-course rows can't even reach the candidate list. The
    # course_task_lookup gate below still defends against legacy
    # source_ref formats.
    hits: list[CurriculumTaskHit] = await search_curriculum_tasks(
        db, client, query=f"{primary} を扱うタスク", limit=8, course_id=course_id,
    )

    seen: set[tuple[int, int]] = set()
    out: list[Recommendation] = []
    for hit in hits:
        key = (hit.phase, hit.task_no)
        if key not in unsubmitted_keys or key in seen:
            continue
        seen.add(key)
        lookup = course_task_lookup.get(key)
        if lookup is None:
            continue  # legacy embeddings beyond current course
        title, tags = lookup
        out.append(Recommendation(
            phase=hit.phase, task_no=hit.task_no, title=title,
            skill_tags=tags,
            match_tag=primary if primary in tags else None,
            rag_score=hit.score,
        ))
        if len(out) == 3:
            break
    return out


async def _user_submitted_phase_task_pairs(
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> set[tuple[int, int]]:
    stmt = select(Submission.phase, Submission.task_no).where(
        Submission.user_id == user_id,
        Submission.course_id == course_id,
    )
    rows = (await db.execute(stmt)).all()
    return {(r[0], r[1]) for r in rows}
