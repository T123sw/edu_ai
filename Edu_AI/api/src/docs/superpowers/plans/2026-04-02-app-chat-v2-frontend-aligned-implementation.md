# app/chat v2 Frontend-Aligned Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `v2` chat API with two frontend-aligned entry points, `reply` and `report`, without continuing to evolve the old `/api/chat` compatibility chain.

**Architecture:** Add a dedicated `v2` API surface that shares the existing fast chat runtime, context builder, persistence adapter, and report workflow runtime. `reply` remains the default entry and can switch into the report workflow; `report` enters the report workflow directly and builds the report engine without going through legacy `ChatService`.

**Tech Stack:** FastAPI, Pydantic, existing `app.chat` orchestrator/runtime modules, pytest

---

## File Structure

### New files

- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
  Purpose: expose `/api/chat/v2/reply` and `/api/chat/v2/report`
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
  Purpose: define `v2` request/response/error schemas
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
  Purpose: normalize reply requests, dispatch through orchestrator, persist writeback
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
  Purpose: direct report entry, direct report engine wiring, persist writeback
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/response_builder_v2.py`
  Purpose: format stable `v2` success and error payloads
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`
  Purpose: schema contract tests
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`
  Purpose: HTTP route tests
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`
  Purpose: reply service tests
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_report_service_v2.py`
  Purpose: report service tests

### Modified files

- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/workflows/report/runtime.py`
  Purpose: accept direct engine dependency cleanly and expose stable `v2` workflow response
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/orchestrator/route_rules.py`
  Purpose: tighten `reply -> report` switching semantics for `v2`
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py`
  Purpose: support the writeback calls needed by new services
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/routes.py`
  Purpose: optionally mount/import `v2` router without affecting old routes
- `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/tools/agent_tools.py`
  Purpose: expose a filtered tool registry by capability policy

---

### Task 1: Add v2 Schemas And Error Contract

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
- Test: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`

- [ ] **Step 1: Write the failing schema tests**

```python
from pydantic import ValidationError

from app.chat.api.schemas_v2 import (
    ChatReplyRequestV2,
    ChatReportRequestV2,
    ChatResponseV2,
    ChatErrorResponseV2,
)


def test_reply_request_defaults_disable_capabilities():
    payload = ChatReplyRequestV2(question="hello")
    assert payload.allow_rag is False
    assert payload.allow_web is False
    assert payload.selected_doc_ids == []


def test_report_request_allows_nullable_report_config():
    payload = ChatReportRequestV2(question="生成报告", report_config=None)
    assert payload.report_config is None


def test_chat_response_v2_requires_message_action_and_trace():
    payload = ChatResponseV2(
        message={"role": "assistant", "content": "ok"},
        conversation={"conversation_id": "conv-1"},
        action={"name": "chat.reply"},
        artifacts=[],
        sources=[],
        trace={"path": "fast"},
    )
    assert payload.trace["path"] == "fast"


def test_error_response_v2_requires_error_code_and_message():
    payload = ChatErrorResponseV2(
        error={"code": "invalid_request", "message": "bad", "retryable": False},
        conversation={"conversation_id": "conv-1"},
        trace={"path": "fast"},
    )
    assert payload.error["code"] == "invalid_request"


def test_trace_path_rejects_unknown_value():
    try:
        ChatResponseV2(
            message={"role": "assistant", "content": "ok"},
            conversation={"conversation_id": "conv-1"},
            action={"name": "chat.reply"},
            artifacts=[],
            sources=[],
            trace={"path": "unknown"},
        )
    except ValidationError as exc:
        assert "trace" in str(exc)
    else:
        raise AssertionError("expected ValidationError")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/chat/test_schemas_v2.py -q -p no:cacheprovider
```

Expected: FAIL because `schemas_v2.py` does not exist yet.

- [ ] **Step 3: Write minimal schema implementation**

