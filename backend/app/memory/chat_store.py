"""Sprint 0 用のプロセス内会話履歴ストア（async 版）。Task 8 で SqlChatStore に置換。"""

from asyncio import Lock


class InMemoryChatStore:
    """In-process async chat history store (transitional)."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, int], list[dict[str, str]]] = {}
        self._lock = Lock()

    async def get_history(self, user_id: str, phase: int) -> list[dict[str, str]]:
        async with self._lock:
            return list(self._data.get((user_id, phase), []))

    async def append(self, user_id: str, phase: int, role: str, content: str) -> None:
        async with self._lock:
            self._data.setdefault((user_id, phase), []).append(
                {"role": role, "content": content}
            )

    async def clear(self, user_id: str, phase: int) -> None:
        async with self._lock:
            self._data.pop((user_id, phase), None)


_store_singleton = InMemoryChatStore()


def get_chat_store() -> InMemoryChatStore:
    return _store_singleton
