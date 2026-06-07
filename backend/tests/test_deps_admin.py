"""get_current_admin dependency tests."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.deps import get_current_admin


@pytest.mark.asyncio
async def test_get_current_admin_returns_admin_user():
    """An admin is passed through untouched."""
    fake = MagicMock()
    fake.is_admin = True
    result = await get_current_admin(user=fake)
    assert result is fake


@pytest.mark.asyncio
async def test_get_current_admin_rejects_non_admin():
    """A non-admin user surfaces 403 with a deliberate error string —
    routing code and reverse proxies key off the status code, ops people
    key off the message when triaging logs."""
    fake = MagicMock()
    fake.is_admin = False
    with pytest.raises(HTTPException) as exc:
        await get_current_admin(user=fake)
    assert exc.value.status_code == 403
    assert "admin" in exc.value.detail.lower()
