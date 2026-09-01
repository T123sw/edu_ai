# Knowledge Graph Hour Allocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-owned knowledge graph hour allocation flow that asks the LLM to allocate one-decimal course hours to leaf nodes, rolls those hours up to parents, persists the graph, and exposes it through the teacher knowledge graph page.

**Architecture:** Put traversal, prompt building, parsing, normalization, and rollup in a focused backend service module. Add one `courses.py` route that loads/saves graphs and maps errors to HTTP responses. Update the stitch frontend API/types/page so the button calls the backend and renders `data.hours`.

**Tech Stack:** FastAPI, Pydantic, pytest, existing `CourseStorageManager`, existing RAG/LLM `_call_llm` surface, React, TypeScript, Vite, lightweight Node frontend regression tests.

---

## File Structure

- Create `backend/src/app/knowledge_graph_hours.py`
  - Owns pure graph-hour allocation helpers and the LLM-backed orchestration function.
  - Defines deterministic exceptions and return metadata used by the route.
- Create `backend/src/tests/chat/test_knowledge_graph_hours.py`
  - Pure backend tests for leaf extraction, JSON parsing, one-decimal normalization, and parent rollup.
- Create `backend/src/tests/chat/test_knowledge_graph_hour_routes.py`
  - FastAPI route tests with a dummy course manager and monkeypatched allocation service.
- Modify `backend/src/app/courses.py`
  - Adds request/response models and `POST /{course_id}/knowledge-graph/allocate-hours`.
  - Adds a small internal LLM caller wrapper that uses the configured backend model.
- Modify `frontend/src/stitch/api/types.ts`
  - Adds `hours?: number` to `KnowledgeGraphNode.data`.
  - Adds allocation request/response types.
- Modify `frontend/src/stitch/api/courses.ts`
  - Adds `allocateKnowledgeGraphHours`.
- Modify `frontend/src/stitch/pages/KnowledgeGraph.tsx`
  - Preserves `data.hours` in flatten/build helpers.
  - Calls backend allocation route from the total-hours button.
  - Displays allocation loading/error state.
- Create `frontend/tests/frontend/knowledgeGraphHours.test.ts`
  - Lightweight frontend regression test that checks API helper, type field, and page wiring exist.

## Task 1: Backend Pure Tests For Allocation Helpers

**Files:**
- Create: `backend/src/tests/chat/test_knowledge_graph_hours.py`
- Later implementation target: `backend/src/app/knowledge_graph_hours.py`

- [ ] **Step 1: Write the failing pure-helper tests**

Create `backend/src/tests/chat/test_knowledge_graph_hours.py`:

```python
import pytest

from app.knowledge_graph_hours import (
    KnowledgeGraphHourAllocationError,
    allocate_graph_hours_from_llm,
    collect_leaf_nodes,
    parse_llm_allocations,
    rollup_hours,
    validate_total_hours_to_tenths,
)


def sample_graph():
    return {
        "id": "root",
        "label": "Course",
        "data": {"summary": "Course summary", "type": "concept"},
        "children": [
            {
                "id": "chapter-1",
                "label": "Chapter 1",
                "data": {"summary": "Basics", "type": "chapter"},
                "children": [
                    {
                        "id": "leaf-a",
                        "label": "Core concept",
                        "data": {"summary": "Important prerequisite", "type": "concept"},
                        "children": [],
                    },
                    {
                        "id": "leaf-b",
                        "label": "Practice task",
                        "data": {"summary": "Practice-heavy task", "type": "topic"},
                    },
                ],
            },
            {
                "id": "leaf-c",
                "label": "Reference topic",
                "data": {"summary": "Optional reference", "type": "concept"},
                "children": [],
            },
        ],
    }


def test_collect_leaf_nodes_includes_path_depth_and_metadata():
    leaves = collect_leaf_nodes(sample_graph())

    assert [leaf.node_id for leaf in leaves] == ["leaf-a", "leaf-b", "leaf-c"]
    assert leaves[0].label == "Core concept"
    assert leaves[0].path == ["Course", "Chapter 1", "Core concept"]
    assert leaves[0].depth == 2
    assert leaves[1].summary == "Practice-heavy task"
    assert leaves[2].node_type == "concept"


def test_validate_total_hours_uses_integer_tenths():
    assert validate_total_hours_to_tenths(32) == 320
    assert validate_total_hours_to_tenths(32.5) == 325
    assert validate_total_hours_to_tenths("0.1") == 1


@pytest.mark.parametrize("value", [-1, "2.25", "abc", None])
def test_validate_total_hours_rejects_invalid_values(value):
    with pytest.raises(KnowledgeGraphHourAllocationError):
        validate_total_hours_to_tenths(value)


def test_parse_llm_allocations_accepts_json_object_and_ignores_reasons():
    raw = """
    {
      "allocations": [
        {"node_id": "leaf-a", "hours": 1.5, "reason": "core"},
        {"node_id": "leaf-b", "hours": "0.5"}
      ]
    }
    """

    assert parse_llm_allocations(raw) == {"leaf-a": 1.5, "leaf-b": 0.5}


def test_parse_llm_allocations_accepts_fenced_json():
    raw = """```json
    {"allocations": [{"node_id": "leaf-a", "hours": 2}]}
    ```"""

    assert parse_llm_allocations(raw) == {"leaf-a": 2.0}


def test_parse_llm_allocations_rejects_unparseable_output():
    with pytest.raises(KnowledgeGraphHourAllocationError):
        parse_llm_allocations("not json")


def test_allocate_graph_hours_normalizes_missing_extra_and_over_total_values():
    def fake_llm(prompt: str) -> str:
        assert "leaf-a" in prompt
        assert "chapter-1" not in prompt
        return """
        {
          "allocations": [
            {"node_id": "leaf-a", "hours": 9.4},
            {"node_id": "leaf-b", "hours": 0.2},
            {"node_id": "unknown", "hours": 99}
          ]
        }
        """

    updated, meta = allocate_graph_hours_from_llm(sample_graph(), 2.5, fake_llm)

    leaves = {child["id"]: child for child in updated["children"][0]["children"]}
    assert leaves["leaf-a"]["data"]["hours"] == 2.3
    assert leaves["leaf-b"]["data"]["hours"] == 0.2
    assert updated["children"][1]["data"]["hours"] == 0
    assert updated["children"][0]["data"]["hours"] == 2.5
    assert updated["data"]["hours"] == 2.5
    assert meta == {
        "total_hours": 2.5,
        "leaf_count": 3,
        "source": "llm",
        "normalized": True,
    }


def test_allocate_graph_hours_distributes_missing_tenths_and_allows_zero_leaf_hours():
    def fake_llm(prompt: str) -> str:
        return '{"allocations": [{"node_id": "leaf-a", "hours": 0.5}]}'

    updated, meta = allocate_graph_hours_from_llm(sample_graph(), "1.0", fake_llm)

    leaves = {child["id"]: child for child in updated["children"][0]["children"]}
    assert leaves["leaf-a"]["data"]["hours"] == 1.0
    assert leaves["leaf-b"]["data"]["hours"] == 0
    assert updated["children"][1]["data"]["hours"] == 0
    assert updated["data"]["hours"] == 1.0
    assert meta["normalized"] is True


def test_allocate_graph_hours_preserves_existing_metadata():
    def fake_llm(prompt: str) -> str:
        return '{"allocations": [{"node_id": "leaf-a", "hours": 1.0}]}'

    updated, _ = allocate_graph_hours_from_llm(sample_graph(), 1.0, fake_llm)

    leaf_a = updated["children"][0]["children"][0]
    assert leaf_a["data"]["summary"] == "Important prerequisite"
    assert leaf_a["data"]["type"] == "concept"
    assert leaf_a["data"]["hours"] == 1.0


def test_rollup_hours_uses_child_sums_not_existing_parent_values():
    graph = sample_graph()
    graph["data"]["hours"] = 999
    graph["children"][0]["data"]["hours"] = 999
    graph["children"][0]["children"][0]["data"]["hours"] = 1.2
    graph["children"][0]["children"][1]["data"]["hours"] = 0.8
    graph["children"][1]["data"]["hours"] = 0.5

    total_tenths = rollup_hours(graph)

    assert total_tenths == 25
    assert graph["children"][0]["data"]["hours"] == 2.0
    assert graph["data"]["hours"] == 2.5


def test_allocate_graph_hours_rejects_graph_without_leaves():
    with pytest.raises(KnowledgeGraphHourAllocationError):
        allocate_graph_hours_from_llm({"id": "root", "label": "Broken", "children": "bad"}, 1.0, lambda _: "{}")
```

- [ ] **Step 2: Run the pure-helper tests and verify RED**

Run:

```bash
cd backend/src
python -m pytest tests/chat/test_knowledge_graph_hours.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'app.knowledge_graph_hours'`.

- [ ] **Step 3: Commit the RED test**

```bash
git add backend/src/tests/chat/test_knowledge_graph_hours.py
git commit -m "test: add knowledge graph hour allocation helper tests"
```

## Task 2: Backend Allocation Service

**Files:**
- Create: `backend/src/app/knowledge_graph_hours.py`
- Test: `backend/src/tests/chat/test_knowledge_graph_hours.py`

- [ ] **Step 1: Implement the minimal service module**

Create `backend/src/app/knowledge_graph_hours.py`:

```python
"""Knowledge graph teaching-hour allocation helpers."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, Dict, Iterable, List, Tuple


class KnowledgeGraphHourAllocationError(ValueError):
    """Raised when a graph hour allocation request cannot be completed."""


@dataclass(frozen=True)
class LeafNodeInfo:
    node_id: str
    label: str
    summary: str
    node_type: str
    depth: int
    path: List[str]
    order: int


def _ensure_dict_node(node: Any) -> Dict[str, Any]:
    if not isinstance(node, dict):
        raise KnowledgeGraphHourAllocationError("knowledge graph root must be an object")
    if not str(node.get("id") or "").strip():
        raise KnowledgeGraphHourAllocationError("knowledge graph node is missing id")
    if not str(node.get("label") or "").strip():
        raise KnowledgeGraphHourAllocationError("knowledge graph node is missing label")
    return node


def _children(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    children = node.get("children")
    if children is None:
        return []
    if not isinstance(children, list):
        return []
    return [child for child in children if isinstance(child, dict)]


def collect_leaf_nodes(root: Dict[str, Any]) -> List[LeafNodeInfo]:
    root = _ensure_dict_node(root)
    leaves: List[LeafNodeInfo] = []

    def visit(node: Dict[str, Any], path: List[str], depth: int) -> None:
        node = _ensure_dict_node(node)
        label = str(node.get("label") or "").strip()
        node_path = [*path, label]
        child_nodes = _children(node)
        if not child_nodes:
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            leaves.append(
                LeafNodeInfo(
                    node_id=str(node.get("id") or "").strip(),
                    label=label,
                    summary=str(data.get("summary") or "").strip(),
                    node_type=str(data.get("type") or "").strip() or "concept",
                    depth=depth,
                    path=node_path,
                    order=len(leaves),
                )
            )
            return
        for child in child_nodes:
            visit(child, node_path, depth + 1)

    visit(root, [], 0)
    if not leaves:
        raise KnowledgeGraphHourAllocationError("knowledge graph has no leaf nodes")
    return leaves


def validate_total_hours_to_tenths(value: Any) -> int:
    if value is None:
        raise KnowledgeGraphHourAllocationError("total_hours is required")
    text = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.\d)?", text):
        raise KnowledgeGraphHourAllocationError("total_hours must be non-negative with at most one decimal place")
    try:
        decimal_value = Decimal(text)
    except InvalidOperation as exc:
        raise KnowledgeGraphHourAllocationError("total_hours must be a valid number") from exc
    if decimal_value < 0:
        raise KnowledgeGraphHourAllocationError("total_hours must be non-negative")
    return int((decimal_value * Decimal("10")).to_integral_value(rounding=ROUND_HALF_UP))


def _hours_to_tenths(value: Any) -> int:
    try:
        decimal_value = Decimal(str(value).strip())
    except Exception:
        return 0
    if decimal_value < 0:
        return 0
    return int((decimal_value * Decimal("10")).to_integral_value(rounding=ROUND_HALF_UP))


def _tenths_to_hours(value: int) -> float | int:
    if value % 10 == 0:
        return value // 10
    return float(Decimal(value) / Decimal("10"))


def parse_llm_allocations(raw: str) -> Dict[str, float]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        payload = json.loads(text)
    except Exception as exc:
        raise KnowledgeGraphHourAllocationError("LLM allocation output is not parseable JSON") from exc

    allocations = payload.get("allocations") if isinstance(payload, dict) else payload
    if not isinstance(allocations, list):
        raise KnowledgeGraphHourAllocationError("LLM allocation output must include an allocations list")

    result: Dict[str, float] = {}
    for item in allocations:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("node_id") or "").strip()
        if not node_id:
            continue
        tenths = _hours_to_tenths(item.get("hours"))
        result[node_id] = float(Decimal(tenths) / Decimal("10"))

    if not result:
        raise KnowledgeGraphHourAllocationError("LLM allocation output did not include any usable node allocations")
    return result


def _build_prompt(leaves: Iterable[LeafNodeInfo], total_hours: float | int) -> str:
    leaf_payload = [
        {
            "id": leaf.node_id,
            "label": leaf.label,
            "summary": leaf.summary,
            "type": leaf.node_type,
            "depth": leaf.depth,
            "path": " > ".join(leaf.path),
        }
        for leaf in leaves
    ]
    return (
        "You are helping a teacher allocate course teaching hours across the LEAF nodes of a knowledge graph.\n"
        "Allocate the requested total hours only to the listed leaf nodes. Parent nodes are calculated by the system.\n"
        "Use non-negative hours with at most one decimal place. A less important leaf may receive 0 hours.\n"
        "Prefer more hours for prerequisite, central, difficult, or practice-heavy concepts.\n"
        "Return strict JSON only in this shape: {\"allocations\":[{\"node_id\":\"...\",\"hours\":1.5,\"reason\":\"...\"}]}.\n"
        f"Total hours: {total_hours}\n"
        f"Leaf nodes: {json.dumps(leaf_payload, ensure_ascii=False)}"
    )


def _normalize_allocations(leaves: List[LeafNodeInfo], requested_hours: Any, allocations: Dict[str, Any]) -> Tuple[Dict[str, int], bool]:
    target = validate_total_hours_to_tenths(requested_hours)
    known_ids = {leaf.node_id for leaf in leaves}
    original: Dict[str, int] = {
        leaf.node_id: _hours_to_tenths(allocations.get(leaf.node_id, 0))
        for leaf in leaves
    }
    current = sum(original.values())
    normalized = current != target or any(node_id not in known_ids for node_id in allocations)
    result = dict(original)

    if target == 0:
        return {leaf.node_id: 0 for leaf in leaves}, True

    if current < target:
        ordered = sorted(leaves, key=lambda leaf: (-original[leaf.node_id], leaf.depth, leaf.order))
        missing = target - current
        for index in range(missing):
            result[ordered[index % len(ordered)].node_id] += 1
        normalized = True
    elif current > target:
        extra = current - target
        while extra > 0:
            candidates = [leaf for leaf in leaves if result[leaf.node_id] > 0]
            if not candidates:
                break
            ordered = sorted(candidates, key=lambda leaf: (-result[leaf.node_id], leaf.order))
            for leaf in ordered:
                if extra <= 0:
                    break
                if result[leaf.node_id] <= 0:
                    continue
                result[leaf.node_id] -= 1
                extra -= 1
        normalized = True

    return result, normalized


def _apply_leaf_hours(node: Dict[str, Any], leaf_hours: Dict[str, int]) -> None:
    children = _children(node)
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    node["data"] = data
    if not children:
        data["hours"] = _tenths_to_hours(leaf_hours.get(str(node.get("id") or ""), 0))
        return
    for child in children:
        _apply_leaf_hours(child, leaf_hours)


def rollup_hours(node: Dict[str, Any]) -> int:
    node = _ensure_dict_node(node)
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    node["data"] = data
    children = _children(node)
    if not children:
        return _hours_to_tenths(data.get("hours", 0))

    total = 0
    for child in children:
        total += rollup_hours(child)
    data["hours"] = _tenths_to_hours(total)
    return total


def allocate_graph_hours_from_llm(
    graph: Dict[str, Any],
    total_hours: Any,
    llm_call: Callable[[str], str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    leaves = collect_leaf_nodes(graph)
    target_tenths = validate_total_hours_to_tenths(total_hours)
    display_total = _tenths_to_hours(target_tenths)
    prompt = _build_prompt(leaves, display_total)
    raw = llm_call(prompt)
    parsed = parse_llm_allocations(raw)
    leaf_hours, normalized = _normalize_allocations(leaves, display_total, parsed)

    updated = copy.deepcopy(graph)
    _apply_leaf_hours(updated, leaf_hours)
    rollup_hours(updated)
    return updated, {
        "total_hours": _tenths_to_hours(target_tenths),
        "leaf_count": len(leaves),
        "source": "llm",
        "normalized": bool(normalized),
    }
```

