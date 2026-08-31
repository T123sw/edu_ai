# Course Knowledge Incremental Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 课程已有知识库时默认基于最新已发布图谱增量追加、强制保留全部旧节点，并把第三阶段改造成“顶部统计与问题提醒 + 左侧折叠树 + 右侧当前节点编辑器”。

**Architecture:** 创建构建草案时把最新图谱版本和完整图谱快照写入现有 `plan_snapshot` JSON；模型生成候选后，由独立的确定性合并模块复用旧节点并只追加新节点。保存、确认和发布都复用同一套基线不变量校验，并在发布事务内再次检查基线版本，防止审核期间图谱发生并发更新。前端从 `baseline_graph` 派生旧节点锁定状态和新增/待完善标签，审核界面拆成汇总、树、单节点编辑器、固定操作栏四个职责清晰的组件。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy、PostgreSQL、pytest、React 18、TypeScript、CSS、Node test runner、Playwright。

---

## 文件结构与职责

- 新建 `Edu_AI/api/src/app/services/course_knowledge_graph_incremental.py`：名称规范化、基线摘要、保留式合并、基线不变量校验和结构化问题定义。
- 修改 `Edu_AI/api/src/app/persistence/postgres_knowledge_repository.py`：读取带版本号的最新图谱；发布事务内校验基线版本。
- 修改 `Edu_AI/api/src/app/api/courses.py`：创建草案时写入基线；保存和确认时执行增量保护校验并返回稳定错误码。
- 修改 `Edu_AI/api/src/app/schemas/course.py`：后端默认策略改为 `incremental`。
- 修改 `Edu_AI/api/src/app/services/course_knowledge_graph_generator.py`：增量提示词、候选图谱与基线的确定性合并、增量校验。
- 新建 `Edu_AI/api/src/tests/services/test_course_knowledge_graph_incremental.py`：合并和不变量的纯单元测试。
- 修改 `Edu_AI/api/src/tests/services/test_course_knowledge_graph_generator.py`、`Edu_AI/api/src/tests/test_course_knowledge_build_workflow.py`、`Edu_AI/api/src/tests/persistence/test_postgres_knowledge_repository.py`：生成、接口和发布并发测试。
- 修改 `Edu_AI/src/stitch/api/types.ts`：公开基线和审核元数据类型。
- 修改 `Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildState.ts`：前端默认策略改为 `incremental`。
- 修改 `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx`：已有版本时按钮文案改为“增量更新知识库”。
- 修改 `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildConfigStep.tsx`：常规入口只展示增量说明；重建选项进入高级设置；完全重建二次确认。
- 修改 `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildWizard.tsx`：传入基线，处理完全重建确认和结构化图谱错误定位。
- 修改 `Edu_AI/src/stitch/course/knowledge/courseKnowledgeGraphDraft.ts`：节点索引、问题列表、过滤、搜索和旧节点保护辅助函数。
- 修改 `Edu_AI/src/stitch/course/knowledge/courseKnowledgeGraphDraft.test.ts`：纯函数测试。
- 新建 `Edu_AI/src/stitch/course/knowledge/KnowledgeGraphReviewSummary.tsx`：顶部六项统计、问题提醒和筛选。
- 新建 `Edu_AI/src/stitch/course/knowledge/KnowledgeGraphTree.tsx`：可折叠、可搜索、可键盘导航的左侧树。
- 新建 `Edu_AI/src/stitch/course/knowledge/KnowledgeGraphNodeEditor.tsx`：只渲染当前选中节点；锁定旧节点结构操作。
- 新建 `Edu_AI/src/stitch/course/knowledge/KnowledgeGraphReviewActions.tsx`：固定底部操作区和确认勾选。
- 修改 `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeGraphReviewStep.tsx`：只负责状态编排、保存、定位问题和响应式面板切换。
- 修改 `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.css`：桌面双栏、窄屏分页、字号、对比度、焦点和固定操作栏。
- 修改 `Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts`：静态集成约束。
- 修改 `Edu_AI/tests/e2e/fixtures/courseKnowledgeBuild.ts`、`Edu_AI/tests/e2e/course-knowledge-build-wizard.spec.ts`：增量更新和大图谱审核端到端覆盖。

### Task 1: 草案加载最新图谱基线并统一默认策略

**Files:**
- Modify: `Edu_AI/api/src/app/schemas/course.py:222-241`
- Modify: `Edu_AI/api/src/app/persistence/postgres_knowledge_repository.py:150-175`
- Modify: `Edu_AI/api/src/app/api/courses.py:1056-1092`
- Modify: `Edu_AI/api/src/tests/test_course_knowledge_build_workflow.py:11-55`
- Modify: `Edu_AI/api/src/tests/persistence/test_postgres_knowledge_repository.py:324-345`

- [ ] **Step 1: 写出失败的仓储和创建草案测试**

在 `test_postgres_knowledge_repository.py` 的版本测试中增加：

```python
latest = repository.get_latest_graph_version("course-1")
assert latest == {
    "version": 2,
    "graph": {
        "id": "v2",
        "data": {
            "publication_status": "published",
            "source_build_id": "kb-2",
            "node_count": 3,
        },
    },
}
```

把 `test_create_build_draft_normalizes_config_without_searching` 的假仓储扩展为：

```python
class Repository:
    def get_latest_graph_version(self, library_id):
        assert library_id == "course-1"
        return {
            "version": 7,
            "graph": _valid_small_graph(),
        }

    def create_build_draft(self, *, course_id, triggered_by, plan):
        captured.update(course_id=course_id, triggered_by=triggered_by, plan=plan)
        return {
            "build_id": "kb-draft-1",
            "library_id": course_id,
            "status": "draft",
            "phase": "draft_config",
            "revision": 1,
            "graph_confirmed_at": None,
            "confirmed_graph_revision": None,
            "confirmed_by": None,
            **plan,
        }
```

并断言：

```python
assert body["config"]["update_strategy"] == "incremental"
assert body["baseline_graph_version"] == 7
assert body["baseline_graph"] == _valid_small_graph()
assert body["current_graph_summary"]["node_count"] == 13
```

- [ ] **Step 2: 运行测试并确认先失败**

Run:

```powershell
cd Edu_AI/api/src
.\.venv\Scripts\python.exe -m pytest tests/persistence/test_postgres_knowledge_repository.py::test_knowledge_repository_versions_and_rolls_back_published_graph tests/test_course_knowledge_build_workflow.py::test_create_build_draft_normalizes_config_without_searching -q
```

