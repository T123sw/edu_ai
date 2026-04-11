# PPT Explicit Workbench Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a direct PPT generation entry in the right-side workbench that uses selected knowledge-base documents plus explicit PPT config to create a draft outline, lets the user confirm it, and then reuses the existing PPT post-outline generation pipeline without depending on chat conversation context.

**Architecture:** Introduce a direct PPT draft/run path parallel to the report direct-entry flow. Backend gains PPT direct outline/generate APIs, a lightweight direct draft store, and a shared post-outline executor extracted from the current `PptWorkflowRuntime`. Frontend gains a PPT workbench entry surface, request helpers, and `StudioPanel` wiring that drives the new direct flow while keeping generated-file and course-material behavior unchanged.

**Tech Stack:** FastAPI, Pydantic, Python workflow/application services, existing html2ppt client/runtime, React, TypeScript, Ant Design, pytest, node --test.

---

## File Structure

### Backend files to create

- `Edu_AI/api/Edu_AI/app/chat/application/ppt_direct_draft_store.py`
- `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_direct_ppt_outline_service_v2.py`
- `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_direct_ppt_generation_service_v2.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/post_outline_executor.py`
- `Edu_AI/api/Edu_AI/tests/chat/test_ppt_direct_draft_store.py`
- `Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_outline_service_v2.py`
- `Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_generation_service_v2.py`

### Backend files to modify

- `Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
- `Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/runtime.py`
- `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`
- `Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`
- `Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py`
- `Edu_AI/api/Edu_AI/tests/chat/test_ppt_course_material_persistence.py`

### Frontend files to create

- `Edu_AI/src/components/teacher/PptEntryPanel.tsx`
- `Edu_AI/src/services/teacher/pptEntry.helpers.ts`
- `Edu_AI/tests/frontend/pptEntry.helpers.test.ts`
- `Edu_AI/tests/frontend/studioPanel.ppt-entry.test.ts`

### Frontend files to modify

- `Edu_AI/src/components/teacher/StudioPanel.tsx`
- `Edu_AI/src/services/teacher/chatV2.ts`
- `Edu_AI/src/services/teacher/chatV2.helpers.ts`
- `Edu_AI/tests/frontend/chatV2.helpers.test.ts`
- `Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts`
- `Edu_AI/tests/frontend/courseMaterials.ppt.test.ts`

## Task 1: Add Direct PPT API Contracts

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`

- [ ] **Step 1: Write the failing schema test**

```python
from app.chat.api.schemas_v2 import (
    ChatDirectPptGenerateResponseV2,
    ChatDirectPptOutlineResponseV2,
    DirectPptConfigV2,
    KnowledgeBaseDirectPptGenerateRequestV2,
    KnowledgeBaseDirectPptOutlineRequestV2,
)


def test_direct_ppt_outline_request_supports_selected_docs_and_config():
    payload = KnowledgeBaseDirectPptOutlineRequestV2(
        course_id="course-1",
        selected_doc_ids=["doc-1"],
        ppt_config=DirectPptConfigV2(
            deck_title="Agent 基础",
            audience="本科生",
            objective="课堂讲解",
            theme_id="heu_academic_elegant",
            target_slide_count=16,
            key_points=["定义", "流程"],
        ),
    )

    assert payload.selected_doc_ids == ["doc-1"]
    assert payload.ppt_config.target_slide_count == 16


def test_direct_ppt_generate_request_uses_draft_id():
    payload = KnowledgeBaseDirectPptGenerateRequestV2(
        draft_id="ppt-draft-1",
        confirm=True,
        outline={"deck_title": "Agent 基础", "slides": []},
    )

    assert payload.draft_id == "ppt-draft-1"
    assert payload.confirm is True


def test_direct_ppt_outline_response_supports_draft_payload():
    payload = ChatDirectPptOutlineResponseV2(
        action={"name": "generate.ppt.outline.direct"},
        draft={"draft_id": "ppt-draft-1", "status": "outline_ready"},
        artifacts=[],
        trace={"path": "direct", "draft_id": "ppt-draft-1"},
    )

    assert payload.draft["draft_id"] == "ppt-draft-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py -q`
