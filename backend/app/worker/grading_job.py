"""arq job: grade a persisted submission by id."""

from __future__ import annotations

import logging
import uuid

from app.core.claude_client import get_claude_client
from app.db.session import SessionLocal
from app.services.submission_grading import grade_submission_by_id

logger = logging.getLogger(__name__)


async def run_grading_job(_ctx: dict, submission_id: str) -> None:
    """arq entrypoint — loads submission and runs Claude grading."""
    sid = uuid.UUID(submission_id)
    claude = get_claude_client()
    async with SessionLocal() as db:
        row = await grade_submission_by_id(db, claude, sid)
        if row is None:
            logger.warning("grading job: submission %s not found", submission_id)
            return
        await db.commit()
