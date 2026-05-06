"""Application bootstrap for the FastAPI backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_router
from app.blog_agent import router as blog_agent_router
from app.chat import router as chat_router
from app.chat.api.routes_v2 import router as chat_v2_router
from app.deepsearch import router as deepsearch_router
from app.dependencies import get_ai_lecturer_process_manager
from app.exceptions import log_bootstrap_exception
from app.pipeline import router as pipeline_router
from app.speech.routes import router as speech_router
from app.video_routes import router as video_router
from core import Config


def _startup_ai_lecturer_bridge() -> None:
    try:
        get_ai_lecturer_process_manager().ensure_started()
    except Exception as exc:  # pragma: no cover - defensive logging only
        log_bootstrap_exception("AI Lecturer startup", exc)


def _shutdown_ai_lecturer_bridge() -> None:
    try:
        get_ai_lecturer_process_manager().shutdown()
    except Exception as exc:  # pragma: no cover - defensive logging only
        log_bootstrap_exception("AI Lecturer shutdown", exc)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _startup_ai_lecturer_bridge()
    try:
        yield
    finally:
        _shutdown_ai_lecturer_bridge()


def create_app() -> FastAPI:
    app = FastAPI(title=Config.APP_NAME, version="1.0.0", lifespan=_lifespan)

    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(chat_v2_router)
    app.include_router(speech_router)
    app.include_router(video_router)
    app.include_router(pipeline_router, prefix="/api/pipeline")
    app.include_router(blog_agent_router, prefix="/api/blog")
    app.include_router(deepsearch_router)

    # lazy imports to avoid circular import via app/api/__init__.py
    from app.api.courses import router as courses_router
    from app.api.health import router as health_router
    from app.api.teacher import router as teacher_router
    from app.api.chat_legacy import router as chat_legacy_router
    from rag_v2.api import router as rag_router

    app.include_router(courses_router)
    app.include_router(health_router)
    app.include_router(teacher_router)
    app.include_router(chat_legacy_router)
    app.include_router(rag_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.ALLOW_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()
