# Knowledge-Point Scoped AI Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add course-root and knowledge-point scoped AI workspace behavior so chat, retrieval, personal knowledge files, history, and generated artifacts all follow the active scope.

**Architecture:** Introduce a shared workspace-scope model across backend and frontend, persist scope metadata on conversations/documents/materials, and make list/read APIs scope-aware with subtree aggregation and explicit pagination. The frontend keeps one authoritative scope state, receives it from direct course entry or knowledge-graph jump entry, and passes it into the source panel, chat panel, and studio panel so each area refreshes against the same scope contract.

**Tech Stack:** FastAPI, JSON-backed storage managers, React, Zustand, TypeScript, Ant Design, pytest, node-based frontend text/structure tests

---

## File Map

### Backend

- Create: `backend/src/app/workspace_scope.py`
  Responsibility: Normalize `scope_type/scope_id`, resolve knowledge-point subtrees from stored course graphs, and expose helpers used by chat/course APIs.
- Modify: `backend/src/app/chat/schemas.py`
  Responsibility: Accept scope fields on chat requests and include scope metadata in conversation history payloads.
- Modify: `backend/src/app/chat/routes.py`
  Responsibility: Parse scope query params for list/detail endpoints and forward them into filtered conversation reads.
- Modify: `backend/src/app/chat/application/route_chat_service.py`
  Responsibility: Persist workspace scope into conversation state and outgoing workflow context.
- Modify: `backend/src/core/conversation_storage.py`
  Responsibility: Store normalized scope metadata on conversations and support filtered/paginated list queries.
- Modify: `backend/src/core/course_storage.py`
  Responsibility: Persist scope metadata on knowledge-base index entries and generated materials, plus add filtered list helpers.
- Modify: `backend/src/app/courses.py`
  Responsibility: Accept scope fields on knowledge-base/material routes, call storage filters, and aggregate course-root reads.
- Test: `backend/src/tests/chat/test_workspace_scope.py`
  Responsibility: Cover normalization and subtree resolution.
- Test: `backend/src/tests/chat/test_conversation_scope_routes.py`
  Responsibility: Cover scoped conversation create/list/detail behavior.
- Test: `backend/src/tests/chat/test_course_scope_materials_routes.py`
  Responsibility: Cover scoped knowledge-base and generated-material reads.

### Frontend

- Create: `frontend/src/pages/teacher/aiWorkspaceScope.ts`
  Responsibility: Parse/query/update workspace scope and generate labels for course-root vs knowledge-point modes.
- Modify: `frontend/src/pages/teacher/AiStudioPage.tsx`
  Responsibility: Build the active scope from route/query params and pass it into all three workspace columns.
- Modify: `frontend/src/pages/teacher/KnowledgeGraphPage.tsx`
  Responsibility: Add the “和 AI 聊一聊” jump using the selected node’s scope.
- Modify: `frontend/src/store/teacher/useStore.ts`
  Responsibility: Persist the active workspace scope and scope-aware conversation state.
- Modify: `frontend/src/store/teacher/useCourseMaterialsStore.ts`
  Responsibility: Hold paged/generated material results keyed by scope.
- Modify: `frontend/src/services/teacher/api.ts`
  Responsibility: Add scope params to conversation/material requests and support `limit/offset`.
- Modify: `frontend/src/services/teacher/chatV2.ts`
  Responsibility: Add scope fields to chat reply payloads.
- Modify: `frontend/src/services/knowledgeBase.ts`
  Responsibility: Add scope-aware list/upload APIs.
- Modify: `frontend/src/components/teacher/ChatPanel.tsx`
  Responsibility: Load/send history within the active scope and page course-root history 20 at a time.
- Modify: `frontend/src/components/teacher/SourcePanel.tsx`
  Responsibility: Load scope-specific documents, label uploads against the current scope, and support course-root aggregation.
- Modify: `frontend/src/components/teacher/StudioPanel.tsx`
  Responsibility: Load generated artifacts by scope, page course-root results, and keep newly generated items scoped.
- Test: `frontend/tests/frontend/aiStudioScopeRouting.test.ts`
  Responsibility: Assert scope parsing and knowledge-graph jump wiring.
- Test: `frontend/tests/frontend/chatPanel.scope-history.test.ts`
  Responsibility: Assert scope-aware conversation loading and “load more” behavior.
- Test: `frontend/tests/frontend/sourcePanel.scope-documents.test.ts`
  Responsibility: Assert scope-aware document reads/uploads.
- Test: `frontend/tests/frontend/studioPanel.scope-materials.test.ts`
  Responsibility: Assert scope-aware generated material hydration and paging.

### Existing Docs To Reference While Implementing

- Read: `docs/superpowers/specs/2026-04-20-knowledge-point-scoped-ai-workspace-design-cn.md`
- Read: `backend/src/core/README_COURSE_STORAGE.md`

---

### Task 1: Add Shared Workspace Scope Helpers

**Files:**
- Create: `backend/src/app/workspace_scope.py`
- Test: `backend/src/tests/chat/test_workspace_scope.py`

- [ ] **Step 1: Write the failing backend scope tests**

