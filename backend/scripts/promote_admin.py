"""Promote (or demote) a user to admin by email.

Usage:
    uv run python -m scripts.promote_admin <email>

Exit codes:
    0 — user is now admin (newly promoted or was already)
    1 — user not found
    2 — bad CLI arguments

This is the operations-grade path until the admin UI gains a "promote"
action of its own. Intentionally minimal: takes one email, mutates one
flag, commits.
"""

import asyncio
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User


def _mask_email(email: str) -> str:
    """MED-2 (sprint-4 security follow-up): mask the local part before
    emitting an email to stdout/stderr. CloudWatch/Datadog and similar
    log sinks have a wider read-audience than the DB, so we keep the
    domain (for ops to triage which tenant/cohort is affected) but drop
    everything past the first two chars of the local part."""
    local, sep, domain = email.partition("@")
    if not sep:
        return "***"
    return f"{local[:2]}***@{domain}"


async def promote(email: str) -> int:
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        masked = _mask_email(email)
        if user is None:
            print(f"user not found: {masked}", file=sys.stderr)
            return 1
        if user.is_admin:
            print(f"already admin: {masked}")
            return 0
        user.is_admin = True
        await session.commit()
        print(f"promoted: {masked}")
        return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(
            "usage: python -m scripts.promote_admin <email>", file=sys.stderr
        )
        return 2
    return asyncio.run(promote(args[0]))


if __name__ == "__main__":
    sys.exit(main())
