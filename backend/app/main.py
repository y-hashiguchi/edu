from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, curriculum, health, progress
from app.api import chat as chat_router
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="AI Tutor Curriculum API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(curriculum.router)
    app.include_router(progress.router)
    app.include_router(chat_router.router)
    return app


app = create_app()