Expected: FAIL，提示 `get_latest_graph_version` 不存在或默认策略仍为 `merge_rebuild`。

- [ ] **Step 3: 实现带版本号的最新图谱读取和草案基线快照**

在仓储类中新增：

```python
def get_latest_graph_version(self, library_id: str) -> dict[str, Any] | None:
    with database_session(engine=self._engine) as session:
        record = session.scalar(
            select(KnowledgeGraphVersion)
            .where(KnowledgeGraphVersion.library_id == library_id)
            .order_by(KnowledgeGraphVersion.version.desc())
            .limit(1)
        )
        if record is None:
            return None
        return {
            "version": int(record.version),
            "graph": dict(record.graph_payload or {}),
        }
```

把 Pydantic 默认值改为：

```python
update_strategy: Literal["incremental", "merge_rebuild", "full_rebuild"] = (
    "incremental"
)
```

创建草案时复用同一个仓储实例，并写入完整快照：

```python
repository = get_postgres_knowledge_repository()
latest_graph = repository.get_latest_graph_version(course_id)
baseline_graph = copy.deepcopy((latest_graph or {}).get("graph"))
plan = {
    "course_id": course_id,
    "course_snapshot": course_snapshot,
    "config": payload.config.model_dump(mode="json"),
    "baseline_graph_version": (latest_graph or {}).get("version"),
    "baseline_graph": baseline_graph,
    "current_graph_summary": summarize_course_knowledge_graph(baseline_graph),
    "textbooks": [],
    "graph_draft": None,
    "topics": [],
    "source_candidates": [],
    "warnings": [],
}
return repository.create_build_draft(
    course_id=course_id,
    triggered_by=principal.user_id,
    plan=plan,
)
```

`summarize_course_knowledge_graph` 在 Task 2 创建；本步骤可先从新模块导入其已计划签名。

- [ ] **Step 4: 运行测试并确认通过**

Run:

```powershell
cd Edu_AI/api/src
.\.venv\Scripts\python.exe -m pytest tests/persistence/test_postgres_knowledge_repository.py::test_knowledge_repository_versions_and_rolls_back_published_graph tests/test_course_knowledge_build_workflow.py::test_create_build_draft_normalizes_config_without_searching -q
```

Expected: 2 passed。

- [ ] **Step 5: 提交本任务**

```powershell
git add Edu_AI/api/src/app/schemas/course.py Edu_AI/api/src/app/persistence/postgres_knowledge_repository.py Edu_AI/api/src/app/api/courses.py Edu_AI/api/src/tests/test_course_knowledge_build_workflow.py Edu_AI/api/src/tests/persistence/test_postgres_knowledge_repository.py
git commit -m "feat: snapshot published graph for incremental builds"
```

### Task 2: 实现确定性保留式合并与基线不变量校验

**Files:**
- Create: `Edu_AI/api/src/app/services/course_knowledge_graph_incremental.py`
- Create: `Edu_AI/api/src/tests/services/test_course_knowledge_graph_incremental.py`

- [ ] **Step 1: 写出覆盖全部合并规则的失败测试**

测试必须使用一个包含根节点、两个旧模块和四个旧知识点的基线，构造候选图谱覆盖以下断言：

```python
def test_incremental_merge_preserves_existing_structure_and_appends_new_nodes():
    merged = merge_incremental_graph(BASELINE, CANDIDATE)

    assert [node["id"] for node in merged["children"][:2]] == ["module-a", "module-b"]
    assert merged["children"][0]["label"] == "旧模块 A"
    assert [node["id"] for node in merged["children"][0]["children"][:2]] == [
        "point-a1",
        "point-a2",
    ]
    assert merged["children"][0]["children"][0]["data"]["summary"].endswith(
        "候选补充说明"
    )
    assert merged["children"][0]["children"][0]["data"]["source_outline_refs"] == [
        "old-ref",
        "new-ref",
    ]
    assert merged["children"][0]["children"][-1]["data"]["review_state"] == "new"
    assert_baseline_graph_preserved(BASELINE, merged)
```

再增加四个独立测试：同父同名复用旧节点而不重复；不同父同名不合并；旧节点缺失/改名/移动/重排分别返回具体 issue；新节点 ID 冲突时生成同输入恒定的新 ID。

- [ ] **Step 2: 运行测试并确认先失败**

Run:

```powershell
cd Edu_AI/api/src
.\.venv\Scripts\python.exe -m pytest tests/services/test_course_knowledge_graph_incremental.py -q
```

Expected: FAIL，模块尚不存在。

- [ ] **Step 3: 写出最小、完整的增量合并模块**

模块公开以下稳定接口：

