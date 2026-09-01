# Report Artifact Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users add a generated report outline or report body into the chat as an explicit reference card, issue structure-based edit instructions, and receive a new persisted version plus report-generation state.

**Architecture:** Extend the existing chat v2 request/state model with an `artifact_reference` payload, persist the active reference in conversation state, add a report structure parser plus edit-intent normalization layer, and route the first-stage MVP into a report-specific versioned edit workflow. Frontend remains card-driven; backend remains artifact/workflow-state driven.

**Tech Stack:** React, TypeScript, Zustand, Ant Design, FastAPI, Pydantic, existing chat v2/report workflow runtime, pytest, lightweight frontend node tests.

---

## File Map

### Frontend files to modify
- `frontend/src/services/teacher/chatV2.ts`
  - Extend request typing for `artifact_reference`.
- `frontend/src/store/teacher/useStore.ts`
  - Persist active artifact reference and expose actions to set/clear it.
- `frontend/src/components/teacher/StudioPanel.tsx`
  - Add `添加到对话` action for report artifacts.
- `frontend/src/components/teacher/ChatPanel.tsx`
  - Render the reference card, include reference in send payload, restore reference from conversation detail.
- `frontend/src/services/teacher/chatV2.helpers.ts`
  - Extract and restore version metadata / generation state from backend artifacts.
- `frontend/src/services/teacher/materials.helpers.ts`
  - Keep newest derived versions at the top and preserve version metadata for list rendering.
- `frontend/src/services/teacher/api.ts`
  - Carry reference-aware conversation detail fields if frontend restore needs a typed helper.

### Frontend files to create
- `frontend/tests/frontend/chatPanel.artifact-reference.test.ts`
  - Reference card behavior, send payload shape, restore behavior.
- `frontend/tests/frontend/studioPanel.add-to-chat.test.ts`
  - `添加到对话` action availability and store write.

### Backend files to modify
- `backend/src/app/chat/api/schemas_v2.py`
  - Add `ArtifactReferencePayload` and request fields.
- `backend/src/app/chat/persistence/conversation_store_adapter.py`
  - Persist active artifact reference and active reference mode in state.
- `backend/src/app/chat/orchestrator/context_builder.py`
  - Restore active reference into snapshot-compatible structures.
- `backend/src/app/chat/domain/conversation_snapshot.py`
  - Add reference payload fields if needed for runtime decisions.
- `backend/src/app/chat/domain/generation_context.py`
  - Surface active artifact reference / generation state to report workflow.
- `backend/src/app/chat/application/reply_service_v2.py`
  - Detect reference-aware report edit flow and dispatch into report edit service/runtime.
- `backend/src/app/chat/application/report_service_v2.py`
  - Add version metadata sync, generation-state persistence, and compact reply behavior for derived artifacts.
- `backend/src/app/chat/orchestrator/route_rules.py`
  - Prioritize artifact-edit route when `artifact_reference` is present.
- `backend/src/core/conversation_storage.py`
  - Preserve reference state in conversation detail payload.
- `backend/src/core/course_storage.py`
  - Persist derived report versions and generation-state metadata in generated materials.

### Backend files to create
- `backend/src/app/chat/domain/artifact_reference.py`
  - Shared typed models for reference payload, version metadata, generation state, edit request.
- `backend/src/app/chat/orchestrator/report_structure_parser.py`
  - Normalize report outline/report markdown into structure nodes.
- `backend/src/app/chat/orchestrator/report_edit_intent_parser.py`
  - Turn `artifact_reference + user text` into a normalized `ArtifactEditRequest`.
- `backend/src/app/chat/workflows/report/edit_runtime.py`
  - Stage-one MVP runtime for outline section rewrite, regenerate from outline, report summary/conclusion rewrite.

### Backend tests to create
- `backend/src/tests/chat/test_report_structure_parser.py`
- `backend/src/tests/chat/test_report_edit_intent_parser.py`
- `backend/src/tests/chat/test_reply_service_v2_artifact_reference.py`
- `backend/src/tests/chat/test_report_edit_runtime.py`
- `backend/src/tests/core/test_conversation_storage_artifact_reference.py`

## Task 1: Frontend Artifact Reference State