```python
from app.workspace_scope import (
    SCOPE_TYPE_COURSE,
    SCOPE_TYPE_KNOWLEDGE_POINT,
    collect_scope_ids_for_query,
    normalize_workspace_scope,
)


def test_normalize_workspace_scope_defaults_course_root():
    normalized = normalize_workspace_scope(course_id="computational-thinking")
    assert normalized == {
        "course_id": "computational-thinking",
        "scope_type": SCOPE_TYPE_COURSE,
        "scope_id": None,
    }


def test_normalize_workspace_scope_requires_scope_id_for_knowledge_point():
    try:
        normalize_workspace_scope(
            course_id="computational-thinking",
            scope_type=SCOPE_TYPE_KNOWLEDGE_POINT,
            scope_id="",
        )
    except ValueError as exc:
        assert "scope_id" in str(exc)
    else:
        raise AssertionError("normalize_workspace_scope should reject empty scope_id")


def test_collect_scope_ids_for_query_returns_parent_and_descendants():
    root = {
        "id": "root",
        "children": [
            {
                "id": "sorting",
                "children": [
                    {"id": "bubble", "children": []},
                    {"id": "quick", "children": []},
                ],
            },
            {"id": "graphs", "children": []},
        ],
    }

    scope_ids = collect_scope_ids_for_query(root, scope_type=SCOPE_TYPE_KNOWLEDGE_POINT, scope_id="sorting")
    assert scope_ids == {"sorting", "bubble", "quick"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest backend/src/tests/chat/test_workspace_scope.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.workspace_scope'`

- [ ] **Step 3: Write the minimal shared scope helper implementation**

```python
from __future__ import annotations

from typing import Any, Dict, Optional, Set


SCOPE_TYPE_COURSE = "course"
SCOPE_TYPE_KNOWLEDGE_POINT = "knowledge_point"


def normalize_workspace_scope(
    *,
    course_id: str,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_course_id = str(course_id or "").strip()
    if not normalized_course_id:
        raise ValueError("course_id is required")

    normalized_scope_type = str(scope_type or SCOPE_TYPE_COURSE).strip() or SCOPE_TYPE_COURSE
    if normalized_scope_type not in {SCOPE_TYPE_COURSE, SCOPE_TYPE_KNOWLEDGE_POINT}:
        raise ValueError("scope_type must be 'course' or 'knowledge_point'")

    normalized_scope_id = str(scope_id or "").strip() or None
    if normalized_scope_type == SCOPE_TYPE_KNOWLEDGE_POINT and not normalized_scope_id:
        raise ValueError("scope_id is required when scope_type=knowledge_point")
    if normalized_scope_type == SCOPE_TYPE_COURSE:
        normalized_scope_id = None

    return {
        "course_id": normalized_course_id,
        "scope_type": normalized_scope_type,
        "scope_id": normalized_scope_id,
    }


def _collect_descendants(node: Dict[str, Any], bucket: Set[str]) -> None:
    node_id = str(node.get("id") or "").strip()
    if node_id:
        bucket.add(node_id)
    for child in list(node.get("children") or []):
        if isinstance(child, dict):
            _collect_descendants(child, bucket)


def collect_scope_ids_for_query(
    graph_root: Optional[Dict[str, Any]],
    *,
    scope_type: str,
    scope_id: Optional[str],
) -> Set[str]:
    if scope_type == SCOPE_TYPE_COURSE:
        return set()
    target_id = str(scope_id or "").strip()
    if not target_id:
        return set()

    def find(node: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(node, dict):
            return None
        if str(node.get("id") or "").strip() == target_id:
            return node
        for child in list(node.get("children") or []):
            found = find(child if isinstance(child, dict) else None)
            if found is not None:
                return found
        return None

    target = find(graph_root)
    if target is None:
        return {target_id}

    result: Set[str] = set()
    _collect_descendants(target, result)
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest backend/src/tests/chat/test_workspace_scope.py -v`

Expected: PASS for all 3 tests

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/workspace_scope.py backend/src/tests/chat/test_workspace_scope.py
git commit -m "feat: add workspace scope helpers"
```

### Task 2: Persist Scope Metadata on Conversations and Add Scoped History Reads

**Files:**
- Modify: `backend/src/app/chat/schemas.py`
- Modify: `backend/src/app/chat/routes.py`
- Modify: `backend/src/app/chat/application/route_chat_service.py`
- Modify: `backend/src/core/conversation_storage.py`
- Test: `backend/src/tests/chat/test_conversation_scope_routes.py`

- [ ] **Step 1: Write the failing scoped conversation route tests**

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_chat_route_persists_scope_metadata(monkeypatch):
    from app.chat import routes as chat_routes

    class DummyService:
        def chat(self, **kwargs):
            return {
                "answer": "ok",
                "conversation_id": "conv-scope-1",
                "model_id": "stub-model",
                "intent_category": "chat",
                "title": "scope",
                "meta": {},
            }

    monkeypatch.setattr(chat_routes, "_get_service", lambda: DummyService())
    monkeypatch.setattr(chat_routes.auth_manager, "get_current_user", lambda token: {"username": "tester"})

    response = client.post(
        "/api/chat",
        headers={"Authorization": "Bearer stub"},
        json={
            "question": "解释快速排序",
            "conversation_id": "conv-scope-1",
            "course_id": "computational-thinking",
            "scope_type": "knowledge_point",
            "scope_id": "sorting",
        },
    )

    assert response.status_code == 200
    detail = client.get("/api/chat/conversations/conv-scope-1", headers={"Authorization": "Bearer stub"})
    payload = detail.json()
    assert payload["state"]["scope_type"] == "knowledge_point"
    assert payload["state"]["scope_id"] == "sorting"


def test_list_conversations_filters_course_root_aggregate(monkeypatch):
    from app.chat import routes as chat_routes

    monkeypatch.setattr(chat_routes.auth_manager, "get_current_user", lambda token: {"username": "tester"})

    response = client.get(
        "/api/chat/conversations",
        headers={"Authorization": "Bearer stub"},
        params={
            "course_id": "computational-thinking",
            "scope_type": "course",
            "aggregate": "true",
            "limit": "20",
            "offset": "0",
        },
    )

    assert response.status_code == 200
    assert "conversations" in response.json()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest backend/src/tests/chat/test_conversation_scope_routes.py -v`

