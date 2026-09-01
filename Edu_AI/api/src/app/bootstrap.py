"""Application bootstrap for the FastAPI backend."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_router
from app.blog_agent import router as blog_agent_router
from app.chat import router as chat_router
from app.chat.api.routes_v2 import router as chat_v2_router
from app.chat.memory.api import router as agent_memory_router
from app.deepsearch import router as deepsearch_router
from app.pipeline import router as pipeline_router
from app.speech.routes import router as speech_router
from app.video_routes import router as video_router
from core import Config
from core.auth import auth_manager
from app.services.runtime_config_resolver import (
    reset_runtime_config_context,
    runtime_config_resolver,
    set_runtime_config_context,
)


def create_app(
    *,
    durable_runtime_factory: Callable[[], object] | None = None,
    membership_bootstrap_factory: Callable[[], object] | None = None,
) -> FastAPI:
    if durable_runtime_factory is None:
        from app.services.durable_job_runtime import build_durable_job_runtime

        durable_runtime_factory = build_durable_job_runtime
    if membership_bootstrap_factory is None:
        from app.services.course_membership_bootstrap import (
            get_course_membership_bootstrap,
        )

        membership_bootstrap_factory = get_course_membership_bootstrap

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app.persistence.retirement import validate_retired_legacy_storage
        from app.services.course_service import ensure_default_courses

        validate_retired_legacy_storage()
        ensure_default_courses()
        membership_bootstrap = membership_bootstrap_factory()
        membership_bootstrap.sync_existing()
        app.state.course_membership_bootstrap = membership_bootstrap
        runtime = durable_runtime_factory()
        runtime.start()
        app.state.durable_job_runtime = runtime
        try:
            yield
        finally:
            runtime.stop(grace_seconds=10)

    app = FastAPI(
        title=Config.APP_NAME,
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def bind_runtime_configuration(request, call_next):
        """Freeze the authenticated user's provider revisions for this request."""
        authorization = request.headers.get("authorization", "")
        tokens = None
        if authorization.lower().startswith("bearer "):
            try:
                current_user = auth_manager.get_current_user(authorization[7:].strip())
                owner = str(current_user.get("username") or "").strip()
                if owner:
                    tokens = set_runtime_config_context(
                        owner_user_id=owner,
                        snapshot=runtime_config_resolver.capture_snapshot(owner),
                    )
            except Exception:
                # Authentication dependencies still own the actual 401 response.
                tokens = None
        try:
            return await call_next(request)
        finally:
            if tokens is not None:
                reset_runtime_config_context(tokens)

    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(chat_v2_router)
    app.include_router(agent_memory_router)
    app.include_router(speech_router)
    app.include_router(video_router)
    app.include_router(pipeline_router, prefix="/api/pipeline")
    app.include_router(blog_agent_router, prefix="/api/blog")
    app.include_router(deepsearch_router)

    # lazy imports to avoid circular import via app/api/__init__.py
    from app.api.courses import router as courses_router
    from app.api.learning import router as learning_router
    from app.api.standard_resources import router as standard_resources_router
    from app.api.resource_learning import router as resource_learning_router
    from app.api.classroom_catalog import router as classroom_catalog_router
    from app.api.assessment import router as assessment_router
    from app.api.personal_knowledge import router as personal_knowledge_router
    from app.api.health import router as health_router
    from app.api.jobs import router as jobs_router
    from app.api.runtime_config import router as runtime_config_router
    from app.api.teacher import router as teacher_router
    from app.api.chat_legacy import router as chat_legacy_router
    from app.api.classroom_qa import router as classroom_qa_router
    from app.api.searched_images import router as searched_images_router
    from modules.rag_v2.api import router as rag_router

    app.include_router(courses_router)
    app.include_router(learning_router)
    app.include_router(standard_resources_router)
    app.include_router(resource_learning_router)
    app.include_router(classroom_catalog_router)
    app.include_router(assessment_router)
    app.include_router(personal_knowledge_router)
    app.include_router(health_router)
    app.include_router(jobs_router)
    app.include_router(runtime_config_router)
    app.include_router(teacher_router)
    app.include_router(chat_legacy_router)
    app.include_router(classroom_qa_router)
    app.include_router(searched_images_router)
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