- [ ] **Step 2: Run the pure-helper tests and verify GREEN**

Run:

```bash
cd backend/src
python -m pytest tests/chat/test_knowledge_graph_hours.py -q
```

Expected: all tests in `test_knowledge_graph_hours.py` PASS.

- [ ] **Step 3: Commit the service**

```bash
git add backend/src/app/knowledge_graph_hours.py backend/src/tests/chat/test_knowledge_graph_hours.py
git commit -m "feat: add knowledge graph hour allocation service"
```

## Task 3: Backend Route Tests

**Files:**
- Create: `backend/src/tests/chat/test_knowledge_graph_hour_routes.py`
- Modify later: `backend/src/app/courses.py`

- [ ] **Step 1: Write the failing route tests**

Create `backend/src/tests/chat/test_knowledge_graph_hour_routes.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import courses as courses_module
from app.knowledge_graph_hours import KnowledgeGraphHourAllocationError


class DummyManager:
    def __init__(self, graph=None):
        self.graph = graph
        self.saved = []

    def get_course_info(self, course_id: str):
        if course_id == "course-1":
            return {"id": "course-1", "title": "Course 1"}
        return None

    def get_knowledge_graph(self, course_id: str):
        return self.graph

    def save_knowledge_graph(self, course_id: str, graph_data):
        self.saved.append({"course_id": course_id, "graph_data": graph_data})
        self.graph = graph_data
        return True


def make_client(manager: DummyManager):
    app = FastAPI()
    app.include_router(courses_module.router)
    app.dependency_overrides[courses_module.get_current_user] = lambda: {"username": "teacher-a"}
    return TestClient(app)


def graph():
    return {
        "id": "root",
        "label": "Course",
        "data": {"summary": "Root"},
        "children": [
            {"id": "leaf-a", "label": "A", "data": {"summary": "A"}, "children": []},
            {"id": "leaf-b", "label": "B", "data": {"summary": "B"}, "children": []},
        ],
    }


def test_allocate_hours_route_saves_and_returns_updated_graph(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

    def fake_allocate(graph_data, total_hours, llm_call):
        assert total_hours == 2.5
        assert llm_call("prompt") == '{"allocations": []}'
        updated = {
            **graph_data,
            "data": {**graph_data["data"], "hours": 2.5},
            "children": [
                {**graph_data["children"][0], "data": {"summary": "A", "hours": 1.5}},
                {**graph_data["children"][1], "data": {"summary": "B", "hours": 1.0}},
            ],
        }
        return updated, {"total_hours": 2.5, "leaf_count": 2, "source": "llm", "normalized": False}

    monkeypatch.setattr(courses_module, "allocate_graph_hours_from_llm", fake_allocate)
    monkeypatch.setattr(courses_module, "_call_knowledge_graph_hour_llm", lambda prompt: '{"allocations": []}')

    client = make_client(manager)
    response = client.post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2.5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["root"]["data"]["hours"] == 2.5
    assert payload["allocation"]["leaf_count"] == 2
    assert manager.saved == [{"course_id": "course-1", "graph_data": payload["root"]}]


def test_allocate_hours_route_returns_404_for_missing_course(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

    response = make_client(manager).post("/api/courses/missing/knowledge-graph/allocate-hours", json={"total_hours": 2})

    assert response.status_code == 404


def test_allocate_hours_route_returns_404_for_missing_graph(monkeypatch):
    manager = DummyManager(None)
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

    response = make_client(manager).post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2})

    assert response.status_code == 404
    assert manager.saved == []


def test_allocate_hours_route_maps_validation_errors_to_400(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

    def fail_validation(graph_data, total_hours, llm_call):
        raise KnowledgeGraphHourAllocationError("total_hours must be non-negative with at most one decimal place")

    monkeypatch.setattr(courses_module, "allocate_graph_hours_from_llm", fail_validation)

    response = make_client(manager).post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2.25})

    assert response.status_code == 400
    assert "total_hours" in response.json()["detail"]
    assert manager.saved == []


def test_allocate_hours_route_does_not_save_when_llm_call_fails(monkeypatch):
    manager = DummyManager(graph())
    monkeypatch.setattr(courses_module, "_get_manager", lambda: manager)

    def fail_llm(graph_data, total_hours, llm_call):
        raise RuntimeError("upstream model timeout")

    monkeypatch.setattr(courses_module, "allocate_graph_hours_from_llm", fail_llm)

    response = make_client(manager).post("/api/courses/course-1/knowledge-graph/allocate-hours", json={"total_hours": 2})

    assert response.status_code == 502
    assert "upstream model timeout" in response.json()["detail"]
    assert manager.saved == []
```

