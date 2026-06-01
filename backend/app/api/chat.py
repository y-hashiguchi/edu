from fastapi import APIRouter, Depends, HTTPException, status

from app.core.claude_client import ClaudeClient, get_claude_client
from app.data.curriculum import CURRICULUM
from app.memory.chat_store import InMemoryChatStore, get_chat_store
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    claude: ClaudeClient = Depends(get_claude_client),
    store: InMemoryChatStore = Depends(get_chat_store),
) -> ChatResponse:
    if request.phase not in CURRICULUM:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"phase {request.phase} not found",
        )

    history = store.get_history(request.user_id, request.phase)
    next_history = history + [{"role": "user", "content": request.message}]

    reply = claude.complete(
        system_prompt=CURRICULUM[request.phase]["system_prompt"],
        history=next_history,
    )

    store.append(request.user_id, request.phase, "user", request.message)
    store.append(request.user_id, request.phase, "assistant", reply)

    full_history = store.get_history(request.user_id, request.phase)
    return ChatResponse(
        reply=reply,
        history=[ChatMessage(**m) for m in full_history],
    )
