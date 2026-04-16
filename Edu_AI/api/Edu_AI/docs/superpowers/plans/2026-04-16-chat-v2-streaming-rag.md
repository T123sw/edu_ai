# Chat V2 Streaming RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add true streaming replies to the main chat v2 path while preserving conversation history, status card, multimodal input, RAG sources, workflow artifacts, and final state persistence.

**Architecture:** Add `POST /api/chat/v2/stream` returning POST-based SSE frames. Fast chat retrieves first, emits `metadata`, streams model chunks as `delta`, then finalizes through the existing v2 persistence path. Workflow replies emit `status` events and stream their final assistant message in chunks, while artifacts and state still finalize once at the end.

**Tech Stack:** FastAPI `StreamingResponse`, `ChatReplyRequestV2`, `ReplyServiceV2`, `MainOrchestrator`, `FastChatRuntime`, `ChatModelGateway.stream_chat`, React + Vite `fetch` + `ReadableStream`.

---

## File Structure

- Modify `Edu_AI/api/Edu_AI/app/chat/runtime/fast_chat_runtime.py`: add shared generation preparation and `run_stream`.
- Modify `Edu_AI/api/Edu_AI/app/chat/orchestrator/main_orchestrator.py`: add `dispatch_stream`.
- Modify `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`: add shared finalization and `reply_stream`.
- Modify `Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`: add `POST /api/chat/v2/stream`.
- Modify `Edu_AI/src/services/teacher/chatV2.ts`: add stream event types, parser, and stream client.
- Modify `Edu_AI/src/components/teacher/ChatPanel.tsx`: consume stream events and reuse current final response handling.
- Test `Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py`.
- Test `Edu_AI/api/Edu_AI/tests/chat/test_main_orchestrator_stream.py`.
- Test `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_stream.py`.
- Test `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2_stream.py`.
- Test `Edu_AI/src/services/teacher/chatV2.helpers.test.ts`.

---

### Task 1: Fast Runtime Streaming

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/runtime/fast_chat_runtime.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
class StreamingGateway(DummyGateway):
    def stream_chat(self, messages, temperature=0.2, max_tokens=1200):
        self.call_count += 1
        self.last_messages = messages
        yield "hello"
        yield " world"


def test_fast_runtime_run_stream_emits_metadata_delta_and_result_in_order():
    gateway = StreamingGateway()
    retriever = DummyRetriever()
    runtime = FastChatRuntime(model_gateway=gateway, rag_retriever=retriever)
    request = ChatRequestV2(question="use rag", conversation_id="conv-stream", owner="teacher-a", capability=CapabilityPolicy(allow_rag=True, selected_doc_ids=["doc-1"]))

    events = list(runtime.run_stream(request=request, snapshot=None, decision=None))

    assert [event["type"] for event in events] == ["metadata", "delta", "delta", "result"]
    assert events[0]["payload"]["conversation_id"] == "conv-stream"
    assert events[0]["payload"]["sources"][0]["source"] == "doc-a"
    assert events[1]["payload"]["content"] == "hello"
    assert events[2]["payload"]["content"] == " world"
    assert events[3]["payload"]["message"]["content"] == "hello world"
    assert "retrieved summary" in gateway.last_messages[-1]["content"]
```

- [ ] **Step 2: Verify red**

Run:

```powershell
python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py::test_fast_runtime_run_stream_emits_metadata_delta_and_result_in_order -q
```

Expected: FAIL with `AttributeError` because `run_stream` does not exist.

- [ ] **Step 3: Implement minimal code**

Extract current `run` retrieval/message-building code into `_prepare_generation(...)` returning `messages`, `sources`, `trace`, and `action_name`. Then make `run` call that helper and add:

```python
def run_stream(self, *, request, snapshot, decision):
    prepared = self._prepare_generation(request=request, snapshot=snapshot, decision=decision)
    yield {"type": "metadata", "payload": {"conversation_id": getattr(request, "conversation_id", "") or "", "sources": prepared["sources"], "trace": prepared["trace"]}}
    chunks: list[str] = []
    stream_chat = getattr(self.model_gateway, "stream_chat", None)
    for chunk in stream_chat(prepared["messages"]) if callable(stream_chat) else [self.model_gateway.chat(prepared["messages"])]:
        text = str(chunk or "")
        if text:
            chunks.append(text)
            yield {"type": "delta", "payload": {"content": text}}
    answer = "".join(chunks)
    yield {"type": "result", "payload": {"message": {"role": "assistant", "content": answer}, "conversation": {"conversation_id": getattr(request, "conversation_id", "") or ""}, "action": {"name": prepared["action_name"]}, "workflow": None, "artifacts": [], "sources": prepared["sources"], "trace": prepared["trace"]}}
