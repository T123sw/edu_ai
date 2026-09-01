# 后端架构重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `backend/src` 后端重构为分层清晰、职责明确、接口尽量兼容的单体架构。

**Architecture:** 先瘦身 `app/main.py`，再把请求/响应模型、业务编排、领域规则和外部适配拆到独立层。路由层保留现有对外 API，service 层承接业务流程，domain 层只保留纯数据与规则，integrations 层封装 RAG、LLM、视频、语音和外部进程。`legacy` 只接短期兼容逻辑，`scripts/` 只保留开发验证工具。

**Tech Stack:** FastAPI, Pydantic, pytest, existing storage modules, existing RAG/LLM integrations.

---

### Task 1: Thin the application entrypoint

**Files:**
- Create: `backend/src/app/bootstrap.py`
- Create: `backend/src/app/dependencies.py`
- Create: `backend/src/app/exceptions.py`
- Create: `backend/src/app/api/__init__.py`
- Modify: `backend/src/app/main.py`
- Test: `backend/src/tests/app/test_bootstrap.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from app.bootstrap import create_app

def test_app_imports_and_health_route_exist():
    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/chat" in paths

def test_app_responds_to_health():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run the test to confirm current entrypoint is too coupled**

Run: `python -m pytest backend/src/tests/app/test_bootstrap.py -q`

Expected: fail or import error until `main.py` becomes a stable import surface.

- [ ] **Step 3: Implement the thin bootstrap layer**

`backend/src/app/bootstrap.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import Config
from app.auth import router as auth_router
from app.courses import router as courses_router
from app.pipeline.routes import router as pipeline_router
from app.video_routes import router as video_router
from app.speech.routes import router as speech_router
from app.deepsearch import router as deepsearch_router
from app.blog_agent import router as blog_router
from app.chat import router as chat_router
from app.chat.api.routes_v2 import router as chat_v2_router
from rag_v2.api import router as rag_router
from app.teaching_video_bridge import get_ai_lecturer_process_manager