- [ ] **Step 2: Run the route tests and verify RED**

Run:

```bash
cd backend/src
python -m pytest tests/chat/test_knowledge_graph_hour_routes.py -q
```

Expected: FAIL with `AttributeError` for missing `allocate_graph_hours_from_llm` on `courses_module` or `404` for missing route.

- [ ] **Step 3: Commit the RED route tests**

```bash
git add backend/src/tests/chat/test_knowledge_graph_hour_routes.py
git commit -m "test: add knowledge graph hour allocation route tests"
```

## Task 4: Backend Route Implementation

**Files:**
- Modify: `backend/src/app/courses.py`
- Test: `backend/src/tests/chat/test_knowledge_graph_hour_routes.py`
- Test: `backend/src/tests/chat/test_knowledge_graph_hours.py`

- [ ] **Step 1: Add imports in `courses.py`**

Add these imports near the existing imports:

```python
from core import Config
from app.knowledge_graph_hours import (
    KnowledgeGraphHourAllocationError,
    allocate_graph_hours_from_llm,
)
```

If `from core import Config` conflicts with the local import style in this file, use:

```python
from core.config import Config
```

- [ ] **Step 2: Add request and response models**

Add below `class KnowledgeGraphData(BaseModel):`:

```python
class KnowledgeGraphHourAllocationRequest(BaseModel):
    total_hours: float = Field(..., description="课程总学时，最多一位小数")


class KnowledgeGraphHourAllocationResponse(KnowledgeGraphData):
    allocation: Dict[str, Any] = Field(default_factory=dict, description="课时分配元信息")
```

