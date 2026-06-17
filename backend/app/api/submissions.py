"""Submissions API: multipart upload, regrade, listing with history."""

import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.claude_client import ClaudeClient, get_claude_client
from app.core.course_deps import CourseContext, get_course_context
from app.core.deps import get_current_user
from app.core.file_storage import (
    FileStorageError,
    FileTooLargeError,
    InvalidExtensionError,
    MimeMismatchError,
    PathTraversalError,
    read_file_bytes,
    stored_filename,
)
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.grading_attempt import GradingAttempt
from app.models.submission import Submission
from app.models.submission_file import SubmissionFile
from app.models.user import User
from app.schemas.grading import GradingAttemptOut
from app.schemas.submission import SubmissionFileOut, SubmissionOut
from app.services import file_storage_service
from app.services.progress import is_phase_unlocked
from app.services.submission import (
    RegradeCooldownError,
    SubmissionNotFoundError,
    SubmissionPhaseInvalidError,
    SubmissionTaskInvalidError,
    list_grading_history,
    list_user_submissions,
    regrade_submission,
    regrade_submission_async,
    upsert_and_enqueue,
    upsert_and_grade,
)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def _to_out(
    row,
    files: list[SubmissionFile],
    history: list[GradingAttempt],
) -> SubmissionOut:
    return SubmissionOut(
        id=row.id,
        phase=row.phase,
        task_no=row.task_no,
        content=row.content,
        ai_feedback=row.ai_feedback,
        score=row.score,
        submitted_at=row.submitted_at,
        graded_at=row.graded_at,
        files=[SubmissionFileOut.from_row(f) for f in files],
        grading_history=[GradingAttemptOut.model_validate(a) for a in history],
    )


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.submission_rate_limit)
async def create_submission(
    request: Request,  # required for the slowapi limiter decorator
    phase: int = Form(..., ge=1, le=4),
    # Sprint 7: per-course task_no upper bound is enforced in the
    # service layer (ai-era-se has 8 tasks; ai-driven-dev has up to 5).
    task_no: int = Form(..., ge=1),
    content: str = Form(..., min_length=1, max_length=10_000),
    files: list[UploadFile] = File(default_factory=list),
    current_user: User = Depends(get_current_user),
    ctx: CourseContext = Depends(get_course_context),
    claude: ClaudeClient = Depends(get_claude_client),
    db: AsyncSession = Depends(get_db),
) -> SubmissionOut:
    if not await is_phase_unlocked(db, current_user.id, phase, course_id=ctx.course.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"phase {phase} is locked",
        )

    uploads: list[tuple[str, bytes]] = []
    for uf in files:
        data = await uf.read()
        uploads.append((uf.filename or "file", data))

    try:
        if settings.grading_async_enabled:
            row = await upsert_and_enqueue(
                db=db,
                user_id=current_user.id,
                course_id=ctx.course.id,
                course_slug=ctx.course.slug,
                phase=phase,
                task_no=task_no,
                content=content,
                uploads=uploads,
            )
        else:
            row = await upsert_and_grade(
                db=db,
                claude=claude,
                user_id=current_user.id,
                course_id=ctx.course.id,
                course_slug=ctx.course.slug,
                phase=phase,
                task_no=task_no,
                content=content,
                uploads=uploads,
            )
    except SubmissionPhaseInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"phase {e.args[0]} not found",
        ) from e
    except SubmissionTaskInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"task {e.args[0]} not found",
        ) from e
    except file_storage_service.TooManyFilesError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"too many files: {e}",
        ) from e
    except InvalidExtensionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported file extension: {e}",
        ) from e
    except FileTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"file too large: {e}",
        ) from e
    except MimeMismatchError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"content type mismatch: {e}",
        ) from e
    except FileStorageError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"storage error: {e}",
        ) from e

    files_rows = await file_storage_service.list_submission_files(db=db, submission_id=row.id)
    history = await list_grading_history(db, row.id)
    return _to_out(row, files_rows, history)