```python
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


TracePath = Literal["fast", "workflow"]
WorkflowStatus = Literal["running", "awaiting_confirm", "completed", "interrupted", "failed"]


class ChatReplyRequestV2(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    course_id: Optional[str] = None
    artifact_id: Optional[str] = None
    allow_rag: bool = False
    allow_web: bool = False
    selected_doc_ids: List[str] = Field(default_factory=list)
    action_hint: Optional[str] = None


class ChatReportRequestV2(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    model_id: Optional[str] = None
    course_id: Optional[str] = None
    allow_rag: bool = False
    allow_web: bool = False
    selected_doc_ids: List[str] = Field(default_factory=list)
    report_config: Optional[Dict[str, Any]] = None


class ChatResponseV2(BaseModel):
    message: Dict[str, Any]
    conversation: Dict[str, Any]
    action: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    workflow: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    trace: Dict[str, TracePath]


class ChatErrorResponseV2(BaseModel):
    error: Dict[str, Any]
    conversation: Dict[str, Any]
    trace: Dict[str, TracePath]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/chat/test_schemas_v2.py -q -p no:cacheprovider
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/chat/api/schemas_v2.py tests/chat/test_schemas_v2.py
git commit -m "feat: add chat v2 schema contracts"
```

---

### Task 2: Add Shared v2 Response Builder

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/response_builder_v2.py`
- Test: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`

- [ ] **Step 1: Write the failing response-builder tests**

```python
from app.chat.application.response_builder_v2 import (
    build_v2_success_response,
    build_v2_error_response,
)


def test_build_v2_success_response_returns_stable_shape():
    payload = build_v2_success_response(
        message="ok",
        conversation_id="conv-1",
        action_name="chat.reply",
        trace_path="fast",
    )
    assert payload["message"]["content"] == "ok"
    assert payload["conversation"]["conversation_id"] == "conv-1"
    assert payload["action"]["name"] == "chat.reply"
    assert payload["trace"]["path"] == "fast"


def test_build_v2_error_response_returns_error_shape():
    payload = build_v2_error_response(
        code="capability_denied",
        message="forbidden",
        conversation_id="conv-1",
        trace_path="workflow",
        retryable=False,
    )
    assert payload["error"]["code"] == "capability_denied"
    assert payload["trace"]["path"] == "workflow"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/chat/test_schemas_v2.py -q -p no:cacheprovider
```

Expected: FAIL with import error for `response_builder_v2`.

- [ ] **Step 3: Write minimal response builder implementation**

```python
from __future__ import annotations


def build_v2_success_response(
    *,
    message: str,
    conversation_id: str,
    action_name: str,
    trace_path: str,
    workflow=None,
    artifacts=None,
    sources=None,
    trace=None,
):
    merged_trace = {"path": trace_path, **(trace or {})}
    return {
        "message": {"role": "assistant", "content": message},
        "conversation": {"conversation_id": conversation_id},
        "action": {"name": action_name},
        "workflow": workflow,
        "artifacts": artifacts or [],
        "sources": sources or [],
        "trace": merged_trace,
    }


def build_v2_error_response(*, code: str, message: str, conversation_id: str, trace_path: str, retryable: bool):
    return {
        "error": {"code": code, "message": message, "retryable": retryable},
        "conversation": {"conversation_id": conversation_id},
        "trace": {"path": trace_path},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/chat/test_schemas_v2.py -q -p no:cacheprovider
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/chat/application/response_builder_v2.py tests/chat/test_schemas_v2.py
git commit -m "feat: add chat v2 response builder"
```

---

### Task 3: Build Reply Service v2

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/orchestrator/route_rules.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py`
- Test: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`

- [ ] **Step 1: Write the failing reply service tests**

```python
from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2


class DummyOrchestrator:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def dispatch(self, request):
        self.calls.append(request)
        return self.result


class DummyStore:
    def __init__(self):
        self.saved = []

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, request.question, result["action"]["name"]))


def test_reply_service_returns_orchestrator_result_and_writes_back():
    orchestrator = DummyOrchestrator(
        {
            "message": {"role": "assistant", "content": "ok"},
            "conversation": {"conversation_id": "conv-1"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        }
    )
    store = DummyStore()
    service = ReplyServiceV2(orchestrator=orchestrator, conversation_store=store)
    payload = SimpleNamespace(
        question="hello",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "chat.reply"
    assert store.saved == [("conv-1", "hello", "chat.reply")]


def test_reply_service_preserves_report_switch_result():
    orchestrator = DummyOrchestrator(
        {
            "message": {"role": "assistant", "content": "report"},
            "conversation": {"conversation_id": "conv-1"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "running"},
            "artifacts": [],
            "sources": [],
            "trace": {"path": "workflow", "workflow_name": "report"},
        }
    )
    store = DummyStore()
    service = ReplyServiceV2(orchestrator=orchestrator, conversation_store=store)
    payload = SimpleNamespace(
        question="整理成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
    )

    result = service.reply(payload)

    assert result["workflow"]["type"] == "report"
    assert store.saved == [("conv-1", "整理成报告", "generate.report")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/chat/test_reply_service_v2.py -q -p no:cacheprovider
```