Expected: FAIL because the direct PPT schema models do not exist.

- [ ] **Step 3: Add the minimal schema types**

```python
class DirectPptConfigV2(BaseModel):
    deck_title: str
    deck_subtitle: Optional[str] = None
    audience: str
    objective: str
    theme_id: str
    target_slide_count: int
    key_points: List[str] = Field(default_factory=list)
    style_hint: Optional[str] = None
    special_requirements: Optional[str] = None


class KnowledgeBaseDirectPptOutlineRequestV2(BaseModel):
    course_id: Optional[str] = None
    selected_doc_ids: List[str] = Field(default_factory=list)
    ppt_config: DirectPptConfigV2


class KnowledgeBaseDirectPptGenerateRequestV2(BaseModel):
    draft_id: str
    confirm: bool = False
    outline: Optional[Dict[str, Any]] = None


class ChatDirectPptOutlineResponseV2(BaseModel):
    action: Dict[str, Any]
    draft: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    trace: DirectTraceMetaV2


class ChatDirectPptGenerateResponseV2(BaseModel):
    action: Dict[str, Any]
    run: Dict[str, Any]
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    trace: DirectTraceMetaV2
```

- [ ] **Step 4: Write the failing route tests**

```python
def test_direct_ppt_outline_v2_route_returns_draft_payload(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def generate_outline(self, payload):
            return {
                "action": {"name": "generate.ppt.outline.direct"},
                "draft": {"draft_id": "ppt-draft-1", "status": "outline_ready"},
                "artifacts": [],
                "trace": {"path": "direct", "draft_id": "ppt-draft-1"},
            }

    monkeypatch.setattr("app.chat.api.routes_v2._get_direct_ppt_outline_service", lambda: DummyService())
    client = TestClient(app)
    response = client.post("/api/chat/v2/ppt/outline", json={"selected_doc_ids": ["doc-1"], "ppt_config": {"deck_title": "Agent 基础", "audience": "本科生", "objective": "课堂讲解", "theme_id": "heu_academic_elegant", "target_slide_count": 16, "key_points": ["定义"]}})

    assert response.status_code == 200
    assert response.json()["draft"]["draft_id"] == "ppt-draft-1"
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py -q`
Expected: FAIL because the direct PPT endpoints do not exist.

- [ ] **Step 6: Add the route helpers and endpoints**

```python
def _get_direct_ppt_outline_service():
    from app.chat.application.knowledge_base_direct_ppt_outline_service_v2 import build_default_knowledge_base_direct_ppt_outline_service_v2
    return build_default_knowledge_base_direct_ppt_outline_service_v2()


def _get_direct_ppt_generation_service():
    from app.chat.application.knowledge_base_direct_ppt_generation_service_v2 import build_default_knowledge_base_direct_ppt_generation_service_v2
    return build_default_knowledge_base_direct_ppt_generation_service_v2()


@router.post("/ppt/outline", response_model=ChatDirectPptOutlineResponseV2)
async def direct_ppt_outline(payload: KnowledgeBaseDirectPptOutlineRequestV2, current_user: dict = Depends(get_current_user)):
    return _get_direct_ppt_outline_service().generate_outline(_with_owner(payload, current_user))


@router.post("/ppt/generate", response_model=ChatDirectPptGenerateResponseV2)
async def direct_ppt_generate(payload: KnowledgeBaseDirectPptGenerateRequestV2, current_user: dict = Depends(get_current_user)):
    return _get_direct_ppt_generation_service().generate(_with_owner(payload, current_user))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/api/schemas_v2.py Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py
git commit -m "feat: add direct ppt api contracts"
```

## Task 2: Add Direct PPT Draft Store and Outline Service

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/application/ppt_direct_draft_store.py`
- Create: `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_direct_ppt_outline_service_v2.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_direct_draft_store.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_outline_service_v2.py`

- [ ] **Step 1: Write the failing draft store test**

```python
from app.chat.application.ppt_direct_draft_store import InMemoryPptDirectDraftStore