```python
from __future__ import annotations

import copy
import hashlib
import re
import unicodedata
from collections.abc import Mapping
from typing import Any


def normalize_graph_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


def summarize_course_knowledge_graph(
    graph: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not graph:
        return None
    node_count = 0
    leaf_count = 0
    modules: list[dict[str, Any]] = []

    def visit(node: Mapping[str, Any]) -> None:
        nonlocal node_count, leaf_count
        node_count += 1
        children = [item for item in node.get("children") or [] if isinstance(item, Mapping)]
        if not children:
            leaf_count += 1
        for child in children:
            visit(child)

    visit(graph)
    for child in graph.get("children") or []:
        if isinstance(child, Mapping):
            modules.append(
                {
                    "id": str(child.get("id") or ""),
                    "label": str(child.get("label") or ""),
                    "child_count": len(child.get("children") or []),
                }
            )
    return {
        "root_id": str(graph.get("id") or ""),
        "root_label": str(graph.get("label") or ""),
        "node_count": node_count,
        "leaf_count": leaf_count,
        "modules": modules,
    }


def _union_strings(left: Any, right: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in list(left or []) + list(right or []):
        value = str(item or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _merge_summary(existing: Any, candidate: Any) -> str:
    old = str(existing or "").strip()
    new = str(candidate or "").strip()
    if not old:
        return new
    if not new or normalize_graph_name(new) in normalize_graph_name(old):
        return old
    return f"{old}\n\n{new}"


def _deterministic_new_id(parent_id: str, preferred_id: str, label: str) -> str:
    source = f"{parent_id}\0{preferred_id}\0{normalize_graph_name(label)}"
    return f"incremental-{hashlib.sha256(source.encode('utf-8')).hexdigest()[:16]}"


def merge_incremental_graph(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(dict(baseline))
    used_ids: set[str] = set()

    def collect_ids(node: Mapping[str, Any]) -> None:
        used_ids.add(str(node.get("id") or ""))
        for child in node.get("children") or []:
            if isinstance(child, Mapping):
                collect_ids(child)

    collect_ids(result)

    def mark_existing(node: dict[str, Any]) -> None:
        data = dict(node.get("data") or {})
        data["review_state"] = "existing"
        node["data"] = data
        for child in node.get("children") or []:
            mark_existing(child)

    mark_existing(result)

    def merge_node(target: dict[str, Any], incoming: Mapping[str, Any]) -> None:
        target_data = dict(target.get("data") or {})
        incoming_data = dict(incoming.get("data") or {})
        target_data["summary"] = _merge_summary(
            target_data.get("summary"), incoming_data.get("summary")
        )
        target_data["source_outline_refs"] = _union_strings(
            target_data.get("source_outline_refs"),
            incoming_data.get("source_outline_refs"),
        )
        target_data["document_ids"] = _union_strings(
            target_data.get("document_ids"), incoming_data.get("document_ids")
        )
        target["data"] = target_data
        existing_children = [dict(item) for item in target.get("children") or []]
        target["children"] = existing_children
        by_id = {str(item.get("id") or ""): item for item in existing_children}
        by_name = {
            normalize_graph_name(item.get("label")): item
            for item in existing_children
            if normalize_graph_name(item.get("label"))
        }
        for incoming_child in incoming.get("children") or []:
            if not isinstance(incoming_child, Mapping):
                continue
            preferred_id = str(incoming_child.get("id") or "").strip()
            match = by_id.get(preferred_id)
            if match is None:
                match = by_name.get(normalize_graph_name(incoming_child.get("label")))
            if match is not None:
                merge_node(match, incoming_child)
                continue
            new_child = copy.deepcopy(dict(incoming_child))
            if not preferred_id or preferred_id in used_ids:
                preferred_id = _deterministic_new_id(
                    str(target.get("id") or ""),
                    preferred_id,
                    str(new_child.get("label") or ""),
                )
            new_child["id"] = preferred_id
            used_ids.add(preferred_id)
            new_data = dict(new_child.get("data") or {})
            new_data["review_state"] = (
                "needs_parent"
                if bool(new_data.get("needs_parent"))
                else "new"
            )
            new_child["data"] = new_data
            target["children"].append(new_child)
            by_id[preferred_id] = new_child
            normalized = normalize_graph_name(new_child.get("label"))
            if normalized:
                by_name[normalized] = new_child

    merge_node(result, candidate)
    return result


def baseline_graph_issues(
    baseline: Mapping[str, Any] | None,
    graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not baseline:
        return []
    issues: list[dict[str, Any]] = []
    current: dict[str, tuple[Mapping[str, Any], str | None]] = {}

    def index(node: Mapping[str, Any], parent_id: str | None) -> None:
        node_id = str(node.get("id") or "")
        current[node_id] = (node, parent_id)
        for child in node.get("children") or []:
            if isinstance(child, Mapping):
                index(child, node_id)

    index(graph, None)

    def issue(code: str, node_id: str, message: str) -> None:
        issues.append({"code": code, "node_id": node_id, "path": node_id, "message": message})

    def visit(node: Mapping[str, Any], parent_id: str | None) -> None:
        node_id = str(node.get("id") or "")
        loaded = current.get(node_id)
        if loaded is None:
            issue("BASELINE_NODE_MISSING", node_id, f"已有节点已丢失：{node.get('label')}")
            return
        actual, actual_parent = loaded
        if str(actual.get("label") or "") != str(node.get("label") or ""):
            issue("BASELINE_NODE_RENAMED", node_id, f"已有节点名称不可修改：{node.get('label')}")
        expected_type = str((node.get("data") or {}).get("type") or "")
        actual_type = str((actual.get("data") or {}).get("type") or "")
        if actual_type != expected_type:
            issue("BASELINE_NODE_TYPE_CHANGED", node_id, f"已有节点类型不可修改：{node.get('label')}")
        if actual_parent != parent_id:
            issue("BASELINE_NODE_MOVED", node_id, f"已有节点不可移动：{node.get('label')}")
        expected_children = [str(item.get("id") or "") for item in node.get("children") or []]
        actual_children = [str(item.get("id") or "") for item in actual.get("children") or []]
        if actual_children[: len(expected_children)] != expected_children:
            issue("BASELINE_CHILD_ORDER_CHANGED", node_id, f"已有子节点顺序不可修改：{node.get('label')}")
        for child in node.get("children") or []:
            if isinstance(child, Mapping):
                visit(child, node_id)

    visit(baseline, None)
    return issues


def incremental_graph_issues(
    baseline: Mapping[str, Any] | None,
    graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues = baseline_graph_issues(baseline, graph)
    seen: set[str] = set()

    def visit(node: Mapping[str, Any], parent_id: str | None) -> None:
        node_id = str(node.get("id") or "")
        if node_id in seen:
            issues.append({"code": "DUPLICATE_ID", "node_id": node_id, "path": node_id, "message": f"节点 ID 重复：{node_id}"})
        seen.add(node_id)
        if parent_id is not None and not parent_id:
            issues.append({"code": "NEW_NODE_PARENT_MISSING", "node_id": node_id, "path": node_id, "message": "新增节点缺少父节点"})
        data = dict(node.get("data") or {})
        if data.get("review_state") == "needs_parent" or data.get("needs_parent"):
            issues.append({"code": "NEW_NODE_PARENT_UNRESOLVED", "node_id": node_id, "path": node_id, "message": f"新增节点尚未选择父节点：{node.get('label')}"})
        for child in node.get("children") or []:
            if isinstance(child, Mapping):
                visit(child, node_id)

    visit(graph, None)
    return issues


def assert_baseline_graph_preserved(
    baseline: Mapping[str, Any] | None,
    graph: Mapping[str, Any],
) -> None:
    issues = incremental_graph_issues(baseline, graph)
    if issues:
        raise ValueError(issues)
```

- [ ] **Step 4: 运行纯单元测试并确认通过**

Run:

```powershell
cd Edu_AI/api/src
.\.venv\Scripts\python.exe -m pytest tests/services/test_course_knowledge_graph_incremental.py -q
```

Expected: 所有增量合并测试通过。

- [ ] **Step 5: 提交本任务**

```powershell
git add Edu_AI/api/src/app/services/course_knowledge_graph_incremental.py Edu_AI/api/src/tests/services/test_course_knowledge_graph_incremental.py
git commit -m "feat: add deterministic incremental graph merge"
```

### Task 3: 把保留式合并接入模型生成和图谱校验