```

- [ ] **Step 4: Verify green**

Run the focused pytest command again. Expected: PASS.

---

### Task 2: Orchestrator Stream Routing

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/main_orchestrator.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_main_orchestrator_stream.py`

- [ ] **Step 1: Write the failing test**

Create:

```python
from types import SimpleNamespace

from app.chat.orchestrator.main_orchestrator import MainOrchestrator


class DummyContextBuilder:
    def build(self, request):
        return SimpleNamespace(workflow_state=None)


class DummyFastRuntime:
    def run_stream(self, *, request, snapshot, decision):
        yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id}}
        yield {"type": "delta", "payload": {"content": "ok"}}
        yield {"type": "result", "payload": {"message": {"role": "assistant", "content": "ok"}, "conversation": {"conversation_id": request.conversation_id}, "action": {"name": "chat.reply"}, "workflow": None, "artifacts": [], "sources": [], "trace": {"path": "fast"}}}


def test_main_orchestrator_dispatch_stream_uses_fast_runtime():
    orchestrator = MainOrchestrator(fast_runtime=DummyFastRuntime(), workflow_registry={}, context_builder=DummyContextBuilder())
    events = list(orchestrator.dispatch_stream(SimpleNamespace(question="hello", conversation_id="conv-1")))
    assert [event["type"] for event in events] == ["metadata", "delta", "result"]
    assert events[-1]["payload"]["message"]["content"] == "ok"
```

- [ ] **Step 2: Verify red**

Run:

```powershell
python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_main_orchestrator_stream.py -q
```

Expected: FAIL because `dispatch_stream` does not exist.

- [ ] **Step 3: Implement stream routing**

Add:

```python
def dispatch_stream(self, request):
    snapshot = self.context_builder.build(request)
    decision = decide_route(request=request, snapshot=snapshot, workflow_state=getattr(snapshot, "workflow_state", None))
    if decision.path == "fast":
        yield from self.fast_runtime.run_stream(request=request, snapshot=snapshot, decision=decision)
        return
    yield {"type": "status", "payload": {"stage": "workflow_routing", "label": f"正在进入{decision.workflow_name or '工作流'}流程", "workflow": {"type": decision.workflow_name or "", "status": "running"}}}
    workflow = self.workflow_registry[decision.workflow_name]
    result = workflow.run(request=request, snapshot=snapshot, decision=decision)
    answer = str(((result.get("message") or {}).get("content")) or "")
    for index in range(0, len(answer), 24):
        yield {"type": "delta", "payload": {"content": answer[index:index + 24]}}
    yield {"type": "result", "payload": result}
```

- [ ] **Step 4: Verify green**

Run the focused pytest command again. Expected: PASS.

---

### Task 3: Reply Service Stream Finalization

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_stream.py`

- [ ] **Step 1: Write the failing test**

Create:

```python
from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2


class StreamOrchestrator:
    def dispatch_stream(self, request):
        yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id, "sources": []}}
        yield {"type": "delta", "payload": {"content": "hello"}}
        yield {"type": "result", "payload": {"message": {"role": "assistant", "content": "hello"}, "conversation": {"conversation_id": request.conversation_id}, "action": {"name": "chat.reply"}, "workflow": None, "artifacts": [], "sources": [], "trace": {"path": "fast"}}}


