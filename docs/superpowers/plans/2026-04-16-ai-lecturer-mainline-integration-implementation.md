# AI Lecturer Mainline Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate `AI_Lecturer` into the main teacher workspace so the system auto-manages the module, persists PPT `content.md`, and lets teachers generate teaching videos from existing course PPT materials inside the generation factory.

**Architecture:** Keep AI Lecturer as an external module managed by the main backend rather than rewriting its internals. Add a backend bridge layer that owns process startup, health reporting, PPT/course-material adaptation, task creation, task polling, and video material persistence. Extend existing PPT material persistence so completed PPT deck materials retain `content_markdown`, allowing the bridge and the frontend to reuse a single course-material record as the source of truth.

**Tech Stack:** FastAPI, Python, subprocess management, course storage JSON persistence, React 18, TypeScript, Zustand, Ant Design, pytest, FastAPI TestClient

---

## File Structure

- Create: `Edu_AI/api/Edu_AI/app/ai_lecturer_bridge.py`
  - Own AI Lecturer process management, health inspection, PPT filtering, task bridging, and result persistence.
- Modify: `Edu_AI/api/Edu_AI/app/main.py`
  - Register startup/shutdown hooks for AI Lecturer management and include any new system-health routes if needed.
- Modify: `Edu_AI/api/Edu_AI/app/courses.py`
  - Add teacher-video PPT list, task creation, and task status routes under the course namespace.
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
  - Persist `ppt_content_markdown` alongside completed PPT deck materials.
- Modify: `Edu_AI/api/Edu_AI/core/config.py`
  - Add AI Lecturer management configuration defaults.
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_ai_lecturer_bridge.py`
  - Cover PPT filtering, task bridging, and result persistence.
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_courses_teaching_video_routes.py`
  - Cover the new course-scoped teaching-video routes.
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`
  - Add regression coverage for PPT persistence including `content_markdown`.
- Modify: `Edu_AI/src/services/teacher/api.ts`
  - Add client functions for teaching-video PPT listing, task creation, and task polling.
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx`
  - Add the “教学视频” action, PPT selection modal, bridge-task polling, and generated video insertion.

## Task 1: Add failing backend tests for PPT persistence and bridge behavior

**Files:**
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_ai_lecturer_bridge.py`
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_courses_teaching_video_routes.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py`

- [ ] **Step 1: Add a failing PPT persistence regression**

Append a test to `Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py` that proves completed PPT materials must retain markdown content:

```python
def test_persist_ppt_course_material_keeps_content_markdown():
    from app.chat.application.report_service_v2 import _persist_ppt_course_material

    class StubStorage:
        def __init__(self):
            self.calls = []

        def save_generated_material(self, **kwargs):
            self.calls.append(kwargs)

    payload = type("Payload", (), {"course_id": "course-1"})()
    storage = StubStorage()
    result = {
        "artifacts": [
            {
                "artifact_type": "ppt_outline",
                "content": {"deck_title": "Test Deck"},
            },
            {
                "artifact_type": "ppt_content_markdown",
                "content": "# Test Deck\\n\\n## Slide 1\\n- point",
            },
            {
                "artifact_id": "deck-1",
                "artifact_type": "ppt_deck",
                "title": "Test Deck.pptx",
                "content": {"pptx_url": "/ppt/test.pptx"},
                "generation_state": {"status": "completed", "phase": "completed"},
            },
        ]
    }

    _persist_ppt_course_material(payload=payload, result=result, course_storage_manager=storage)

    assert storage.calls, "expected save_generated_material to be called"
    saved = storage.calls[0]["material_data"]
    assert saved["content"]["content_markdown"] == "# Test Deck\\n\\n## Slide 1\\n- point"
```

- [ ] **Step 2: Add a failing bridge unit test**

Create `Edu_AI/api/Edu_AI/tests/chat/test_ai_lecturer_bridge.py`:

```python
from app.ai_lecturer_bridge import build_teaching_video_ppt_candidates


def test_build_teaching_video_ppt_candidates_filters_incomplete_ppt_materials():
    materials = [
        {
            "material_id": "ppt-ok",
            "title": "Complete PPT",
            "material_type": "ppt",
            "content": {"pptx_url": "/ppt/ok.pptx", "content_markdown": "# ok"},
            "generation_state": {"status": "completed"},
        },
        {
            "material_id": "ppt-no-md",
            "title": "Missing Markdown",
            "material_type": "ppt",
            "content": {"pptx_url": "/ppt/missing-md.pptx"},
            "generation_state": {"status": "completed"},
        },
    ]

    candidates = build_teaching_video_ppt_candidates(materials)

    assert [item["material_id"] for item in candidates] == ["ppt-ok"]
```

- [ ] **Step 3: Add failing route tests**

Create `Edu_AI/api/Edu_AI/tests/chat/test_courses_teaching_video_routes.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.courses import router as courses_router


def test_list_teaching_video_ppts_route_returns_candidates(monkeypatch):
    app = FastAPI()
    app.include_router(courses_router)

    monkeypatch.setattr("app.courses.get_current_user", lambda: {"username": "teacher"})
    monkeypatch.setattr("app.courses._get_manager", lambda: type("Mgr", (), {
        "get_course_info": lambda self, course_id: {"id": course_id},
        "list_generated_materials": lambda self, course_id, material_type=None: [],
    })())

    client = TestClient(app)
    response = client.get("/api/courses/course-1/teaching-videos/ppts")

    assert response.status_code == 200
```

- [ ] **Step 4: Run backend tests to verify they fail**

Run:

```bash
pytest Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py -k content_markdown -q
pytest Edu_AI/api/Edu_AI/tests/chat/test_ai_lecturer_bridge.py Edu_AI/api/Edu_AI/tests/chat/test_courses_teaching_video_routes.py -q
```

Expected: FAIL because the bridge module and routes do not exist yet, and PPT persistence does not yet retain `content_markdown`.

## Task 2: Implement backend PPT persistence and AI Lecturer bridge

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/report_service_v2.py`
- Create: `Edu_AI/api/Edu_AI/app/ai_lecturer_bridge.py`
- Modify: `Edu_AI/api/Edu_AI/core/config.py`
- Modify: `Edu_AI/api/Edu_AI/app/courses.py`
- Modify: `Edu_AI/api/Edu_AI/app/main.py`

- [ ] **Step 1: Extend PPT material persistence**

Update `_persist_ppt_course_material()` so it reads the `ppt_content_markdown` artifact and persists it both as a top-level field and inside the deck content payload:

```python
markdown_artifact = next(
    (
        artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and str(artifact.get("artifact_type") or "").strip() == "ppt_content_markdown"
    ),
    None,
)
deck_content = dict(deck_artifact.get("content") or {})
content_markdown = str(markdown_artifact.get("content") or "").strip() if isinstance(markdown_artifact, dict) else ""
if content_markdown:
    deck_content["content_markdown"] = content_markdown

course_storage_manager.save_generated_material(
    ...,
    material_data={
        ...,
        "content": deck_content,
        "content_markdown": content_markdown or None,
        "outline": ...,
    },
)
```

- [ ] **Step 2: Add AI Lecturer bridge configuration**

Extend `Config` with bridge settings:

```python
AI_LECTURER_ENABLED = os.getenv("AI_LECTURER_ENABLED", "1") == "1"
AI_LECTURER_AUTOSTART = os.getenv("AI_LECTURER_AUTOSTART", "1") == "1"
AI_LECTURER_BASE_URL = os.getenv("AI_LECTURER_BASE_URL", "http://127.0.0.1:8008")
AI_LECTURER_STARTUP_TIMEOUT_SEC = float(os.getenv("AI_LECTURER_STARTUP_TIMEOUT_SEC", "20"))
AI_LECTURER_MODULE_DIR = Path(os.getenv("AI_LECTURER_MODULE_DIR", BASE_DIR / "AI_Lecturer"))
AI_LECTURER_GATEWAY_ENTRY = Path(os.getenv("AI_LECTURER_GATEWAY_ENTRY", AI_LECTURER_MODULE_DIR / "unified_gateway.py"))
```

- [ ] **Step 3: Create the bridge module**

Implement `Edu_AI/api/Edu_AI/app/ai_lecturer_bridge.py` with:

```python
def build_teaching_video_ppt_candidates(materials: list[dict]) -> list[dict]:
    ...