**Files:**
- Modify: `Edu_AI/api/src/app/services/course_knowledge_graph_generator.py:145-205, 405-485`
- Modify: `Edu_AI/api/src/tests/services/test_course_knowledge_graph_generator.py:13-245`

- [ ] **Step 1: 写出失败的增量生成测试**

在 `_build` 中把默认策略改成 `incremental`，增加包含 `baseline_graph` 和 `baseline_graph_version` 的测试：

```python
def test_incremental_generation_merges_candidate_without_changing_baseline_nodes():
    build = _build(preset="small")
    baseline = _valid_payload(modules=3, points=3)["root"]
    build.update(
        baseline_graph=baseline,
        baseline_graph_version=4,
        current_graph_summary={"node_count": 13},
    )
    candidate = _valid_payload(modules=3, points=3)
    candidate["root"]["children"][0]["label"] = "模型试图改名"
    candidate["root"]["children"][0]["children"].append(
        {
            "id": "point-new",
            "label": "新增鉴赏方法",
            "type": "knowledge_point",
            "summary": "新增教材覆盖的方法",
            "children": [],
        }
    )

    graph = generate_course_knowledge_graph_draft(
        build,
        owner_user_id="teacher-1",
        model_adapter=FakeAdapter(candidate),
    )

    assert graph["children"][0]["label"] == baseline["children"][0]["label"]
    assert [item["id"] for item in graph["children"][0]["children"]][-1] == "point-new"
    assert graph["data"]["baseline_graph_version"] == 4
```

同时断言首轮提示词包含“保留全部已有节点”“不得改名、移动或删除”和 `current_graph` 摘要。

再扩展现有 `test_module_regeneration_preserves_unselected_module_ids`：当目标模块属于基线时，候选模块即使尝试改名、删除旧知识点，也只能补充说明和追加新知识点；目标模块原 ID、名称、旧子节点及其顺序全部保持不变。

- [ ] **Step 2: 运行测试并确认先失败**

Run:

```powershell
cd Edu_AI/api/src
.\.venv\Scripts\python.exe -m pytest tests/services/test_course_knowledge_graph_generator.py -q
```

Expected: 新测试 FAIL，候选仍直接替换基线。

- [ ] **Step 3: 接入增量提示词、合并和校验**

导入：

```python
from app.services.course_knowledge_graph_incremental import (
    incremental_graph_issues,
    merge_incremental_graph,
)
```

为系统提示词附加策略约束：

```python
strategy = str((build.get("config") or {}).get("update_strategy") or "incremental")
incremental_rules = (
    "当前任务是增量更新。必须复用 current_graph 中的已有节点 ID；"
    "不得删除、改名、移动或重排已有节点；只补充说明、教材映射和真正缺失的新节点。"
    if strategy == "incremental" and build.get("baseline_graph")
    else ""
)
```

生成循环在解析、规范化之后先合并，再做结构校验：

```python
candidate_graph = _normalize_node(payload["root"], level=0)
strategy = str((build.get("config") or {}).get("update_strategy") or "incremental")
baseline_graph = build.get("baseline_graph")
graph = (
    merge_incremental_graph(baseline_graph, candidate_graph)
    if strategy == "incremental" and isinstance(baseline_graph, Mapping)
    else candidate_graph
)
issues, metrics = validate_course_knowledge_graph(
    graph,
    config=dict(build.get("config") or {}),
    textbook_outline_keys=outline_keys,
    unmapped_outline_items=unmapped,
    enforce_scale=not (strategy == "incremental" and bool(baseline_graph)),
)
issues.extend(
    incremental_graph_issues(baseline_graph, graph)
    if strategy == "incremental"
    else []
)
```

给 `validate_course_knowledge_graph` 增加关键字参数：

```python
enforce_scale: bool = True,
```

仅当 `enforce_scale` 为真时添加 `MODULE_SCALE_MISMATCH` 和 `LEAF_SCALE_MISMATCH`，因为已有图谱可能天然大于本次新增目标；深度、节点类型、重复 ID、教材目录映射等结构校验继续执行。生成成功后写入：

```python
"baseline_graph_version": build.get("baseline_graph_version"),
"update_strategy": strategy,
```

`regenerate_course_knowledge_graph_module` 在增量模式下不得直接替换目标模块：先从 `baseline_graph` 找到同 ID 模块，再调用 `merge_incremental_graph(baseline_module, candidate_module)`，把合并结果放回当前草案；随后对完整图谱执行 `incremental_graph_issues(build.get("baseline_graph"), regenerated)`。非增量策略保持原有模块替换行为。

- [ ] **Step 4: 运行生成器测试并确认通过**

Run:

```powershell
cd Edu_AI/api/src
.\.venv\Scripts\python.exe -m pytest tests/services/test_course_knowledge_graph_generator.py -q
```

Expected: 所有生成器测试通过，原有首次构建、修复、教材映射和模块重生成测试不回归。

- [ ] **Step 5: 提交本任务**

```powershell
git add Edu_AI/api/src/app/services/course_knowledge_graph_generator.py Edu_AI/api/src/tests/services/test_course_knowledge_graph_generator.py
git commit -m "feat: merge incremental graph candidates with baseline"
```

### Task 4: 保存、确认和发布三阶段强制保护旧节点

**Files:**
- Modify: `Edu_AI/api/src/app/api/courses.py:1251-1355`
- Modify: `Edu_AI/api/src/app/persistence/postgres_knowledge_repository.py:668-724`
- Modify: `Edu_AI/api/src/tests/test_course_knowledge_build_workflow.py:200-335`
- Modify: `Edu_AI/api/src/tests/persistence/test_postgres_knowledge_repository.py:140-190`

- [ ] **Step 1: 写出保存、确认和并发发布失败测试**

接口测试分别提交删除旧节点、改名旧节点、移动旧节点的草案，断言：

```python
assert response.status_code == 422
detail = response.json()["detail"]
assert detail["code"] == "GRAPH_BASELINE_VIOLATION"
assert detail["issues"][0]["node_id"] == "point-1-1"
```

让假仓储 `get_latest_graph_version` 返回比草案 `baseline_graph_version` 更高的版本，断言保存和确认返回：

```python
assert response.status_code == 409
assert response.json()["detail"]["code"] == "GRAPH_BASELINE_VERSION_CONFLICT"
```

仓储测试创建版本 1 的草案后再插入版本 2，把构建推进到 `publishing`，调用 `publish_build` 并断言抛出 `KnowledgeBuildBaselineConflict`，且未写入版本 3。

- [ ] **Step 2: 运行测试并确认先失败**

