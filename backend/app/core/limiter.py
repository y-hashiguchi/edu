"""Shared slowapi Limiter instance.

Defined in its own module so route decorators can import it without forcing
the router modules to depend on `app.main` (which imports the routers and
would create a cycle).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
)
