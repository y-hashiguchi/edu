from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/version")
def version() -> dict[str, str]:
    """Expose the running revision so deploys are verifiable from outside.

    Values come from Render's per-deploy ``RENDER_GIT_*`` env vars and fall
    back to ``"unknown"`` locally / in CI where they are absent.
    """
    return {
        "commit": settings.render_git_commit or "unknown",
        "branch": settings.render_git_branch or "unknown",
    }