@router.post(
    "/{submission_id}/regrade",
    response_model=GradingAttemptOut,
    status_code=status.HTTP_200_OK,
)
async def regrade(
    submission_id: uuid.UUID = Path(...),
    current_user: User = Depends(get_current_user),
    ctx: CourseContext = Depends(get_course_context),
    claude: ClaudeClient = Depends(get_claude_client),
    db: AsyncSession = Depends(get_db),
) -> GradingAttemptOut:
    """Sprint 3 baseline + Sprint 8 follow-up: regrade an existing submission.

    Sync mode (``GRADING_ASYNC_ENABLED=false``) returns the freshly written
    GradingAttempt with status ``graded``/``failed``.

    Async mode queues the work on the arq worker and returns a synthetic
    PENDING attempt (not persisted) so the client can pivot to polling
    ``GET /api/me/submissions/{id}`` until ``graded_at`` is set."""
    try:
        if settings.grading_async_enabled:
            await regrade_submission_async(
                db=db,
                user_id=current_user.id,
                course_slug=ctx.course.slug,
                submission_id=submission_id,
            )
            # Synthetic PENDING attempt — never persisted (DB CHECK
            # constraint forbids it). The client uses this only to
            # learn that polling should begin.
            from datetime import UTC, datetime

            return GradingAttemptOut(
                id=uuid.uuid4(),
                status="pending",  # type: ignore[arg-type]
                score=None,
                feedback=None,
                error_message=None,
                model_name="(pending)",
                created_at=datetime.now(UTC),
            )

        attempt = await regrade_submission(
            db=db,
            claude=claude,
            user_id=current_user.id,
            course_slug=ctx.course.slug,
            submission_id=submission_id,
        )
    except SubmissionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="submission not found",
        ) from e
    except RegradeCooldownError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"cooldown active; retry in {e.retry_after_seconds}s",
            headers={"Retry-After": str(e.retry_after_seconds)},
        ) from e

    return GradingAttemptOut.model_validate(attempt)


@router.get("/{submission_id}/files/{file_id}")
async def download_file(
    submission_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    ctx: CourseContext = Depends(get_course_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    # NOTE: ctx is injected for ?course= enrollment check. The file lookup
    # is keyed by submission_id (which already pins one course), so we do
    # not need to thread course_id into the query.
    _ = ctx
    submission = (
        await db.execute(
            select(Submission).where(
                Submission.id == submission_id,
                Submission.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="submission not found",
        )

    file_row = (
        await db.execute(
            select(SubmissionFile).where(
                SubmissionFile.id == file_id,
                SubmissionFile.submission_id == submission_id,
            )
        )
    ).scalar_one_or_none()
    if file_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file not found",
        )

    try:
        data = read_file_bytes(file_row.file_path)
    except (FileNotFoundError, PathTraversalError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="file unavailable",
        ) from e

    filename = stored_filename(file_row.file_path)
    return Response(
        content=data,
        media_type=file_row.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{phase}", response_model=list[SubmissionOut])
async def list_my_submissions(
    phase: int = Path(ge=1, le=4),
    current_user: User = Depends(get_current_user),
    ctx: CourseContext = Depends(get_course_context),
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionOut]:
    if not await is_phase_unlocked(db, current_user.id, phase, course_id=ctx.course.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"phase {phase} is locked",
        )
    rows = await list_user_submissions(db, current_user.id, phase)
    # Filter to current course in-route (service still returns all-course rows
    # for backward compat — narrow here):
    rows = [r for r in rows if r.course_id == ctx.course.id]
    out: list[SubmissionOut] = []
    for row in rows:
        files_rows = await file_storage_service.list_submission_files(db=db, submission_id=row.id)
        history = await list_grading_history(db, row.id)
        out.append(_to_out(row, files_rows, history))
    return out