**Files:**
- Modify: `frontend/src/services/teacher/chatV2.ts`
- Modify: `frontend/src/store/teacher/useStore.ts`
- Test: `frontend/tests/frontend/chatPanel.artifact-reference.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import assert from 'node:assert/strict';
import { useStore } from '../../src/store/teacher/useStore';

useStore.getState().setCurrentConversationId('conv-1');
useStore.getState().setArtifactReference?.({
  artifactId: 'report-1',
  artifactType: 'report',
  versionId: 'v1',
  title: '李白性格分析',
  sourceConversationId: 'conv-1',
  sourceCourseId: 'course-1',
});

assert.equal(useStore.getState().artifactReference?.artifactId, 'report-1');
useStore.getState().clearArtifactReference?.();
assert.equal(useStore.getState().artifactReference, null);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --experimental-strip-types frontend/tests/frontend/chatPanel.artifact-reference.test.ts`
Expected: FAIL because `artifactReference` state/actions do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```ts
export interface ArtifactReference {
  artifactId: string;
  artifactType: 'report' | 'report_outline';
  versionId?: string;
  title?: string;
  sourceConversationId?: string;
  sourceCourseId?: string;
}

artifactReference: ArtifactReference | null;
setArtifactReference: (reference: ArtifactReference | null) => void;
clearArtifactReference: () => void;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --experimental-strip-types frontend/tests/frontend/chatPanel.artifact-reference.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/teacher/chatV2.ts frontend/src/store/teacher/useStore.ts frontend/tests/frontend/chatPanel.artifact-reference.test.ts
git commit -m "feat: add frontend artifact reference state"
```

## Task 2: Right-Side “添加到对话” Action And Reference Card

**Files:**
- Modify: `frontend/src/components/teacher/StudioPanel.tsx`
- Modify: `frontend/src/components/teacher/ChatPanel.tsx`
- Test: `frontend/tests/frontend/studioPanel.add-to-chat.test.ts`
- Test: `frontend/tests/frontend/chatPanel.artifact-reference.test.ts`

- [ ] **Step 1: Write the failing tests**

```ts
import assert from 'node:assert/strict';
import { useStore } from '../../src/store/teacher/useStore';

const generated = {
  id: 'report-1',
  name: '李白性格分析.md',
  type: 'report' as const,
  meta: { versionId: 'v1', kind: 'final_report', conversationId: 'conv-1', courseId: 'course-1' },
};

useStore.getState().addGeneratedFile(generated);
useStore.getState().setArtifactReference?.({
  artifactId: generated.id,
  artifactType: 'report',
  versionId: 'v1',
  title: generated.name,
  sourceConversationId: 'conv-1',
  sourceCourseId: 'course-1',
});

assert.equal(useStore.getState().artifactReference?.title, '李白性格分析.md');
```

```ts
// in chat panel test
assert.deepEqual(sentPayload.artifact_reference, {
  artifact_id: 'report-1',
  artifact_type: 'report',
  version_id: 'v1',
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `node --experimental-strip-types frontend/tests/frontend/studioPanel.add-to-chat.test.ts`
- `node --experimental-strip-types frontend/tests/frontend/chatPanel.artifact-reference.test.ts`

Expected: FAIL because StudioPanel has no add-to-chat action and ChatPanel does not send reference payload.

- [ ] **Step 3: Write minimal implementation**

```tsx
{
  key: 'add-to-chat',
  label: '添加到对话',
  icon: <MessageOutlined />,
  onClick: (info) => {
    info.domEvent.stopPropagation();
    setArtifactReference({
      artifactId: item.id,
      artifactType: item.meta?.kind === 'outline' ? 'report_outline' : 'report',
      versionId: String(item.meta?.versionId || ''),
      title: item.name,
      sourceConversationId: String(item.meta?.conversationId || ''),
      sourceCourseId: String(courseId || ''),
    });
  },
}
```

```tsx
{artifactReference ? (
  <Card size="small">
    <Text strong>{artifactReference.title}</Text>
    <Button type="text" onClick={() => clearArtifactReference()}>移除引用</Button>
  </Card>
) : null}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
- `node --experimental-strip-types frontend/tests/frontend/studioPanel.add-to-chat.test.ts`
- `node --experimental-strip-types frontend/tests/frontend/chatPanel.artifact-reference.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/teacher/StudioPanel.tsx frontend/src/components/teacher/ChatPanel.tsx frontend/tests/frontend/studioPanel.add-to-chat.test.ts frontend/tests/frontend/chatPanel.artifact-reference.test.ts
git commit -m "feat: add report artifact references to chat UI"
```