Run:

```powershell
cd Edu_AI/api/src
.\.venv\Scripts\python.exe -m pytest tests/test_course_knowledge_build_workflow.py tests/persistence/test_postgres_knowledge_repository.py -q
```

Expected: 新增保护测试 FAIL。

- [ ] **Step 3: 实现统一接口校验和发布事务检查**

在 API 层新增：

```python
def _incremental_graph_guard(repository, build, graph) -> None:
    config = dict(build.get("config") or {})
    if config.get("update_strategy") != "incremental":
        return
    baseline_version = build.get("baseline_graph_version")
    latest = repository.get_latest_graph_version(str(build.get("library_id") or ""))
    latest_version = (latest or {}).get("version")
    if baseline_version != latest_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "GRAPH_BASELINE_VERSION_CONFLICT",
                "message": "知识图谱已发布新版本，请刷新后重新合并本次修改",
                "baseline_version": baseline_version,
                "current_version": latest_version,
            },
        )
    issues = incremental_graph_issues(build.get("baseline_graph"), graph)
    if issues:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "GRAPH_BASELINE_VIOLATION",
                "message": "增量更新必须保留全部已有节点",
                "issues": issues,
            },
        )
```

`update_knowledge_base_graph_draft` 与 `confirm_knowledge_base_graph_draft` 都在结构校验前调用该守卫。仓储层增加异常：

```python
class KnowledgeBuildBaselineConflict(ValueError):
    pass
```

并在 `publish_build` 的同一事务、计算 `next_version` 前执行：

```python
plan = dict(build.plan_snapshot or {})
config = dict(plan.get("config") or {})
if config.get("update_strategy") == "incremental":
    expected = plan.get("baseline_graph_version")
    current = session.scalar(
        select(func.max(KnowledgeGraphVersion.version)).where(
            KnowledgeGraphVersion.library_id == build.library_id
        )
    )
    normalized_current = int(current) if current is not None else None
    if expected != normalized_current:
        raise KnowledgeBuildBaselineConflict(
            f"图谱基线版本冲突：草案 {expected}，当前 {normalized_current}"
        )
    issues = incremental_graph_issues(plan.get("baseline_graph"), graph)
    if issues:
        raise ValueError({"code": "GRAPH_BASELINE_VIOLATION", "issues": issues})
```

首次构建的 `baseline_graph_version=None` 与当前无版本 `None` 匹配，正常发布版本 1；`merge_rebuild` 和 `full_rebuild` 不应用旧节点不变量，但仍保留历史版本。

- [ ] **Step 4: 运行接口与仓储测试并确认通过**

Run:

```powershell
cd Edu_AI/api/src
.\.venv\Scripts\python.exe -m pytest tests/test_course_knowledge_build_workflow.py tests/persistence/test_postgres_knowledge_repository.py -q
```

Expected: 全部通过。

- [ ] **Step 5: 提交本任务**

```powershell
git add Edu_AI/api/src/app/api/courses.py Edu_AI/api/src/app/persistence/postgres_knowledge_repository.py Edu_AI/api/src/tests/test_course_knowledge_build_workflow.py Edu_AI/api/src/tests/persistence/test_postgres_knowledge_repository.py
git commit -m "feat: enforce graph baseline invariants"
```

### Task 5: 前端默认增量更新并把重建收进高级设置

**Files:**
- Modify: `Edu_AI/src/stitch/api/types.ts:476-580`
- Modify: `Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildState.ts:13-31`
- Modify: `Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildState.test.ts:9-45`
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx:90-115, 166-185`
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildConfigStep.tsx:1-100`
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildWizard.tsx:84-112, 226-232`
- Modify: `Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts:46-65`

- [ ] **Step 1: 写出失败的前端默认值和静态集成测试**

在状态测试增加：

```typescript
assert.equal(DEFAULT_COURSE_KNOWLEDGE_CONFIG.update_strategy, "incremental");
```

静态集成测试增加：

```typescript
assert.match(buildCard, /增量更新知识库/);
assert.match(configStep, /增量追加/);
assert.match(configStep, /高级设置/);
assert.match(configStep, /完全重建/);
assert.match(configStep, /window\.confirm/);
```

- [ ] **Step 2: 运行测试并确认先失败**

Run:

```powershell
cd Edu_AI
pnpm test -- src/stitch/course/knowledge/courseKnowledgeBuildState.test.ts src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
```

Expected: 默认策略和新文案断言 FAIL。

- [ ] **Step 3: 更新类型、默认值、按钮文案和高级设置**

给 `CourseKnowledgeBuild` 增加：

```typescript
baseline_graph_version?: number | null;
baseline_graph?: KnowledgeGraphNode | null;
current_graph_summary?: {
  root_id: string;
  root_label: string;
  node_count: number;
  leaf_count: number;
  modules: Array<{ id: string; label: string; child_count: number }>;
} | null;
```

给节点 `data` 增加：

```typescript
review_state?: "existing" | "new" | "needs_review" | "needs_parent";
needs_parent?: boolean;
```

默认策略改为 `incremental`。卡片按钮以 `versions.length > 0 || documentCount > 0` 判定已有知识库并显示“增量更新知识库”。配置步骤用以下结构取代常规策略下拉框：

```tsx
<div className="course-kb-wizard__strategy-note">
  <strong>增量追加</strong>
  <span>保留现有知识结构，只补充新节点与资料。</span>
</div>
<details className="course-kb-wizard__advanced">
  <summary>高级设置</summary>
  <label>
    更新方式
    <select
      value={config.update_strategy}
      onChange={(event) => {
        const strategy = event.target.value as CourseKnowledgeBuildConfig["update_strategy"];
        if (
          strategy === "full_rebuild"
          && !window.confirm("完全重建会用新结构替换当前知识图谱，但历史版本仍可恢复。确认继续吗？")
        ) return;
        onChange({ ...config, update_strategy: strategy });
      }}
    >
      <option value="incremental">增量追加（推荐）</option>
      <option value="merge_rebuild">合并重建</option>
      <option value="full_rebuild">完全重建</option>
    </select>
  </label>