def test_ppt_direct_draft_store_round_trips_draft():
    store = InMemoryPptDirectDraftStore()
    draft = {
        "draft_id": "ppt-draft-1",
        "selected_doc_ids": ["doc-1"],
        "selected_doc_snapshot_id": "snap-1",
        "normalized_ppt_config": {"deck_title": "Agent 基础"},
        "draft_outline": {"deck_title": "Agent 基础", "slides": []},
        "status": "outline_ready",
    }

    store.save(draft)
    loaded = store.get("ppt-draft-1")

    assert loaded["draft_id"] == "ppt-draft-1"
    assert loaded["selected_doc_snapshot_id"] == "snap-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_direct_draft_store.py -q`
Expected: FAIL because the direct draft store does not exist.

- [ ] **Step 3: Implement the draft store**

```python
class InMemoryPptDirectDraftStore:
    def __init__(self):
        self._drafts: dict[str, dict[str, Any]] = {}

    def save(self, draft: dict[str, Any]) -> None:
        draft_id = str(draft.get("draft_id") or "").strip()
        if not draft_id:
            raise ValueError("draft_id is required")
        self._drafts[draft_id] = dict(draft)

    def get(self, draft_id: str) -> dict[str, Any]:
        normalized = str(draft_id or "").strip()
        if normalized not in self._drafts:
            raise KeyError(normalized)
        return dict(self._drafts[normalized])

    def update(self, draft_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        current = self.get(draft_id)
        current.update(dict(patch or {}))
        self.save(current)
        return current
```

- [ ] **Step 4: Write the failing outline service test**

```python
def test_direct_ppt_outline_service_creates_draft_without_chat_context():
    class DummySummaryProvider:
        def get_selected_document_summaries(self, *, selected_doc_ids, owner=None):
            return {
                "documents": [{"document_id": "doc-1", "title": "Agent 讲义", "summary": "介绍 Agent 定义与流程"}],
                "fallback_used": False,
            }

    class DummyOutlineBuilder:
        def build(self, *, preparation):
            return PptOutline(
                deck_title="Agent 基础",
                deck_subtitle="课堂讲解",
                theme_id="heu_academic_elegant",
                slides=[PptOutlineSlide(slide_index=1, role="cover", title="Agent 基础", goal="开场", key_points=["定义"])],
            )

    store = InMemoryPptDirectDraftStore()
    service = KnowledgeBaseDirectPptOutlineServiceV2(
        summary_provider=DummySummaryProvider(),
        outline_builder=DummyOutlineBuilder(),
        draft_store=store,
    )

    result = service.generate_outline(
        SimpleNamespace(
            selected_doc_ids=["doc-1"],
            ppt_config={
                "deck_title": "Agent 基础",
                "audience": "本科生",
                "objective": "课堂讲解",
                "theme_id": "heu_academic_elegant",
                "target_slide_count": 16,
                "key_points": ["定义"],
            },
            owner="tester",
        )
    )

    assert result["draft"]["status"] == "outline_ready"
    assert result["trace"]["source_scope"] == "selected_documents_only"
    assert store.get(result["draft"]["draft_id"])["normalized_ppt_config"]["deck_title"] == "Agent 基础"
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_outline_service_v2.py -q`
Expected: FAIL because the outline service does not exist.

- [ ] **Step 6: Implement the outline service**