class DummyStore:
    def __init__(self):
        self.saved = []

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, request.question, result["message"]["content"]))


class DummyStatusCardBuilder:
    def build(self, *, snapshot, workflow, capability):
        return {"mode": "chat", "status_label": "普通对话"}


def test_reply_service_stream_finalizes_result_and_writes_once():
    store = DummyStore()
    snapshot = SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])
    service = ReplyServiceV2(orchestrator=StreamOrchestrator(), conversation_store=store, context_builder=SimpleNamespace(build=lambda request: snapshot), status_card_builder=DummyStatusCardBuilder())
    payload = SimpleNamespace(question="hello", conversation_id="conv-1", model_id=None, course_id=None, artifact_id=None, allow_rag=False, allow_web=False, selected_doc_ids=[], action_hint=None, owner="u1")
    events = list(service.reply_stream(payload))
    assert [event["type"] for event in events] == ["metadata", "delta", "result", "done"]
    assert events[2]["payload"]["status_card"]["status_label"] == "普通对话"
    assert events[3]["payload"]["conversation_id"] == "conv-1"
    assert store.saved == [("conv-1", "hello", "hello")]
```

- [ ] **Step 2: Verify red**

Run:

```powershell
python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_stream.py -q
```

Expected: FAIL because `reply_stream` does not exist.

- [ ] **Step 3: Implement finalization and stream method**

Extract finalization from `reply` into `_finalize_result(...)`, preserving `finalize_report_result`, `_persist_quiz_course_material`, `write_v2_result`, refreshed snapshot, and `status_card_builder.build`. Add:

```python
def reply_stream(self, payload):
    request = normalize_chat_request(payload)
    if not getattr(request, "conversation_id", None):
        request.conversation_id = f"conv-{uuid4().hex[:12]}"
    orchestrator = self.orchestrator_factory(request) if self.orchestrator_factory is not None else self.orchestrator
    final_result = None
    for event in orchestrator.dispatch_stream(request):
        if event.get("type") == "result":
            final_result = self._finalize_result(payload=payload, request=request, result=dict(event.get("payload") or {}))
            yield {"type": "result", "payload": final_result}
        else:
            yield event
    conversation_id = str(((final_result or {}).get("conversation") or {}).get("conversation_id") or request.conversation_id or "")
    yield {"type": "done", "payload": {"conversation_id": conversation_id}}
```

- [ ] **Step 4: Verify green**

Run the focused pytest command again. Expected: PASS.

---

### Task 4: Chat V2 Stream Route

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/api/routes_v2.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2_stream.py`

- [ ] **Step 1: Write the failing route test**

Create:

```python
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.chat.api.routes_v2 import router as v2_router


def test_chat_v2_stream_route_returns_sse_frames(monkeypatch):
    app = FastAPI()
    app.include_router(v2_router)
    app.dependency_overrides[get_current_user] = lambda: {"username": "tester"}

    class DummyService:
        def reply_stream(self, payload):
            assert payload.owner == "tester"
            yield {"type": "metadata", "payload": {"conversation_id": "conv-1", "sources": []}}
            yield {"type": "delta", "payload": {"content": "ok"}}
            yield {"type": "result", "payload": {"message": {"role": "assistant", "content": "ok"}, "conversation": {"conversation_id": "conv-1"}, "action": {"name": "chat.reply"}, "workflow": None, "artifacts": [], "sources": [], "trace": {"path": "fast"}, "status_card": {"status_label": "普通对话"}}}
            yield {"type": "done", "payload": {"conversation_id": "conv-1"}}

    monkeypatch.setattr("app.chat.api.routes_v2._get_reply_service", lambda: DummyService())
    response = TestClient(app).post("/api/chat/v2/stream", json={"question": "hello"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = [json.loads(line.removeprefix("data: ").strip()) for line in response.text.splitlines() if line.startswith("data:")]
    assert [frame["type"] for frame in frames] == ["metadata", "delta", "result", "done"]
```