</details>
```

向导标题在存在 `baseline_graph` 时显示“课程知识库增量更新向导”。

- [ ] **Step 4: 运行前端单元测试并确认通过**

Run:

```powershell
cd Edu_AI
pnpm test -- src/stitch/course/knowledge/courseKnowledgeBuildState.test.ts src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
```

Expected: 全部通过。

- [ ] **Step 5: 提交本任务**

```powershell
git add Edu_AI/src/stitch/api/types.ts Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildState.ts Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildState.test.ts Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildConfigStep.tsx Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildWizard.tsx Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
git commit -m "feat: make course knowledge updates incremental by default"
```

### Task 6: 建立审核树的纯状态模型和旧节点保护

**Files:**
- Modify: `Edu_AI/src/stitch/course/knowledge/courseKnowledgeGraphDraft.ts`
- Modify: `Edu_AI/src/stitch/course/knowledge/courseKnowledgeGraphDraft.test.ts`

- [ ] **Step 1: 写出失败的索引、筛选、问题和保护测试**

增加以下测试场景：

```typescript
test("review model identifies baseline nodes and selects the first issue", () => {
  const model = buildGraphReviewModel(root, baseline);
  assert.equal(model.nodesById.get("old-point")?.isExisting, true);
  assert.equal(model.nodesById.get("new-point")?.isExisting, false);
  assert.equal(model.issues[0].nodeId, "new-point");
  assert.equal(model.initialSelectedNodeId, "new-point");
});

test("tree search keeps ancestors and filters retain matching nodes", () => {
  const model = buildGraphReviewModel(root, baseline);
  assert.deepEqual(visibleGraphNodeIds(model, "牛顿", "all"), [
    "root",
    "mechanics",
    "newton",
  ]);
  assert.deepEqual(visibleGraphNodeIds(model, "", "new"), [
    "root",
    "mechanics",
    "new-point",
  ]);
});

test("existing node structural edits are rejected but summaries remain editable", () => {
  assert.equal(canEditGraphNodeStructure("old-point", baseline), false);
  assert.equal(canEditGraphNodeStructure("new-point", baseline), true);
  assert.match(
    updateGraphNode(root, "old-point", { summary: "补充说明" }).data?.summary || "",
    /补充说明/,
  );
});
```

- [ ] **Step 2: 运行测试并确认先失败**

Run:

```powershell
cd Edu_AI
pnpm test -- src/stitch/course/knowledge/courseKnowledgeGraphDraft.test.ts
```

Expected: 新辅助函数尚不存在。

- [ ] **Step 3: 实现稳定的审核状态模型**

新增导出类型和函数：

```typescript
export type GraphReviewFilter = "all" | "new" | "issues" | "mapped";

export type GraphReviewIssue = {
  code: "missing_content" | "needs_parent";
  nodeId: string;
  message: string;
  severity: "error" | "warning";
};

export type GraphReviewNode = GraphNodeOption & {
  node: KnowledgeGraphNode;
  childCount: number;
  isExisting: boolean;
  isNew: boolean;
  isMapped: boolean;
  hasIssue: boolean;
};

