"""RAG search + context formatter."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.embedding_client import EmbeddingClient
from app.models.embedding import Embedding


@dataclass(frozen=True)
class RagHit:
    source_type: str
    content: str
    score: float


async def search_context(
    db: AsyncSession,
    client: EmbeddingClient,
    *,
    user_id: uuid.UUID,
    phase: int,
    query: str,
    top_k: int = 4,
) -> list[RagHit]:
    """Embed the query and return top-K closest rows.

    Filter:
      - row is either global (user_id IS NULL) or owned by the caller
      - phase matches the caller's current phase OR is NULL
    """
    if not query.strip():
        return []
    # MED-1 (sprint-5 follow-up): cap before embedding to bound the
    # asyncio.to_thread call duration.
    query = query[: settings.embed_query_max_chars]
    vectors = await client.embed([query])
    qvec = vectors[0]

    stmt = (
        select(
            Embedding.source_type,
            Embedding.content,
            Embedding.embedding.cosine_distance(qvec).label("distance"),
        )
        .where(
            or_(Embedding.user_id.is_(None), Embedding.user_id == user_id),
            or_(Embedding.phase == phase, Embedding.phase.is_(None)),
        )
        .order_by("distance")
        .limit(top_k)
    )
    rows = (await db.execute(stmt)).all()
    return [
        RagHit(source_type=r.source_type, content=r.content, score=1.0 - float(r.distance))
        for r in rows
    ]


def format_context(hits: list[RagHit]) -> str:
    if not hits:
        return ""
    lines = ["以下はこの受講者の学習履歴・カリキュラム内容からの参考情報です:", ""]
    for i, h in enumerate(hits, 1):
        label = {
            "curriculum_skill": "カリキュラム(スキル)",
            "curriculum_task": "カリキュラム(課題)",
            "chat_message": "過去のやり取り",
            "submission": "本人の提出物",
        }.get(h.source_type, h.source_type)
        lines.append(f"[{i}] ({label}, 類似度={h.score:.2f}) {h.content}")
    lines.append("")
    lines.append("関連がある場合のみ参考にし、無関係な情報は無視してください。")
    return "\n".join(lines)


@dataclass(frozen=True)
class CurriculumTaskHit:
    """Phase/task coordinates parsed out of `Embedding.source_ref` plus the
    cosine similarity score. The recommendation service uses (phase,
    task_no) to filter against the learner's submission history; the
    content text is not surfaced to callers — they reconstruct titles
    via `curriculum.get_task_title`."""

    phase: int
    task_no: int  # 1-indexed (matches submissions.task_no)
    score: float


async def search_curriculum_tasks(
    db: AsyncSession,
    client: EmbeddingClient,
    *,
    query: str,
    limit: int = 8,
) -> list[CurriculumTaskHit]:
    """Vector search restricted to `source_type='curriculum_task'`.

    Differs from `search_context` in three ways:
      - No phase filter (Sprint 5 recommendation crosses phases).
      - No user_id filter (curriculum embeddings are global).
      - Returns (phase, task_no) coordinates instead of free text.
    """
    if not query.strip():
        return []
    # MED-1 (sprint-5 follow-up): same query cap as `search_context`;
    # symmetric defense in case curriculum becomes admin-editable and
    # learner-facing flows feed user input here.
    query = query[: settings.embed_query_max_chars]
    vectors = await client.embed([query])
    qvec = vectors[0]

    stmt = (
        select(
            Embedding.source_ref,
            Embedding.embedding.cosine_distance(qvec).label("distance"),
        )
        .where(Embedding.source_type == "curriculum_task")
        .order_by("distance")
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    out: list[CurriculumTaskHit] = []
    for r in rows:
        # Expected shape: "phase:{p}:task:{i}" with i 0-indexed.
        # Anything else is legacy data we silently drop — the
        # alternative (raising) would bubble through the recommendation
        # service and replace a dashboard section with a 500.
        try:
            tag, p_str, _, i_str = r.source_ref.split(":")
            if tag != "phase":
                continue
            phase = int(p_str)
            task_no = int(i_str) + 1
        except (ValueError, AttributeError):
            continue
        out.append(
            CurriculumTaskHit(
                phase=phase, task_no=task_no, score=1.0 - float(r.distance),
            )
        )
    return out
