"""RAG search + context formatter."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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
