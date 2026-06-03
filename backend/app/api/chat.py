from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.core.claude_client import ClaudeClient, get_claude_client
from app.core.deps import get_current_user
from app.core.embedding_client import EmbeddingClient, get_embedding_client
from app.data.curriculum import CURRICULUM
from app.memory.chat_store import SqlChatStore, get_chat_store
from app.models.user import User
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse
from app.services import embedding as embedding_service
from app.services.progress import is_phase_unlocked
from app.services.rag import format_context, search_context

router = APIRouter(prefix="/api", tags=["chat"])


async def _ensure_phase_accessible(
    user: User, phase: int, store: SqlChatStore
) -> None:
    if phase not in CURRICULUM:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"phase {phase} not found"
        )
    unlocked = await is_phase_unlocked(store.db, user.id, phase)
    if not unlocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"phase {phase} is locked"
        )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    claude: ClaudeClient = Depends(get_claude_client),
    store: SqlChatStore = Depends(get_chat_store),
    embedder: EmbeddingClient = Depends(get_embedding_client),
) -> ChatResponse:
    await _ensure_phase_accessible(current_user, request.phase, store)

    history = await store.get_history(current_user.id, request.phase)
    next_history = history + [{"role": "user", "content": request.message}]

    # RAG: retrieve top-K relevant context
    hits = await search_context(
        store.db,
        embedder,
        user_id=current_user.id,
        phase=request.phase,
        query=request.message,
        top_k=4,
    )
    system_prompt = CURRICULUM[request.phase]["system_prompt"]
    context_block = format_context(hits)
    if context_block:
        system_prompt = system_prompt + "\n\n" + context_block

    try:
        reply = await claude.complete(system_prompt=system_prompt, history=next_history)
    except Exception as e:  # noqa: BLE001  upstream SDK error -> 502
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="upstream LLM error"
        ) from e

    await store.append(current_user.id, request.phase, "user", request.message)
    await store.append(current_user.id, request.phase, "assistant", reply)

    # Embed this round of conversation for future RAG hits
    now_iso = datetime.now(UTC).isoformat()
    try:
        await embedding_service.upsert_embeddings(
            store.db,
            embedder,
            user_id=current_user.id,
            items=[
                (
                    "chat_message",
                    f"user:{current_user.id}:phase:{request.phase}:{now_iso}:u",
                    request.phase,
                    request.message,
                ),
                (
                    "chat_message",
                    f"user:{current_user.id}:phase:{request.phase}:{now_iso}:a",
                    request.phase,
                    reply,
                ),
            ],
        )
    except Exception:  # noqa: BLE001  RAG embedding is best-effort
        pass

    await store.db.commit()

    full_history = await store.get_history(current_user.id, request.phase)
    return ChatResponse(
        reply=reply, history=[ChatMessage(**m) for m in full_history]
    )


@router.get("/chat/history/{phase}", response_model=list[ChatMessage])
async def get_chat_history(
    phase: int = Path(ge=1, le=4),
    current_user: User = Depends(get_current_user),
    store: SqlChatStore = Depends(get_chat_store),
) -> list[ChatMessage]:
    await _ensure_phase_accessible(current_user, phase, store)
    history = await store.get_history(current_user.id, phase)
    return [ChatMessage(**m) for m in history]