class AiLecturerBridge:
    def ensure_started(self) -> None:
        ...

    def shutdown(self) -> None:
        ...

    def health(self) -> dict[str, object]:
        ...

    def list_course_ppt_candidates(self, *, course_id: str, storage_manager) -> list[dict]:
        ...

    def create_teaching_video_task(self, *, course_id: str, material_id: str, storage_manager) -> dict[str, object]:
        ...

    def get_teaching_video_task(self, *, course_id: str, task_id: str, storage_manager) -> dict[str, object]:
        ...
```

Implementation requirements:

1. Filter candidates to completed PPT deck materials only.
2. Require both `pptx_url` and `content_markdown`.
3. Use `requests` to call `${AI_LECTURER_BASE_URL}/api/v1/offline/generate_full_video` and `/api/v1/offline/status/{task_id}`.
4. Persist a `video` course material when the remote task succeeds.
5. Keep a small in-memory bridge task map to avoid duplicate video material writes.

- [ ] **Step 4: Add course routes**

In `app/courses.py`, add:

```python
@router.get("/{course_id}/teaching-videos/ppts")
def list_teaching_video_ppts(...):
    ...


@router.post("/{course_id}/teaching-videos")
def create_teaching_video(...):
    ...


@router.get("/{course_id}/teaching-videos/tasks/{task_id}")
def get_teaching_video_task(...):
    ...
```

Use the existing auth dependency and `_get_manager()` patterns.

- [ ] **Step 5: Hook startup/shutdown**

In `app/main.py`, register startup and shutdown hooks that call the bridge:

```python
@app.on_event("startup")
def _startup_ai_lecturer_bridge():
    from app.ai_lecturer_bridge import ai_lecturer_bridge
    ai_lecturer_bridge.ensure_started()


@app.on_event("shutdown")
def _shutdown_ai_lecturer_bridge():
    from app.ai_lecturer_bridge import ai_lecturer_bridge
    ai_lecturer_bridge.shutdown()
```

Also expose a small system health route if the bridge module does not already attach one under `courses.py`.

- [ ] **Step 6: Run backend tests to verify they pass**

Run:

```bash
pytest Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py -k content_markdown -q
pytest Edu_AI/api/Edu_AI/tests/chat/test_ai_lecturer_bridge.py Edu_AI/api/Edu_AI/tests/chat/test_courses_teaching_video_routes.py -q
```

Expected: PASS

## Task 3: Add failing frontend tests or source-level regressions for the new entry

**Files:**
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx`
- Modify or Create: `Edu_AI/tests/frontend/aiStudioTeachingVideo.test.ts`

- [ ] **Step 1: Add a failing source regression**

Create `Edu_AI/tests/frontend/aiStudioTeachingVideo.test.ts`:

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const studioPanel = readFileSync(
  new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url),
  'utf8',
);

assert.match(studioPanel, /教学视频/, 'StudioPanel should expose a teaching-video action');
assert.match(studioPanel, /teachingVideo/, 'StudioPanel should manage teaching-video state');
assert.match(studioPanel, /createTeachingVideoTask/, 'StudioPanel should call the teaching-video create API');
```

- [ ] **Step 2: Run the frontend regression and verify it fails**

Run:

```bash
node --test Edu_AI/tests/frontend/aiStudioTeachingVideo.test.ts
```

Expected: FAIL because the new teaching-video entry and API calls are not implemented yet.

## Task 4: Implement frontend teaching-video entry and task polling

**Files:**
- Modify: `Edu_AI/src/services/teacher/api.ts`
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx`

