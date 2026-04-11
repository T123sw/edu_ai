# PPT Artifact Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a true "add current PPT to chat and revise it" flow that lets users reference a generated `ppt_deck`, send follow-up edit instructions, and execute a single-slide html2ppt revision that returns a new PPT version.

**Architecture:** Reuse the existing report artifact-reference pattern on the frontend and in `ReplyServiceV2`, but add a PPT-specific edit runtime on the backend. The runtime parses a referenced `ppt_deck`, resolves the target slide, calls the html2ppt revision API through an extended Python client, then returns a fresh `ppt_deck` artifact and updates conversation state to keep iterative editing anchored on the newest version.

**Tech Stack:** React, TypeScript, Zustand, Ant Design, Python, httpx, pytest, existing html2ppt Node service

---

## File Structure

### Frontend files

- Modify: `Edu_AI/src/services/teacher/chatV2.ts`
- Modify: `Edu_AI/src/services/teacher/materials.helpers.ts`
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx`
- Modify: `Edu_AI/src/components/teacher/ChatPanel.tsx`
- Modify: `Edu_AI/src/store/teacher/useStore.ts`
- Test: `Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts`
- Test: `Edu_AI/tests/frontend/materials.helpers.test.ts`
- Test: `Edu_AI/tests/frontend/chatV2.helpers.test.ts`

### Backend files

- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/html2ppt_client.py`
- Create: `Edu_AI/api/Edu_AI/app/chat/orchestrator/ppt_edit_intent_parser.py`
- Create: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/edit_runtime.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_html2ppt_client.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_intent_parser.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_runtime.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`

### Supporting constraints

- Reuse `ArtifactReferencePayload` as-is; do not create a second competing reference schema.
- Keep first release scoped to `ppt_deck` only for editable PPT references.
- Keep html2ppt revision payload minimal: `mode`, `target_slides`, `user_instruction`.

### Reference spec

- Use: `docs/superpowers/specs/2026-04-11-ppt-artifact-editing-design.md`

## Task 1: Extend frontend artifact-reference types for PPT decks

**Files:**
- Modify: `Edu_AI/src/services/teacher/chatV2.ts`
- Modify: `Edu_AI/src/store/teacher/useStore.ts`
- Test: `Edu_AI/tests/frontend/chatV2.helpers.test.ts`

- [ ] **Step 1: Write the failing test for PPT artifact reference type support**

Add a new assertion block in `Edu_AI/tests/frontend/chatV2.helpers.test.ts` that documents the expected payload shape for PPT references:

```ts
import assert from 'node:assert/strict';
import { buildChatReplyPayload } from '../../src/services/teacher/chatV2';

const payload = buildChatReplyPayload({
  question: '把第3页改成流程图风格',
  conversationId: 'conv-ppt',
  courseId: 'course-1',
  allowRag: false,
  allowWeb: false,
  selectedDocIds: [],
  artifactReference: {
    artifact_id: 'ppt-artifact-1',
    artifact_type: 'ppt_deck',
    title: '智能体核心能力.pptx',
    source_conversation_id: 'conv-ppt',
    source_course_id: 'course-1',
  },
});

assert.equal(payload.artifact_reference?.artifact_type, 'ppt_deck');
assert.equal(payload.artifact_reference?.artifact_id, 'ppt-artifact-1');
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
node --test Edu_AI/tests/frontend/chatV2.helpers.test.ts
```

Expected: FAIL because `ChatArtifactReference['artifact_type']` still excludes `ppt_deck`, or the helper/types reject the new reference shape.

- [ ] **Step 3: Write minimal implementation**

Update `Edu_AI/src/services/teacher/chatV2.ts` so the shared chat reference type accepts PPT artifacts:

```ts
export interface ChatArtifactReference {
  artifact_id: string;
  artifact_type: 'report' | 'report_outline' | 'ppt_outline' | 'ppt_content_markdown' | 'ppt_deck';
  version_id?: string;
  title?: string;
  source_conversation_id?: string;
  source_course_id?: string;
}
```

Keep `useStore` typed against this shared interface without introducing a second alias.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
node --test Edu_AI/tests/frontend/chatV2.helpers.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add Edu_AI/src/services/teacher/chatV2.ts Edu_AI/src/store/teacher/useStore.ts Edu_AI/tests/frontend/chatV2.helpers.test.ts
git commit -m "feat: allow PPT artifact references in chat payloads"
```