Expected: FAIL because `ChatRequest` does not accept `scope_type/scope_id` and `/api/chat/conversations` does not accept pagination/scope params

- [ ] **Step 3: Implement scoped conversation persistence and list filtering**

```python
# backend/src/app/chat/schemas.py
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户输入")
    conversation_id: Optional[str] = Field(default=None, description="会话ID")
    model_id: Optional[str] = Field(default=None, description="模型ID")
    owner: Optional[str] = Field(default=None, description="当前用户名")
    artifact_id: Optional[str] = Field(default=None, description="当前活跃产物ID")
    use_rag: Optional[bool] = Field(default=None, description="是否启用知识库检索")
    allow_rag: bool = Field(default=False, description="是否允许使用 RAG")
    allow_web: bool = Field(default=False, description="是否允许使用 Web")
    action_hint: Optional[str] = Field(default=None, description="前端动作提示")
    selected_doc_ids: List[str] = Field(default_factory=list, description="指定检索文档ID列表")
    course_id: Optional[str] = Field(default=None, description="课程ID")
    scope_type: str = Field(default="course", description="工作台作用域类型")
    scope_id: Optional[str] = Field(default=None, description="知识点作用域ID")
```

```python
# backend/src/core/conversation_storage.py
def list_conversations(
    self,
    *,
    owner: Optional[str] = None,
    course_id: Optional[str] = None,
    scope_type: Optional[str] = None,
    scope_ids: Optional[set[str]] = None,
    aggregate: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    with self._lock:
        items = []
        for conv in self._conversations.values():
            if owner and conv.get("owner") != owner:
                continue
            state = conv.get("state") or {}
            if course_id and str(state.get("course_id") or "") != str(course_id):
                continue
            current_scope_type = str(state.get("scope_type") or "course")
            current_scope_id = str(state.get("scope_id") or "").strip() or None
            if scope_type == "course" and aggregate:
                pass
            elif scope_type == "course":
                if current_scope_type != "course":
                    continue
            elif scope_type == "knowledge_point":
                if current_scope_type != "knowledge_point":
                    continue
                if scope_ids and current_scope_id not in scope_ids:
                    continue
            items.append(
                {
                    "conversation_id": conv["conversation_id"],
                    "title": conv.get("title") or self._generate_title_from_messages(conv.get("messages", [])),
                    "created_at": conv.get("created_at"),
                    "updated_at": conv.get("updated_at"),
                    "message_count": len(conv.get("messages", [])),
                    "scope_type": current_scope_type,
                    "scope_id": current_scope_id,
                }
            )
        items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        sliced = items[offset : offset + limit]
        return {
            "conversations": sliced,
            "count": len(sliced),
            "total": len(items),
            "limit": limit,
            "offset": offset,
        }
```

```python
# backend/src/app/chat/application/route_chat_service.py
from app.workspace_scope import normalize_workspace_scope

scope = normalize_workspace_scope(
    course_id=str(getattr(payload, "course_id", "") or "").strip(),
    scope_type=getattr(payload, "scope_type", None),
    scope_id=getattr(payload, "scope_id", None),
)
state_patch["course_id"] = scope["course_id"]
state_patch["scope_type"] = scope["scope_type"]
state_patch["scope_id"] = scope["scope_id"]
state_patch["active_context"] = {
    **dict(existing_state.get("active_context") or {}),
    "current_course_id": scope["course_id"],
    "scope_type": scope["scope_type"],
    "scope_id": scope["scope_id"],
    "pinned_doc_ids": list(getattr(payload, "selected_doc_ids", None) or []),
}
```

```python
# backend/src/app/chat/routes.py
@router.get("/conversations")
async def list_conversations(
    course_id: str | None = None,
    scope_type: str = "course",
    scope_id: str | None = None,
    aggregate: bool = False,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    graph_root = None
    scope_ids = None
    if course_id and scope_type == "knowledge_point":
        graph_root = storage_manager.get_knowledge_graph(course_id)
        scope_ids = collect_scope_ids_for_query(graph_root, scope_type=scope_type, scope_id=scope_id)
    return conversation_storage.list_conversations(
        owner=current_user.get("username"),
        course_id=course_id,
        scope_type=scope_type,
        scope_ids=scope_ids,
        aggregate=aggregate,
        limit=limit,
        offset=offset,
    )
```