- [ ] **Step 2: Verify red**

Run:

```powershell
python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_routes_v2_stream.py -q
```

Expected: FAIL with `404`.

- [ ] **Step 3: Implement route**

Import `json` and `StreamingResponse`, then add:

```python
def _stream_json_frame(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def stream_reply(payload: ChatReplyRequestV2, current_user: dict = Depends(get_current_user)):
    def generate():
        try:
            for event in _get_reply_service().reply_stream(_with_owner(payload, current_user)):
                yield _stream_json_frame(event)
        except Exception as exc:
            yield _stream_json_frame({"type": "error", "payload": {"message": str(exc), "conversation_id": payload.conversation_id or ""}})

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 4: Verify green**

Run the focused pytest command again. Expected: PASS.

---

### Task 5: Frontend Stream Client

**Files:**
- Modify: `Edu_AI/src/services/teacher/chatV2.ts`
- Modify: `Edu_AI/src/services/teacher/chatV2.helpers.test.ts`

- [ ] **Step 1: Write parser contract test**

Replace `chatV2.helpers.test.ts` with:

```ts
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseChatReplyV2StreamChunk } from './chatV2';

test('parseChatReplyV2StreamChunk parses complete SSE frames and preserves remainder', () => {
  const parsed = parseChatReplyV2StreamChunk('', 'data: {"type":"metadata","payload":{"conversation_id":"conv-1"}}\n\ndata: {"type":"delta","payload":{"content":"he');
  assert.equal(parsed.events.length, 1);
  assert.equal(parsed.events[0].type, 'metadata');
  assert.equal(parsed.remainder, 'data: {"type":"delta","payload":{"content":"he');
});
```

- [ ] **Step 2: Verify red**

Run:

```powershell
node --test Edu_AI/src/services/teacher/chatV2.helpers.test.ts
```

Expected: FAIL because parser export is missing. If TypeScript cannot run with `node --test`, record that limitation and use `cmd /c npm run build` as executable frontend verification.

- [ ] **Step 3: Implement parser and stream client**

Add stream event types, `parseChatReplyV2StreamChunk(previousRemainder, chunk)`, and `sendChatReplyV2Stream(payload, handlers)`. The client must POST JSON to `/api/chat/v2/stream`, read `response.body.getReader()`, decode chunks with `TextDecoder`, parse `data:` frames, and dispatch `onMetadata`, `onStatus`, `onDelta`, `onResult`, `onDone`, and `onError`.

- [ ] **Step 4: Verify frontend build**

Run:

```powershell
cmd /c npm run build
```

Expected: build PASS, or report exact unrelated pre-existing errors.

---

### Task 6: ChatPanel Streaming Integration

**Files:**
- Modify: `Edu_AI/src/components/teacher/ChatPanel.tsx`

- [ ] **Step 1: Replace import**

Replace `sendChatReplyV2` with `sendChatReplyV2Stream` in the `chatV2` import.

- [ ] **Step 2: Extract final response handling**

Move the current code after `const response = await sendChatReplyV2(...)` into a local helper named `applyFinalChatResponse(response, currentConversationIdAtSend)`. The helper must keep conversation id updates, `setStatusCard`, workflow updates, generated file extraction, course material persistence, viewing file selection, final message replacement, and `refreshHistoryList`.

Use this minimum shape:

```ts
const applyFinalChatResponse = async (response: ChatResponseV2, currentConversationIdAtSend: string | null) => {
  const nextConversationId = String(response.conversation?.conversation_id || '').trim();
  if (nextConversationId && nextConversationId !== currentConversationId) setCurrentConversationId(nextConversationId);
  setStatusCard(response.status_card || null);
  setWorkflowType(String(response.workflow?.type || '').trim() || null);
  setWorkflowStatus(String(response.workflow?.status || '').trim() || null);
  const sources = Array.isArray(response.sources) ? (response.sources as ChatSourceV2[]) : [];
  const generatedFiles = extractGeneratedFilesFromV2Response(response).map((file) => ({ ...file, meta: { ...(file.meta || {}), origin: 'conversation', conversationId: nextConversationId || currentConversationIdAtSend } }));
  generatedFiles.forEach((file) => addGeneratedFile(file));
  const replyText = generatedFiles.some((file) => file.meta?.kind === 'final_report') ? '已生成，请在右侧查看。' : String(response.message?.content || '');
  updateLastMessage({ text: replyText, sources, statusText: '' });
  await refreshHistoryList();
};
```

- [ ] **Step 3: Consume stream events**

Replace the non-stream request with:

```ts
let streamedText = '';
let finalResponse: ChatResponseV2 | null = null;
await sendChatReplyV2Stream(payload, {
  onMetadata: (payload) => {
    const nextConversationId = String(payload.conversation_id || '').trim();
    if (nextConversationId && nextConversationId !== currentConversationId) setCurrentConversationId(nextConversationId);
    if (Array.isArray(payload.sources)) updateLastMessage({ sources: payload.sources as ChatSourceV2[], statusText: '正在生成回复...' });
    if (payload.status_card && typeof payload.status_card === 'object') setStatusCard(payload.status_card as any);
  },
  onStatus: (payload) => {
    updateLastMessage({ statusText: String(payload.label || payload.stage || '正在处理...') });
    const workflow = payload.workflow as any;
    if (workflow) {
      setWorkflowType(String(workflow.type || '').trim() || null);
      setWorkflowStatus(String(workflow.status || '').trim() || null);
    }
  },
  onDelta: (content) => {
    streamedText += content;
    updateLastMessage({ text: streamedText, statusText: '正在生成回复...' });
  },
  onResult: (response) => {
    finalResponse = response;
  },
  onError: (error) => {
    throw error;
  },
});
if (finalResponse) await applyFinalChatResponse(finalResponse, currentConversationId);
```

- [ ] **Step 4: Preserve cleanup semantics**

Keep `clearPendingImages()` and `clearPendingVideos()` only after successful final result handling. Expected: sent images/videos display immediately and remain in reloaded history because final backend persistence still uses `write_v2_result`.

---

### Task 7: Verification

**Files:** no new files unless verification exposes a focused fix.

- [ ] **Step 1: Run focused backend streaming tests**

Run:

```powershell
python -m pytest `
  Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py::test_fast_runtime_run_stream_emits_metadata_delta_and_result_in_order `
  Edu_AI/api/Edu_AI/tests/chat/test_main_orchestrator_stream.py `
  Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_stream.py `
  Edu_AI/api/Edu_AI/tests/chat/test_routes_v2_stream.py `
  -q
```

