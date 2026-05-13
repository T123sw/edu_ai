# Knowledge Graph Textbook Import Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the left-side textbook import on the knowledge graph page generate and persist the graph only on first import, then reuse the saved graph for later textbook imports while classifying split documents into course knowledge-base scopes by pure rules.

**Architecture:** Keep the existing `POST /api/courses/{course_id}/knowledge-graph/textbook-import` entrypoint, but refactor the backend service in `app/textbook_knowledge_graph.py` into two branches: initial graph generation and saved-graph reuse. Add pure rule helpers that flatten graph nodes, normalize titles, assign each split document to a node or the course root, then persist those split documents through the normal course knowledge-base index before vectorization.

**Tech Stack:** FastAPI, Python course storage utilities, existing RAG import pipeline, pytest, React/TypeScript API types.

---

### Task 1: Lock the new backend behavior with failing tests

**Files:**
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_service.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_routes.py`
- Reference: `Edu_AI/api/Edu_AI/app/textbook_knowledge_graph.py`

- [ ] **Step 1: Write the failing service tests for first-import graph generation and later graph reuse**

```python
from pathlib import Path

from app import textbook_knowledge_graph as textbook_module
from core.course_storage import CourseStorageManager


class FakeRagSystem:
    def __init__(self):
        self.imported = []

    def import_document(self, file_path, force_reimport=False):
        self.imported.append((str(file_path), force_reimport))
        return {"status": "success", "message": "ok", "chunk_count": 1}

    def delete_document(self, file_path):
        return None


def test_import_textbook_generates_graph_only_when_course_has_no_graph(tmp_path, monkeypatch):
    manager = CourseStorageManager(base_dir=tmp_path / "courses")
    manager.save_course_info("course-1", {"id": "course-1", "title": "计算思维"})
    rag = FakeRagSystem()

    monkeypatch.setattr(textbook_module, "_parse_textbook_content", lambda *args, **kwargs: ("# 第1章 排序\n\n内容", "markdown", []))
    monkeypatch.setattr(textbook_module, "_extract_outline_candidates", lambda markdown: ["第1章 排序"])
    monkeypatch.setattr(
        textbook_module,
        "_invoke_outline_model",
        lambda **kwargs: {
            "course_title": "计算思维",
            "summary": "课程摘要",
            "chapters": [{"title": "排序", "summary": "排序摘要", "sections": [], "content": "排序内容"}],
        },
    )

    first = textbook_module.import_textbook_into_knowledge_graph(
        course_id="course-1",
        filename="book-a.md",
        file_bytes=b"# 第1章 排序\n\n内容",
        manager=manager,
        rag_system=rag,
    )

    saved_graph = manager.get_knowledge_graph("course-1")
    assert first["graph_reused"] is False
    assert saved_graph["label"] == "计算思维"

    monkeypatch.setattr(
        textbook_module,
        "_invoke_outline_model",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("reuse path must not rebuild graph")),
    )
    second = textbook_module.import_textbook_into_knowledge_graph(
        course_id="course-1",
        filename="book-b.md",
        file_bytes=b"# 第1章 排序\n\n新内容",
        manager=manager,
        rag_system=rag,
    )

    assert second["graph_reused"] is True
    assert second["knowledge_graph"]["root"] == saved_graph