```python
class KnowledgeBaseDirectPptOutlineServiceV2:
    def __init__(self, *, summary_provider=None, outline_builder=None, draft_store=None):
        self.summary_provider = summary_provider or KnowledgeBaseSummaryProvider()
        self.outline_builder = outline_builder or PptOutlineBuilder(llm=get_fallback_llm())
        self.draft_store = draft_store or InMemoryPptDirectDraftStore()

    def generate_outline(self, payload):
        selected_doc_ids = [str(item or "").strip() for item in list(getattr(payload, "selected_doc_ids", []) or []) if str(item or "").strip()]
        if not selected_doc_ids:
            raise ValueError("selected_doc_ids is required")

        ppt_config = dict(getattr(payload, "ppt_config", {}) or {})
        normalized_config = {
            "deck_title": str(ppt_config.get("deck_title") or "").strip(),
            "deck_subtitle": str(ppt_config.get("deck_subtitle") or "").strip(),
            "audience": str(ppt_config.get("audience") or "").strip(),
            "objective": str(ppt_config.get("objective") or "").strip(),
            "theme_id": str(ppt_config.get("theme_id") or "heu_academic_elegant").strip(),
            "target_slide_count": int(ppt_config.get("target_slide_count") or 12),
            "key_points": [str(item).strip() for item in list(ppt_config.get("key_points") or []) if str(item).strip()],
            "style_hint": str(ppt_config.get("style_hint") or "").strip(),
            "special_requirements": str(ppt_config.get("special_requirements") or "").strip(),
        }

        summary_result = self.summary_provider.get_selected_document_summaries(selected_doc_ids=selected_doc_ids, owner=str(getattr(payload, "owner", "") or "").strip() or None)
        documents = list(summary_result.get("documents") or [])
        if not documents:
            raise ValueError("selected documents summary is empty")

        preparation = SimpleNamespace(
            topic=normalized_config["deck_title"],
            audience=normalized_config["audience"],
            objective=normalized_config["objective"],
            key_points=normalized_config["key_points"],
            theme_id=normalized_config["theme_id"],
            slide_count=normalized_config["target_slide_count"],
            source_basis=[str(doc.get("title") or "").strip() for doc in documents if str(doc.get("title") or "").strip()],
            source_excerpts=[str(doc.get("summary") or "").strip() for doc in documents if str(doc.get("summary") or "").strip()],
        )
        outline = self.outline_builder.build(preparation=preparation)
        draft_id = f"ppt-draft-{uuid4().hex[:12]}"
        draft = {
            "draft_id": draft_id,
            "selected_doc_ids": selected_doc_ids,
            "selected_doc_snapshot_id": f"snap-{uuid4().hex[:12]}",
            "selected_doc_snapshot": documents,
            "normalized_ppt_config": normalized_config,
            "draft_outline": outline.model_dump(exclude_none=True),
            "status": "outline_ready",
        }
        self.draft_store.save(draft)
        return {
            "action": {"name": "generate.ppt.outline.direct"},
            "draft": {"draft_id": draft_id, "status": "outline_ready"},
            "artifacts": [{"artifact_id": f"{draft_id}:outline", "artifact_type": "ppt_outline", "title": f"{outline.deck_title}-大纲", "content": outline.model_dump(exclude_none=True)}],
            "trace": {"path": "direct", "draft_id": draft_id, "source_scope": "selected_documents_only", "uses_chat_context": False, "selected_doc_snapshot_id": draft["selected_doc_snapshot_id"]},
        }
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_direct_draft_store.py Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_outline_service_v2.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/application/ppt_direct_draft_store.py Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_direct_ppt_outline_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_direct_draft_store.py Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_outline_service_v2.py
git commit -m "feat: add direct ppt draft outline preparation"
```

## Task 3: Extract Shared PPT Post-Outline Executor and Direct Generation Service

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/post_outline_executor.py`
- Create: `Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_direct_ppt_generation_service_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/runtime.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_generation_service_v2.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py`

- [ ] **Step 1: Write the failing direct generation test**

```python
def test_direct_ppt_generation_service_uses_draft_id_and_executor():
    class DummyDraftStore:
        def get(self, draft_id):
            return {
                "draft_id": draft_id,
                "selected_doc_ids": ["doc-1"],
                "selected_doc_snapshot_id": "snap-1",
                "selected_doc_snapshot": [{"document_id": "doc-1", "summary": "Agent 定义"}],
                "normalized_ppt_config": {"deck_title": "Agent 基础", "audience": "本科生", "objective": "课堂讲解", "theme_id": "heu_academic_elegant", "target_slide_count": 16, "key_points": ["定义"]},
                "draft_outline": {"deck_title": "Agent 基础", "theme_id": "heu_academic_elegant", "slides": []},
                "status": "outline_ready",
            }

    class DummyExecutor:
        def execute(self, *, outline, request, metadata):
            return {
                "action": {"name": "generate.ppt.direct"},
                "run": {"run_id": "ppt-run-1", "status": "running"},
                "artifacts": [],
                "trace": {"path": "direct", "draft_id": "ppt-draft-1", "run_id": "ppt-run-1"},
            }

    service = KnowledgeBaseDirectPptGenerationServiceV2(draft_store=DummyDraftStore(), post_outline_executor=DummyExecutor())
    result = service.generate(SimpleNamespace(draft_id="ppt-draft-1", confirm=True, outline=None, owner="tester"))

    assert result["run"]["run_id"] == "ppt-run-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_generation_service_v2.py -q`