def create_app() -> FastAPI:
    Config.ensure_directories()
    app = FastAPI(title=Config.APP_NAME, version="1.0.0")
    app.include_router(auth_router)
    app.include_router(courses_router)
    app.include_router(rag_router)
    app.include_router(chat_router)
    app.include_router(chat_v2_router)
    app.include_router(speech_router)
    app.include_router(video_router)
    app.include_router(pipeline_router, prefix="/api/pipeline")
    app.include_router(blog_router, prefix="/api/blog")
    app.include_router(deepsearch_router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=Config.ALLOW_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup_ai_lecturer_bridge() -> None:
        get_ai_lecturer_process_manager().ensure_started()

    @app.on_event("shutdown")
    def _shutdown_ai_lecturer_bridge() -> None:
        get_ai_lecturer_process_manager().shutdown()

    return app
```

`backend/src/app/main.py`
```python
from app.bootstrap import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 4: Run the test again**

Run: `python -m pytest backend/src/tests/app/test_bootstrap.py -q`

Expected: pass.

- [ ] **Step 5: Keep the import surface stable**

Run: `python -m compileall backend/src/app`

Expected: no syntax errors.

### Task 2: Extract request/response schemas out of `main.py` and auth routes

**Files:**
- Create: `backend/src/app/schemas/common.py`
- Create: `backend/src/app/schemas/auth.py`
- Create: `backend/src/app/schemas/chat.py`
- Create: `backend/src/app/schemas/lesson_plan.py`
- Create: `backend/src/app/schemas/report.py`
- Create: `backend/src/app/schemas/quiz.py`
- Create: `backend/src/app/schemas/question.py`
- Modify: `backend/src/app/main.py`
- Modify: `backend/src/app/auth.py`
- Test: `backend/src/tests/app/test_schema_imports.py`

- [ ] **Step 1: Write the failing test**

```python
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.chat import ChatRequest, ChatResponse

def test_schema_modules_import_cleanly():
    assert LoginRequest.model_fields["username"].is_required()
    assert "answer" in ChatResponse.model_fields
```

- [ ] **Step 2: Run the test to confirm schemas are still embedded**

Run: `python -m pytest backend/src/tests/app/test_schema_imports.py -q`

Expected: fail until schema classes move out of `main.py` and `auth.py`.

- [ ] **Step 3: Move the models into schema modules**

`backend/src/app/schemas/auth.py`
```python
from typing import Optional
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    username: str = Field(...)
    password: str = Field(...)

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: Optional[str] = Field(default="student")

class LoginResponse(BaseModel):
    token: str
    user: dict

class UserInfoResponse(BaseModel):
    username: str
    role: str
```

`backend/src/app/schemas/chat.py`
```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    question: str = Field(...)
    conversation_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)
    model_id: Optional[str] = None
    use_rag: Optional[bool] = True
    selected_doc_ids: Optional[List[str]] = None

class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: List[Dict[str, Any]]
    title: Optional[str] = None
    model_id: Optional[str] = None
```

Move the remaining lesson plan, report, quiz, question, and health models the same way.

- [ ] **Step 4: Wire the routes to the new imports**

Update `app/auth.py` and `app/main.py` so they import models from `app.schemas.*` only.

- [ ] **Step 5: Run the import test and compile**

Run:
`python -m pytest backend/src/tests/app/test_schema_imports.py -q`
`python -m compileall backend/src/app`

Expected: both pass.

### Task 3: Split chat orchestration into service, domain, and integration layers

**Files:**
- Create: `backend/src/app/services/chat_service.py`
- Create: `backend/src/app/domain/chat_models.py`
- Create: `backend/src/app/integrations/rag_client.py`
- Create: `backend/src/app/integrations/llm_client.py`
- Create: `backend/src/app/api/chat.py`
- Modify: `backend/src/app/main.py`
- Modify: `backend/src/app/chat/api/routes_v2.py`
- Modify: `backend/src/app/chat/__init__.py`
- Test: `backend/src/tests/app/test_chat_service.py`

- [ ] **Step 1: Write the failing service test**

```python
def test_chat_service_assembles_history_and_calls_rag():
    from app.services.chat_service import ChatService

    service = ChatService()
    result = service.chat(question="What is recursion?", conversation_id=None, top_k=3)
    assert "answer" in result
    assert "conversation_id" in result
```

- [ ] **Step 2: Run the test to confirm service does not exist yet**

Run: `python -m pytest backend/src/tests/app/test_chat_service.py -q`

Expected: fail with import or attribute errors.

- [ ] **Step 3: Implement the chat service boundary**

`backend/src/app/services/chat_service.py`
```python
from datetime import datetime
from core.config import Config
from core.conversation_storage import conversation_storage
from app.integrations.rag_client import RagClient

class ChatService:
    def __init__(self, rag_client: RagClient | None = None):
        self.rag_client = rag_client or RagClient()

    def chat(self, question: str, conversation_id: str | None, top_k: int, model_id: str | None, use_rag: bool, selected_doc_ids: list[str] | None, owner: str | None) -> dict:
        conversation_id = conversation_id or f"conv_{datetime.now().timestamp()}"
        conversation_storage.ensure_conversation(conversation_id, question)
        history = conversation_storage.get_messages(conversation_id, limit=Config.CHAT_HISTORY_WINDOW * 2)
        model_config = Config.get_llm_model(model_id or Config.DEFAULT_LLM_MODEL_ID)
        result = self.rag_client.query(
            question=question,
            top_k=top_k,
            conversation_history=history,
            llm_config=model_config,
            use_rag=use_rag,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
        )
        return {
            "answer": result.get("answer", ""),
            "conversation_id": conversation_id,
            "sources": result.get("sources", []),
            "title": conversation_storage.get_conversation(conversation_id).get("title"),
            "model_id": model_config.get("id"),
        }
```

Keep `app/api/chat.py` thin: dependency inject `get_current_user`, call `ChatService.chat`, map to `ChatResponse`.

- [ ] **Step 4: Add a legacy compatibility wrapper only if needed**

If any internal module still imports the old chat entry, point it to the new service instead of duplicating logic.

- [ ] **Step 5: Run the chat test and a focused import scan**

Run:
`python -m pytest backend/src/tests/app/test_chat_service.py -q`
`rg -n "def chat\\(|def generate_lesson_plan\\(|def generate_questions\\(" backend/src/app/main.py`

Expected: test passes and `main.py` no longer holds chat business logic.

### Task 4: Move lesson plan, report, quiz, question, course, pipeline, video, speech, and deepsearch logic behind services

**Files:**
- Create: `backend/src/app/services/lesson_plan_service.py`
- Create: `backend/src/app/services/report_service.py`
- Create: `backend/src/app/services/quiz_service.py`
- Create: `backend/src/app/services/question_service.py`
- Create: `backend/src/app/services/course_service.py`
- Create: `backend/src/app/services/pipeline_service.py`
- Create: `backend/src/app/services/video_service.py`
- Create: `backend/src/app/services/speech_service.py`
- Create: `backend/src/app/services/deepsearch_service.py`
- Create: `backend/src/app/integrations/lecturer_manager.py`
- Modify: `backend/src/app/main.py`
- Modify: `backend/src/app/courses.py`
- Modify: `backend/src/app/pipeline/routes.py`
- Modify: `backend/src/app/video_routes.py`
- Modify: `backend/src/app/speech/routes.py`
- Modify: `backend/src/app/deepsearch.py`
- Test: `backend/src/tests/app/test_service_boundaries.py`

- [ ] **Step 1: Write the failing boundary test**

```python
def test_main_has_no_business_functions():
    from app import main
    assert not hasattr(main, "generate_lesson_plan")
    assert not hasattr(main, "generate_questions")
    assert not hasattr(main, "chat")
```

- [ ] **Step 2: Run the boundary test**

Run: `python -m pytest backend/src/tests/app/test_service_boundaries.py -q`

Expected: fail until the business functions are removed from `main.py`.

- [ ] **Step 3: Implement the service modules and route thin wrappers**

Move the following logic into services:

1. lesson plan prompt assembly and selected document loading.
2. report prompt assembly and section formatting.
3. quiz generation, JSON cleanup, and question normalization.
4. question generation and answer shape normalization.
5. course resource aggregation.
6. pipeline task orchestration.
7. video upload/search/job status orchestration.
8. speech upload/transcribe orchestration.
9. deepsearch query or import orchestration.
10. AI Lecturer process startup/shutdown into `integrations/lecturer_manager.py`.

Each route file should keep only the request/response mapping and `HTTPException` translation.

- [ ] **Step 4: Run the boundary test and a focused endpoint smoke test**

Run:
`python -m pytest backend/src/tests/app/test_service_boundaries.py -q`
`python -m compileall backend/src/app`

Expected: boundary test passes, compile passes.

### Task 5: Isolate legacy code and test/probe scripts from the mainline

**Files:**
- Create: `backend/src/app/legacy/route_compat.py`
- Create: `backend/src/app/legacy/old_handlers/__init__.py`
- Modify: `backend/src/app/chat/legacy/legacy_chat_runtime.py`
- Modify: `backend/src/app/chat/legacy/compat_service.py`
- Modify: `backend/src/scripts/check_report_skill_wiring.py`
- Modify: `backend/src/scripts/phase_a_smoke_test.py`
- Modify: `backend/src/scripts/test_report_service.py`
- Modify: `backend/src/scripts/test_stream_chat.py`
- Test: `backend/src/tests/app/test_legacy_boundary.py`

- [ ] **Step 1: Write the failing boundary test**

```python
def test_mainline_does_not_import_legacy_modules():
    import pathlib
    main_text = pathlib.Path("backend/src/app/main.py").read_text(encoding="utf-8")
    assert "legacy" not in main_text.lower()
```

- [ ] **Step 2: Run the boundary test**

Run: `python -m pytest backend/src/tests/app/test_legacy_boundary.py -q`

Expected: fail until legacy references are removed from the mainline entrypoints.

- [ ] **Step 3: Move uncertain code into legacy wrappers**

Keep old behavior available behind `app/legacy/*`, but stop importing it from the mainline unless a compatibility path absolutely needs it.

- [ ] **Step 4: Reclassify scripts as devtools**

Leave `scripts/` runnable for developer validation, but make sure nothing in `app/` imports from there.

- [ ] **Step 5: Run the boundary test and import scan**

Run:
`python -m pytest backend/src/tests/app/test_legacy_boundary.py -q`
`rg "scripts\\.|from scripts|import scripts" backend/src/app`

Expected: boundary test passes and `app/` has no imports from `scripts/`.

### Task 6: Verify, clean up, and document the new structure

**Files:**
- Modify: `backend/src/README.md`
- Modify: `backend/src/STRUCTURE.md`
- Modify: `backend/src/docs/REFACTORING_SUMMARY.md`
- Test: `backend/src/tests/app/test_import_surface.py`

- [ ] **Step 1: Write the final import-surface test**

```python
def test_app_package_import_surface_is_small():
    import app.main
    import app.bootstrap
    import app.schemas.chat
    import app.services.chat_service
    assert app.main.app is not None
```

- [ ] **Step 2: Run the full backend verification set**

Run:
`python -m pytest backend/src/tests -q`
`python -m compileall backend/src`

Expected: pass, or fail only in clearly unrelated legacy pockets that are explicitly out of scope for this phase.

- [ ] **Step 3: Update structure docs**

Document the new `app/api`, `app/services`, `app/domain`, `app/integrations`, `app/legacy`, and `core` boundaries so the repo matches the code.

- [ ] **Step 4: Final import scan**

Run:
`rg -n "from app\\.main import|from .*legacy|import .*scripts" backend/src`

Expected: no new mainline imports from legacy or scripts.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app backend/src/tests backend/src/README.md backend/src/STRUCTURE.md backend/src/docs/REFACTORING_SUMMARY.md
git commit -m "refactor: clarify backend architecture"
```