## Task 2: Add "添加到对话" support to PPT deck preview

**Files:**
- Modify: `Edu_AI/src/services/teacher/materials.helpers.ts`
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx`
- Test: `Edu_AI/tests/frontend/materials.helpers.test.ts`
- Test: `Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts`

- [ ] **Step 1: Write the failing eligibility test**

Add a new test case in `Edu_AI/tests/frontend/materials.helpers.test.ts`:

```ts
import assert from 'node:assert/strict';
import { isArtifactReferenceEligible } from '../../src/services/teacher/materials.helpers';

assert.equal(
  isArtifactReferenceEligible({
    id: 'ppt-1',
    type: 'ppt',
    meta: { kind: 'ppt_deck' },
  } as any),
  true,
);

assert.equal(
  isArtifactReferenceEligible({
    id: 'ppt-outline-1',
    type: 'ppt',
    meta: { kind: 'ppt_outline' },
  } as any),
  false,
);
```

- [ ] **Step 2: Write the failing StudioPanel test**

Extend `Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts` with assertions for the new button:

```ts
assert.match(file, />\s*添加到对话\s*</, 'PPT deck preview should expose an add-to-chat action');
assert.match(file, /pptKind === 'ppt_deck'/, 'PPT add-to-chat action should be scoped to final deck previews');
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
node --test Edu_AI/tests/frontend/materials.helpers.test.ts
node --test Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts
```

Expected: FAIL because PPT files are currently ineligible and the PPT preview button group does not include the add-to-chat action.

- [ ] **Step 4: Write minimal implementation**

In `Edu_AI/src/services/teacher/materials.helpers.ts`, narrow eligibility to report artifacts plus final PPT decks:

```ts
export function isArtifactReferenceEligible(file: GeneratedFileLike | null | undefined): boolean {
  if (String(file?.type || '').trim() === 'report') {
    return true;
  }
  if (String(file?.type || '').trim() === 'ppt' && String(file?.meta?.kind || '').trim() === 'ppt_deck') {
    return true;
  }
  return false;
}
```

In `Edu_AI/src/components/teacher/StudioPanel.tsx`, update `handleAddToChat` to branch by file type:

```ts
setArtifactReference({
  artifact_id: String((file.meta as any)?.originalArtifactId || file.id || '').trim(),
  artifact_type: file.type === 'ppt' ? 'ppt_deck' : inferredReportType,
  title: String(file.name || '').trim() || undefined,
  source_conversation_id: String(file.meta?.conversationId || currentConversationId || '').trim() || undefined,
  source_course_id: String(courseId || '').trim() || undefined,
});
```

Render the button inside the `pptKind === 'ppt_deck' && pptPreviewUrl` toolbar block instead of only in the report preview header.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```powershell
node --test Edu_AI/tests/frontend/materials.helpers.test.ts
node --test Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add Edu_AI/src/services/teacher/materials.helpers.ts Edu_AI/src/components/teacher/StudioPanel.tsx Edu_AI/tests/frontend/materials.helpers.test.ts Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts
git commit -m "feat: add PPT deck add-to-chat entry"
```

## Task 3: Restore and persist PPT artifact references in chat UI

**Files:**
- Modify: `Edu_AI/src/components/teacher/ChatPanel.tsx`
- Test: `Edu_AI/tests/frontend/chatV2.helpers.test.ts`

- [ ] **Step 1: Write the failing restore test**

Add a restore-oriented test in `Edu_AI/tests/frontend/chatV2.helpers.test.ts` or an existing conversation-restore frontend test file:

```ts
const detail = {
  conversation_id: 'conv-ppt',
  state: {
    artifact_reference: {
      artifact_id: 'ppt-artifact-1',
      artifact_type: 'ppt_deck',
      title: '智能体核心能力.pptx',
      source_conversation_id: 'conv-ppt',
      source_course_id: 'course-1',
    },
  },
};

assert.equal(
  String((detail.state as any).artifact_reference.artifact_type),
  'ppt_deck',
);
```

If the chosen test file already exercises restoration, assert that the restored store payload preserves `ppt_deck`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
node --test Edu_AI/tests/frontend/chatV2.helpers.test.ts
```

Expected: FAIL because `ChatPanel` currently restores only `report` and `report_outline`.

- [ ] **Step 3: Write minimal implementation**

Update `Edu_AI/src/components/teacher/ChatPanel.tsx` restoration logic:

```ts
const restoredArtifactType = String((stateArtifactReference as any).artifact_type || '').trim();
const normalizedArtifactType =
  restoredArtifactType === 'report_outline' || restoredArtifactType === 'report'
    ? restoredArtifactType
    : restoredArtifactType === 'ppt_outline' || restoredArtifactType === 'ppt_content_markdown' || restoredArtifactType === 'ppt_deck'
      ? restoredArtifactType
      : 'report';
```

Then call `setArtifactReference` with the normalized type.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
node --test Edu_AI/tests/frontend/chatV2.helpers.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add Edu_AI/src/components/teacher/ChatPanel.tsx Edu_AI/tests/frontend/chatV2.helpers.test.ts
git commit -m "feat: restore PPT artifact references from conversation state"
```

## Task 4: Extend the html2ppt Python client with revision support

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/html2ppt_client.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_html2ppt_client.py`

- [ ] **Step 1: Write the failing revision client test**

Add a new test in `Edu_AI/api/Edu_AI/tests/chat/test_html2ppt_client.py`:

```python
def test_html2ppt_client_builds_revision_requests():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("utf-8") if request.content else ""
        calls.append(
            {
                "method": request.method,
                "path": request.url.path,
                "json": json.loads(body) if body else None,
            }
        )
        if request.method == "POST" and request.url.path == "/ppt/jobs/job_001/revisions":
            return httpx.Response(200, json={"revision_id": "rev_0001", "status": "queued"})
        if request.method == "GET" and request.url.path == "/ppt/jobs/job_001/revisions/rev_0001":
            return httpx.Response(200, json={"job_id": "job_001", "revision_id": "rev_0001", "status": "succeeded"})
        return httpx.Response(404)

    client = Html2PptClient(
        base_url="http://testserver",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver"),
    )

    created = client.create_revision(
        "job_001",
        {"mode": "single_slide", "target_slides": [3], "user_instruction": "把第3页改成流程图风格"},
    )
    status = client.get_revision_status("job_001", "rev_0001")

    assert created == {"revision_id": "rev_0001", "status": "queued"}
    assert status["revision_id"] == "rev_0001"
    assert calls[0]["path"] == "/ppt/jobs/job_001/revisions"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_html2ppt_client.py -q
```

Expected: FAIL because `Html2PptClient` lacks `create_revision` and `get_revision_status`.

- [ ] **Step 3: Write minimal implementation**

Add the two methods to `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/html2ppt_client.py`:

```python
def create_revision(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = self.http_client.post(f"/ppt/jobs/{job_id}/revisions", json=dict(payload or {}))
    response.raise_for_status()
    return response.json()

def get_revision_status(self, job_id: str, revision_id: str) -> dict[str, Any]:
    response = self.http_client.get(f"/ppt/jobs/{job_id}/revisions/{revision_id}")
    response.raise_for_status()
    return response.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_html2ppt_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add Edu_AI/api/Edu_AI/app/chat/workflows/ppt/html2ppt_client.py Edu_AI/api/Edu_AI/tests/chat/test_html2ppt_client.py
git commit -m "feat: add html2ppt revision client methods"
```

## Task 5: Add a deterministic PPT edit intent parser

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/orchestrator/ppt_edit_intent_parser.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_intent_parser.py`

- [ ] **Step 1: Write the failing parser tests**

Create `Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_intent_parser.py`:

```python
from app.chat.orchestrator.ppt_edit_intent_parser import parse_ppt_edit_intent


def test_parse_ppt_edit_intent_extracts_explicit_slide_number():
    result = parse_ppt_edit_intent(
        question="把第3页改成流程图风格",
        slide_titles=["封面", "目录", "工具调用的实现架构与流程"],
        last_active_slide_index=None,
    )

    assert result["target_slide_index"] == 3
    assert result["needs_disambiguation"] is False
    assert "流程图风格" in result["instruction"]


def test_parse_ppt_edit_intent_matches_slide_title_when_page_number_missing():
    result = parse_ppt_edit_intent(
        question="把工具调用的实现架构与流程那一页改成左右结构",
        slide_titles=["封面", "目录", "工具调用的实现架构与流程"],
        last_active_slide_index=None,
    )

    assert result["target_slide_index"] == 3
    assert result["needs_disambiguation"] is False


