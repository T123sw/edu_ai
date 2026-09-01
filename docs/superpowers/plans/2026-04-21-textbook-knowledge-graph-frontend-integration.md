# Textbook Knowledge Graph Frontend Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a course-level textbook import entry on the knowledge-graph pages, wire it to the backend textbook-import flow, and move the provided `textbook_knowledge_graph.py` module into the project backend package.

**Architecture:** Keep the existing node-scoped knowledge-base upload flow unchanged and add a separate course-scoped textbook-import flow in the frontend service layer. Place the provided Python module inside the backend package so the import pipeline can be referenced by project code, then expose or confirm a dedicated route contract that returns the new graph plus import metadata.

**Tech Stack:** React, TypeScript, FastAPI, Python, existing course storage and knowledge graph APIs, node-based frontend structure tests, pytest route tests if backend glue is needed

---

## File Map

- Create: `backend/src/app/textbook_knowledge_graph.py`
  Responsibility: Project-local home for the provided textbook import pipeline module.
- Modify: `backend/src/app/courses.py`
  Responsibility: Confirm or add the textbook-import route and wire it to the moved module if backend glue is still missing.
- Test: `backend/src/tests/chat/test_textbook_knowledge_graph_routes.py`
  Responsibility: Verify the dedicated textbook-import route shape if `courses.py` requires changes.
- Modify: `frontend/src/services/teacher/api.ts`
  Responsibility: Add the teacher-side textbook-import API types and request helper.
- Modify: `frontend/src/pages/teacher/KnowledgeGraphPage.tsx`
  Responsibility: Add the course-level textbook-import control, loading state, success summary, and graph refresh.
- Modify: `frontend/src/stitch/api/types.ts`
  Responsibility: Add stitch-side textbook-import response types.
- Modify: `frontend/src/stitch/api/courses.ts`
  Responsibility: Add the stitch-side textbook-import request helper.
- Modify: `frontend/src/stitch/pages/KnowledgeGraph.tsx`
  Responsibility: Add the same course-level textbook-import flow to the stitch knowledge-graph page.
- Test: `frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts`
  Responsibility: Assert the teacher knowledge-graph page exposes and wires the textbook-import flow.
- Test: `frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`
  Responsibility: Assert the stitch knowledge-graph page exposes and wires the textbook-import flow.

## Task 1: Move the Textbook Import Module into the Backend Package

**Files:**
- Create: `backend/src/app/textbook_knowledge_graph.py`
- Modify: `backend/src/app/courses.py`
- Test: `backend/src/tests/chat/test_textbook_knowledge_graph_routes.py`

- [ ] **Step 1: Write the failing backend route test if the route is not already project-visible**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import courses as courses_module


class DummyManager:
    def get_course_info(self, course_id: str):
        if course_id == "course-1":
            return {"id": "course-1", "title": "Course 1"}
        return None


