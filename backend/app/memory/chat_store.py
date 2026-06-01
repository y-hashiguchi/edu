"""Sprint 0 用のプロセス内会話履歴ストア。Sprint 1 でDB実装に差し替える。"""

from threading import Lock


class InMemoryChatStore:
    """Sprint 0 in-process chat history store.

    Thread-safety: individual operations (get_history, append, clear) are
    protected by a lock, but the get-then-append sequence used by the chat
    route is NOT atomic. Concurrent requests for the same (user_id, phase)
    may interleave appends. Acceptable for single-tenant Sprint 0; before
    multi-user production use, swap to a transactional store or add per-key
    locking in the route.
    """

    def __init__(self) -> None:
        self._data: dict[tuple[str, int], list[dict[str, str]]] = {}
        self._lock = Lock()

    def get_history(self, user_id: str, phase: int) -> list[dict[str, str]]:
        with self._lock:
            return list(self._data.get((user_id, phase), []))

    def append(self, user_id: str, phase: int, role: str, content: str) -> None:
        with self._lock:
            self._data.setdefault((user_id, phase), []).append(
                {"role": role, "content": content}
            )

    def clear(self, user_id: str, phase: int) -> None:
        with self._lock:
            self._data.pop((user_id, phase), None)


_store_singleton = InMemoryChatStore()


def get_chat_store() -> InMemoryChatStore:
    return _store_singleton
