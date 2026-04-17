# Artifact Reference Context Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make teacher chat keep a referenced artifact as the active context, distinguish discussion vs modification, and clear or switch that context only on explicit user intent.

**Architecture:** Add a small deterministic artifact-context resolver in the backend before the current edit-runtime dispatch, then persist its decisions through existing conversation state fields. Keep frontend changes minimal by continuing to send `artifact_reference` and syncing the store from backend state after each response or conversation restore.

**Tech Stack:** FastAPI/Pydantic backend, Python pytest, React/TypeScript frontend, existing string-based frontend tests

---

### Task 1: Add backend artifact-context decision coverage

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`

- [ ] **Step 1: Write the failing report discussion vs edit tests**

```python
def test_reply_service_keeps_referenced_report_questions_on_chat_path():
    orchestrator_calls = []

    class FakeOrchestrator:
        def dispatch(self, request):
            orchestrator_calls.append(request.question)
            return {
                "message": {"role": "assistant", "content": "report discussion"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "chat.reply"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    report_runtime_calls = []

    class FakeReportEditRuntime:
        def run_from_request(self, **kwargs):
            report_runtime_calls.append(kwargs["request"].question)
            return {}

    service = ReplyServiceV2(
        orchestrator=FakeOrchestrator(),
        conversation_store=SimpleNamespace(write_v2_result=lambda *args, **kwargs: None),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(
                workflow_state=None,
                active_artifact={"artifact_id": "report-1", "artifact_type": "report", "title": "报告A"},
                active_task=None,
                recent_messages=[],
            )
        ),
        report_edit_runtime=FakeReportEditRuntime(),
    )

    result = service.reply(
        SimpleNamespace(
            question="这份报告的核心观点是什么",
            conversation_id="conv-1",
            course_id="course-1",
            selected_doc_ids=[],
            allow_rag=False,
            allow_web=False,
            artifact_reference={
                "artifact_id": "report-1",
                "artifact_type": "report",
                "title": "报告A",
            },
        )
    )

    assert result["action"]["name"] == "chat.reply"
    assert orchestrator_calls == ["这份报告的核心观点是什么"]
    assert report_runtime_calls == []


def test_reply_service_routes_referenced_report_edit_commands_to_edit_runtime():
    report_runtime_calls = []

    class FakeReportEditRuntime:
        def run_from_request(self, **kwargs):
            report_runtime_calls.append(kwargs["request"].question)
            return {
                "message": {"role": "assistant", "content": "report edited"},
                "conversation": {"conversation_id": kwargs["request"].conversation_id},
                "action": {"name": "report.edit"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(dispatch=lambda request: {"message": {}, "conversation": {}, "action": {}, "artifacts": [], "sources": [], "trace": {"path": "fast"}}),
        conversation_store=SimpleNamespace(write_v2_result=lambda *args, **kwargs: None),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(
                workflow_state=None,
                active_artifact={"artifact_id": "report-1", "artifact_type": "report", "title": "报告A"},
                active_task=None,
                recent_messages=[],
            )
        ),
        report_edit_runtime=FakeReportEditRuntime(),
    )

    result = service.reply(
        SimpleNamespace(
            question="把第三部分扩写一下",
            conversation_id="conv-1",
            course_id="course-1",
            selected_doc_ids=[],
            allow_rag=False,
            allow_web=False,
            artifact_reference={
                "artifact_id": "report-1",
                "artifact_type": "report",
                "title": "报告A",
            },
        )
    )

    assert result["action"]["name"] == "report.edit"
    assert report_runtime_calls == ["把第三部分扩写一下"]
```

- [ ] **Step 2: Write the failing PPT edit and explicit-exit tests**

```python
def test_reply_service_routes_referenced_ppt_edit_commands_to_ppt_runtime():
    ppt_runtime_calls = []

    class FakePptEditRuntime:
        def run_from_request(self, **kwargs):
            ppt_runtime_calls.append(kwargs["request"].question)
            return {
                "message": {"role": "assistant", "content": "ppt edited"},
                "conversation": {"conversation_id": kwargs["request"].conversation_id},
                "action": {"name": "ppt.edit"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(dispatch=lambda request: {"message": {}, "conversation": {}, "action": {}, "artifacts": [], "sources": [], "trace": {"path": "fast"}}),
        conversation_store=SimpleNamespace(write_v2_result=lambda *args, **kwargs: None),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(
                workflow_state=None,
                active_artifact={"artifact_id": "ppt-1", "artifact_type": "ppt_deck", "title": "课件A"},
                active_task=None,
                recent_messages=[],
            )
        ),
        ppt_edit_runtime=FakePptEditRuntime(),
    )

    result = service.reply(
        SimpleNamespace(
            question="第2页标题改短一点",
            conversation_id="conv-ppt",
            course_id="course-1",
            selected_doc_ids=[],
            allow_rag=False,
            allow_web=False,
            artifact_reference={
                "artifact_id": "ppt-1",
                "artifact_type": "ppt_deck",
                "title": "课件A",
            },
        )
    )

    assert result["action"]["name"] == "ppt.edit"
    assert ppt_runtime_calls == ["第2页标题改短一点"]


def test_reply_service_clears_artifact_context_on_explicit_exit():
    storage_writes = []

    class FakeStore:
        def write_v2_result(self, conversation_id, request, result):
            storage_writes.append((conversation_id, result))

    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(
            dispatch=lambda request: {
                "message": {"role": "assistant", "content": "普通对话"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "chat.reply"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }
        ),
        conversation_store=FakeStore(),
        context_builder=SimpleNamespace(
            build=lambda request: SimpleNamespace(
                workflow_state=None,
                active_artifact={"artifact_id": "report-1", "artifact_type": "report", "title": "报告A"},
                active_task=None,
                recent_messages=[],
            )
        ),
    )

    result = service.reply(
        SimpleNamespace(
            question="不要基于这个了，我们聊课程目标",
            conversation_id="conv-exit",
            course_id="course-1",
            selected_doc_ids=[],
            allow_rag=False,
            allow_web=False,
            artifact_reference={
                "artifact_id": "report-1",
                "artifact_type": "report",
                "title": "报告A",
            },
        )
    )

    assert result["action"]["name"] == "chat.reply"
    _, persisted = storage_writes[-1]
    assert persisted["conversation"]["conversation_id"] == "conv-exit"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q
```

Expected:

- FAIL because discussion turns currently still route directly into edit runtime
- FAIL because explicit exit does not clear artifact context

- [ ] **Step 4: Commit the failing tests**

```bash
git add Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py
git commit -m "test: cover artifact reference context routing"
```

### Task 2: Implement backend artifact-context resolver and persistence

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/orchestrator/artifact_context_resolver.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py`

- [ ] **Step 1: Add the resolver module**

```python
from __future__ import annotations

from dataclasses import dataclass


EXIT_PATTERNS = (
    "不要基于这个了",
    "清除引用",
    "移除引用",
    "不看这个了",
    "我们聊别的",
    "新开话题",
)

EDIT_PATTERNS = (
    "修改",
    "重写",
    "改写",
    "扩写",
    "精简",
    "删除",
    "调整结构",
    "改标题",
    "合并",
    "拆分",
    "补充",
)


@dataclass(slots=True)
class ArtifactContextDecision:
    action: str
    next_reference: dict
    clear_reference: bool = False


def _normalize_reference(value) -> dict:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if v is not None}
    return {}


def resolve_artifact_context(*, question: str, request_reference, snapshot) -> ArtifactContextDecision:
    text = str(question or "").strip()
    request_ref = _normalize_reference(request_reference)
    active_artifact = {}
    if snapshot is not None and getattr(snapshot, "active_artifact", None):
        raw_active = getattr(snapshot, "active_artifact")
        active_artifact = raw_active if isinstance(raw_active, dict) else {
            "artifact_id": getattr(raw_active, "artifact_id", ""),
            "artifact_type": getattr(raw_active, "artifact_type", ""),
            "title": getattr(raw_active, "title", None),
        }

    if not request_ref and not active_artifact:
        return ArtifactContextDecision(action="no_artifact", next_reference={})

    if any(pattern in text for pattern in EXIT_PATTERNS):
        return ArtifactContextDecision(action="exit_artifact_context", next_reference={}, clear_reference=True)

    if request_ref and request_ref.get("artifact_id") and request_ref.get("artifact_id") != active_artifact.get("artifact_id"):
        return ArtifactContextDecision(action="switch_artifact", next_reference=request_ref)

    current_ref = request_ref or active_artifact
    if any(pattern in text for pattern in EDIT_PATTERNS):
        return ArtifactContextDecision(action="edit_current_artifact", next_reference=current_ref)

    return ArtifactContextDecision(action="discuss_current_artifact", next_reference=current_ref)
```

- [ ] **Step 2: Wire the resolver into `ReplyServiceV2.reply`**

```python
from app.chat.orchestrator.artifact_context_resolver import resolve_artifact_context


    def reply(self, payload):
        request = normalize_chat_request(payload)
        if not getattr(request, "conversation_id", None):
            request.conversation_id = f"conv-{uuid4().hex[:12]}"

        snapshot = self.context_builder.build(request) if self.context_builder is not None else None
        decision = resolve_artifact_context(
            question=getattr(request, "question", ""),
            request_reference=getattr(request, "artifact_reference", None),
            snapshot=snapshot,
        )

        if decision.clear_reference:
            request.artifact_reference = None
        elif decision.next_reference:
            request.artifact_reference = decision.next_reference

        artifact_reference = getattr(request, "artifact_reference", None)
        artifact_type = str(getattr(artifact_reference, "artifact_type", "") or artifact_reference.get("artifact_type", "") if isinstance(artifact_reference, dict) else "").strip()

        if decision.action == "edit_current_artifact":
            if artifact_type in {"ppt_deck", "ppt_outline", "ppt_content_markdown"} and self.ppt_edit_runtime is not None:
                result = self.ppt_edit_runtime.run_from_request(
                    request=request,
                    snapshot=snapshot,
                    course_storage_manager=self.course_storage_manager,
                )
            elif self.report_edit_runtime is not None:
                result = self.report_edit_runtime.run_from_request(
                    request=request,
                    snapshot=snapshot,
                    course_storage_manager=self.course_storage_manager,
                )
            else:
                orchestrator = self.orchestrator_factory(request) if self.orchestrator_factory is not None else self.orchestrator
                result = orchestrator.dispatch(request)
        else:
            orchestrator = self.orchestrator_factory(request) if self.orchestrator_factory is not None else self.orchestrator
            result = orchestrator.dispatch(request)

        if decision.clear_reference:
            result.setdefault("conversation", {"conversation_id": request.conversation_id})
            result.setdefault("state_patch", {})
            result["state_patch"]["artifact_reference"] = {}
            result["state_patch"]["active_artifact"] = {}
        return self._finalize_result(payload=payload, request=request, result=result)
```

- [ ] **Step 3: Persist clear/switch state in `ConversationStoreAdapter.write_v2_result`**

```python
        state_patch = dict(result.get("state_patch") or {})
        artifact_reference = self._normalize_artifact_reference(getattr(request, "artifact_reference", None))

        if "artifact_reference" in state_patch and not state_patch.get("artifact_reference"):
            state_patch["artifact_reference"] = {}
            state_patch["active_artifact"] = {}
            state_patch["active_context"] = {
                **dict(self.state.get("active_context") or {}),
                "active_artifact_id": "",
                "active_artifact_type": "",
            }
            state_patch["referenced_artifact_ids"] = []
        elif artifact_reference:
            state_patch["artifact_reference"] = dict(artifact_reference)
            state_patch["active_artifact"] = {
                "artifact_id": artifact_reference.get("artifact_id") or "",
                "artifact_type": artifact_reference.get("artifact_type") or "",
                "title": artifact_reference.get("title"),
            }
            state_patch["active_context"] = {
                **dict(self.state.get("active_context") or {}),
                "active_artifact_id": artifact_reference.get("artifact_id") or "",
                "active_artifact_type": artifact_reference.get("artifact_type") or "",
            }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q
```

Expected:

- PASS for discussion/edit/exit routing

- [ ] **Step 5: Commit the backend implementation**

```bash
git add Edu_AI/api/Edu_AI/app/chat/orchestrator/artifact_context_resolver.py Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py
git commit -m "feat: route artifact references by discussion and edit intent"
```

### Task 3: Sync frontend artifact reference state with backend decisions

**Files:**
- Modify: `Edu_AI/src/components/teacher/ChatPanel.tsx`
- Modify: `Edu_AI/src/services/teacher/chatV2.ts`
- Modify: `Edu_AI/tests/frontend/chatPanel.artifact-reference.test.ts`

- [ ] **Step 1: Write the failing frontend sync tests**

```ts
assert.match(
  chatPanelFile,
  /const responseArtifactReference = detail\?\.state\?\.artifact_reference;/,
  'ChatPanel should read artifact reference state from restored conversation detail',
);

assert.match(
  chatPanelFile,
  /const responseArtifactReference = \(response as any\)\?\.state\?\.artifact_reference;/,
  'ChatPanel should read artifact reference state from reply responses',
);

assert.match(
  chatPanelFile,
  /if \(responseArtifactReference && typeof responseArtifactReference === 'object'\)[\s\S]*setArtifactReference\(/,
  'ChatPanel should refresh the store when backend returns an active artifact reference',
);

assert.match(
  chatPanelFile,
  /else \{\s*clearArtifactReference\(\);\s*\}/,
  'ChatPanel should clear the reference card when backend clears artifact context',
);
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run:

```powershell
node --test Edu_AI/tests/frontend/chatPanel.artifact-reference.test.ts
```

Expected:

- FAIL because reply-response-driven reference sync does not exist yet

- [ ] **Step 3: Implement response-state-driven sync in `ChatPanel.tsx`**

```tsx
const syncArtifactReferenceFromState = (rawState: any, fallbackConversationId?: string | null) => {
  const responseArtifactReference = rawState?.artifact_reference;
  if (responseArtifactReference && typeof responseArtifactReference === 'object') {
    setArtifactReference({
      artifact_id: String(responseArtifactReference.artifact_id || '').trim(),
      artifact_type: normalizeArtifactReferenceType(responseArtifactReference.artifact_type),
      version_id: String(responseArtifactReference.version_id || '').trim() || undefined,
      title: String(responseArtifactReference.title || '').trim() || undefined,
      source_conversation_id: String(
        responseArtifactReference.source_conversation_id || fallbackConversationId || currentConversationId || '',
      ).trim() || undefined,
      source_course_id: String(responseArtifactReference.source_course_id || courseId || '').trim() || undefined,
    });
  } else {
    clearArtifactReference();
  }
};

// inside loadConversation success branch
syncArtifactReferenceFromState(detail?.state, detail.conversation_id);

// inside reply result branch
syncArtifactReferenceFromState((response as any)?.state, response.conversation?.conversation_id || currentConversationId);
```

- [ ] **Step 4: Run the frontend test to verify it passes**

Run:

```powershell
node --test Edu_AI/tests/frontend/chatPanel.artifact-reference.test.ts
```

Expected:

- PASS

- [ ] **Step 5: Commit the frontend sync**

```bash
git add Edu_AI/src/components/teacher/ChatPanel.tsx Edu_AI/tests/frontend/chatPanel.artifact-reference.test.ts
git commit -m "feat: sync chat artifact reference from backend state"
```

### Task 4: Full verification

**Files:**
- Modify: none
- Test: existing backend and frontend suites touched above

- [ ] **Step 1: Run backend regression tests**

Run:

```powershell
d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py Edu_AI/api/Edu_AI/tests/core/test_conversation_storage_artifact_reference.py -q
```

Expected:

- PASS

- [ ] **Step 2: Run frontend regression tests**

Run:

```powershell
node --test Edu_AI/tests/frontend/chatPanel.artifact-reference.test.ts Edu_AI/tests/frontend/studioPanel.add-to-chat.test.ts
```

Expected:

- PASS

- [ ] **Step 3: Inspect final worktree status**

Run:

```bash
git status --short --branch
```

Expected:

- only intended implementation files modified

- [ ] **Step 4: Commit the verification-safe final state**

```bash
git add Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py Edu_AI/api/Edu_AI/app/chat/orchestrator/artifact_context_resolver.py Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py Edu_AI/src/components/teacher/ChatPanel.tsx Edu_AI/tests/frontend/chatPanel.artifact-reference.test.ts
git commit -m "feat: keep artifact references active across chat turns"
```