- [ ] **Step 1: Add API client methods**

Add the following to `src/services/teacher/api.ts`:

```ts
export interface TeachingVideoPptCandidate {
  material_id: string;
  title: string;
  pptx_url: string;
  content_markdown: string;
  slide_count?: number;
  created_at?: string;
}

export interface TeachingVideoTaskResponse {
  task_id: string;
  status: string;
  remote_task_id?: string;
  video_material?: CourseMaterialItem;
  error?: string;
}

export const listTeachingVideoPpts = async (courseId: string): Promise<TeachingVideoPptCandidate[]> => { ... }
export const createTeachingVideoTask = async (courseId: string, materialId: string): Promise<TeachingVideoTaskResponse> => { ... }
export const getTeachingVideoTask = async (courseId: string, taskId: string): Promise<TeachingVideoTaskResponse> => { ... }
```

- [ ] **Step 2: Add StudioPanel state and modal**

In `StudioPanel.tsx`, add state for:

```ts
const [teachingVideoVisible, setTeachingVideoVisible] = useState(false);
const [teachingVideoLoading, setTeachingVideoLoading] = useState(false);
const [teachingVideoCandidates, setTeachingVideoCandidates] = useState<TeachingVideoPptCandidate[]>([]);
const [selectedTeachingVideoMaterialId, setSelectedTeachingVideoMaterialId] = useState<string>('');
const [teachingVideoTaskId, setTeachingVideoTaskId] = useState<string | null>(null);
```

Add a new action card with label `教学视频`.

- [ ] **Step 3: Load PPT candidates when opening the modal**

Implement a handler:

```ts
const openTeachingVideoModal = async () => {
  if (!courseId) {
    message.error('缺少课程 ID');
    return;
  }
  setTeachingVideoVisible(true);
  setTeachingVideoLoading(true);
  try {
    const items = await listTeachingVideoPpts(courseId);
    setTeachingVideoCandidates(items);
    setSelectedTeachingVideoMaterialId(items[0]?.material_id || '');
  } finally {
    setTeachingVideoLoading(false);
  }
};
```

- [ ] **Step 4: Submit and poll**

When the user confirms:

```ts
const result = await createTeachingVideoTask(courseId, selectedTeachingVideoMaterialId);
setTeachingVideoTaskId(result.task_id);
```

Add an effect that polls `getTeachingVideoTask(courseId, taskId)` until the task becomes `completed` or `failed`. On completion:

1. Refresh course materials.
2. Convert the returned video material into a `GeneratedFile`.
3. Insert it with `addGeneratedFile`.
4. Optionally set it as `viewingFile`.

- [ ] **Step 5: Render generated video previews**

Reuse the existing `video` generated-file rendering path in `StudioPanel`; if needed, extend the preview branch so `video` materials can open using a native `<video controls>` player from their stored URL.

- [ ] **Step 6: Run the frontend regression to verify it passes**

Run:

```bash
node --test Edu_AI/tests/frontend/aiStudioTeachingVideo.test.ts
```

Expected: PASS

## Task 5: End-to-end verification

**Files:**
- No new files

- [ ] **Step 1: Run the targeted backend tests**

Run:

```bash
pytest Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py -k content_markdown -q
pytest Edu_AI/api/Edu_AI/tests/chat/test_ai_lecturer_bridge.py Edu_AI/api/Edu_AI/tests/chat/test_courses_teaching_video_routes.py -q
```

Expected: PASS

- [ ] **Step 2: Run the targeted frontend regression**

Run:

```bash
node --test Edu_AI/tests/frontend/aiStudioTeachingVideo.test.ts
```

Expected: PASS

- [ ] **Step 3: Run a broader UI/backend sanity subset**

Run:

```bash
pytest Edu_AI/api/Edu_AI/tests/chat/test_routes_v2.py -q
node --test Edu_AI/tests/frontend/teacherWorkspace.text-safety.test.ts
```

Expected: PASS, confirming the new teaching-video path did not regress the nearby teacher workspace flows.