- [ ] **Step 4: Run the scoped conversation tests**

Run: `pytest backend/src/tests/chat/test_conversation_scope_routes.py -v`

Expected: PASS for scoped create/list tests

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/chat/schemas.py backend/src/app/chat/routes.py backend/src/app/chat/application/route_chat_service.py backend/src/core/conversation_storage.py backend/src/tests/chat/test_conversation_scope_routes.py
git commit -m "feat: add scoped conversation history support"
```

### Task 3: Persist Scope Metadata for Knowledge-Base Documents and Generated Materials

**Files:**
- Modify: `backend/src/core/course_storage.py`
- Modify: `backend/src/app/courses.py`
- Test: `backend/src/tests/chat/test_course_scope_materials_routes.py`

- [ ] **Step 1: Write the failing material/document scope tests**

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_knowledge_base_documents_filter_by_scope(monkeypatch):
    from app import courses as course_routes

    monkeypatch.setattr(course_routes.auth_manager, "get_current_user", lambda token: {"username": "tester"})

    response = client.get(
        "/api/courses/computational-thinking/knowledge-base/documents",
        headers={"Authorization": "Bearer stub"},
        params={"scope_type": "knowledge_point", "scope_id": "sorting"},
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_materials_endpoint_supports_course_aggregate_paging(monkeypatch):
    from app import courses as course_routes

    monkeypatch.setattr(course_routes.auth_manager, "get_current_user", lambda token: {"username": "tester"})

    response = client.get(
        "/api/courses/computational-thinking/materials",
        headers={"Authorization": "Bearer stub"},
        params={"scope_type": "course", "aggregate": "true", "limit": "20", "offset": "0"},
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest backend/src/tests/chat/test_course_scope_materials_routes.py -v`

Expected: FAIL because the routes ignore `scope_type/scope_id/aggregate/limit/offset`

- [ ] **Step 3: Implement scoped storage metadata and filtered list helpers**

```python
# backend/src/core/course_storage.py
def save_knowledge_base_file(
    self,
    course_id: str,
    file_data: bytes,
    filename: str,
    *,
    scope_type: str = "course",
    scope_id: str | None = None,
) -> Optional[str]:
    ...
    file_info = {
        "id": f"doc-{datetime.now().timestamp()}",
        "filename": filename,
        "path": f"knowledge_base/documents/{filename}",
        "size": len(file_data),
        "uploaded_at": datetime.now().isoformat(),
        "scope_type": scope_type,
        "scope_id": scope_id,
    }
```

```python
def list_knowledge_base_documents(
    self,
    course_id: str,
    *,
    scope_type: str = "course",
    scope_ids: Optional[set[str]] = None,
    aggregate: bool = False,
) -> List[Dict[str, Any]]:
    items = self.get_knowledge_base_index(course_id)
    results: List[Dict[str, Any]] = []
    for item in items:
        item_scope_type = str(item.get("scope_type") or "course")
        item_scope_id = str(item.get("scope_id") or "").strip() or None
        if scope_type == "course" and aggregate:
            results.append(item)
        elif scope_type == "course":
            if item_scope_type == "course":
                results.append(item)
        elif item_scope_type == "knowledge_point" and (not scope_ids or item_scope_id in scope_ids):
            results.append(item)
    return results
```

```python
def list_generated_materials(
    self,
    course_id: str,
    material_type: Optional[str] = None,
    *,
    scope_type: str = "course",
    scope_ids: Optional[set[str]] = None,
    aggregate: bool = False,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    ...
    filtered = []
    for material in materials:
        material_scope_type = str(material.get("scope_type") or "course")
        material_scope_id = str(material.get("scope_id") or "").strip() or None
        if scope_type == "course" and aggregate:
            filtered.append(material)
        elif scope_type == "course":
            if material_scope_type == "course":
                filtered.append(material)
        elif material_scope_type == "knowledge_point" and (not scope_ids or material_scope_id in scope_ids):
            filtered.append(material)
    sorted_items = self._sort_generated_materials(filtered)
    if limit is None:
        return sorted_items[offset:]
    return sorted_items[offset : offset + limit]
```

```python
# backend/src/app/courses.py
@router.get("/{course_id}/knowledge-base/documents")
def get_knowledge_base_documents(
    course_id: str,
    scope_type: str = "course",
    scope_id: str | None = None,
    aggregate: bool = False,
    current_user: dict = Depends(get_current_user),
):
    scope = normalize_workspace_scope(course_id=course_id, scope_type=scope_type, scope_id=scope_id)
    graph_root = mgr.get_knowledge_graph(course_id)
    scope_ids = collect_scope_ids_for_query(graph_root, scope_type=scope["scope_type"], scope_id=scope["scope_id"])
    index = mgr.list_knowledge_base_documents(
        course_id,
        scope_type=scope["scope_type"],
        scope_ids=scope_ids,
        aggregate=aggregate,
    )
    ...
```

- [ ] **Step 4: Run the scoped material/document tests**