## Task 3: Backend Request Schema And Conversation State Persistence

**Files:**
- Modify: `backend/src/app/chat/api/schemas_v2.py`
- Create: `backend/src/app/chat/domain/artifact_reference.py`
- Modify: `backend/src/app/chat/persistence/conversation_store_adapter.py`
- Modify: `backend/src/app/chat/orchestrator/context_builder.py`
- Modify: `backend/src/core/conversation_storage.py`
- Test: `backend/src/tests/core/test_conversation_storage_artifact_reference.py`
- Test: `backend/src/tests/chat/test_reply_service_v2_artifact_reference.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_write_v2_result_persists_active_artifact_reference():
    request = SimpleNamespace(
        question="重写结论",
        conversation_id="conv-1",
        course_id="course-1",
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        capability=SimpleNamespace(allow_rag=False, allow_web=False, selected_doc_ids=[]),
    )
    result = {"message": {"content": "已生成，请在右侧查看。"}, "action": {"name": "report.edit"}, "artifacts": []}
    adapter.write_v2_result("conv-1", request, result)
    state = storage.get_state("conv-1")
    assert state["active_context"]["active_artifact_id"] == "report-1"
    assert state["active_context"]["active_reference_mode"] == "artifact_edit"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `d:\\github\\edu_ai\\Edu_AI\\api\\Edu_AI\\.venv\\Scripts\\python.exe -m pytest backend/src/tests/core/test_conversation_storage_artifact_reference.py -q`
- `d:\\github\\edu_ai\\Edu_AI\\api\\Edu_AI\\.venv\\Scripts\\python.exe -m pytest backend/src/tests/chat/test_reply_service_v2_artifact_reference.py -q`

Expected: FAIL because request schema and persistence do not support artifact reference yet.

- [ ] **Step 3: Write minimal implementation**

```python
class ArtifactReferencePayload(BaseModel):
    artifact_id: str
    artifact_type: Literal["report", "report_outline"]
    version_id: Optional[str] = None
    title: Optional[str] = None
    source_conversation_id: Optional[str] = None
    source_course_id: Optional[str] = None
```

```python
if getattr(request, "artifact_reference", None):
    ref = request.artifact_reference
    state_patch["active_artifact"] = {
        "artifact_id": ref.get("artifact_id") or "",
        "artifact_type": ref.get("artifact_type") or "",
        "title": ref.get("title"),
    }
    state_patch["active_context"] = {
        **state_patch.get("active_context", {}),
        "active_artifact_id": ref.get("artifact_id") or "",
        "active_artifact_type": ref.get("artifact_type") or "",
        "active_reference_mode": "artifact_edit",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run the same pytest commands.
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/chat/api/schemas_v2.py backend/src/app/chat/domain/artifact_reference.py backend/src/app/chat/persistence/conversation_store_adapter.py backend/src/app/chat/orchestrator/context_builder.py backend/src/core/conversation_storage.py backend/src/tests/core/test_conversation_storage_artifact_reference.py backend/src/tests/chat/test_reply_service_v2_artifact_reference.py
git commit -m "feat: persist chat artifact references"
```

## Task 4: Report Structure Parser And Edit Intent Parser

**Files:**
- Create: `backend/src/app/chat/orchestrator/report_structure_parser.py`
- Create: `backend/src/app/chat/orchestrator/report_edit_intent_parser.py`
- Create: `backend/src/tests/chat/test_report_structure_parser.py`
- Create: `backend/src/tests/chat/test_report_edit_intent_parser.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_markdown_report_nodes():
    content = "# 标题\n\n## 摘要\n内容A\n\n## 第二部分\n内容B\n\n## 结论\n内容C"
    nodes = parse_report_nodes(artifact_id="report-1", version_id="v1", content=content)
    assert [node["node_type"] for node in nodes] == ["section", "section", "conclusion"]
    assert nodes[1]["title"] == "第二部分"
```

```python
def test_parse_edit_intent_for_summary_compress():
    request = parse_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="把摘要压缩到150字以内",
        structure_nodes=[{"node_id": "summary-1", "node_type": "summary", "title": "摘要"}],
    )
    assert request["target_type"] == "report"
    assert request["action_type"] == "compress"
    assert request["target_node_id"] == "summary-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `d:\\github\\edu_ai\\Edu_AI\\api\\Edu_AI\\.venv\\Scripts\\python.exe -m pytest backend/src/tests/chat/test_report_structure_parser.py -q`