Expected: all focused tests PASS.

- [ ] **Step 2: Run related backend regression tests**

Run:

```powershell
python -m pytest `
  Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py `
  Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py `
  Edu_AI/api/Edu_AI/tests/chat/test_fast_chat_runtime.py `
  -q
```

Expected: all related tests PASS.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
cmd /c npm run build
```

Expected: build PASS, or report exact unrelated pre-existing errors.

- [ ] **Step 4: Manual smoke check**

Run:

```text
1. Send a normal chat message and confirm the AI bubble fills incrementally.
2. Enable RAG, select one document, and confirm sources appear before or during answer generation.
3. Paste an image, ask about it, and confirm the user message displays the image above text immediately.
4. Reload the conversation and confirm image, user text, assistant answer, status card, and sources remain in history.
5. Trigger a workflow reply and confirm status text changes before final result/artifacts appear.
```

---

## Self-Review

- Spec coverage: This plan covers the POST stream route, metadata/status/delta/result/done envelopes, fast-path true streaming, workflow streaming facade, centralized final persistence, frontend stream consumption, and multimodal/history preservation.
- Placeholder scan: No unresolved placeholders are intentionally left. The frontend parser test notes the current TypeScript runner limitation and keeps `npm run build` as the executable verification.
- Type consistency: Backend and frontend both use `{"type": string, "payload": object}` envelopes. Final `result` remains compatible with `ChatResponseV2`.