```

- [ ] **Step 2: Add a failing service test for rule-based scope assignment and course-root fallback**

```python
def test_import_textbook_assigns_split_documents_to_matching_node_or_course_root(tmp_path, monkeypatch):
    manager = CourseStorageManager(base_dir=tmp_path / "courses")
    manager.save_course_info("course-1", {"id": "course-1", "title": "计算思维"})
    manager.save_knowledge_graph(
        "course-1",
        {
            "id": "root",
            "label": "计算思维",
            "children": [
                {"id": "sorting", "label": "排序", "children": [], "data": {"level": 1, "hasChildren": False, "type": "concept"}},
            ],
            "data": {"level": 0, "hasChildren": True, "type": "course"},
        },
    )
    rag = FakeRagSystem()

    monkeypatch.setattr(textbook_module, "_parse_textbook_content", lambda *args, **kwargs: ("# 第1章 排序\n\n内容", "markdown", []))
    monkeypatch.setattr(textbook_module, "_extract_outline_candidates", lambda markdown: ["第1章 排序"])
    monkeypatch.setattr(
        textbook_module,
        "_split_parsed_markdown_by_outline",
        lambda **kwargs: [
            {"title": "第1章 排序", "summary": "a", "sections": [], "content": "排序内容"},
            {"title": "附录 术语表", "summary": "b", "sections": [], "content": "术语内容"},
        ],
    )
    monkeypatch.setattr(
        textbook_module,
        "_merge_outline_with_splits",
        lambda **kwargs: {
            "course_title": "计算思维",
            "summary": "课程摘要",
            "outline_source": "saved-graph",
            "env_path": None,
            "chapters": kwargs["split_chapters"],
        },
    )

    result = textbook_module.import_textbook_into_knowledge_graph(
        course_id="course-1",
        filename="book-c.md",
        file_bytes=b"# 第1章 排序\n\n内容",
        manager=manager,
        rag_system=rag,
    )

    split_documents = result["split_documents"]
    assert split_documents[0]["matched_scope_type"] == "knowledge_point"
    assert split_documents[0]["matched_scope_id"] == "sorting"
    assert split_documents[1]["matched_scope_type"] == "course"
    assert split_documents[1]["fallback_to_course_root"] is True
    assert result["import_summary"]["fallback_to_course_root_count"] == 1