- `d:\\github\\edu_ai\\Edu_AI\\api\\Edu_AI\\.venv\\Scripts\\python.exe -m pytest backend/src/tests/chat/test_report_edit_intent_parser.py -q`

Expected: FAIL because parser modules do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def parse_report_nodes(*, artifact_id: str, version_id: str, content: str) -> list[dict]:
    nodes = []
    current_title = None
    current_lines: list[str] = []
    order_index = 0
    for line in str(content or "").splitlines():
        match = re.match(r"^#{1,6}\\s+(.+)$", line.strip())
        if match:
            if current_title and current_lines:
                order_index += 1
                nodes.append(_make_node(...))
            current_title = match.group(1).strip()
            current_lines = []
            continue
        current_lines.append(line)
    ...
```

```python
if "摘要" in question and any(node["node_type"] == "summary" for node in structure_nodes):
    return {..., "action_type": "compress", "target_node_id": summary_node["node_id"]}
```

- [ ] **Step 4: Run tests to verify they pass**

Run the same pytest commands.
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/chat/orchestrator/report_structure_parser.py backend/src/app/chat/orchestrator/report_edit_intent_parser.py backend/src/tests/chat/test_report_structure_parser.py backend/src/tests/chat/test_report_edit_intent_parser.py
git commit -m "feat: parse report structure and edit intent"
```

## Task 5: Stage-One Report Edit Runtime

**Files:**
- Create: `backend/src/app/chat/workflows/report/edit_runtime.py`
- Modify: `backend/src/app/chat/application/reply_service_v2.py`
- Modify: `backend/src/app/chat/application/report_service_v2.py`
- Modify: `backend/src/app/chat/orchestrator/route_rules.py`
- Modify: `backend/src/app/chat/domain/generation_context.py`
- Test: `backend/src/tests/chat/test_report_edit_runtime.py`
- Test: `backend/src/tests/chat/test_reply_service_v2_artifact_reference.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_report_edit_runtime_rewrites_summary_and_returns_new_artifact():
    runtime = ReportEditRuntime(model_gateway=FakeGateway("## 摘要\\n新摘要"))
    result = runtime.run(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="把摘要压缩到150字以内",
        source_artifact={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析.md", "content": REPORT_MD},
    )
    report_artifact = next(a for a in result["artifacts"] if a["artifact_type"] == "report")
    assert report_artifact["artifact_id"] != "report-1"
    assert report_artifact["version"]["parent_artifact_id"] == "report-1"
    assert result["message"]["content"] == "已生成，请在右侧查看。"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `d:\\github\\edu_ai\\Edu_AI\\api\\Edu_AI\\.venv\\Scripts\\python.exe -m pytest backend/src/tests/chat/test_report_edit_runtime.py -q`
- `d:\\github\\edu_ai\\Edu_AI\\api\\Edu_AI\\.venv\\Scripts\\python.exe -m pytest backend/src/tests/chat/test_reply_service_v2_artifact_reference.py -q`

Expected: FAIL because no edit runtime or route exists.

- [ ] **Step 3: Write minimal implementation**

```python
class ReportEditRuntime:
    def run(self, *, artifact_reference: dict, question: str, source_artifact: dict) -> dict:
        nodes = parse_report_nodes(...)
        edit_request = parse_edit_intent(...)
        if edit_request["action_type"] == "regenerate":
            return self._regenerate_from_outline(...)
        return self._rewrite_single_node(...)
```

```python
if getattr(request, "artifact_reference", None):
    return self.report_edit_runtime.run_from_request(request=request, snapshot=snapshot)
```

- [ ] **Step 4: Run tests to verify they pass**

Run the same pytest commands.
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/chat/workflows/report/edit_runtime.py backend/src/app/chat/application/reply_service_v2.py backend/src/app/chat/application/report_service_v2.py backend/src/app/chat/orchestrator/route_rules.py backend/src/app/chat/domain/generation_context.py backend/src/tests/chat/test_report_edit_runtime.py backend/src/tests/chat/test_reply_service_v2_artifact_reference.py
git commit -m "feat: add report artifact edit runtime"
```

