from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import auth, curriculum, health, progress, submissions
from app.api import chat as chat_router
from app.config import settings
from app.core.limiter import limiter


class LimitUploadSize(BaseHTTPMiddleware):
    """Reject requests whose declared body exceeds the configured limit.

    Without this guard Starlette will buffer the full multipart body (spooling
    to a tempfile after a memory threshold) before any per-file size check in
    application code runs, allowing an attacker to OOM the worker with a
    single oversized POST.
    """

    def __init__(self, app, max_body_bytes: int) -> None:
        super().__init__(app)
        self._max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    declared = int(content_length)
                except ValueError:
                    return JSONResponse(
                        {"detail": "invalid content-length header"},
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                if declared > self._max_body_bytes:
                    return JSONResponse(
                        {"detail": "request body too large"},
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
        return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(title="AI Tutor Curriculum API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        LimitUploadSize,
        max_body_bytes=settings.max_request_body_bytes,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(curriculum.router)
    app.include_router(progress.router)
    app.include_router(submissions.router)
    app.include_router(chat_router.router)
    return app


app = create_app()