Expected: FAIL because `reply_service_v2.py` does not exist.

- [ ] **Step 3: Extend conversation adapter with a dedicated v2 writeback**

```python
def write_v2_result(self, conversation_id: str, request, result: dict):
    self.storage.ensure_conversation(conversation_id, request.question)
    self.append_message(conversation_id, "user", request.question)
    answer = str(((result.get("message") or {}).get("content")) or "").strip()
    if answer:
        self.append_message(conversation_id, "assistant", answer, sources=result.get("sources") or None)

    state_patch = {}
    action_name = str(((result.get("action") or {}).get("name")) or "").strip()
    if action_name:
        state_patch["active_task"] = action_name

    workflow = result.get("workflow") or None
    if workflow:
        state_patch["workflow_state"] = {
            "workflow_id": conversation_id,
            "workflow_type": workflow.get("type") or "",
            "status": workflow.get("status") or "running",
            "stage": workflow.get("phase") or workflow.get("stage") or "",
            "artifacts": result.get("artifacts") or [],
        }

    artifacts = result.get("artifacts") or []
    if artifacts:
        first = artifacts[0]
        state_patch["active_artifact"] = {
            "artifact_id": first.get("artifact_id") or "",
            "artifact_type": first.get("artifact_type") or "",
            "title": first.get("title"),
        }

    if state_patch:
        self.storage.update_state(conversation_id, state_patch)
```

- [ ] **Step 4: Write minimal reply service implementation**

```python
from __future__ import annotations

from app.chat.application.request_normalizer import normalize_chat_request


class ReplyServiceV2:
    def __init__(self, *, orchestrator, conversation_store):
        self.orchestrator = orchestrator
        self.conversation_store = conversation_store

    def reply(self, payload):
        request = normalize_chat_request(payload)
        result = self.orchestrator.dispatch(request)
        conversation_id = str(((result.get("conversation") or {}).get("conversation_id")) or request.conversation_id or "")
        if conversation_id:
            self.conversation_store.write_v2_result(conversation_id, request, result)
        return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/chat/test_reply_service_v2.py -q -p no:cacheprovider
```

Expected: PASS

- [ ] **Step 6: Tighten reply-to-report route coverage**

Add a test in `tests/chat/test_reply_service_v2.py` or `tests/chat/test_route_rules.py`:

```python
def test_reply_route_switches_to_report_for_report_keywords(snapshot_factory, request_factory):
    decision = decide_route(
        request=request_factory(question="帮我整理成报告", action_hint=None),
        snapshot=snapshot_factory(),
        workflow_state=None,
    )
    assert decision.path == "workflow"
    assert decision.workflow_name == "report"
```

- [ ] **Step 7: Run focused route tests**

Run:

```bash
python -m pytest tests/chat/test_reply_service_v2.py tests/chat/test_route_rules.py -q -p no:cacheprovider
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app/chat/application/reply_service_v2.py app/chat/orchestrator/route_rules.py app/chat/persistence/conversation_store_adapter.py tests/chat/test_reply_service_v2.py tests/chat/test_route_rules.py
git commit -m "feat: add chat reply v2 service"
```

---

### Task 4: Build Report Service v2 With Direct Engine Wiring

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/workflows/report/runtime.py`
- Test: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_report_service_v2.py`

- [ ] **Step 1: Write the failing report service tests**

```python
from types import SimpleNamespace

from app.chat.application.report_service_v2 import ReportServiceV2


class DummyRuntime:
    def __init__(self):
        self.calls = []

    def run(self, *, request, snapshot, decision):
        self.calls.append((request.question, decision.workflow_name))
        return {
            "message": {"role": "assistant", "content": "report"},
            "conversation": {"conversation_id": request.conversation_id or "conv-1"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "running"},
            "artifacts": [],
            "sources": [],
            "trace": {"path": "workflow", "workflow_name": "report"},
        }


class DummyBuilder:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def build(self, request):
        return self.snapshot


class DummyStore:
    def __init__(self):
        self.saved = []

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, result["action"]["name"]))


def test_report_service_calls_runtime_directly_and_writes_back():
    runtime = DummyRuntime()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    service = ReportServiceV2(
        context_builder=DummyBuilder(snapshot),
        report_runtime=runtime,
        conversation_store=DummyStore(),
    )
    payload = SimpleNamespace(
        question="生成报告",
        conversation_id="conv-1",
        model_id=None,
        course_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        report_config=None,
        owner="u1",
    )

    result = service.report(payload)

    assert runtime.calls == [("生成报告", "report")]
    assert result["action"]["name"] == "generate.report"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/chat/test_report_service_v2.py -q -p no:cacheprovider
```

