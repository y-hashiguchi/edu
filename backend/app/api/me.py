"""`/api/me/...` endpoints — learner-facing actions that read or mutate
the caller's own resources (Sprint 4 onward).

Separated from `/api/submissions/...` and `/api/auth/me` so the BOLA
boundary is structural: every route in this module ends up filtering
the response by `current_user.id`. New `/api/me/...` endpoints should
preserve that invariant.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.comment import LearnerCommentOut
from app.services import comment as comment_service

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get(
    "/submissions/{submission_id}/comments",
    response_model=list[LearnerCommentOut],
)
async def list_my_submission_comments(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LearnerCommentOut]:
    try:
        rows = await comment_service.list_for_owner(
            db, submission_id=submission_id, owner_user_id=user.id
        )
    except comment_service.SubmissionNotFoundError as e:
        # Uniform 404 for both 'submission missing' and 'submission belongs
        # to someone else'. Distinguishing them would leak BOLA signal.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="submission not found"
        ) from e
    return [
        LearnerCommentOut(
            id=c.id,
            author_name=author.name,
            body=c.body,
            created_at=c.created_at,
        )
        for c, author in rows
    ]
