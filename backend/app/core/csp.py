"""Content-Security-Policy middleware (MED-5).

The API itself does not render HTML, so a restrictive policy
(`default-src 'none'`) is safe and acts as a tripwire: any accidental
future HTML response would be sandboxed by the browser instead of
executing arbitrary script.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CSPMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, policy: str) -> None:
        super().__init__(app)
        self._policy = policy

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # setdefault so a future route that needs a relaxed policy can set
        # its own header without colliding with this default.
        response.headers.setdefault("Content-Security-Policy", self._policy)
        return response