- [ ] **Step 3: Add the LLM caller wrapper**

Add near `_find_kg_node`:

```python
def _call_knowledge_graph_hour_llm(prompt: str) -> str:
    rag_system = get_rag_system()
    model_config = Config.get_deep_model()
    raw = rag_system._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]
    return str(raw or "")
```

- [ ] **Step 4: Add the allocation route**

Add this route after `get_knowledge_graph_subtree` and before the existing `PUT /knowledge-graph` route:

```python
@router.post(
    "/{course_id}/knowledge-graph/allocate-hours",
    response_model=KnowledgeGraphHourAllocationResponse,
    summary="根据课程总学时为知识图谱节点分配课时",
)
def allocate_knowledge_graph_hours(
    course_id: str,
    payload: KnowledgeGraphHourAllocationRequest,
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    graph_data = mgr.get_knowledge_graph(course_id)
    if graph_data is None:
        raise HTTPException(status_code=404, detail="课程知识图谱不存在")

    try:
        updated_graph, allocation_meta = allocate_graph_hours_from_llm(
            graph_data,
            payload.total_hours,
            _call_knowledge_graph_hour_llm,
        )
    except KnowledgeGraphHourAllocationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"调用大模型分配课时失败: {exc}") from exc

    if not mgr.save_knowledge_graph(course_id, updated_graph):
        raise HTTPException(status_code=500, detail="保存知识图谱课时分配失败")

    return KnowledgeGraphHourAllocationResponse(root=updated_graph, allocation=allocation_meta)
```

- [ ] **Step 5: Run route and helper tests**

Run:

```bash
cd backend/src
python -m pytest tests/chat/test_knowledge_graph_hours.py tests/chat/test_knowledge_graph_hour_routes.py -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit the route**

```bash
git add backend/src/app/courses.py backend/src/tests/chat/test_knowledge_graph_hour_routes.py
git commit -m "feat: expose knowledge graph hour allocation API"
```

## Task 5: Frontend API, Types, And Wiring Tests

**Files:**
- Create: `frontend/tests/frontend/knowledgeGraphHours.test.ts`
- Modify later: `frontend/src/stitch/api/types.ts`
- Modify later: `frontend/src/stitch/api/courses.ts`
- Modify later: `frontend/src/stitch/pages/KnowledgeGraph.tsx`

- [ ] **Step 1: Write the failing frontend regression test**

Create `frontend/tests/frontend/knowledgeGraphHours.test.ts`:

```typescript
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const typesFile = readFileSync(new URL('../../src/stitch/api/types.ts', import.meta.url), 'utf8');
const coursesApiFile = readFileSync(new URL('../../src/stitch/api/courses.ts', import.meta.url), 'utf8');
const graphPageFile = readFileSync(new URL('../../src/stitch/pages/KnowledgeGraph.tsx', import.meta.url), 'utf8');

assert.match(
  typesFile,
  /hours\?\s*:\s*number/,
  'KnowledgeGraphNode.data should expose optional numeric hours',
);

assert.match(
  typesFile,
  /export type KnowledgeGraphHourAllocationRequest[\s\S]*total_hours:\s*number/,
  'types should define a total-hours allocation request',
);

assert.match(
  typesFile,
  /export type KnowledgeGraphHourAllocationResponse[\s\S]*allocation:/,
  'types should define an allocation response with metadata',
);