def test_textbook_import_route_returns_graph_payload(monkeypatch):
    manager = DummyManager()
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)
    monkeypatch.setattr(
        courses_module,
        "import_textbook_into_knowledge_graph",
        lambda **kwargs: {
            "source_document": {"name": "book.pdf"},
            "parser_used": "mineru",
            "outline_source": "llm",
            "knowledge_graph": {"root": {"id": "root", "label": "Course", "children": [], "data": {"level": 0, "hasChildren": False, "type": "concept"}}},
            "split_documents": [],
            "vectorized_documents": [],
            "warnings": [],
        },
    )

    app = FastAPI()
    app.include_router(courses_module.router)
    app.dependency_overrides[courses_module.get_current_user] = lambda: {"username": "teacher-a"}
    client = TestClient(app)

    response = client.post(
        "/api/courses/course-1/knowledge-graph/textbook-import",
        files={"file": ("book.pdf", b"%PDF-1.4", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_document"]["name"] == "book.pdf"
    assert payload["knowledge_graph"]["root"]["id"] == "root"
```

- [ ] **Step 2: Run the targeted backend test to verify the current route behavior fails or is missing**

Run: `pytest backend/src/tests/chat/test_textbook_knowledge_graph_routes.py -q`
Expected: FAIL because the route file or route handler does not exist yet, or the import helper is not exposed from `courses.py`.

- [ ] **Step 3: Copy the provided module into the backend package and make imports project-local**

```python
from core.course_storage import CourseStorageManager


def import_textbook_into_knowledge_graph(
    *,
    course_id: str,
    filename: str,
    file_bytes: bytes,
    manager: CourseStorageManager,
    rag_system: Any,
    explicit_env_path: Optional[str] = None,
) -> Dict[str, Any]:
    ...
```

Implementation notes:
- Copy `D:\Documents\xwechat_files\wxid_2641gv25syvc22_4a94\msg\file\2026-04\textbook_knowledge_graph.py` to `backend/src/app/textbook_knowledge_graph.py`.
- Preserve the public `import_textbook_into_knowledge_graph(...)` entry point.
- Fix obvious mojibake or broken string literals if the copied module contains encoding damage.
- Remove assumptions that the file is running from an external chat attachment directory.

- [ ] **Step 4: Add or confirm a dedicated textbook-import route in `courses.py`**

```python
from app.textbook_knowledge_graph import (
    TextbookKnowledgeGraphError,
    import_textbook_into_knowledge_graph,
)


@router.post(
    "/{course_id}/knowledge-graph/textbook-import",
    summary="Import a textbook and regenerate the course knowledge graph",
)
async def import_textbook_for_knowledge_graph(
    course_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        file_bytes = await file.read()
        result = import_textbook_into_knowledge_graph(
            course_id=course_id,
            filename=file.filename or "textbook.pdf",
            file_bytes=file_bytes,
            manager=mgr,
            rag_system=get_rag_system(),
        )
    except TextbookKnowledgeGraphError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result
```

If this route already exists elsewhere in the dirty worktree, adapt the moved module import to that existing route instead of creating a duplicate.

- [ ] **Step 5: Run the backend route test again**

Run: `pytest backend/src/tests/chat/test_textbook_knowledge_graph_routes.py -q`
Expected: PASS

## Task 2: Add the Teacher-Side Textbook Import API Helper

**Files:**
- Modify: `frontend/src/services/teacher/api.ts`
- Test: `frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts`

- [ ] **Step 1: Write the failing frontend structure test for the teacher API helper**

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const apiFile = readFileSync(new URL('../../src/services/teacher/api.ts', import.meta.url), 'utf8');

assert.match(
  apiFile,
  /export interface TextbookKnowledgeGraphImportResponse/,
  'teacher API should define a textbook import response type',
);

assert.match(
  apiFile,
  /export const importTextbookKnowledgeGraph = async/,
  'teacher API should expose a textbook knowledge-graph import helper',
);

assert.match(
  apiFile,
  /\/api\/courses\/\$\{courseId\}\/knowledge-graph\/textbook-import/,
  'teacher API helper should call the dedicated textbook-import route',
);
```

- [ ] **Step 2: Run the teacher frontend test to verify the helper is not present yet**

Run: `node --test frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts`
Expected: FAIL because the new response type and API helper are not defined.

- [ ] **Step 3: Add the teacher-side response types and API helper**

```ts
export interface TextbookKnowledgeGraphImportResponse {
  source_document: {
    id?: string;
    name: string;
    file_path?: string | null;
  };
  parser_used?: string;
  outline_source?: string;
  knowledge_graph: KnowledgeGraphData;
  split_documents: Array<{
    id: string;
    title: string;
    file_path: string;
    preview?: string;
  }>;
  vectorized_documents: Array<Record<string, unknown>>;
  warnings: string[];
}

export const importTextbookKnowledgeGraph = async (
  courseId: string,
  file: File,
): Promise<TextbookKnowledgeGraphImportResponse> => {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append('file', file);

  const resp = await fetch(`${BACKEND_BASE_URL}/api/courses/${courseId}/knowledge-graph/textbook-import`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`教材导入失败: ${resp.status} ${resp.statusText}\n${text}`);
  }

  return (await resp.json()) as TextbookKnowledgeGraphImportResponse;
};
```

- [ ] **Step 4: Run the teacher frontend test again**

Run: `node --test frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts`
Expected: PASS for the API helper assertions, even though the page assertions will still fail until Task 3.

## Task 3: Add the Course-Level Teacher Knowledge-Graph Import UI

**Files:**
- Modify: `frontend/src/pages/teacher/KnowledgeGraphPage.tsx`
- Test: `frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts`

- [ ] **Step 1: Extend the failing teacher frontend test to require the course-level UI flow**

```ts
assert.match(
  graphPageFile,
  /importTextbookKnowledgeGraph/,
  'KnowledgeGraphPage should call the dedicated textbook-import helper',
);

assert.match(
  graphPageFile,
  /textbookImportInputRef/,
  'KnowledgeGraphPage should expose a hidden file input for textbook import',
);

assert.match(
  graphPageFile,
  /setImportingTextbookKnowledgeGraph/,
  'KnowledgeGraphPage should track a loading state while the textbook import is running',
);

assert.match(
  graphPageFile,
  /knowledge_graph:\s*result\.knowledge_graph|result\.knowledge_graph\.root|convertBackendToTreeGraph\(result\.knowledge_graph\.root\)/,
  'KnowledgeGraphPage should refresh the graph from the textbook import response',
);
```

- [ ] **Step 2: Run the teacher frontend test to verify the page flow fails**

Run: `node --test frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts`
Expected: FAIL because the page does not yet import the new helper or expose the course-level textbook control.

- [ ] **Step 3: Implement the course-level textbook import flow in `KnowledgeGraphPage.tsx`**

```tsx
const [importingTextbookKnowledgeGraph, setImportingTextbookKnowledgeGraph] = useState(false);
const [textbookImportSummary, setTextbookImportSummary] = useState<TextbookKnowledgeGraphImportResponse | null>(null);
const textbookImportInputRef = useRef<HTMLInputElement | null>(null);

const handleTextbookImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file || !courseId) return;

  try {
    setImportingTextbookKnowledgeGraph(true);
    const result = await importTextbookKnowledgeGraph(courseId, file);
    const nextRoot = convertBackendToTreeGraph(result.knowledge_graph.root);
    fullTreeRef.current = nextRoot;
    visibleTreeRef.current = nextRoot;
    setRootNodeId(String(nextRoot.id));
    setSelectedNodeId(String(nextRoot.id));
    setTextbookImportSummary(result);
    await setGraphDataAndRender(nextRoot);
    message.success(`已根据教材《${result.source_document.name}》生成课程知识图谱`);
  } catch (error) {
    message.error(error instanceof Error ? error.message : '教材导入失败');
  } finally {
    setImportingTextbookKnowledgeGraph(false);
  }
};
```

UI notes:
- Put the button in the course-level toolbar, not the node detail panel.
- Keep the existing node-scoped knowledge-base upload button untouched.
- Render a small summary card for parser, outline source, split count, and warnings.

- [ ] **Step 4: Run the teacher frontend test again**

Run: `node --test frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts`
Expected: PASS

## Task 4: Add the Stitch-Side Textbook Import API Helper

**Files:**
- Modify: `frontend/src/stitch/api/types.ts`
- Modify: `frontend/src/stitch/api/courses.ts`
- Test: `frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`

- [ ] **Step 1: Write the failing stitch frontend test for the new API helper**

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const typesFile = readFileSync(new URL('../../src/stitch/api/types.ts', import.meta.url), 'utf8');
const apiFile = readFileSync(new URL('../../src/stitch/api/courses.ts', import.meta.url), 'utf8');

assert.match(typesFile, /export type TextbookKnowledgeGraphImportResponse/, 'stitch types should define the textbook import response');
assert.match(apiFile, /export function importTextbookKnowledgeGraph/, 'stitch API should expose a textbook import helper');
assert.match(apiFile, /\/api\/courses\/\$\{courseId\}\/knowledge-graph\/textbook-import/, 'stitch API helper should call the textbook-import route');
```

- [ ] **Step 2: Run the stitch frontend test to verify the helper is missing**

Run: `node --test frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`
Expected: FAIL because the stitch types and API helper do not exist yet.

- [ ] **Step 3: Add the stitch-side response type and API helper**

```ts
export type TextbookKnowledgeGraphImportResponse = {
  source_document: {
    id?: string;
    name: string;
    file_path?: string | null;
  };
  parser_used?: string;
  outline_source?: string;
  knowledge_graph: KnowledgeGraphData;
  split_documents: Array<{
    id: string;
    title: string;
    file_path: string;
    preview?: string;
  }>;
  vectorized_documents: Array<Record<string, unknown>>;
  warnings: string[];
};
```

```ts
export function importTextbookKnowledgeGraph(courseId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);

  return apiRequest<TextbookKnowledgeGraphImportResponse>(`/api/courses/${courseId}/knowledge-graph/textbook-import`, {
    method: "POST",
    body: formData,
  });
}
```

- [ ] **Step 4: Run the stitch frontend test again**

Run: `node --test frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`
Expected: PASS for the API assertions, while the page assertions still fail until Task 5.

## Task 5: Add the Course-Level Stitch Knowledge-Graph Import UI

**Files:**
- Modify: `frontend/src/stitch/pages/KnowledgeGraph.tsx`
- Test: `frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`

- [ ] **Step 1: Extend the failing stitch frontend test to require the page-level import flow**

```ts
assert.match(
  graphPageFile,
  /importTextbookKnowledgeGraph/,
  'stitch KnowledgeGraphPage should call the dedicated textbook-import helper',
);

assert.match(
  graphPageFile,
  /textbookImportInputRef/,
  'stitch KnowledgeGraphPage should expose a hidden file input for course-level textbook import',
);

assert.match(
  graphPageFile,
  /setImportingTextbookKnowledgeGraph/,
  'stitch KnowledgeGraphPage should track textbook import loading state',
);

assert.match(
  graphPageFile,
  /flattenGraph\(result\.knowledge_graph\.root\)/,
  'stitch KnowledgeGraphPage should rebuild the graph from the textbook import response',
);
```

- [ ] **Step 2: Run the stitch frontend test to verify the page flow fails**

Run: `node --test frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`
Expected: FAIL because the page does not yet expose the textbook-import UI.

- [ ] **Step 3: Implement the course-level textbook import flow in the stitch page**

```tsx
const [importingTextbookKnowledgeGraph, setImportingTextbookKnowledgeGraph] = useState(false);
const [textbookImportSummary, setTextbookImportSummary] = useState<TextbookKnowledgeGraphImportResponse | null>(null);
const textbookImportInputRef = useRef<HTMLInputElement | null>(null);

async function handleTextbookImport(fileList: FileList | null) {
  if (!course?.id || !fileList?.length) return;

  const file = fileList[0];
  try {
    setImportingTextbookKnowledgeGraph(true);
    const result = await importTextbookKnowledgeGraph(course.id, file);
    const flat = flattenGraph(result.knowledge_graph.root);
    setNodes(flat);
    const root = flat.find((node) => node.parentId === null) ?? flat[0];
    setActiveNodeId(root?.id || "");
    setExpandedIds(root ? new Set([root.id]) : new Set());
    setTextbookImportSummary(result);
  } catch (err) {
    setError(err instanceof Error ? err.message : "教材导入失败");
  } finally {
    setImportingTextbookKnowledgeGraph(false);
    if (textbookImportInputRef.current) {
      textbookImportInputRef.current.value = "";
    }
  }
}
```

UI notes:
- Reuse the stitch visual language instead of copying teacher-page Ant Design controls directly.
- Keep the node-level document upload section intact.

- [ ] **Step 4: Run the stitch frontend test again**

Run: `node --test frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`
Expected: PASS

## Task 6: Run the Verification Pass

**Files:**
- Modify: `backend/src/app/textbook_knowledge_graph.py`
- Modify: `backend/src/app/courses.py`
- Modify: `frontend/src/services/teacher/api.ts`
- Modify: `frontend/src/pages/teacher/KnowledgeGraphPage.tsx`
- Modify: `frontend/src/stitch/api/types.ts`
- Modify: `frontend/src/stitch/api/courses.ts`
- Modify: `frontend/src/stitch/pages/KnowledgeGraph.tsx`
- Test: `backend/src/tests/chat/test_textbook_knowledge_graph_routes.py`
- Test: `frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts`
- Test: `frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`

- [ ] **Step 1: Run the backend route test if backend glue changed**

Run: `pytest backend/src/tests/chat/test_textbook_knowledge_graph_routes.py -q`
Expected: PASS

- [ ] **Step 2: Run the teacher frontend test**

Run: `node --test frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts`
Expected: PASS

- [ ] **Step 3: Run the stitch frontend test**

Run: `node --test frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`
Expected: PASS

- [ ] **Step 4: Run the existing knowledge-graph frontend regression tests**

Run: `node --test frontend/tests/frontend/knowledgeGraphWorkspaceJump.test.ts`
Expected: PASS

Run: `node --test frontend/tests/frontend/knowledgeGraphHours.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-21-textbook-knowledge-graph-frontend-integration-design-cn.md docs/superpowers/plans/2026-04-21-textbook-knowledge-graph-frontend-integration.md backend/src/app/textbook_knowledge_graph.py backend/src/app/courses.py backend/src/tests/chat/test_textbook_knowledge_graph_routes.py frontend/src/services/teacher/api.ts frontend/src/pages/teacher/KnowledgeGraphPage.tsx frontend/src/stitch/api/types.ts frontend/src/stitch/api/courses.ts frontend/src/stitch/pages/KnowledgeGraph.tsx frontend/tests/frontend/knowledgeGraph.textbook-import.test.ts frontend/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts
git commit -m "feat: add textbook knowledge graph import flow"
```

If the worktree is still dirty with unrelated changes, skip the commit and report that the implementation is complete but not committed.