export type GraphReviewModel = {
  orderedIds: string[];
  nodesById: Map<string, GraphReviewNode>;
  issues: GraphReviewIssue[];
  initialSelectedNodeId: string;
};
```

`buildGraphReviewModel` 一次深度优先遍历创建索引，以基线 ID 集合判定 `isExisting`；名称或说明为空生成 `missing_content`，`needs_parent` 生成错误；首选中节点为第一个问题节点，否则为根节点。`visibleGraphNodeIds` 对搜索和筛选匹配节点向上补齐全部祖先。`canEditGraphNodeStructure` 只允许非基线节点执行改名、移动、重排和删除。

保持 `updateGraphNode` 的说明编辑能力；结构组件在调用 `removeGraphNode`、`moveGraphNode`、`moveGraphSibling` 前必须查询 `canEditGraphNodeStructure`。

- [ ] **Step 4: 运行纯函数测试并确认通过**

Run:

```powershell
cd Edu_AI
pnpm test -- src/stitch/course/knowledge/courseKnowledgeGraphDraft.test.ts
```

Expected: 全部通过。

- [ ] **Step 5: 提交本任务**

```powershell
git add Edu_AI/src/stitch/course/knowledge/courseKnowledgeGraphDraft.ts Edu_AI/src/stitch/course/knowledge/courseKnowledgeGraphDraft.test.ts
git commit -m "feat: add knowledge graph review state model"
```

### Task 7: 拆分顶部汇总、折叠树、单节点编辑器和固定操作栏

**Files:**
- Create: `Edu_AI/src/stitch/course/knowledge/KnowledgeGraphReviewSummary.tsx`
- Create: `Edu_AI/src/stitch/course/knowledge/KnowledgeGraphTree.tsx`
- Create: `Edu_AI/src/stitch/course/knowledge/KnowledgeGraphNodeEditor.tsx`
- Create: `Edu_AI/src/stitch/course/knowledge/KnowledgeGraphReviewActions.tsx`
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeGraphReviewStep.tsx`
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildWizard.tsx:250-282`
- Modify: `Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts`

- [ ] **Step 1: 写出失败的组件边界静态测试**

读取五个组件源文件并断言：

```typescript
assert.match(graphStep, /selectedNodeId/);
assert.match(graphStep, /expandedNodeIds/);
assert.match(graphStep, /mobilePane/);
assert.match(graphStep, /KnowledgeGraphReviewSummary/);
assert.match(graphStep, /KnowledgeGraphTree/);
assert.match(graphStep, /KnowledgeGraphNodeEditor/);
assert.match(graphStep, /KnowledgeGraphReviewActions/);
assert.doesNotMatch(graphStep, /function NodeEditor/);
assert.match(graphTree, /role="tree"/);
assert.match(graphTree, /aria-expanded/);
assert.match(nodeEditor, /当前节点/);
assert.match(nodeEditor, /现有节点的名称、类型和位置受保护/);
```

- [ ] **Step 2: 运行测试并确认先失败**

Run:

```powershell
cd Edu_AI
pnpm test -- src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
```

Expected: 新组件文件不存在。

- [ ] **Step 3: 实现顶部汇总和问题筛选**

`KnowledgeGraphReviewSummary` 接收 `stats`、`newCount`、`issues`、`activeFilter`、`onFilterChange`、`onSelectIssue`，渲染六项指标：全部节点、模块、知识点、教材映射、本次新增、待完善。问题按钮必须包含节点名称和问题说明，点击时调用 `onSelectIssue(nodeId)`。筛选按钮使用 `aria-pressed`，保存状态用明确文本显示“已保存”或“有未保存修改”。

- [ ] **Step 4: 实现可折叠、可搜索和键盘导航的左侧树**

`KnowledgeGraphTree` 的公开属性固定为：

```typescript
type Props = {
  model: GraphReviewModel;
  selectedNodeId: string;
  expandedNodeIds: Set<string>;
  query: string;
  filter: GraphReviewFilter;
  onQueryChange: (query: string) => void;
  onExpandedChange: (ids: Set<string>) => void;
  onSelect: (nodeId: string) => void;
};
```

树节点使用 `role="treeitem"`、`aria-level`、`aria-selected` 和 `aria-expanded`。键盘行为：上下箭头移动到可见前后节点；右箭头展开或进入首个子节点；左箭头折叠或返回父节点；Enter 选择。每行只显示类型、名称、直属子节点数以及“新增”“待完善”“待选择父节点”“教材已映射”文字标签，不渲染输入框。

- [ ] **Step 5: 实现只编辑当前节点的右侧编辑器**

`KnowledgeGraphNodeEditor` 接收当前节点、根图谱、基线和全部修改回调。旧节点：名称、类型、父节点、移动和删除禁用，显示“现有节点的名称、类型和位置受保护；可以补充说明和教材映射”。新增节点：允许改名、选择合法父节点、添加子节点、上下移动和删除。低频操作收进 `<details><summary>更多操作</summary>`；教材映射和来源引用以文本列表显示，不使用低对比度的小字。

- [ ] **Step 6: 实现固定操作栏并重写编排组件**

`KnowledgeGraphReviewActions` 始终包含返回教材步骤、保存草案、确认图谱并开始构建；确认勾选使用完整标签。`CourseKnowledgeGraphReviewStep` 维护：

```typescript
const [selectedNodeId, setSelectedNodeId] = useState(model.initialSelectedNodeId);
const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(
  () => new Set([root.id, ...(root.children || []).map((node) => node.id)]),
);
const [treeQuery, setTreeQuery] = useState("");
const [activeFilter, setActiveFilter] = useState<GraphReviewFilter>("all");
const [mobilePane, setMobilePane] = useState<"tree" | "editor">("tree");
const [impactAccepted, setImpactAccepted] = useState(false);
```

点击问题时展开所有祖先、选中对应节点并在窄屏切到详情。向导传入 `baselineRoot={build.baseline_graph || null}`。当后端错误含 `issues[0].node_id` 时，保留本地草案并把该 ID 传给审核步骤作为 `focusNodeId`。

- [ ] **Step 7: 运行前端测试并确认通过**

Run:

```powershell
cd Edu_AI
pnpm test -- src/stitch/course/knowledge/courseKnowledgeGraphDraft.test.ts src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
```

Expected: 全部通过。

- [ ] **Step 8: 提交本任务**

```powershell
git add Edu_AI/src/stitch/course/knowledge/KnowledgeGraphReviewSummary.tsx Edu_AI/src/stitch/course/knowledge/KnowledgeGraphTree.tsx Edu_AI/src/stitch/course/knowledge/KnowledgeGraphNodeEditor.tsx Edu_AI/src/stitch/course/knowledge/KnowledgeGraphReviewActions.tsx Edu_AI/src/stitch/course/knowledge/CourseKnowledgeGraphReviewStep.tsx Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildWizard.tsx Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
git commit -m "feat: redesign course knowledge graph review"
```

### Task 8: 完成可读性、焦点和响应式样式

**Files:**
- Modify: `Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.css:450-930`
- Modify: `Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts`

- [ ] **Step 1: 写出失败的布局与无障碍样式约束**

增加静态断言：

```typescript
assert.match(wizardStyles, /\.course-kb-graph__workspace\s*\{[^}]*grid-template-columns:\s*minmax\(260px,\s*35%\)\s+minmax\(0,\s*1fr\)/s);
assert.match(wizardStyles, /\.course-kb-graph__tree-pane\s*\{[^}]*overflow:\s*auto/s);
assert.match(wizardStyles, /\.course-kb-graph__editor-pane\s*\{[^}]*overflow:\s*auto/s);
assert.match(wizardStyles, /font-size:\s*16px/);
assert.match(wizardStyles, /:focus-visible/);
assert.match(wizardStyles, /@media\s*\(max-width:\s*767px\)/);
assert.match(wizardStyles, /\.course-kb-graph__mobile-tabs/);
```

- [ ] **Step 2: 运行测试并确认先失败**

Run:

```powershell
cd Edu_AI
pnpm test -- src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
```

Expected: 新布局选择器不存在。

- [ ] **Step 3: 实现桌面双栏和窄屏分页样式**

核心规则固定为：

```css
.course-kb-graph__workspace {
  display: grid;
  grid-template-columns: minmax(260px, 35%) minmax(0, 1fr);
  min-height: 520px;
  max-height: min(68vh, 760px);
  overflow: hidden;
  border: 1px solid var(--course-shell-line);
  border-radius: 14px;
  background: #fff;
}

.course-kb-graph__tree-pane,
.course-kb-graph__editor-pane {
  min-width: 0;
  overflow: auto;
}

.course-kb-graph__tree-pane {
  border-right: 1px solid var(--course-shell-line);
  background: #f8fafc;
}

.course-kb-graph__editor-pane {
  padding: 20px;
}

.course-kb-graph__editor-pane input,
.course-kb-graph__editor-pane textarea,
.course-kb-graph__editor-pane select,
.course-kb-graph__tree-row {
  font-size: 16px;
  line-height: 1.5;
}

.course-kb-graph button:focus-visible,
.course-kb-graph input:focus-visible,
.course-kb-graph textarea:focus-visible,
.course-kb-graph select:focus-visible,
.course-kb-graph [role="treeitem"]:focus-visible {
  outline: 3px solid rgb(37 99 235 / 35%);
  outline-offset: 2px;
}

@media (max-width: 767px) {
  .course-kb-graph__workspace {
    display: block;
    min-height: 480px;
    max-height: none;
  }

  .course-kb-graph__tree-pane,
  .course-kb-graph__editor-pane {
    border-right: 0;
  }

  .course-kb-graph__pane[hidden] {
    display: none;
  }

  .course-kb-graph__mobile-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}