Expected: FAIL because `report_service_v2.py` does not exist.

- [ ] **Step 3: Write minimal report service implementation**

```python
from __future__ import annotations

from types import SimpleNamespace

from app.chat.application.request_normalizer import normalize_chat_request


class ReportServiceV2:
    def __init__(self, *, context_builder, report_runtime, conversation_store):
        self.context_builder = context_builder
        self.report_runtime = report_runtime
        self.conversation_store = conversation_store

    def report(self, payload):
        request = normalize_chat_request(payload)
        snapshot = self.context_builder.build(request)
        decision = SimpleNamespace(path="workflow", action="generate.report", workflow_name="report")
        result = self.report_runtime.run(request=request, snapshot=snapshot, decision=decision)
        conversation_id = str(((result.get("conversation") or {}).get("conversation_id")) or request.conversation_id or "")
        if conversation_id:
            self.conversation_store.write_v2_result(conversation_id, request, result)
        return result
```

- [ ] **Step 4: Update report runtime to preserve direct engine usage**

```python
class ReportWorkflowRuntime:
    def __init__(self, *, engine=None, engine_factory=None):
        self._engine = engine
        self._engine_factory = engine_factory

    @property
    def engine(self):
        if self._engine is None and self._engine_factory is not None:
            self._engine = self._engine_factory()
        return self._engine
```

Keep `run()` returning a stable `generate.report` result. Do not reintroduce dependency on legacy `ChatService.get_report_engine()`.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/chat/test_report_service_v2.py -q -p no:cacheprovider
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/chat/application/report_service_v2.py app/chat/workflows/report/runtime.py tests/chat/test_report_service_v2.py
git commit -m "feat: add chat report v2 service"
```

---

### Task 5: Add Capability-Gated Tool Registry

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/tools/agent_tools.py`
- Test: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_report_service_v2.py`

- [ ] **Step 1: Write the failing tool-filter tests**

```python
from app.chat.tools.agent_tools import get_tool_registry_for_capability


def test_tool_registry_excludes_external_tools_when_not_allowed():
    registry = get_tool_registry_for_capability(allow_rag=False, allow_web=False)
    assert "rag_search_tool" not in registry
    assert "web_search_tool" not in registry
    assert "generate_long_report_content" in registry


def test_tool_registry_includes_authorized_external_tools():
    registry = get_tool_registry_for_capability(allow_rag=True, allow_web=False)
    assert "rag_search_tool" in registry
    assert "web_search_tool" not in registry
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/chat/test_report_service_v2.py -q -p no:cacheprovider
```

Expected: FAIL because `get_tool_registry_for_capability` does not exist.

- [ ] **Step 3: Implement minimal capability filter**

```python
def get_tool_registry_for_capability(*, allow_rag: bool, allow_web: bool) -> ToolRegistry:
    registry = get_default_tool_registry()
    filtered = dict(registry)
    if not allow_rag:
        filtered.pop("rag_search_tool", None)
    if not allow_web:
        filtered.pop("web_search_tool", None)
    return filtered
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/chat/test_report_service_v2.py -q -p no:cacheprovider
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/chat/tools/agent_tools.py tests/chat/test_report_service_v2.py
git commit -m "feat: add capability gated tool registry"
```

---

### Task 6: Expose v2 Routes

**Files:**
- Create: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/routes.py`
- Test: `D:/Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py`

- [ ] **Step 1: Write the failing route tests**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.chat.api.routes_v2 import router as v2_router