```

- [ ] **Step 3: Add a failing route test for the expanded response contract**

```python
def test_textbook_import_route_returns_graph_reuse_and_import_summary(monkeypatch):
    monkeypatch.setattr(courses_module, "_get_manager", lambda: DummyManager())
    monkeypatch.setattr(
        courses_module,
        "import_textbook_into_knowledge_graph",
        lambda **kwargs: {
            "source_document": {"name": "book.pdf"},
            "parser_used": "mineru",
            "outline_source": "saved-graph",
            "graph_reused": True,
            "knowledge_graph": {"root": {"id": "root", "label": "Course", "children": [], "data": {"level": 0, "hasChildren": False, "type": "concept"}}},
            "split_documents": [{"id": "split-1", "title": "排序", "file_path": "knowledge_base/documents/01-sorting.md", "matched_scope_type": "knowledge_point", "matched_scope_id": "sorting", "matched_node_label": "排序", "fallback_to_course_root": False}],
            "vectorized_documents": [],
            "import_summary": {"total_split_count": 1, "matched_node_count": 1, "fallback_to_course_root_count": 0},
            "warnings": [],
        },
    )

    response = make_client().post(
        "/api/courses/course-1/knowledge-graph/textbook-import",
        files={"file": ("book.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["graph_reused"] is True
    assert payload["import_summary"]["total_split_count"] == 1
```

- [ ] **Step 4: Run the focused tests to verify they fail for the right reasons**

Run:

```bash
pytest Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_routes.py -v
pytest Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_service.py -v
```

Expected:

- Route test fails because `graph_reused` / `import_summary` are not yet part of the mocked contract or response expectations
- Service tests fail because `import_textbook_into_knowledge_graph(...)` still always rebuilds the graph and does not assign split documents into scoped course knowledge-base entries

- [ ] **Step 5: Commit the red tests**

```bash
git add Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_routes.py Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_service.py
git commit -m "test: cover textbook import graph reuse behavior"
```

### Task 2: Implement graph reuse and pure rule matching in the backend

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/textbook_knowledge_graph.py`
- Reference: `Edu_AI/api/Edu_AI/core/course_storage.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_service.py`

- [ ] **Step 1: Add minimal helper functions for graph flattening and title normalization**

```python
def _normalize_match_title(value: str) -> str:
    text = re.sub(r"^\s*(第\s*[0-9一二三四五六七八九十百]+[章节篇部]|chapter\s*\d+|\d+(\.\d+)*|[（(]?[一二三四五六七八九十]+[)）]?、?)\s*", "", str(value or ""), flags=re.IGNORECASE)
    text = text.replace("：", ":").replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _flatten_graph_nodes(root: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []

    def walk(node: Dict[str, Any], *, is_root: bool = False) -> None:
        nodes.append(
            {
                "node_id": str(node.get("id") or ""),
                "label": str(node.get("label") or ""),
                "normalized_label": _normalize_match_title(str(node.get("label") or "")),
                "is_root": is_root,
            }
        )
        for child in node.get("children") or []:
            walk(child, is_root=False)

    walk(root, is_root=True)
    return nodes
```

- [ ] **Step 2: Add minimal helper functions for picking a scope from a split document**

```python
def _match_split_document_scope(split_document: Dict[str, Any], graph_root: Dict[str, Any]) -> Dict[str, Any]:
    nodes = _flatten_graph_nodes(graph_root)
    root_node = next((node for node in nodes if node["is_root"]), None)
    title_candidates = [str(split_document.get("title") or "")]
    title_candidates.extend(str(title or "") for title in split_document.get("section_titles") or [])

    for candidate in title_candidates:
        normalized = _normalize_match_title(candidate)
        if not normalized:
            continue
        for node in nodes:
            if normalized == node["normalized_label"] and not node["is_root"]:
                return {
                    "matched_scope_type": "knowledge_point",
                    "matched_scope_id": node["node_id"],
                    "matched_node_label": node["label"],
                    "fallback_to_course_root": False,
                }

    return {
        "matched_scope_type": "course",
        "matched_scope_id": None,
        "matched_node_label": root_node["label"] if root_node else "",
        "fallback_to_course_root": True,
    }
```

- [ ] **Step 3: Refactor the main import flow so it only generates a graph when none exists**

```python
existing_graph = manager.get_knowledge_graph(course_id)
graph_reused = isinstance(existing_graph, dict) and bool(existing_graph)

if graph_reused:
    knowledge_graph = existing_graph
    normalized_outline = None
    split_chapters = _split_parsed_markdown_by_outline_using_graph(
        parsed_markdown=parsed_markdown,
        graph_root=knowledge_graph,
    )
    merged_outline = _merge_graph_reuse_chapters(
        course_title=course_title,
        split_chapters=split_chapters,
    )
else:
    outline = _invoke_outline_model(payload=llm_payload, explicit_env_path=explicit_env_path)
    normalized_outline = _normalize_outline_from_llm(course_title=course_title, outline=outline)
    split_chapters = _split_parsed_markdown_by_outline(parsed_markdown=parsed_markdown, outline=normalized_outline)
    merged_outline = _merge_outline_with_splits(course_title=course_title, split_chapters=split_chapters, outline=normalized_outline)
    knowledge_graph = _build_knowledge_graph(merged_outline["course_title"], merged_outline["summary"], merged_outline["chapters"])
    if not manager.save_knowledge_graph(course_id, knowledge_graph):
        raise TextbookKnowledgeGraphError("Failed to persist generated knowledge graph.")
```

- [ ] **Step 4: Persist split documents into the scoped course knowledge-base index before vectorization**

```python
def _persist_split_documents_to_course_kb(*, course_id: str, split_documents: List[Dict[str, Any]], graph_root: Dict[str, Any], manager: CourseStorageManager) -> List[Dict[str, Any]]:
    persisted: List[Dict[str, Any]] = []
    course_dir = manager.get_course_dir(course_id)

    for split_document in split_documents:
        match_info = _match_split_document_scope(split_document, graph_root)
        absolute_path = Path(str(split_document["absolute_path"]))
        relative_path = manager.save_knowledge_base_file(
            course_id,
            absolute_path.read_bytes(),
            absolute_path.name,
            scope_type=match_info["matched_scope_type"],
            scope_id=match_info["matched_scope_id"],
            library_type="course",
        )
        persisted.append({**split_document, **match_info, "knowledge_base_file_path": relative_path})

    return persisted
```

- [ ] **Step 5: Return the new response fields and keep generated material writes consistent**

```python
persisted_split_documents = _persist_split_documents_to_course_kb(
    course_id=course_id,
    split_documents=split_documents,
    graph_root=knowledge_graph,
    manager=manager,
)
vectorized_documents = _vectorize_split_documents(persisted_split_documents, rag_system)
import_summary = {
    "total_split_count": len(persisted_split_documents),
    "matched_node_count": sum(1 for item in persisted_split_documents if item["matched_scope_type"] == "knowledge_point"),
    "fallback_to_course_root_count": sum(1 for item in persisted_split_documents if item["fallback_to_course_root"]),
}

return {
    "graph_reused": graph_reused,
    "knowledge_graph": {"root": knowledge_graph},
    "split_documents": [
        {
            "id": item["id"],
            "title": item["title"],
            "section_titles": item["section_titles"],
            "file_path": item["knowledge_base_file_path"] or item["file_path"],
            "matched_scope_type": item["matched_scope_type"],
            "matched_scope_id": item["matched_scope_id"],
            "matched_node_label": item["matched_node_label"],
            "fallback_to_course_root": item["fallback_to_course_root"],
        }
        for item in persisted_split_documents
    ],
    "import_summary": import_summary,
    "vectorized_documents": vectorized_documents,
    "warnings": warnings,
}
```

- [ ] **Step 6: Run the focused tests to verify they pass**

Run:

```bash
pytest Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_service.py -v
pytest Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_routes.py -v
```

Expected:

- All textbook-import route tests pass
- New service tests pass, proving first import builds a graph, later imports reuse the saved graph, and split documents are classified into the matched knowledge point or course root

- [ ] **Step 7: Commit the backend implementation**

```bash
git add Edu_AI/api/Edu_AI/app/textbook_knowledge_graph.py Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_routes.py Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_service.py
git commit -m "feat: reuse saved knowledge graph for textbook imports"
```

### Task 3: Update the frontend contract without changing the entrypoint

**Files:**
- Modify: `Edu_AI/src/services/teacher/api.ts`
- Modify: `Edu_AI/src/pages/teacher/KnowledgeGraphPage.tsx`
- Test: verify manually from existing UI behavior after backend tests pass

- [ ] **Step 1: Expand the frontend TypeScript response interfaces**

```ts
export interface TextbookKnowledgeGraphImportSplitDocument {
  id: string;
  title: string;
  file_path: string;
  preview?: string;
  matched_scope_type?: 'course' | 'knowledge_point';
  matched_scope_id?: string | null;
  matched_node_label?: string;
  fallback_to_course_root?: boolean;
}

export interface TextbookKnowledgeGraphImportResponse {
  source_document: {
    id?: string;
    name: string;
    file_path?: string | null;
  };
  parser_used?: string;
  outline_source?: string;
  graph_reused?: boolean;
  knowledge_graph: KnowledgeGraphData;
  split_documents: TextbookKnowledgeGraphImportSplitDocument[];
  vectorized_documents: Array<Record<string, unknown>>;
  import_summary?: {
    total_split_count: number;
    matched_node_count: number;
    fallback_to_course_root_count: number;
  };
  warnings: string[];
}
```

- [ ] **Step 2: Keep the same button flow but update the success message to reflect graph reuse**

```tsx
const result = await importTextbookKnowledgeGraph(courseId, file);
const root = convertBackendToTreeGraph(result.knowledge_graph.root);
setTextbookImportSummary(result);
await applyGraphRoot(root);

if (result.warnings.length) {
  message.warning(`教材已导入，但有 ${result.warnings.length} 条提示信息`);
} else if (result.graph_reused) {
  message.success(`教材已按当前知识图谱归档入库，未重建知识图谱`);
} else {
  message.success(`已根据教材《${result.source_document.name}》生成并保存课程知识图谱`);
}
```

- [ ] **Step 3: Surface the new summary tags in the right-side import summary card**

```tsx
{textbookImportSummary.import_summary ? (
  <>
    <Tag color="blue">切片 {textbookImportSummary.import_summary.total_split_count}</Tag>
    <Tag color="green">命中节点 {textbookImportSummary.import_summary.matched_node_count}</Tag>
    <Tag color="gold">回落根节点 {textbookImportSummary.import_summary.fallback_to_course_root_count}</Tag>
    {textbookImportSummary.graph_reused ? <Tag color="purple">复用图谱</Tag> : <Tag color="cyan">首次建图</Tag>}
  </>
) : null}
```

- [ ] **Step 4: Run the minimal frontend checks**

Run:

```bash
npm test -- KnowledgeGraphPage
```

If there is no focused frontend test target for this page, do this instead:

```bash
npm run build
```

Expected:

- TypeScript compiles with the expanded response type
- The page still renders the returned `knowledge_graph.root`
- No change is required for the right-side direct knowledge-base upload button

- [ ] **Step 5: Commit the frontend contract update**

```bash
git add Edu_AI/src/services/teacher/api.ts Edu_AI/src/pages/teacher/KnowledgeGraphPage.tsx
git commit -m "feat: show textbook import graph reuse summary"
```

### Task 4: Run targeted regression verification and close the loop

**Files:**
- Verify only; no planned code changes

- [ ] **Step 1: Re-run the course scope regression tests to prove right-side uploads are unchanged**

Run:

```bash
pytest Edu_AI/api/Edu_AI/tests/chat/test_course_scope_routes.py -v
```

Expected:

- Existing tests covering `upload_knowledge_base_document(...)` still pass
- Knowledge-point uploads still write `scope_type="knowledge_point"` and course-root uploads still write `scope_type="course"`

- [ ] **Step 2: Re-run the textbook import tests together**

Run:

```bash
pytest Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_routes.py Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_service.py -v
```

Expected:

- All route and service tests pass together
- The response contract and backend persistence flow stay aligned

- [ ] **Step 3: Inspect the final diff for accidental spillover into unrelated PPT work**

Run:

```bash
git diff --stat HEAD~3..HEAD
git status --short
```

Expected:

- Only the intended knowledge-graph textbook import files are part of the new commits
- Existing unrelated PPT changes remain untouched in the working tree

- [ ] **Step 4: Create the final implementation commit if verification required follow-up edits**

```bash
git add Edu_AI/api/Edu_AI/app/textbook_knowledge_graph.py Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_routes.py Edu_AI/api/Edu_AI/tests/chat/test_textbook_knowledge_graph_service.py Edu_AI/src/services/teacher/api.ts Edu_AI/src/pages/teacher/KnowledgeGraphPage.tsx
git commit -m "test: verify textbook import graph reuse flow"
```

## Self-Review

Spec coverage check:

- “首次生成知识图谱并保存” is covered by Task 1 service red tests and Task 2 graph generation branch.
- “后续复用已存图谱，不再重建” is covered by Task 1 reuse red test and Task 2 branch refactor.
- “纯规则匹配，未命中落课程根节点” is covered by Task 1 scope-assignment red test and Task 2 helper functions.
- “切片写入课程知识库索引并向量化” is covered by Task 2 persistence helper and returned split-document metadata.
- “右侧导入逻辑不变” is covered by Task 4 regression run of `test_course_scope_routes.py`.
- “前端按返回图谱渲染并展示摘要” is covered by Task 3 type and UI updates.

Placeholder scan:

- No `TODO` / `TBD` placeholders remain.
- Each code-changing step includes concrete code snippets.
- Each verification step includes exact commands and expected outcomes.

Type consistency check:

- Response field names are consistent across backend and frontend: `graph_reused`, `import_summary`, `matched_scope_type`, `matched_scope_id`, `matched_node_label`, `fallback_to_course_root`.
- Scope values are consistently `knowledge_point` or `course`.
- The plan keeps the existing route path unchanged throughout.