```

普通正文颜色使用现有高对比度 `--course-shell-ink`，辅助文本不得小于 14px，指标和输入正文不得小于 16px。375px、768px、1024px、1440px 下外层容器均设置 `min-width: 0`，禁止页面级横向滚动。

- [ ] **Step 4: 运行测试、类型检查和构建**

Run:

```powershell
cd Edu_AI
pnpm test -- src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
pnpm exec tsc --noEmit
pnpm build
```

Expected: 测试通过、TypeScript 无错误、Vite build 成功。

- [ ] **Step 5: 提交本任务**

```powershell
git add Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.css Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
git commit -m "style: improve knowledge graph review readability"
```

### Task 9: 端到端验证增量保留、审核交互和历史版本

**Files:**
- Modify: `Edu_AI/tests/e2e/fixtures/courseKnowledgeBuild.ts`
- Modify: `Edu_AI/tests/e2e/course-knowledge-build-wizard.spec.ts`

- [ ] **Step 1: 扩展夹具为“已有图谱 + 新候选节点”**

把默认策略改为 `incremental`，夹具初始状态包含 `baseline_graph_version: 3`、`baseline_graph` 和对应摘要。生成图谱时保留所有基线节点并追加 `point-new`，版本接口先返回版本 3，发布后返回版本 4，同时保留版本 3。记录创建草案请求体、保存图谱和发布事件，供测试比较节点集合、名称、父节点和顺序。

- [ ] **Step 2: 写出失败的增量端到端测试**

新增测试：

```typescript
test("已有知识库默认增量追加并在树中审核新增节点", async ({ teacherPage }) => {
  const fixture = await installCourseKnowledgeBuildRoutes(teacherPage, { existingGraph: true });
  await openBuildWizard(teacherPage);

  await expect(teacherPage.getByText("课程知识库增量更新向导")).toBeVisible();
  await expect(teacherPage.getByText("增量追加（推荐）")).toBeVisible();
  await configureSmallBuild(teacherPage);
  await teacherPage.getByRole("button", { name: "跳过教材并生成图谱" }).click();

  await expect(teacherPage.getByRole("tree")).toBeVisible();
  await expect(teacherPage.getByText("本次新增")).toBeVisible();
  await teacherPage.getByRole("treeitem", { name: /新增鉴赏方法/ }).click();
  await expect(teacherPage.getByRole("heading", { name: "当前节点" })).toBeVisible();
  await expect(teacherPage.getByLabel("新增鉴赏方法名称")).toBeEnabled();

  await teacherPage.getByRole("treeitem", { name: /旧知识点/ }).click();
  await expect(teacherPage.getByText("现有节点的名称、类型和位置受保护")).toBeVisible();
  await expect(teacherPage.getByLabel("旧知识点名称")).toBeDisabled();

  await teacherPage.getByLabel(/我已审核图谱/).check();
  await teacherPage.getByRole("button", { name: "确认图谱并开始构建" }).click();

  expect(fixture.publishedBaselineSnapshot()).toEqual(fixture.originalBaselineSnapshot());
  expect(fixture.publishedNodeIds()).toContain("point-new");
  expect(fixture.versions()).toEqual([4, 3]);
});
```

再增加完全重建选择会触发确认框，以及问题提醒点击后定位对应节点的测试。

- [ ] **Step 3: 运行端到端测试并确认先失败**

Run:

```powershell
cd Edu_AI
pnpm test:e2e -- tests/e2e/course-knowledge-build-wizard.spec.ts --project=chromium
```

Expected: 新增流程断言 FAIL。

- [ ] **Step 4: 完成夹具并让端到端测试通过**

夹具必须模拟实际 API 返回的 `baseline_graph`、`review_state`、版本列表和发布新版本行为，不在浏览器测试中绕过保存、确认或启动接口。

Run:

```powershell
cd Edu_AI
pnpm test:e2e -- tests/e2e/course-knowledge-build-wizard.spec.ts --project=chromium
```

Expected: 文件内全部端到端测试通过。

- [ ] **Step 5: 提交本任务**

```powershell
git add Edu_AI/tests/e2e/fixtures/courseKnowledgeBuild.ts Edu_AI/tests/e2e/course-knowledge-build-wizard.spec.ts
git commit -m "test: cover incremental course knowledge updates"
```

### Task 10: 全量回归、人工响应式验收和交付收口

**Files:**
- Verify only; no planned product file changes.

- [ ] **Step 1: 运行后端相关回归**

Run:

```powershell
cd Edu_AI/api/src
.\.venv\Scripts\python.exe -m pytest tests/services/test_course_knowledge_graph_incremental.py tests/services/test_course_knowledge_graph_generator.py tests/test_course_knowledge_build_workflow.py tests/persistence/test_postgres_knowledge_repository.py -q
```

Expected: 全部通过，无 warning 转 error。

- [ ] **Step 2: 运行前端单元、类型和构建回归**

Run:

```powershell
cd Edu_AI
pnpm test -- src/stitch/course/knowledge/courseKnowledgeBuildState.test.ts src/stitch/course/knowledge/courseKnowledgeGraphDraft.test.ts src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
pnpm exec tsc --noEmit
pnpm build
```

Expected: 全部通过。

- [ ] **Step 3: 运行端到端回归**

Run:

```powershell
cd Edu_AI
pnpm test:e2e -- tests/e2e/course-knowledge-build-wizard.spec.ts --project=chromium
```

Expected: 全部通过。

- [ ] **Step 4: 在四个宽度完成可视化验收**

用浏览器分别设置 375px、768px、1024px、1440px，验证：顶部统计和问题提醒可读；桌面为左树右编辑器；窄屏为“图谱 / 节点详情”分页；只渲染一个节点编辑器；无页面级横向滚动；Tab、方向键、Enter 可完成树导航；焦点轮廓清晰；保存状态不只靠颜色表达。

- [ ] **Step 5: 检查变更范围并提交必要的验收修正**

Run:

```powershell
git status --short
git diff --check
git log --oneline -10
```

Expected: 仅包含本计划文件；`git diff --check` 无输出；每个任务有独立提交。若人工验收产生样式修正，重新执行 Steps 2-4 后提交：

```powershell
git add Edu_AI/src/stitch/course/knowledge
git commit -m "fix: finalize incremental graph review acceptance"
```

## 规格覆盖自检

- “已有知识库默认追加”由 Tasks 1、3、5、9 覆盖。
- “保留全部现有节点”由 Tasks 2、4、9 覆盖，保护存在于模型生成之后、保存/确认之前和发布事务内。
- “同父同名复用、不同父不误合并、稳定 ID”由 Task 2 覆盖。
- “完全重建仅在高级设置并二次确认，历史版本可回滚”由 Tasks 4、5、9 覆盖。
- “顶部统计与问题提醒、左侧折叠树、右侧单节点编辑”由 Tasks 6、7 覆盖。
- “旧节点只可补充说明和映射；新增节点可编辑结构”由 Tasks 6、7 覆盖。
- “窄屏分页、字号、对比度、焦点和键盘导航”由 Tasks 7、8、10 覆盖。
- “后端、前端、端到端验证”由 Tasks 1-10 的测试先行步骤和最终回归覆盖。