Expected: FAIL because the direct generation service does not exist.

- [ ] **Step 3: Create the shared executor**

```python
class PptPostOutlineExecutor:
    def __init__(self, *, content_markdown_generator=None, content_gate=None, html2ppt_client=None, html2ppt_client_factory=None, poll_interval_seconds: float = 2.0, max_poll_attempts: int = 600, max_poll_seconds: float = 1800.0, phase_poll_timeout_seconds: dict[str, float] | None = None):
        self.content_markdown_generator = content_markdown_generator or PptContentMarkdownGenerator()
        self.content_gate = content_gate or PptContentGate(content_validator=PptContentValidator())
        self._html2ppt_client = html2ppt_client
        self._html2ppt_client_factory = html2ppt_client_factory
        self.poll_interval_seconds = poll_interval_seconds
        self.max_poll_attempts = max_poll_attempts
        self.max_poll_seconds = max_poll_seconds
        self.phase_poll_timeout_seconds = phase_poll_timeout_seconds or {}
```

- [ ] **Step 4: Implement `execute()` with the current runtime sequence**

```python
def execute(self, *, outline, request, metadata):
    content_markdown, _ = self.content_markdown_generator.generate(outline=outline, preparation=metadata["preparation"])
    validation = self.content_gate.apply(content_markdown=content_markdown, outline=outline)
    final_markdown = str(validation.get("final_markdown") or content_markdown)
    job_payload = self.html2ppt_client.create_job(
        content_markdown=final_markdown,
        theme_id=outline.theme_id,
        metadata=metadata["job_metadata"],
    )
    status_payload, results_payload = self._wait_for_job_terminal_state(
        request=request,
        job_id=str(job_payload["job_id"]),
        initial_status=job_payload,
    )
    return {
        "action": {"name": "generate.ppt.direct"},
        "run": {"run_id": f"ppt-run-{job_payload['job_id']}", "status": _normalize_job_status(status_payload.get('status')), "job_id": job_payload["job_id"]},
        "artifacts": metadata["artifact_builder"](outline=outline, final_markdown=final_markdown, status_payload=status_payload, results_payload=results_payload),
        "trace": {"path": metadata.get("trace_path", "direct"), "job_id": job_payload["job_id"], "draft_id": metadata.get("draft_id")},
    }
```

- [ ] **Step 5: Implement the direct generation service**

```python
class KnowledgeBaseDirectPptGenerationServiceV2:
    def __init__(self, *, draft_store=None, post_outline_executor=None):
        self.draft_store = draft_store or InMemoryPptDirectDraftStore()
        self.post_outline_executor = post_outline_executor or PptPostOutlineExecutor()

    def generate(self, payload):
        draft_id = str(getattr(payload, "draft_id", "") or "").strip()
        if not draft_id:
            raise ValueError("draft_id is required")
        draft = self.draft_store.get(draft_id)
        outline_payload = dict(getattr(payload, "outline", None) or draft.get("draft_outline") or {})
        outline = PptOutline.model_validate(outline_payload)
        return self.post_outline_executor.execute(
            outline=outline,
            request=SimpleNamespace(conversation_id="", owner=str(getattr(payload, "owner", "") or "").strip()),
            metadata=build_direct_ppt_metadata_from_draft(draft_id=draft_id, draft=draft),
        )
```

- [ ] **Step 6: Refactor `PptWorkflowRuntime` to delegate post-outline execution**