assert.match(
  coursesApiFile,
  /allocateKnowledgeGraphHours\(/,
  'courses API should expose allocateKnowledgeGraphHours',
);

assert.match(
  coursesApiFile,
  /\/api\/courses\/\$\{courseId\}\/knowledge-graph\/allocate-hours/,
  'courses API helper should call the backend allocation route',
);

assert.match(
  coursesApiFile,
  /method:\s*["']POST["']/,
  'allocation API helper should use POST',
);

assert.match(
  graphPageFile,
  /allocateKnowledgeGraphHours/,
  'KnowledgeGraphPage should call the backend allocation helper',
);

assert.match(
  graphPageFile,
  /hours:\s*typeof root\.data\?\.hours === ["']number["'] \? root\.data\.hours : null/,
  'flattenGraph should read data.hours into flat node state',
);

assert.match(
  graphPageFile,
  /data:\s*\{[\s\S]*hours:\s*node\.hours ?? undefined/,
  'buildGraph should preserve flat node hours in node data',
);

assert.match(
  graphPageFile,
  /allocatingHours/,
  'KnowledgeGraphPage should expose a loading state while allocation runs',
);

console.log('knowledgeGraphHours frontend tests passed');
```

- [ ] **Step 2: Run frontend test and verify RED**

Run:

```bash
cd Edu_AI
node --test tests/frontend/knowledgeGraphHours.test.ts
```

Expected: FAIL because `hours?: number`, allocation types, and `allocateKnowledgeGraphHours` do not exist yet.

- [ ] **Step 3: Commit the RED frontend test**

```bash
git add frontend/tests/frontend/knowledgeGraphHours.test.ts
git commit -m "test: add knowledge graph hour frontend wiring checks"
```

## Task 6: Frontend Types And API Helper

**Files:**
- Modify: `frontend/src/stitch/api/types.ts`
- Modify: `frontend/src/stitch/api/courses.ts`
- Test: `frontend/tests/frontend/knowledgeGraphHours.test.ts`

- [ ] **Step 1: Update `KnowledgeGraphNode` and add allocation types**

In `frontend/src/stitch/api/types.ts`, change `KnowledgeGraphNode.data` to include `hours?: number`:

```typescript
export type KnowledgeGraphNode = {
  id: string;
  label: string;
  children?: KnowledgeGraphNode[];
  data?: {
    level?: number;
    summary?: string;
    hasChildren?: boolean;
    type?: string;
    hours?: number;
  };
};
```

Add below `KnowledgeGraphData`:

```typescript
export type KnowledgeGraphHourAllocationRequest = {
  total_hours: number;
};

export type KnowledgeGraphHourAllocationResponse = KnowledgeGraphData & {
  allocation: {
    total_hours?: number;
    leaf_count?: number;
    source?: string;
    normalized?: boolean;
    [key: string]: unknown;
  };
};
```

- [ ] **Step 2: Import the new types in `courses.ts`**

Update the type import in `frontend/src/stitch/api/courses.ts`:

```typescript
import type {
  BackendCourse,
  CourseMaterial,
  KnowledgeBaseDocument,
  KnowledgeGraphData,
  KnowledgeGraphHourAllocationRequest,
  KnowledgeGraphHourAllocationResponse,
} from "./types";
```

- [ ] **Step 3: Add the API helper**

Add below `saveKnowledgeGraph` in `frontend/src/stitch/api/courses.ts`:

```typescript
export function allocateKnowledgeGraphHours(courseId: string, payload: KnowledgeGraphHourAllocationRequest) {
  return apiRequest<KnowledgeGraphHourAllocationResponse>(`/api/courses/${courseId}/knowledge-graph/allocate-hours`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
```

- [ ] **Step 4: Run frontend test and verify partial GREEN expectation**

Run:

```bash
cd Edu_AI
node --test tests/frontend/knowledgeGraphHours.test.ts
```

Expected: still FAIL because `KnowledgeGraphPage.tsx` has not been wired yet.

- [ ] **Step 5: Commit API/type changes**

```bash
git add frontend/src/stitch/api/types.ts frontend/src/stitch/api/courses.ts
git commit -m "feat: add knowledge graph hour allocation API helper"
```

## Task 7: Frontend Knowledge Graph Page Wiring

**Files:**
- Modify: `frontend/src/stitch/pages/KnowledgeGraph.tsx`
- Test: `frontend/tests/frontend/knowledgeGraphHours.test.ts`

- [ ] **Step 1: Import the API helper**

Change the import at the top of `frontend/src/stitch/pages/KnowledgeGraph.tsx` from:

```typescript
import { getKnowledgeGraph, saveKnowledgeGraph } from "../api/courses";
```

to:

```typescript
import { allocateKnowledgeGraphHours, getKnowledgeGraph, saveKnowledgeGraph } from "../api/courses";
```

- [ ] **Step 2: Preserve `data.hours` when flattening**

Change the `hours` assignment inside `flattenGraph` to:

```typescript
hours: typeof root.data?.hours === "number" ? root.data.hours : null,
```

- [ ] **Step 3: Preserve `hours` when rebuilding a graph**

Change the `data` object inside `makeNode` in `buildGraph` to:

```typescript
data: {
  level: node.level,
  summary: node.summary,
  hasChildren: children.length > 0,
  type: node.type,
  hours: node.hours ?? undefined,
},
```

- [ ] **Step 4: Add allocation loading state**

Add a state variable near `saving`:

```typescript
const [allocatingHours, setAllocatingHours] = useState(false);
```

- [ ] **Step 5: Add a total-hours parser**

Add this helper inside `KnowledgeGraphPage` before `handleSave`:

```typescript
function parseTotalHoursInput() {
  const normalized = totalHours.trim();
  if (!/^\d+(?:\.\d)?$/.test(normalized)) {
    throw new Error("课程总学时需为非负数字，最多一位小数");
  }
  return Number(normalized);
}
```

- [ ] **Step 6: Add the backend allocation handler**

Add this function inside `KnowledgeGraphPage` before `handleSave`:

```typescript
async function handleAllocateHours() {
  if (!course?.id) return;
  try {
    setAllocatingHours(true);
    setError(null);
    const parsedTotalHours = parseTotalHoursInput();
    const response = await allocateKnowledgeGraphHours(course.id, { total_hours: parsedTotalHours });
    const flat = flattenGraph(response.root);
    setNodes(flat);
    const root = flat.find((node) => node.parentId === null) ?? flat[0];
    setActiveNodeId((current) => (current && flat.some((node) => node.id === current) ? current : root?.id || ""));
    setExpandedIds((current) => {
      if (current.size) return current;
      return root ? new Set([root.id]) : new Set();
    });
  } catch (err) {
    setError(err instanceof Error ? err.message : "节点学时生成失败");
  } finally {
    setAllocatingHours(false);
  }
}
```

- [ ] **Step 7: Replace the local allocation button action**

Find the button that currently has:

```typescript
onClick={() => setNodes((current) => generateHours(Number(totalHours) || 32, current))}
```

Replace it with:

```typescript
onClick={() => void handleAllocateHours()}
disabled={allocatingHours || !course?.id}
```

Change the button label from the static text to:

```tsx
{allocatingHours ? "生成中..." : "生成节点学时"}
```

The final button should look like:

```tsx
<button
  type="button"
  onClick={() => void handleAllocateHours()}
  disabled={allocatingHours || !course?.id}
  className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--accent)] px-4 py-3 text-sm font-bold text-white disabled:opacity-50"
>
  <MaterialIcon name="auto_graph" className="text-base" />
  {allocatingHours ? "生成中..." : "生成节点学时"}
</button>
```

- [ ] **Step 8: Remove the obsolete local `generateHours` helper**

Delete the `generateHours(totalHours: number, nodes: FlatNode[])` function from `frontend/src/stitch/pages/KnowledgeGraph.tsx`. It should no longer be referenced.

- [ ] **Step 9: Run frontend wiring test**

Run:

```bash
cd Edu_AI
node --test tests/frontend/knowledgeGraphHours.test.ts
```

Expected: PASS with `knowledgeGraphHours frontend tests passed`.

- [ ] **Step 10: Commit page wiring**

```bash
git add frontend/src/stitch/pages/KnowledgeGraph.tsx frontend/tests/frontend/knowledgeGraphHours.test.ts
git commit -m "feat: wire knowledge graph hour allocation UI"
```

## Task 8: Final Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
cd backend/src
python -m pytest tests/chat/test_knowledge_graph_hours.py tests/chat/test_knowledge_graph_hour_routes.py -q
```

Expected: all focused backend tests PASS.

- [ ] **Step 2: Run frontend focused test**

Run:

```bash
cd Edu_AI
node --test tests/frontend/knowledgeGraphHours.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd Edu_AI
npm run build
```

Expected: Vite build completes without TypeScript or bundling errors.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short
```

Expected: only intentional files from this feature are modified or untracked. Do not revert unrelated existing workspace changes.

- [ ] **Step 5: Final commit if previous tasks were not committed**

If there are any remaining unstaged intentional feature changes:

```bash
git add backend/src/app/knowledge_graph_hours.py backend/src/app/courses.py backend/src/tests/chat/test_knowledge_graph_hours.py backend/src/tests/chat/test_knowledge_graph_hour_routes.py frontend/src/stitch/api/types.ts frontend/src/stitch/api/courses.ts frontend/src/stitch/pages/KnowledgeGraph.tsx frontend/tests/frontend/knowledgeGraphHours.test.ts
git commit -m "feat: allocate knowledge graph hours"
```

Expected: commit succeeds, or Git reports nothing to commit because earlier task commits already captured the work.

## Self-Review

Spec coverage:
- Backend allocation API: Task 3 and Task 4.
- Leaf extraction: Task 1 and Task 2.
- LLM prompt and parse contract: Task 1 and Task 2.
- One-decimal normalization with integer tenths: Task 1 and Task 2.
- Leaf total equals requested total: Task 1 and Task 2.
- Parent rollup: Task 1 and Task 2.
- Persist `data.hours`: Task 3 and Task 4.
- Frontend API helper and page button: Task 5, Task 6, and Task 7.
- Tests and verification: Task 1, Task 3, Task 5, and Task 8.

Placeholder scan:
- No forbidden placeholder markers or unspecified implementation steps remain.

Type consistency:
- Backend route returns `KnowledgeGraphHourAllocationResponse(root=..., allocation=...)`.
- Frontend helper returns `KnowledgeGraphHourAllocationResponse`.
- `KnowledgeGraphNode.data.hours` is numeric everywhere.
- Route path is consistently `/api/courses/{course_id}/knowledge-graph/allocate-hours`.
