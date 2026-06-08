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
from app.data.curriculum import (
    get_task_skill_tags, get_task_title, iter_all_phase_task_pairs,
)
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
    top_weakness_tags: list[str],
) -> list[Recommendation]:
    if not top_weakness_tags:
        return []

    submitted = await _user_submitted_phase_task_pairs(db, user_id)
    unsubmitted_keys: set[tuple[int, int]] = {
        (p, t) for p, t in iter_all_phase_task_pairs() if (p, t) not in submitted
    }
    if not unsubmitted_keys:
        return []

    primary = top_weakness_tags[0]
    hits: list[CurriculumTaskHit] = await search_curriculum_tasks(
        db, client, query=f"{primary} を扱うタスク", limit=8,
    )

    seen: set[tuple[int, int]] = set()
    out: list[Recommendation] = []
    for hit in hits:
        key = (hit.phase, hit.task_no)
        if key not in unsubmitted_keys or key in seen:
            continue
        seen.add(key)
        try:
            tags = get_task_skill_tags(hit.phase, hit.task_no)
            title = get_task_title(hit.phase, hit.task_no)
        except KeyError:
            continue  # legacy embeddings beyond current curriculum
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
    db: AsyncSession, user_id: uuid.UUID,
) -> set[tuple[int, int]]:
    stmt = select(Submission.phase, Submission.task_no).where(
        Submission.user_id == user_id,
    )
    rows = (await db.execute(stmt)).all()
    return {(r[0], r[1]) for r in rows}