```python
class PptWorkflowRuntime:
    def __init__(self, *, post_outline_executor=None, ...):
        ...
        self.post_outline_executor = post_outline_executor or PptPostOutlineExecutor(
            content_markdown_generator=self.content_markdown_generator,
            content_gate=self.content_gate,
            html2ppt_client=self._html2ppt_client,
            html2ppt_client_factory=self._html2ppt_client_factory,
            poll_interval_seconds=self.poll_interval_seconds,
            max_poll_attempts=self.max_poll_attempts,
            max_poll_seconds=self.max_poll_seconds,
            phase_poll_timeout_seconds=self.phase_poll_timeout_seconds,
        )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_generation_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/workflows/ppt/post_outline_executor.py Edu_AI/api/Edu_AI/app/chat/application/knowledge_base_direct_ppt_generation_service_v2.py Edu_AI/api/Edu_AI/app/chat/workflows/ppt/runtime.py Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_generation_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py
git commit -m "feat: share ppt post-outline execution"
```

## Task 4: Add Frontend Direct PPT APIs and Workbench Entry Surface

**Files:**
- Create: `Edu_AI/src/services/teacher/pptEntry.helpers.ts`
- Create: `Edu_AI/src/components/teacher/PptEntryPanel.tsx`
- Modify: `Edu_AI/src/services/teacher/chatV2.ts`
- Modify: `Edu_AI/src/services/teacher/chatV2.helpers.ts`
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx`
- Test: `Edu_AI/tests/frontend/pptEntry.helpers.test.ts`
- Test: `Edu_AI/tests/frontend/studioPanel.ppt-entry.test.ts`
- Test: `Edu_AI/tests/frontend/chatV2.helpers.test.ts`

- [ ] **Step 1: Write the failing helper and wiring tests**

```ts
import assert from 'node:assert/strict';
import { buildDirectPptGenerateRequest, buildDirectPptOutlineRequest } from '../../src/services/teacher/pptEntry.helpers';

const outlinePayload = buildDirectPptOutlineRequest({
  courseId: 'course-1',
  selectedDocIds: ['doc-1'],
  config: {
    deckTitle: 'Agent 基础',
    audience: '本科生',
    objective: '课堂讲解',
    themeId: 'heu_academic_elegant',
    targetSlideCount: 16,
    keyPoints: ['定义'],
  },
});

assert.equal(outlinePayload.selected_doc_ids[0], 'doc-1');
assert.equal(outlinePayload.ppt_config.deck_title, 'Agent 基础');

const generatePayload = buildDirectPptGenerateRequest({
  draftId: 'ppt-draft-1',
  outline: { deck_title: 'Agent 基础', slides: [] },
});