Run: `pytest backend/src/tests/chat/test_course_scope_materials_routes.py -v`

Expected: PASS for both route tests

- [ ] **Step 5: Commit**

```bash
git add backend/src/core/course_storage.py backend/src/app/courses.py backend/src/tests/chat/test_course_scope_materials_routes.py
git commit -m "feat: add scoped course assets support"
```

### Task 4: Add Frontend Workspace Scope State and Knowledge-Graph Jump Entry

**Files:**
- Create: `frontend/src/pages/teacher/aiWorkspaceScope.ts`
- Modify: `frontend/src/pages/teacher/AiStudioPage.tsx`
- Modify: `frontend/src/pages/teacher/KnowledgeGraphPage.tsx`
- Modify: `frontend/src/store/teacher/useStore.ts`
- Test: `frontend/tests/frontend/aiStudioScopeRouting.test.ts`

- [ ] **Step 1: Write the failing frontend scope-routing tests**

```ts
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const aiStudioPage = readFileSync(new URL('../../src/pages/teacher/AiStudioPage.tsx', import.meta.url), 'utf8');
const knowledgeGraphPage = readFileSync(new URL('../../src/pages/teacher/KnowledgeGraphPage.tsx', import.meta.url), 'utf8');
const storeFile = readFileSync(new URL('../../src/store/teacher/useStore.ts', import.meta.url), 'utf8');

assert.match(aiStudioPage, /getWorkspaceScopeFromLocation\(/, 'AiStudioPage should derive the active workspace scope from the route location');
assert.match(aiStudioPage, /workspaceScope/, 'AiStudioPage should pass an explicit workspaceScope into the workspace columns');
assert.match(knowledgeGraphPage, /navigate\(`\/course\/\$\{courseId\}\/studio\?scopeType=knowledge_point&scopeId=/, 'KnowledgeGraphPage should jump into studio with knowledge-point scope params');
assert.match(storeFile, /workspaceScope:/, 'useStore should persist the active workspace scope');
console.log('aiStudioScopeRouting tests passed');
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test frontend/tests/frontend/aiStudioScopeRouting.test.ts`

Expected: FAIL because no workspace scope helper or route jump exists yet

- [ ] **Step 3: Implement frontend scope parsing and knowledge-graph jump**

```ts
// frontend/src/pages/teacher/aiWorkspaceScope.ts
export type WorkspaceScope =
  | { scopeType: 'course'; scopeId: null; courseId: string }
  | { scopeType: 'knowledge_point'; scopeId: string; courseId: string };

export function getWorkspaceScopeFromLocation(courseId: string, search: string): WorkspaceScope {
  const params = new URLSearchParams(search);
  const scopeType = params.get('scopeType');
  const scopeId = params.get('scopeId');
  if (scopeType === 'knowledge_point' && scopeId) {
    return { scopeType: 'knowledge_point', scopeId, courseId };
  }
  return { scopeType: 'course', scopeId: null, courseId };
}
```

```tsx
// frontend/src/pages/teacher/AiStudioPage.tsx
import { useLocation } from 'react-router-dom';
import { getWorkspaceScopeFromLocation } from './aiWorkspaceScope';

const location = useLocation();
const workspaceScope = useMemo(
  () => (courseId ? getWorkspaceScopeFromLocation(courseId, location.search) : null),
  [courseId, location.search],
);

useEffect(() => {
  setWorkspaceScope(workspaceScope);
}, [setWorkspaceScope, workspaceScope]);

<SourcePanel courseId={courseId} workspaceScope={workspaceScope} ... />
<ChatPanel courseId={courseId} workspaceScope={workspaceScope} />
<StudioPanel courseId={courseId} workspaceScope={workspaceScope} ... />
```

```tsx
// frontend/src/pages/teacher/KnowledgeGraphPage.tsx
import { useNavigate } from 'react-router-dom';

const navigate = useNavigate();

<Button
  type="primary"
  icon={<MessageOutlined />}
  onClick={() => {
    if (!courseId || !selectedNodeId) return;
    navigate(`/course/${courseId}/studio?scopeType=knowledge_point&scopeId=${encodeURIComponent(selectedNodeId)}`);
  }}
>
  和 AI 聊一聊
</Button>
```

- [ ] **Step 4: Run the frontend routing tests**

Run: `node --test frontend/tests/frontend/aiStudioScopeRouting.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/teacher/aiWorkspaceScope.ts frontend/src/pages/teacher/AiStudioPage.tsx frontend/src/pages/teacher/KnowledgeGraphPage.tsx frontend/src/store/teacher/useStore.ts frontend/tests/frontend/aiStudioScopeRouting.test.ts
git commit -m "feat: add workspace scope routing"
```

### Task 5: Make Chat and History Scope-Aware With 20-Item Paging

**Files:**
- Modify: `frontend/src/services/teacher/api.ts`
- Modify: `frontend/src/services/teacher/chatV2.ts`
- Modify: `frontend/src/components/teacher/ChatPanel.tsx`
- Test: `frontend/tests/frontend/chatPanel.scope-history.test.ts`

- [ ] **Step 1: Write the failing chat-panel scope tests**

```ts
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const apiFile = readFileSync(new URL('../../src/services/teacher/api.ts', import.meta.url), 'utf8');
const chatV2File = readFileSync(new URL('../../src/services/teacher/chatV2.ts', import.meta.url), 'utf8');
const panelFile = readFileSync(new URL('../../src/components/teacher/ChatPanel.tsx', import.meta.url), 'utf8');

