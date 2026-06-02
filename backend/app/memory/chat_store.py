"""SQL-backed chat history store (Sprint 1)."""

import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.chat_history import ChatHistory


class SqlChatStore:
    """Async chat history store backed by `chat_history` table."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @property
    def db(self) -> AsyncSession:
        """Expose the bound session (chat route owns transaction commits)."""
        return self._db

    async def get_history(
        self, user_id: uuid.UUID, phase: int
    ) -> list[dict[str, str]]:
        result = await self._db.execute(
            select(ChatHistory)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.phase == phase,
            )
            .order_by(ChatHistory.created_at)
        )
        return [{"role": m.role, "content": m.content} for m in result.scalars().all()]

    async def append(
        self, user_id: uuid.UUID, phase: int, role: str, content: str
    ) -> None:
        self._db.add(
            ChatHistory(user_id=user_id, phase=phase, role=role, content=content)
        )
        await self._db.flush()


async def get_chat_store(db: AsyncSession = Depends(get_db)) -> SqlChatStore:
    return SqlChatStore(db)