assert.equal(generatePayload.draft_id, 'ppt-draft-1');
assert.equal(generatePayload.confirm, true);
```

```ts
const studioPanel = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');
assert.match(studioPanel, /import\s+PptEntryPanel\s+from\s+['"]\.\/PptEntryPanel['"]/);
assert.match(studioPanel, /if\s*\(type\s*===\s*'ppt'\)\s*\{[\s\S]*setPptEntryVisible\(true\)/);
assert.match(studioPanel, /generateKnowledgeBasePptOutlineV2\(/);
assert.match(studioPanel, /generateKnowledgeBasePptV2\(/);
assert.match(studioPanel, /<PptEntryPanel/);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test Edu_AI/tests/frontend/pptEntry.helpers.test.ts Edu_AI/tests/frontend/studioPanel.ppt-entry.test.ts`
Expected: FAIL because the helper and panel do not exist.

- [ ] **Step 3: Add direct PPT API functions in `chatV2.ts`**

```ts
export interface KnowledgeBaseDirectPptOutlineRequestV2 {
  course_id?: string;
  selected_doc_ids?: string[];
  ppt_config: {
    deck_title: string;
    deck_subtitle?: string;
    audience: string;
    objective: string;
    theme_id: 'heu_academic_elegant' | 'heu_academic_basic';
    target_slide_count: number;
    key_points: string[];
    style_hint?: string;
    special_requirements?: string;
  };
}

export interface KnowledgeBaseDirectPptGenerateRequestV2 {
  draft_id: string;
  confirm: boolean;
  outline?: Record<string, unknown>;
}

export async function generateKnowledgeBasePptOutlineV2(payload: KnowledgeBaseDirectPptOutlineRequestV2) {
  return postV2('/api/chat/v2/ppt/outline', payload);
}

export async function generateKnowledgeBasePptV2(payload: KnowledgeBaseDirectPptGenerateRequestV2) {
  return postV2('/api/chat/v2/ppt/generate', payload);
}
```

- [ ] **Step 4: Add PPT entry helper functions**

```ts
export function buildDirectPptOutlineRequest(options: {
  courseId?: string;
  selectedDocIds: string[];
  config: {
    deckTitle: string;
    deckSubtitle?: string;
    audience: string;
    objective: string;
    themeId: 'heu_academic_elegant' | 'heu_academic_basic';
    targetSlideCount: number;
    keyPoints: string[];
    styleHint?: string;
    specialRequirements?: string;
  };
}): KnowledgeBaseDirectPptOutlineRequestV2 {
  return {
    course_id: options.courseId,
    selected_doc_ids: options.selectedDocIds,
    ppt_config: {
      deck_title: options.config.deckTitle,
      deck_subtitle: options.config.deckSubtitle,
      audience: options.config.audience,
      objective: options.config.objective,
      theme_id: options.config.themeId,
      target_slide_count: options.config.targetSlideCount,
      key_points: options.config.keyPoints,
      style_hint: options.config.styleHint,
      special_requirements: options.config.specialRequirements,
    },
  };
}

export function buildDirectPptGenerateRequest(options: { draftId: string; outline?: Record<string, unknown> }): KnowledgeBaseDirectPptGenerateRequestV2 {
  return {
    draft_id: options.draftId,
    confirm: true,
    outline: options.outline,
  };
}
```

- [ ] **Step 5: Add `PptEntryPanel.tsx`**

```tsx
export default function PptEntryPanel({ open, selectedDocIds, onCancel, onSubmitOutline, onSubmitGenerate }: Props) {
  const [entryState, setEntryState] = useState<'configuring' | 'outline_loading' | 'outline_ready' | 'generating' | 'error'>('configuring');
  const [draftId, setDraftId] = useState('');
  const [outlinePreview, setOutlinePreview] = useState('');
  const [form] = Form.useForm<DirectPptEntryFormValue>();

  return (
    <Modal title="创建 PPT" open={open} onCancel={onCancel} footer={null} width={920} destroyOnClose>
      <Form form={form} layout="vertical">
        <Form.Item name="deckTitle" label="PPT 标题" rules={[{ required: true, message: '请输入 PPT 标题' }]}><Input /></Form.Item>
        <Form.Item name="audience" label="受众" rules={[{ required: true, message: '请输入受众' }]}><Input /></Form.Item>
        <Form.Item name="objective" label="目标" rules={[{ required: true, message: '请输入目标' }]}><Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} /></Form.Item>
        <Form.Item name="themeId" label="主题" initialValue="heu_academic_elegant"><Select options={[{ value: 'heu_academic_elegant', label: '学院典雅' }, { value: 'heu_academic_basic', label: '学院基础' }]} /></Form.Item>
        <Form.Item name="targetSlideCount" label="目标页数" initialValue={16}><InputNumber min={8} max={40} style={{ width: '100%' }} /></Form.Item>
      </Form>
      {entryState === 'outline_ready' ? <pre>{outlinePreview}</pre> : null}
    </Modal>
  );
}
```

- [ ] **Step 6: Wire `StudioPanel.tsx`**

```tsx
const [pptEntryVisible, setPptEntryVisible] = useState(false);

if (type === 'ppt') {
  if (!selectedDocs || selectedDocs.length === 0) {
    message.warning('请先选择至少一份知识库文档');
    return;
  }
  setPptEntryVisible(true);
  return;
}

const handleDirectPptOutlineSubmit = async ({ config }: { config: DirectPptEntryFormValue }) => {
  const response = await generateKnowledgeBasePptOutlineV2(
    buildDirectPptOutlineRequest({ courseId, selectedDocIds: selectedDocs, config }),
  );
  extractGeneratedFilesFromV2Response(response as any).forEach((file) => addGeneratedFile(file));
};

const handleDirectPptGenerateSubmit = async ({ draftId, outline }: { draftId: string; outline?: Record<string, unknown> }) => {
  const response = await generateKnowledgeBasePptV2(buildDirectPptGenerateRequest({ draftId, outline }));
  const files = extractGeneratedFilesFromV2Response(response as any);
  files.forEach((file) => addGeneratedFile(file));
  if (courseId) await refreshCourseMaterials();
};
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `node --test Edu_AI/tests/frontend/pptEntry.helpers.test.ts Edu_AI/tests/frontend/studioPanel.ppt-entry.test.ts Edu_AI/tests/frontend/chatV2.helpers.test.ts`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add Edu_AI/src/services/teacher/pptEntry.helpers.ts Edu_AI/src/components/teacher/PptEntryPanel.tsx Edu_AI/src/services/teacher/chatV2.ts Edu_AI/src/services/teacher/chatV2.helpers.ts Edu_AI/src/components/teacher/StudioPanel.tsx Edu_AI/tests/frontend/pptEntry.helpers.test.ts Edu_AI/tests/frontend/studioPanel.ppt-entry.test.ts Edu_AI/tests/frontend/chatV2.helpers.test.ts
git commit -m "feat: add workbench direct ppt entry"
```

## Task 5: Regression and Integration Verification

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_course_material_persistence.py`
- Modify: `Edu_AI/tests/frontend/courseMaterials.ppt.test.ts`
- Modify: `Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts`

- [ ] **Step 1: Add failing persistence regression test**

```python
def test_direct_ppt_generation_persists_completed_ppt_course_material():
    saved = {}

    class DummyStorage:
        def save_generated_material(self, *, course_id, material_type, material_id, material_data):
            saved["course_id"] = course_id
            saved["material_type"] = material_type
            saved["material_id"] = material_id

    result = {
        "artifacts": [
            {
                "artifact_id": "ppt-run-1:deck",
                "artifact_type": "ppt_deck",
                "title": "Agent 基础.pptx",
                "content": {"job_id": "job-1", "html_full_url": "/ppt/artifacts/job-1/rev_0000/deck.html"},
                "generation_state": {"status": "completed"},
            }
        ]
    }

    _persist_ppt_course_material(
        payload=SimpleNamespace(course_id="course-1"),
        result=result,
        course_storage_manager=DummyStorage(),
    )

    assert saved["course_id"] == "course-1"
    assert saved["material_type"] == "ppt"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_course_material_persistence.py -q`
Expected: FAIL until direct results are wired through the same persistence path.

- [ ] **Step 3: Wire direct PPT results through existing persistence**

```python
_persist_ppt_course_material(
    payload=SimpleNamespace(course_id=getattr(payload, "course_id", None)),
    result={"artifacts": result.get("artifacts") or []},
    course_storage_manager=self.course_storage_manager,
)
```

- [ ] **Step 4: Run backend verification set**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_schemas_v2.py Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_direct_draft_store.py Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_outline_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_direct_ppt_generation_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_course_material_persistence.py -q`
Expected: PASS

- [ ] **Step 5: Run frontend verification set**

Run: `node --test Edu_AI/tests/frontend/pptEntry.helpers.test.ts Edu_AI/tests/frontend/studioPanel.ppt-entry.test.ts Edu_AI/tests/frontend/chatV2.helpers.test.ts Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts Edu_AI/tests/frontend/courseMaterials.ppt.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add Edu_AI/api/Edu_AI/tests/chat/test_ppt_course_material_persistence.py Edu_AI/tests/frontend/courseMaterials.ppt.test.ts Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts
git commit -m "test: cover direct ppt integration regressions"
```

## Self-Review

- Spec coverage:
  - direct workbench entry: Task 4
  - selected docs + explicit config only: Tasks 2 and 4
  - no chat context dependency: Tasks 2 and 3
  - `draft_id` flow and snapshot consistency: Tasks 2 and 3
  - shared post-outline executor reuse: Task 3
  - generated file/persistence reuse: Tasks 4 and 5

- Placeholder scan:
  - no `TODO`/`TBD`
  - all tasks include exact files, commands, expected results, and code snippets

- Type consistency:
  - `draft_id`, `target_slide_count`, `theme_id`, `style_hint`, and `PptPostOutlineExecutor` are consistent across tasks

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-11-ppt-explicit-workbench-entry-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