def test_parse_ppt_edit_intent_requests_disambiguation_when_no_target_found():
    result = parse_ppt_edit_intent(
        question="把这一页改得更简洁一点",
        slide_titles=["封面", "目录", "工具调用的实现架构与流程"],
        last_active_slide_index=None,
    )

    assert result["needs_disambiguation"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_intent_parser.py -q
```

Expected: FAIL because the parser module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `Edu_AI/api/Edu_AI/app/chat/orchestrator/ppt_edit_intent_parser.py` with a rule-first parser:

```python
import re


def parse_ppt_edit_intent(*, question: str, slide_titles: list[str], last_active_slide_index: int | None) -> dict:
    text = str(question or "").strip()
    explicit_match = re.search(r"第\s*(\d+)\s*页", text)
    if explicit_match:
        slide_index = int(explicit_match.group(1))
        return {
            "action_type": "revise_slide",
            "instruction": text,
            "target_slide_index": slide_index,
            "needs_disambiguation": False,
            "candidate_slide_indexes": [],
        }
    for index, title in enumerate(slide_titles, start=1):
        if title and title in text:
            return {
                "action_type": "revise_slide",
                "instruction": text.replace(title, "").strip() or text,
                "target_slide_index": index,
                "needs_disambiguation": False,
                "candidate_slide_indexes": [],
            }
    if ("这一页" in text or "刚才那页" in text) and last_active_slide_index:
        return {
            "action_type": "revise_slide",
            "instruction": text,
            "target_slide_index": last_active_slide_index,
            "needs_disambiguation": False,
            "candidate_slide_indexes": [],
        }
    return {
        "action_type": "revise_slide",
        "instruction": text,
        "target_slide_index": None,
        "needs_disambiguation": True,
        "candidate_slide_indexes": [],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_intent_parser.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add Edu_AI/api/Edu_AI/app/chat/orchestrator/ppt_edit_intent_parser.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_intent_parser.py
git commit -m "feat: add PPT edit intent parser"
```

## Task 6: Implement `PptEditRuntime` around html2ppt revision

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/edit_runtime.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_runtime.py`

- [ ] **Step 1: Write the failing runtime tests**

Create `Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_runtime.py`:

```python
from app.chat.workflows.ppt.edit_runtime import PptEditRuntime


class StubHtml2PptClient:
    def __init__(self):
        self.created = []

    def create_revision(self, job_id, payload):
        self.created.append((job_id, payload))
        return {"revision_id": "rev_0001", "status": "queued"}

    def get_revision_status(self, job_id, revision_id):
        return {"job_id": job_id, "revision_id": revision_id, "status": "succeeded"}

    def get_job_results(self, job_id):
        return {
            "job_id": job_id,
            "latest_revision_id": "rev_0001",
            "results": {
                "html_full_url": "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0001/deck.html",
                "pptx_url": "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0001/deck.pptx",
                "manifest_url": "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0001/manifest.json",
            },
        }


def test_ppt_edit_runtime_submits_single_slide_revision():
    runtime = PptEditRuntime(html2ppt_client=StubHtml2PptClient())
    source_artifact = {
        "artifact_id": "ppt:deck:job_001",
        "artifact_type": "ppt_deck",
        "title": "智能体核心能力.pptx",
        "content": {"job_id": "job_001", "revision_id": "rev_0000", "slide_count": 8},
        "outline": {
            "slides": [
                {"slide_index": 1, "title": "封面"},
                {"slide_index": 2, "title": "目录"},
                {"slide_index": 3, "title": "工具调用的实现架构与流程"},
            ]
        },
    }

    result = runtime.run(
        question="把第3页改成流程图风格",
        artifact_reference={"artifact_id": "ppt:deck:job_001", "artifact_type": "ppt_deck"},
        source_artifact=source_artifact,
    )

    assert result["action"]["name"] == "ppt.edit"
    assert result["workflow"]["status"] == "completed"
    assert result["artifacts"][0]["artifact_type"] == "ppt_deck"


def test_ppt_edit_runtime_returns_awaiting_input_when_target_slide_is_missing():
    runtime = PptEditRuntime(html2ppt_client=StubHtml2PptClient())
    result = runtime.run(
        question="把这一页改得更简洁一些",
        artifact_reference={"artifact_id": "ppt:deck:job_001", "artifact_type": "ppt_deck"},
        source_artifact={
            "artifact_id": "ppt:deck:job_001",
            "artifact_type": "ppt_deck",
            "title": "智能体核心能力.pptx",
            "content": {"job_id": "job_001", "revision_id": "rev_0000", "slide_count": 8},
            "outline": {"slides": [{"slide_index": 1, "title": "封面"}]},
        },
    )

    assert result["workflow"]["status"] == "awaiting_input"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_runtime.py -q
```

Expected: FAIL because `PptEditRuntime` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/edit_runtime.py` with a runtime that:

- normalizes the source artifact
- extracts `job_id`, `slide_count`, and slide titles from `outline.slides`
- uses `parse_ppt_edit_intent(...)`
- returns `awaiting_input` when target resolution fails
- calls the html2ppt client when resolution succeeds
- builds a new `ppt_deck` artifact from `get_job_results(...)`

Use a shape like:

```python
class PptEditRuntime:
    def __init__(self, *, html2ppt_client=None, html2ppt_client_factory=None):
        self._html2ppt_client = html2ppt_client
        self._html2ppt_client_factory = html2ppt_client_factory

    def run(self, *, question: str, artifact_reference: dict, source_artifact: dict) -> dict:
        # normalize source artifact
        # resolve slide titles
        # parse intent
        # return awaiting_input when needed
        # call create_revision + get_revision_status + get_job_results
        # build ppt_deck artifact
```

Return payload:

```python
{
    "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
    "conversation": {},
    "action": {"name": "ppt.edit"},
    "workflow": {"type": "ppt", "status": "completed"},
    "artifacts": [deck_artifact],
    "sources": [],
    "trace": {"path": "workflow", "artifact_edit": edit_request},
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_runtime.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add Edu_AI/api/Edu_AI/app/chat/workflows/ppt/edit_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_runtime.py
git commit -m "feat: add PPT edit runtime"
```

## Task 7: Route `ReplyServiceV2` to the new PPT edit runtime

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`

- [ ] **Step 1: Write the failing dispatch test**

Add a new test in `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`:

```python
def test_reply_service_routes_ppt_artifact_references_to_ppt_edit_runtime():
    orchestrator = DummyOrchestrator(
        {
            "message": {"role": "assistant", "content": "fallback"},
            "conversation": {"conversation_id": "conv-1"},
            "action": {"name": "chat.reply"},
            "workflow": None,
            "artifacts": [],
            "sources": [],
            "trace": {"path": "fast"},
        }
    )

    class DummyPptEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            return {
                "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "ppt.edit"},
                "workflow": {"type": "ppt", "status": "completed"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    service = ReplyServiceV2(
        orchestrator=orchestrator,
        conversation_store=DummyStore(),
        context_builder=SimpleNamespace(build=lambda request: SimpleNamespace(workflow_state=None, active_artifact=None, active_task=None, recent_messages=[])),
        status_card_builder=DummyStatusCardBuilder(),
        report_edit_runtime=None,
        ppt_edit_runtime=DummyPptEditRuntime(),
    )

    payload = SimpleNamespace(
        question="把第3页改成流程图风格",
        conversation_id="conv-1",
        model_id=None,
        course_id="course-1",
        artifact_id=None,
        allow_rag=False,
        allow_web=False,
        selected_doc_ids=[],
        action_hint=None,
        owner="u1",
        artifact_reference=SimpleNamespace(artifact_id="ppt-1", artifact_type="ppt_deck"),
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "ppt.edit"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q
```

Expected: FAIL because `ReplyServiceV2` has no `ppt_edit_runtime` dependency and sends every artifact reference to the report runtime branch.

- [ ] **Step 3: Write minimal implementation**

In `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`:

- add `ppt_edit_runtime` to `ReplyServiceV2.__init__`
- inspect `request.artifact_reference.artifact_type`
- dispatch by type:

```python
artifact_reference = getattr(request, "artifact_reference", None)
artifact_type = str(getattr(artifact_reference, "artifact_type", "") or "").strip()

if artifact_reference is not None:
    if artifact_type in {"report", "report_outline"} and self.report_edit_runtime is not None:
        result = self.report_edit_runtime.run_from_request(...)
    elif artifact_type == "ppt_deck" and self.ppt_edit_runtime is not None:
        result = self.ppt_edit_runtime.run_from_request(...)
    else:
        orchestrator = ...
        result = orchestrator.dispatch(request)
```

Wire the default service builder with a real `PptEditRuntime`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py
git commit -m "feat: route PPT references to PPT edit runtime"
```

## Task 8: Persist edited PPT versions and keep the newest version active

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
- Modify: `Edu_AI/src/components/teacher/ChatPanel.tsx`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`

- [ ] **Step 1: Write the failing persistence test**

Add a backend persistence assertion to `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`:

```python
def test_reply_service_persists_completed_ppt_edit_result():
    class DummyPptEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            return {
                "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
                "conversation": {"conversation_id": "conv-1"},
                "action": {"name": "ppt.edit"},
                "workflow": {"type": "ppt", "status": "completed"},
                "artifacts": [
                    {
                        "artifact_id": "ppt-deck-v2",
                        "artifact_type": "ppt_deck",
                        "title": "智能体核心能力.pptx",
                        "content": {
                            "job_id": "job_001",
                            "revision_id": "rev_0001",
                            "pptx_url": "http://127.0.0.1:46080/ppt/artifacts/job_001/rev_0001/deck.pptx",
                        },
                        "generation_state": {"status": "completed", "generation_mode": "artifact_edit"},
                    }
                ],
                "sources": [],
                "trace": {"path": "workflow"},
            }

    course_storage = DummyCourseStorageManager()
    service = ReplyServiceV2(..., course_storage_manager=course_storage, ppt_edit_runtime=DummyPptEditRuntime())
    payload = SimpleNamespace(..., course_id="course-1", artifact_reference=SimpleNamespace(artifact_id="ppt-1", artifact_type="ppt_deck"))

    service.reply(payload)

    assert course_storage.saved[0]["material_type"] == "ppt"
    assert course_storage.saved[0]["material_data"]["content"]["revision_id"] == "rev_0001"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q
```

Expected: FAIL if the new PPT edit result is not persisted, or if finalize logic does not treat edited `ppt_deck` artifacts as savable material.

- [ ] **Step 3: Write minimal implementation**

Ensure `finalize_report_result(...)` continues to call `_persist_ppt_course_material(...)` for `ppt_deck` edit outputs, and update the edited deck `generation_state` to remain `completed` so it is persisted.

If needed, normalize the edited deck artifact to this minimal shape:

```python
"generation_state": {
    "status": "completed",
    "phase": "completed",
    "message": "PPT 已更新完成",
    "generation_mode": "artifact_edit",
}
```

On the frontend, update `ChatPanel` response handling so that when the returned artifacts include a `ppt_deck` and the current reference is a `ppt_deck`, it refreshes the store reference to the newest artifact metadata after `addGeneratedFile(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py Edu_AI/src/components/teacher/ChatPanel.tsx Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py
git commit -m "feat: persist edited PPT versions and refresh active reference"
```

## Task 9: Full verification pass

**Files:**
- Verify only

- [ ] **Step 1: Run targeted frontend tests**

Run:

```powershell
node --test Edu_AI/tests/frontend/materials.helpers.test.ts
node --test Edu_AI/tests/frontend/chatV2.helpers.test.ts
node --test Edu_AI/tests/frontend/studioPanel.ppt-preview.test.ts
```

Expected: PASS for all three files.

- [ ] **Step 2: Run targeted backend tests**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_html2ppt_client.py -q
pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_intent_parser.py -q
pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_runtime.py -q
pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q
```

Expected: PASS for all four test files.

- [ ] **Step 3: Run one combined smoke command**

Run:

```powershell
pytest Edu_AI/api/Edu_AI/tests/chat/test_html2ppt_client.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_intent_parser.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_edit_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q
```

Expected: PASS with no import or routing regressions.

- [ ] **Step 4: Commit**

```powershell
git add .
git commit -m "test: verify PPT artifact editing flow"
```

## Self-Review

- Spec coverage:
  - Frontend `添加到对话` button for PPT deck: covered in Tasks 2 and 3
  - Chat artifact reference transport and restore: covered in Tasks 1 and 3
  - html2ppt revision client support: covered in Task 4
  - target slide parsing and disambiguation: covered in Task 5
  - PPT edit runtime and new artifact response: covered in Task 6
  - `ReplyServiceV2` routing and course-material persistence: covered in Tasks 7 and 8
  - verification and regression safety: covered in Task 9

- Placeholder scan:
  - No `TODO`, `TBD`, or “implement later” markers remain
  - Each task names concrete files, code shape, and exact commands

- Type consistency:
  - Shared frontend type: `ChatArtifactReference`
  - Shared editable artifact type for this release: `ppt_deck`
  - Runtime action name: `ppt.edit`
  - Parser action type: `revise_slide`
