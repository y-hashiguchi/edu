"""arq cron: deliver due scheduled broadcasts."""

from __future__ import annotations

import logging

from app.config import settings
from app.db.session import SessionLocal
from app.services.scheduled_broadcast import process_due_scheduled_broadcasts

logger = logging.getLogger(__name__)


async def run_scheduled_broadcast_cron(_ctx: dict) -> None:
    """Every-minute cron entrypoint."""
    if not settings.scheduled_broadcast_cron_enabled:
        return
    async with SessionLocal() as db:
        count = await process_due_scheduled_broadcasts(db)
        if count:
            logger.info("scheduled broadcast cron: processed %d row(s)", count)