## Task 6: Version Metadata, Generation State, And Course Material Persistence

**Files:**
- Modify: `backend/src/app/chat/application/report_service_v2.py`
- Modify: `backend/src/core/course_storage.py`
- Modify: `frontend/src/services/teacher/chatV2.helpers.ts`
- Modify: `frontend/src/services/teacher/materials.helpers.ts`
- Test: `backend/src/tests/chat/test_report_service_v2.py`
- Test: `frontend/tests/frontend/chatPanel.artifact-reference.test.ts`

- [ ] **Step 1: Write the failing tests**

```python
def test_finalize_report_result_preserves_generation_state_and_version_metadata():
    result = {
        "artifacts": [{
            "artifact_id": "report-v2",
            "artifact_type": "report",
            "title": "李白性格分析.md",
            "content": REPORT_MD,
            "version": {"root_artifact_id": "report-v1", "parent_artifact_id": "report-v1", "version_number": 2},
            "generation_state": {"topic": "李白性格", "generation_mode": "revise_report"},
        }]
    }
    finalize_report_result(payload=payload, result=result, course_storage_manager=manager, compact_message=True)
    stored = manager.get_generated_material(course_id="course-1", material_id="report-v2")
    assert stored["metadata"]["version"]["version_number"] == 2
    assert stored["metadata"]["generation_state"]["generation_mode"] == "revise_report"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `d:\\github\\edu_ai\\Edu_AI\\api\\Edu_AI\\.venv\\Scripts\\python.exe -m pytest backend/src/tests/chat/test_report_service_v2.py -q`
- `node --experimental-strip-types frontend/tests/frontend/chatPanel.artifact-reference.test.ts`

Expected: FAIL because metadata is not yet preserved end-to-end.

- [ ] **Step 3: Write minimal implementation**

```python
metadata = {
    "version": dict(report_artifact.get("version") or {}),
    "generation_state": dict(report_artifact.get("generation_state") or {}),
}
```

```ts
meta: {
  ...file.meta,
  versionId: artifact.version?.version_id,
  versionNumber: artifact.version?.version_number,
  parentArtifactId: artifact.version?.parent_artifact_id,
  generationState: artifact.generation_state,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run the same commands.
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/chat/application/report_service_v2.py backend/src/core/course_storage.py frontend/src/services/teacher/chatV2.helpers.ts frontend/src/services/teacher/materials.helpers.ts backend/src/tests/chat/test_report_service_v2.py frontend/tests/frontend/chatPanel.artifact-reference.test.ts
git commit -m "feat: persist report version metadata and generation state"
```

## Task 7: End-To-End Verification

**Files:**
- Test: `backend/src/tests/chat/test_reply_service_v2_artifact_reference.py`
- Test: `backend/src/tests/chat/test_report_edit_runtime.py`
- Test: `frontend/tests/frontend/chatPanel.artifact-reference.test.ts`
- Test: `frontend/tests/frontend/studioPanel.add-to-chat.test.ts`

- [ ] **Step 1: Run backend targeted test suite**

Run:
```bash
d:\github\edu_ai\backend\src\.venv\Scripts\python.exe -m pytest \
  backend/src/tests/chat/test_report_structure_parser.py \
  backend/src/tests/chat/test_report_edit_intent_parser.py \
  backend/src/tests/chat/test_report_edit_runtime.py \
  backend/src/tests/chat/test_reply_service_v2_artifact_reference.py \
  backend/src/tests/chat/test_report_service_v2.py -q
```

Expected: PASS

- [ ] **Step 2: Run frontend targeted tests**

Run:
```bash
node --experimental-strip-types frontend/tests/frontend/chatPanel.artifact-reference.test.ts
node --experimental-strip-types frontend/tests/frontend/studioPanel.add-to-chat.test.ts
```

Expected: PASS

- [ ] **Step 3: Run production build**

Run:
```bash
cd d:\github\edu_ai\Edu_AI
npm.cmd run build
```

Expected: PASS

- [ ] **Step 4: Manual smoke checks**

Verify:
- Right-side report outline can be added to chat as a card
- `修改第三部分` creates a new outline version
- `基于这个大纲重新生成一版正式报告` creates a new report version
- Referencing a report and asking `把摘要压缩到150字以内` creates a new report version
- New versions appear at top of right-side list and in course materials

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: add report artifact editing workflow"
```