assert.match(apiFile, /scope_type\?: 'course' \| 'knowledge_point'/, 'teacher api should define scope params for conversation reads');
assert.match(apiFile, /limit\?: number/, 'teacher api should expose limit for paged history reads');
assert.match(chatV2File, /scope_type\?: 'course' \| 'knowledge_point'/, 'chat v2 payload should include workspace scope');
assert.match(panelFile, /listChatConversations\(\{[\s\S]*limit:\s*20/, 'ChatPanel should request scoped history in batches of 20');
assert.match(panelFile, /加载更多/, 'ChatPanel should render a visible load-more action for paged history');
console.log('chatPanel.scope-history tests passed');
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test frontend/tests/frontend/chatPanel.scope-history.test.ts`

Expected: FAIL because the API and panel still use unscoped history calls

- [ ] **Step 3: Implement scoped/paged history requests and chat payload fields**

```ts
// frontend/src/services/teacher/api.ts
export interface ConversationScopeRequest {
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  aggregate?: boolean;
  limit?: number;
  offset?: number;
}

export const listChatConversations = async (
  params: ConversationScopeRequest = {},
): Promise<ConversationListResponse> => {
  const query = new URLSearchParams();
  if (params.course_id) query.set('course_id', params.course_id);
  if (params.scope_type) query.set('scope_type', params.scope_type);
  if (params.scope_id) query.set('scope_id', params.scope_id);
  if (params.aggregate) query.set('aggregate', 'true');
  if (typeof params.limit === 'number') query.set('limit', String(params.limit));
  if (typeof params.offset === 'number') query.set('offset', String(params.offset));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const resp = await fetch(`${BACKEND_BASE_URL}/api/chat/conversations${suffix}`, { ... });
  ...
};
```

```ts
// frontend/src/services/teacher/chatV2.ts
export interface ChatReplyRequestV2 {
  question: string;
  conversation_id?: string;
  model_id?: string;
  course_id?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  ...
}
```

```tsx
// frontend/src/components/teacher/ChatPanel.tsx
const HISTORY_PAGE_SIZE = 20;

const historyRequest = workspaceScope?.scopeType === 'knowledge_point'
  ? {
      course_id: workspaceScope.courseId,
      scope_type: 'knowledge_point' as const,
      scope_id: workspaceScope.scopeId,
      limit: HISTORY_PAGE_SIZE,
      offset: historyOffset,
    }
  : {
      course_id: workspaceScope?.courseId,
      scope_type: 'course' as const,
      aggregate: true,
      limit: HISTORY_PAGE_SIZE,
      offset: historyOffset,
    };

const result = await listChatConversations(historyRequest);
```

- [ ] **Step 4: Run the chat-panel scope tests**

Run: `node --test frontend/tests/frontend/chatPanel.scope-history.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/teacher/api.ts frontend/src/services/teacher/chatV2.ts frontend/src/components/teacher/ChatPanel.tsx frontend/tests/frontend/chatPanel.scope-history.test.ts
git commit -m "feat: add scoped chat history paging"
```

### Task 6: Make SourcePanel Scope-Aware for Reads and Uploads

**Files:**
- Modify: `frontend/src/services/knowledgeBase.ts`
- Modify: `frontend/src/components/teacher/SourcePanel.tsx`
- Test: `frontend/tests/frontend/sourcePanel.scope-documents.test.ts`

- [ ] **Step 1: Write the failing source-panel scope tests**

```ts
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const kbService = readFileSync(new URL('../../src/services/knowledgeBase.ts', import.meta.url), 'utf8');
const panel = readFileSync(new URL('../../src/components/teacher/SourcePanel.tsx', import.meta.url), 'utf8');

assert.match(kbService, /scope_type\?: 'course' \| 'knowledge_point'/, 'knowledgeBase service should accept scope params');
assert.match(panel, /workspaceScope/, 'SourcePanel should consume the active workspace scope');
assert.match(panel, /scopeType === 'course'[\s\S]*aggregate:\s*true/, 'SourcePanel should aggregate course-root documents');
assert.match(panel, /scopeType === 'knowledge_point'/, 'SourcePanel should request knowledge-point scoped documents');
assert.match(panel, /导入到课程总目录|导入到当前知识点/, 'SourcePanel should show a readable upload target label');
console.log('sourcePanel.scope-documents tests passed');
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test frontend/tests/frontend/sourcePanel.scope-documents.test.ts`

Expected: FAIL because document APIs and upload labeling are still course-only

- [ ] **Step 3: Implement scope-aware document list/upload behavior**

```ts
// frontend/src/services/knowledgeBase.ts
export interface KnowledgeBaseScopeParams {
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  aggregate?: boolean;
}

export async function getKnowledgeBaseDocuments(
  courseId: string,
  token: string,
  params: KnowledgeBaseScopeParams = {},
): Promise<KnowledgeBaseDocument[]> {
  const query = new URLSearchParams();
  if (params.scope_type) query.set('scope_type', params.scope_type);
  if (params.scope_id) query.set('scope_id', params.scope_id);
  if (params.aggregate) query.set('aggregate', 'true');
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/knowledge-base/documents${suffix}`, ...);
  ...
}
```

```tsx
// frontend/src/components/teacher/SourcePanel.tsx
const documentScopeParams =
  workspaceScope?.scopeType === 'knowledge_point'
    ? { scope_type: 'knowledge_point' as const, scope_id: workspaceScope.scopeId }
    : { scope_type: 'course' as const, aggregate: true };

const documents = await getKnowledgeBaseDocuments(courseId, token, documentScopeParams);

const uploadScopeLabel =
  workspaceScope?.scopeType === 'knowledge_point' ? '导入到当前知识点' : '导入到课程总目录';
```

- [ ] **Step 4: Run the source-panel scope tests**

Run: `node --test frontend/tests/frontend/sourcePanel.scope-documents.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/knowledgeBase.ts frontend/src/components/teacher/SourcePanel.tsx frontend/tests/frontend/sourcePanel.scope-documents.test.ts
git commit -m "feat: scope source panel documents"
```

### Task 7: Make StudioPanel Scope-Aware and Page Course-Root Generated Materials

**Files:**
- Modify: `frontend/src/store/teacher/useCourseMaterialsStore.ts`
- Modify: `frontend/src/components/teacher/StudioPanel.tsx`
- Modify: `frontend/src/services/teacher/api.ts`
- Test: `frontend/tests/frontend/studioPanel.scope-materials.test.ts`

- [ ] **Step 1: Write the failing studio-panel scope tests**

```ts
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const apiFile = readFileSync(new URL('../../src/services/teacher/api.ts', import.meta.url), 'utf8');
const storeFile = readFileSync(new URL('../../src/store/teacher/useCourseMaterialsStore.ts', import.meta.url), 'utf8');
const panelFile = readFileSync(new URL('../../src/components/teacher/StudioPanel.tsx', import.meta.url), 'utf8');

assert.match(apiFile, /scope_type\?: 'course' \| 'knowledge_point'/, 'teacher api materials helper should accept scope filters');
assert.match(storeFile, /scopeKey/, 'course materials store should key hydrated lists by scope');
assert.match(panelFile, /workspaceScope/, 'StudioPanel should consume workspaceScope');
assert.match(panelFile, /limit:\s*20/, 'StudioPanel should load generated materials in batches of 20');
assert.match(panelFile, /加载更多/, 'StudioPanel should expose a load-more action for generated materials');
console.log('studioPanel.scope-materials tests passed');
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test frontend/tests/frontend/studioPanel.scope-materials.test.ts`

Expected: FAIL because StudioPanel still hydrates from course-only materials

- [ ] **Step 3: Implement scope-aware generated-material reads and store hydration**

```ts
// frontend/src/services/teacher/api.ts
export interface CourseMaterialsScopeRequest {
  material_type?: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  aggregate?: boolean;
  limit?: number;
  offset?: number;
}

export const getCourseMaterials = async (
  courseId: string,
  params: CourseMaterialsScopeRequest = {},
) => {
  const query = new URLSearchParams();
  if (params.material_type) query.set('material_type', params.material_type);
  if (params.scope_type) query.set('scope_type', params.scope_type);
  if (params.scope_id) query.set('scope_id', params.scope_id);
  if (params.aggregate) query.set('aggregate', 'true');
  if (typeof params.limit === 'number') query.set('limit', String(params.limit));
  if (typeof params.offset === 'number') query.set('offset', String(params.offset));
  ...
};
```

```ts
// frontend/src/store/teacher/useCourseMaterialsStore.ts
interface CourseMaterialsState {
  materialsByScope: Record<string, CourseMaterial[]>;
  setMaterialsForScope: (scopeKey: string, materials: CourseMaterial[]) => void;
}

setMaterialsForScope: (scopeKey, materials) =>
  set((state) => ({
    materialsByScope: {
      ...state.materialsByScope,
      [scopeKey]: sortCourseMaterials(materials),
    },
  })),
```

```tsx
// frontend/src/components/teacher/StudioPanel.tsx
const MATERIAL_PAGE_SIZE = 20;
const materialScopeRequest =
  workspaceScope?.scopeType === 'knowledge_point'
    ? { scope_type: 'knowledge_point' as const, scope_id: workspaceScope.scopeId, limit: MATERIAL_PAGE_SIZE, offset: materialOffset }
    : { scope_type: 'course' as const, aggregate: true, limit: MATERIAL_PAGE_SIZE, offset: materialOffset };

const materials = await getCourseMaterials(courseId, materialScopeRequest);
```

- [ ] **Step 4: Run the studio-panel scope tests**

Run: `node --test frontend/tests/frontend/studioPanel.scope-materials.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/teacher/useCourseMaterialsStore.ts frontend/src/components/teacher/StudioPanel.tsx frontend/src/services/teacher/api.ts frontend/tests/frontend/studioPanel.scope-materials.test.ts
git commit -m "feat: scope generated materials in studio"
```

### Task 8: End-to-End Regression Pass for Scope Inheritance and Verification

**Files:**
- Modify: `backend/src/tests/chat/test_conversation_scope_routes.py`
- Modify: `backend/src/tests/chat/test_course_scope_materials_routes.py`
- Modify: `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts`
- Modify: `frontend/tests/frontend/aiStudioLayout.test.ts`

- [ ] **Step 1: Add failing regression assertions for scope inheritance**

```python
def test_generated_material_keeps_scope_metadata(tmp_path):
    from core.course_storage import CourseStorageManager

    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("computational-thinking")
    ok = manager.save_generated_material(
        "computational-thinking",
        "report",
        "report-scope-1",
        {
            "title": "排序总结",
            "scope_type": "knowledge_point",
            "scope_id": "sorting",
        },
    )
    assert ok is True
    material = manager.get_generated_material("computational-thinking", "report", "report-scope-1")
    assert material["scope_type"] == "knowledge_point"
    assert material["scope_id"] == "sorting"
```

```ts
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const aiStudioPage = readFileSync(new URL('../../src/pages/teacher/AiStudioPage.tsx', import.meta.url), 'utf8');
assert.match(aiStudioPage, /课程总目录/, 'AiStudioPage should show a readable course-root label');
assert.match(aiStudioPage, /当前知识点/, 'AiStudioPage should keep the top context label readable after scope refactor');
console.log('scope regression text checks passed');
```

- [ ] **Step 2: Run the focused regression suite and confirm failures**

Run: `pytest backend/src/tests/chat/test_workspace_scope.py backend/src/tests/chat/test_conversation_scope_routes.py backend/src/tests/chat/test_course_scope_materials_routes.py -v`

Expected: PASS for earlier cases and FAIL for any newly added inheritance gap

Run: `node --test frontend/tests/frontend/aiStudioScopeRouting.test.ts frontend/tests/frontend/chatPanel.scope-history.test.ts frontend/tests/frontend/sourcePanel.scope-documents.test.ts frontend/tests/frontend/studioPanel.scope-materials.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts`

Expected: PASS for earlier checks and FAIL if any new readable labels or scope wiring are missing

- [ ] **Step 3: Fill the final gaps**

```python
# Ensure every generated material save path passes scope through unchanged
next_data["scope_type"] = str(next_data.get("scope_type") or existing_data.get("scope_type") or "course")
next_data["scope_id"] = next_data.get("scope_id", existing_data.get("scope_id"))
```

```tsx
// Keep top-bar labels readable and explicit
const scopeLabel = workspaceScope?.scopeType === 'knowledge_point' ? knowledgePointLabel : '课程总目录';
```

- [ ] **Step 4: Run the final verification suite**

Run: `pytest backend/src/tests/chat/test_workspace_scope.py backend/src/tests/chat/test_conversation_scope_routes.py backend/src/tests/chat/test_course_scope_materials_routes.py -v`

Expected: PASS

Run: `node --test frontend/tests/frontend/aiStudioScopeRouting.test.ts frontend/tests/frontend/chatPanel.scope-history.test.ts frontend/tests/frontend/sourcePanel.scope-documents.test.ts frontend/tests/frontend/studioPanel.scope-materials.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts frontend/tests/frontend/aiStudioLayout.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/tests/chat/test_workspace_scope.py backend/src/tests/chat/test_conversation_scope_routes.py backend/src/tests/chat/test_course_scope_materials_routes.py frontend/tests/frontend/aiStudioScopeRouting.test.ts frontend/tests/frontend/chatPanel.scope-history.test.ts frontend/tests/frontend/sourcePanel.scope-documents.test.ts frontend/tests/frontend/studioPanel.scope-materials.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts frontend/tests/frontend/aiStudioLayout.test.ts
git commit -m "test: verify scoped AI workspace flows"
```

---

## Self-Review

### Spec Coverage Check

- Course-root vs knowledge-point dual scope: covered by Tasks 1, 2, 4
- Knowledge-graph jump into scoped AI chat: covered by Task 4
- Scope-aware chat persistence and history reads: covered by Task 2 and Task 5
- Scope-aware personal knowledge-base reads/uploads: covered by Task 3 and Task 6
- Scope-aware generated artifact reads and inheritance: covered by Task 3 and Task 7
- Parent knowledge point subtree aggregation: covered by Task 1 and reused in Tasks 2 and 3
- Course-root aggregate reads across all knowledge points: covered by Tasks 2, 3, 5, 6, 7
- 20-at-a-time pagination for history and generated materials: covered by Tasks 5 and 7
- Old course-level data remaining in the course root: covered by Task 3 filter semantics and verified in Task 8

No uncovered spec section remains.

### Placeholder Scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every code-change step includes an explicit snippet.
- Every test/run step includes an exact command and expected outcome.

### Type Consistency Check

- Backend uses `scope_type` and `scope_id` consistently.
- Frontend uses `scopeType` and `scopeId` in component/store helpers and maps them to backend `scope_type` and `scope_id` at service boundaries.
- Course-root aggregate reads always use `scope_type=course` plus `aggregate=true`.

No type-name drift remains in the plan.