def test_reply_v2_route_returns_v2_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)

    class DummyService:
        def reply(self, payload):
            return {
                "message": {"role": "assistant", "content": "ok"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/reply", json={"question": "hello"})
    assert response.status_code == 200
    assert response.json()["action"]["name"] == "chat.reply"


def test_report_v2_route_returns_v2_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)

    class DummyService:
        def report(self, payload):
            return {
                "message": {"role": "assistant", "content": "report"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "generate.report"},
                "workflow": {"type": "report", "status": "running"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "report"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_report_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/report", json={"question": "生成报告"})
    assert response.status_code == 200
    assert response.json()["action"]["name"] == "generate.report"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/chat/test_routes_v2.py -q -p no:cacheprovider
```

Expected: FAIL because `routes_v2.py` does not exist.

- [ ] **Step 3: Implement the v2 routes**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.chat.api.schemas_v2 import ChatReplyRequestV2, ChatReportRequestV2, ChatResponseV2

router = APIRouter(prefix="/api/chat/v2", tags=["chat-v2"])


def _get_reply_service():
    from app.chat.application.reply_service_v2 import build_default_reply_service_v2
    return build_default_reply_service_v2()


def _get_report_service():
    from app.chat.application.report_service_v2 import build_default_report_service_v2
    return build_default_report_service_v2()
```

Add two route handlers:

- `POST /reply`
- `POST /report`

Each route should attach `owner=current_user["username"]` to the incoming payload before delegating.

- [ ] **Step 4: Mount or expose the router**

In `app/chat/routes.py`, expose the `v2` router in a way that preserves old routes but allows the app to include the new endpoints.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/chat/test_routes_v2.py -q -p no:cacheprovider
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/chat/api/routes_v2.py app/chat/routes.py tests/chat/test_routes_v2.py
git commit -m "feat: add chat v2 routes"
```

---

### Task 7: Wire Default Builders And Direct Report Engine Construction

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
- Test: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`
- Test: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_report_service_v2.py`

- [ ] **Step 1: Write the failing builder tests**

```python
def test_build_default_reply_service_v2_returns_service():
    service = build_default_reply_service_v2()
    assert service is not None


def test_build_default_report_service_v2_builds_runtime_without_legacy_chat_service(monkeypatch):
    seen = {}

    def fake_build_engine():
        seen["built"] = True
        class DummyEngine:
            def invoke(self, state):
                return {"reply": "ok", "status": "running"}
        return DummyEngine()

    monkeypatch.setattr("app.chat.application.report_service_v2.build_default_report_engine", fake_build_engine)
    service = build_default_report_service_v2()
    assert service is not None
    assert seen["built"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/chat/test_reply_service_v2.py tests/chat/test_report_service_v2.py -q -p no:cacheprovider
```

Expected: FAIL because builder helpers do not exist yet.

- [ ] **Step 3: Add default builder helpers**

Implement in `reply_service_v2.py`:

```python
def build_default_reply_service_v2():
    gateway = build_default_gateway(None)
    fast_runtime = FastChatRuntime(model_gateway=gateway)
    orchestrator = MainOrchestrator(
        fast_runtime=fast_runtime,
        workflow_registry={"report": ReportWorkflowRuntime(engine_factory=build_default_report_engine)},
        context_builder=ContextBuilder(conversation_store=ConversationStoreAdapter()),
    )
    return ReplyServiceV2(orchestrator=orchestrator, conversation_store=ConversationStoreAdapter())
```

Implement in `report_service_v2.py`:

```python
def build_default_report_engine():
    planner_llm = get_fallback_llm()
    analyzer_llm = planner_llm
    extractor_llm = planner_llm
    skill_manager = SkillManager()
    return build_universal_report_graph(
        planner_llm=planner_llm,
        analyzer_llm=analyzer_llm,
        extractor_llm=extractor_llm,
        extractor_prompt_template=skill_manager.extract_section("edu-report-agent", "EXTRACTOR_SYSTEM_PROMPT"),
        planner_skill_prompt="",
        analyzer_skill_prompt="",
        tool_registry=get_tool_registry_for_capability(allow_rag=False, allow_web=False),
    )


def build_default_report_service_v2():
    runtime = ReportWorkflowRuntime(engine=build_default_report_engine())
    return ReportServiceV2(
        context_builder=ContextBuilder(conversation_store=ConversationStoreAdapter()),
        report_runtime=runtime,
        conversation_store=ConversationStoreAdapter(),
    )
```

Keep this builder focused on construction only. Do not move workflow logic into the service.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/chat/test_reply_service_v2.py tests/chat/test_report_service_v2.py -q -p no:cacheprovider
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/chat/application/reply_service_v2.py app/chat/application/report_service_v2.py tests/chat/test_reply_service_v2.py tests/chat/test_report_service_v2.py
git commit -m "feat: wire chat v2 service builders"
```

---

### Task 8: Full Regression And Legacy Freeze Validation

**Files:**
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`
- Modify: `D:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_report_service_v2.py`

- [ ] **Step 1: Add final regression tests covering the agreed boundaries**

```python
def test_reply_v2_does_not_require_legacy_answer_shape():
    service = ReplyServiceV2(
        orchestrator=DummyOrchestrator(
            {
                "message": {"role": "assistant", "content": "ok"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }
        ),
        conversation_store=DummyStore(),
    )
    result = service.reply(
        SimpleNamespace(
            question="hello",
            conversation_id="conv-1",
            model_id=None,
            course_id=None,
            artifact_id=None,
            allow_rag=False,
            allow_web=False,
            selected_doc_ids=[],
            action_hint=None,
            owner="u1",
        )
    )
    assert "answer" not in result
    assert result["action"]["name"] == "chat.reply"


def test_report_v2_returns_generate_report_action():
    result = ReportServiceV2(
        context_builder=DummyBuilder(SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])),
        report_runtime=DummyRuntime(),
        conversation_store=DummyStore(),
    ).report(
        SimpleNamespace(
            question="生成报告",
            conversation_id="conv-1",
            model_id=None,
            course_id=None,
            allow_rag=False,
            allow_web=False,
            selected_doc_ids=[],
            report_config=None,
            owner="u1",
        )
    )
    assert result["action"]["name"] == "generate.report"


def test_reply_v2_switches_to_report_when_report_intent_detected():
    decision = decide_route(
        request=SimpleNamespace(question="根据以上内容整理成报告", action_hint=None),
        snapshot=SimpleNamespace(active_artifact=None),
        workflow_state=None,
    )
    assert decision.path == "workflow"
    assert decision.workflow_name == "report"


def test_report_v2_preserves_report_config_in_trace_when_present():
    payload = build_v2_success_response(
        message="report",
        conversation_id="conv-1",
        action_name="generate.report",
        trace_path="workflow",
        trace={"workflow_name": "report", "input": {"report_config": {"topic": "课堂观察"}}},
    )
    assert payload["trace"]["input"]["report_config"]["topic"] == "课堂观察"


def test_capability_policy_disables_rag_and_web_by_default():
    request = ChatReplyRequestV2(question="hello")
    assert request.allow_rag is False
    assert request.allow_web is False
```

- [ ] **Step 2: Run focused v2 tests**

Run:

```bash
python -m pytest tests/chat/test_schemas_v2.py tests/chat/test_reply_service_v2.py tests/chat/test_report_service_v2.py tests/chat/test_routes_v2.py -q -p no:cacheprovider
```

Expected: PASS

- [ ] **Step 3: Run full chat regression**

Run:

```bash
python -m pytest tests/chat -q -p no:cacheprovider
```

Expected: PASS with no new failures relative to the current baseline.

- [ ] **Step 4: Record freeze status for old endpoints**

Manually verify:

- old `app/chat/routes.py` still exposes legacy routes
- new `app/chat/api/routes_v2.py` exposes `reply/report`
- no new code path depends on legacy `CompatChatService` for `v2`

- [ ] **Step 5: Commit**

```bash
git add tests/chat/test_schemas_v2.py tests/chat/test_reply_service_v2.py tests/chat/test_report_service_v2.py tests/chat/test_routes_v2.py
git commit -m "test: add chat v2 regression coverage"
```

---

## Self-Review

### Spec coverage

- `reply` and `report` new entry points: covered by Tasks 1, 3, 4, 6
- stable `v2` schema and error model: covered by Tasks 1 and 2
- `reply -> report` switching: covered by Tasks 3 and 8
- direct report engine wiring: covered by Tasks 4 and 7
- capability-gated `rag/web` tools: covered by Task 5
- persistence writeback semantics: covered by Task 3
- frontend-facing route integration: covered by Task 6

No spec gaps remain for the first implementation phase.

### Placeholder scan

- No `TODO`
- No `TBD`
- No “similar to”
- Each task has explicit files, tests, commands, and code targets

### Type consistency

- `ChatResponseV2` is the single `v2` response contract
- `ReplyServiceV2.reply()` and `ReportServiceV2.report()` both return `ChatResponseV2`-shaped dicts
- `ConversationStoreAdapter.write_v2_result()` is the shared writeback entry for both services
