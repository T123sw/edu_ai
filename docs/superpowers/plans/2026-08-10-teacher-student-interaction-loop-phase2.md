# 教师—学生交互回环 Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让教师发布、学生学习、可信证据沉淀、教师反馈和双端 Agent 学习判断形成真实、可信、可复测的完整回环。

**Architecture:** 保留 Phase 1 的 `LearningStore → LearningService → HTTP/Agent projection` 主线，在领域契约中显式区分课程学习任务与后台生成任务；学习完成增加证据口径，前端和 Agent 读取同一结构化事实。实施按领域语义、可信事件、查询投影、Agent 工具、双端界面、对话恢复、真实 E2E 七个独立评审边界推进。

**Tech Stack:** Python 3.12、FastAPI、Pydantic v2、SQLite/WAL、React 18、TypeScript、Vite、Node test runner、Playwright。

## Global Constraints

- 课程学习任务、后台生成任务和 Agent 执行计划必须使用独立领域语义。
- 现有 `lt_...` 学习任务和学习事件必须向前兼容，不删除用户数据。
- 旧 `completed` 事件只能迁移为 `self_reported`，不得推断为测评验证。
- 学生只能读取和写入自己的学习进度；教师只能读取自己可编辑课程的数据。
- UI、HTTP API 和 Agent 学习工具必须读取 `LearningService` 产生的同一事实。
- Agent 涉及数字和状态的学习回答必须来自结构化上下文或专用只读工具。
- 学习上下文不可用时不得依据历史生成任务猜测学习事实。
- 本阶段不实现向量化长期记忆，不基于阅读时长生成知识点掌握分。
- 所有新增事件写入必须保持 `event_id` 幂等、进度单调、完成口径单调。
- 不修改课程创建/加入链路，不破坏现有教师生成、学生个人知识库和课程资源能力。

---

## File Structure

### Backend files to create

- `Edu_AI/api/src/app/chat/domain/task_domain.py`：任务领域判定、显式 ID 防错和当前请求优先规则。
- `Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/learning.py`：学生与教师课程学习只读工具。
- `Edu_AI/api/src/tests/chat/runtime/test_learning_task_domain.py`：任务领域与计划编译契约。
- `Edu_AI/api/src/tests/chat/runtime/test_learning_agent_tools.py`：双端工具、权限和领域冲突测试。

### Backend files to modify

- `Edu_AI/api/src/app/learning/models.py`：完成口径、证据、扩展事件与进度字段。
- `Edu_AI/api/src/app/learning/store.py`：兼容迁移、证据持久化和单调投影。
- `Edu_AI/api/src/app/learning/service.py`：课程/学生 overview、证据汇总和 Agent 投影。
- `Edu_AI/api/src/app/schemas/learning.py`：新增字段与 overview 响应。
- `Edu_AI/api/src/app/api/learning.py`：新增 `/overview` 路由。
- `Edu_AI/api/src/app/chat/domain/teaching_task_contract.py`：新增 `task_domain`。
- `Edu_AI/api/src/app/chat/runtime/planning/task_contract_extractor.py`：从当前请求解析任务领域并隔离历史引用。
- `Edu_AI/api/src/app/chat/runtime/planning/compiler.py`：按角色和任务领域编译专用工具。
- `Edu_AI/api/src/app/chat/runtime/agent_tools/schemas.py`：替换模糊任务工具并添加学习工具 schema。
- `Edu_AI/api/src/app/chat/runtime/agent_tools/registry.py`：注册学习工具和生成任务工具新名称。
- `Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/control.py`：将现有状态工具明确重命名为生成任务状态工具。
- `Edu_AI/api/src/app/chat/runtime/nodes/executor.py`：工具调用约束和任务 ID 领域校验。
- `Edu_AI/api/src/app/chat/runtime/learning_context_prompt.py`：补充完成口径与禁止跨域回退规则。
- `Edu_AI/api/src/tests/learning/test_learning_store.py`
- `Edu_AI/api/src/tests/learning/test_learning_service.py`
- `Edu_AI/api/src/tests/learning/test_learning_api.py`
- `Edu_AI/api/src/tests/learning/test_learning_loop_acceptance.py`
- `Edu_AI/api/src/tests/chat/test_learning_context_injection.py`
- `Edu_AI/api/src/tests/chat/runtime/test_teaching_task_contract.py`
- `Edu_AI/api/src/tests/chat/runtime/test_plan_compiler.py`
- `Edu_AI/api/src/tests/chat/runtime/test_agent_tools.py`

### Frontend files to create

- `Edu_AI/src/stitch/pages/courseLearningOverview.ts`：课程卡片学习指标映射和失败降级。
- `Edu_AI/src/stitch/pages/courseLearningOverview.test.ts`：教师/学生卡片指标单元测试。
- `Edu_AI/src/components/teacher/chatHistoryRecovery.ts`：历史对话恢复的纯状态决策。
- `Edu_AI/src/components/teacher/chatHistoryRecovery.test.ts`：失败隔离与重试决策测试。
- `Edu_AI/src/stitch/pages/profilePresentation.ts`：个人中心真实课程数量的纯展示映射。
- `Edu_AI/src/stitch/pages/profilePresentation.test.ts`：课程数量成功与失败状态测试。
- `Edu_AI/tests/e2e/teacher-student-learning-loop.spec.ts`：真实双账号闭环和 Agent 领域验收。

### Frontend files to modify

- `Edu_AI/src/stitch/api/types.ts`：完成口径、证据字段和 overview 类型。
- `Edu_AI/src/stitch/api/learning.ts`：overview 客户端。
- `Edu_AI/src/stitch/pages/courseLearningPresentation.ts`：真实进度和证据标签。
- `Edu_AI/src/stitch/pages/courseLearningPresentation.test.ts`
- `Edu_AI/src/stitch/pages/CourseLearning.tsx`：学生自报文案、教师证据列、资源搜索与重名元数据。
- `Edu_AI/src/stitch/pages/CourseLearning.css`
- `Edu_AI/src/stitch/pages/courseCardPresentation.ts`：拆分学习任务和后台生成指标。
- `Edu_AI/src/stitch/pages/courseCardPresentation.test.ts`
- `Edu_AI/src/stitch/pages/HomeDashboard.tsx`：教师课程学习 overview。
- `Edu_AI/src/stitch/student/pages/StudentHome.tsx`：学生待学习任务 overview。
- `Edu_AI/src/components/teacher/ChatPanel.tsx`：恢复失败隔离、局部错误和重试。
- `Edu_AI/src/services/teacher/api.ts`：对话详情错误归一化。
- `Edu_AI/src/stitch/pages/LoginPage.tsx`：登录页统一角色文案并维持只记用户名的边界。
- `Edu_AI/src/stitch/pages/Profile.tsx`：真实课程数量。

---

### Task 1: 建立不可混淆的任务领域契约

**Files:**
- Create: `Edu_AI/api/src/app/chat/domain/task_domain.py`
- Create: `Edu_AI/api/src/tests/chat/runtime/test_learning_task_domain.py`
- Modify: `Edu_AI/api/src/app/chat/domain/teaching_task_contract.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/planning/task_contract_extractor.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/planning/compiler.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/agent_tools/schemas.py`
- Test: `Edu_AI/api/src/tests/chat/runtime/test_teaching_task_contract.py`
- Test: `Edu_AI/api/src/tests/chat/runtime/test_plan_compiler.py`

**Interfaces:**
- Produces: `TaskDomain`, `resolve_task_domain(question, explicit_task_ids) -> TaskDomain`。
- Produces: `TeachingTaskContract.task_domain`。
- Produces: `status` 计划对 `get_my_learning_progress`、`get_course_learning_progress`、`query_generation_job_status` 的确定性路由。
- Consumes: 当前请求的 `question`、`actor_role`、`course_id` 和分领域历史引用。

- [ ] **Step 1: 写任务领域失败测试**

```python
from types import SimpleNamespace

from app.chat.runtime.planning.compiler import compile_plan
from app.chat.runtime.planning.task_contract_extractor import extract_task_contract


def capability():
    return SimpleNamespace(
        allow_rag=False,
        allow_web=False,
        allow_image_search=False,
        selected_doc_ids=[],
        source_mode="none",
    )


def test_teacher_learning_status_uses_course_learning_tool():
    request = SimpleNamespace(
        question="这门课最新学习任务完成情况怎样？",
        actor_role="teacher",
        course_id="course-a",
        conversation_id="conv-a",
    )
    contract = extract_task_contract(request, capability(), {"pending_tasks": [{"task_id": "job_old"}]})
    assert contract.intent == "status"
    assert contract.task_domain == "course_learning"
    plan = compile_plan(contract)
    assert plan.steps[0].expected_tools == ["get_course_learning_progress"]


def test_student_completed_learning_never_falls_back_to_generation_job():
    request = SimpleNamespace(
        question="我刚完成了哪个学习任务？",
        actor_role="student",
        course_id="course-a",
        conversation_id="conv-a",
    )
    contract = extract_task_contract(request, capability(), {"pending_tasks": [{"task_id": "job_old"}]})
    assert contract.task_domain == "course_learning"
    assert contract.conversation_refs["generation_job_ids"] == ["job_old"]
    assert contract.conversation_refs["learning_task_ids"] == []
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
cd Edu_AI/api/src
python -m pytest -q tests/chat/runtime/test_learning_task_domain.py
```

Expected: FAIL，提示 `task_domain` 不存在或状态计划仍使用 `query_task_status`。

- [ ] **Step 3: 实现任务领域解析器**

```python
# app/chat/domain/task_domain.py
from __future__ import annotations

import re
from typing import Literal

TaskDomain = Literal["none", "course_learning", "generation_job"]

_LEARNING = ("学习任务", "学习进度", "完成率", "学生完成", "待学习", "刚完成")
_GENERATION = ("生成任务", "生成进度", "生成完成", "后台任务", "闪卡生成", "报告生成")
_TASK_ID = re.compile(r"\b(?:lt|job)_[a-zA-Z0-9_-]+\b")


def resolve_task_domain(question: str, explicit_task_ids: list[str] | None = None) -> TaskDomain:
    text = str(question or "").strip().lower()
    ids = list(explicit_task_ids or []) + _TASK_ID.findall(text)
    if any(value.startswith("lt_") for value in ids):
        return "course_learning"
    if any(value.startswith("job_") for value in ids):
        return "generation_job"
    learning = any(token in text for token in _LEARNING)
    generation = any(token in text for token in _GENERATION)
    if learning and not generation:
        return "course_learning"
    if generation and not learning:
        return "generation_job"
    return "none"
```

- [ ] **Step 4: 扩展契约与历史引用分区**

在 `TeachingTaskContract` 中添加：

```python
TaskDomain = Literal["none", "course_learning", "generation_job"]

class TeachingTaskContract(BaseModel):
    schema_version: Literal["2026-08-09", "2026-08-09.v2", "2026-08-10.v3"] = "2026-08-10.v3"
    task_domain: TaskDomain = "none"
```

在 extractor 中把候选引用分开：

```python
generation_job_ids = [value for value in candidate_task_ids if value.startswith("job_")]
learning_task_ids = [value for value in candidate_task_ids if value.startswith("lt_")]
task_domain = resolve_task_domain(question, learning_task_ids + generation_job_ids)

conversation_refs={
    "conversation_id": str(getattr(request, "conversation_id", "") or ""),
    "course_id": str(getattr(request, "course_id", "") or ""),
    "active_outline": bool(active_outline),
    "learning_task_ids": learning_task_ids,
    "generation_job_ids": generation_job_ids,
}
```

不得再生成无领域的 `candidate_task_ids`。

- [ ] **Step 5: 按领域编译状态计划**

```python
elif contract.intent == "status":
    if contract.task_domain == "course_learning":
        tool = (
            "get_my_learning_progress"
            if contract.actor_role == "student"
            else "get_course_learning_progress"
        )
        add("learning_status", "查询课程学习进度", [tool])
        add("report_result", "汇报学习结果", [])
        template_id = "course_learning_status"
    elif contract.task_domain == "generation_job":
        add("generation_status", "查询后台生成状态", ["query_generation_job_status"])
        add("report_result", "汇报生成结果", [])
        template_id = "generation_job_status"
    else:
        add("clarify", "确认要查询学习任务还是生成任务", [])
        template_id = "task_domain_clarification"
```

取消操作只允许 `generation_job`；对课程学习任务的“取消”返回澄清，Phase 2 不引入学生取消学习任务。

- [ ] **Step 6: 运行领域、契约和编译测试**

Run:

```powershell
python -m pytest -q tests/chat/runtime/test_learning_task_domain.py tests/chat/runtime/test_teaching_task_contract.py tests/chat/runtime/test_plan_compiler.py
```

Expected: PASS，且既有生成任务状态/取消测试使用 `generation_job`。

- [ ] **Step 7: 提交任务领域契约**

```powershell
git add Edu_AI/api/src/app/chat/domain/task_domain.py Edu_AI/api/src/app/chat/domain/teaching_task_contract.py Edu_AI/api/src/app/chat/runtime/planning/task_contract_extractor.py Edu_AI/api/src/app/chat/runtime/planning/compiler.py Edu_AI/api/src/app/chat/runtime/agent_tools/schemas.py Edu_AI/api/src/tests/chat/runtime/test_learning_task_domain.py Edu_AI/api/src/tests/chat/runtime/test_teaching_task_contract.py Edu_AI/api/src/tests/chat/runtime/test_plan_compiler.py
git commit -m "feat: separate learning and generation task domains"
```

---

### Task 2: 扩展可信学习证据与兼容迁移

**Files:**
- Modify: `Edu_AI/api/src/app/learning/models.py`
- Modify: `Edu_AI/api/src/app/learning/store.py`
- Modify: `Edu_AI/api/src/app/learning/service.py`
- Modify: `Edu_AI/api/src/app/schemas/learning.py`
- Test: `Edu_AI/api/src/tests/learning/test_learning_store.py`
- Test: `Edu_AI/api/src/tests/learning/test_learning_service.py`

**Interfaces:**
- Produces: `CompletionBasis`、`LearningEvidence`。
- Extends: `LearningEventRecord.evidence`。
- Extends: `TaskProgressRecord.completion_basis/evidence_count/last_activity_at`。
- Preserves: 旧 `completed` 事件与既有 SQLite 文件。

- [ ] **Step 1: 写迁移、幂等和单调口径失败测试**

```python
def test_existing_completed_progress_migrates_as_self_reported(tmp_path):
    database_path = tmp_path / "learning.db"
    legacy = build_legacy_learning_database(database_path, status="completed", progress=100)
    legacy.close()

    store = LearningStore(database_path)
    progress = store.get_progress("lt_legacy", "student-a")
    assert progress is not None
    assert progress.completion_basis == "self_reported"
    assert progress.evidence_count == 0


def test_completion_basis_is_idempotent_and_monotonic(learning_store, published_task):
    self_report = event("evt-1", "completed", 100)
    first = learning_store.record_event(self_report)
    duplicate = learning_store.record_event(self_report)
    evidenced = learning_store.record_event(event("evt-2", "resource_completed", 100))
    late_open = learning_store.record_event(event("evt-3", "resource_opened", 1))

    assert first.created is True
    assert duplicate.created is False
    assert evidenced.progress.completion_basis == "activity_evidenced"
    assert late_open.progress.completion_basis == "activity_evidenced"
    assert late_open.progress.progress_percent == 100
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_store.py -k "migrates_as_self_reported or basis_is_idempotent"
```

Expected: FAIL，缺少新字段或旧库读取失败。

- [ ] **Step 3: 扩展领域模型**

```python
CompletionBasis = Literal[
    "none",
    "self_reported",
    "activity_evidenced",
    "assessment_verified",
]

LearningEventType = Literal[
    "started",
    "resource_opened",
    "progress_updated",
    "completed",
    "resource_completed",
    "assessment_scored",
]

@dataclass(frozen=True)
class LearningEvidence:
    evidence_type: str
    source_type: str
    source_id: str
    value: float | str | bool | None
    occurred_at: str

@dataclass(frozen=True)
class TaskProgressRecord:
    task_id: str
    course_id: str
    student_id: str
    status: ProgressStatus
    progress_percent: int
    completion_basis: CompletionBasis
    evidence_count: int
    last_activity_at: str | None
    started_at: str | None
    completed_at: str | None
    updated_at: str
```

- [ ] **Step 4: 实现 SQLite 向前迁移**

在 `_initialize()` 建表后执行：

```python
def _ensure_column(self, table: str, name: str, declaration: str) -> None:
    columns = {
        str(row["name"])
        for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if name not in columns:
        self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

self._ensure_column("learning_events", "evidence_json", "TEXT")
self._ensure_column("task_progress", "completion_basis", "TEXT NOT NULL DEFAULT 'none'")
self._ensure_column("task_progress", "evidence_count", "INTEGER NOT NULL DEFAULT 0")
self._ensure_column("task_progress", "last_activity_at", "TEXT")
self._connection.execute(
    """
    UPDATE task_progress
    SET completion_basis='self_reported'
    WHERE status='completed' AND completion_basis='none'
    """
)
```

`table` 和 `name` 只允许内部常量调用，不接受请求参数。

- [ ] **Step 5: 实现证据口径投影**

```python
_BASIS_RANK = {
    "none": 0,
    "self_reported": 1,
    "activity_evidenced": 2,
    "assessment_verified": 3,
}

def _event_basis(event_type: str) -> str:
    return {
        "completed": "self_reported",
        "resource_completed": "activity_evidenced",
        "assessment_scored": "assessment_verified",
    }.get(event_type, "none")

def _max_basis(current: str, incoming: str) -> str:
    return incoming if _BASIS_RANK[incoming] > _BASIS_RANK[current] else current
```

只有 `INSERT OR IGNORE` 实际创建事件时才增加 `evidence_count`。`last_activity_at` 取成功创建事件的时间，重复事件不改变投影。

- [ ] **Step 6: 扩展服务验证与公开 schema**

要求：

```python
if event_type in {"resource_completed", "assessment_scored"} and normalized_ref is None:
    raise LearningRuleError("EVIDENCE_SOURCE_REQUIRED", "Evidence events require an assigned resource")

if event_type == "assessment_scored" and not evidence:
    raise LearningRuleError("ASSESSMENT_EVIDENCE_REQUIRED", "Assessment score evidence is required")
```

Pydantic 请求增加：

```python
class LearningEvidencePayload(BaseModel):
    evidence_type: str = Field(min_length=1, max_length=64)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=160)
    value: float | str | bool | None = None

class LearningEventRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=160)
    event_type: Literal[
        "started", "resource_opened", "progress_updated", "completed",
        "resource_completed", "assessment_scored",
    ]
    progress_percent: int = Field(ge=0, le=100)
    resource_ref: LearningResourceRef | None = None
    evidence: LearningEvidencePayload | None = None
```

- [ ] **Step 7: 运行学习存储与服务测试**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_store.py tests/learning/test_learning_service.py
```

Expected: PASS；旧库迁移、自报、活动证据、测评证据、重复事件和乱序事件均通过。

- [ ] **Step 8: 提交可信学习事实**

```powershell
git add Edu_AI/api/src/app/learning/models.py Edu_AI/api/src/app/learning/store.py Edu_AI/api/src/app/learning/service.py Edu_AI/api/src/app/schemas/learning.py Edu_AI/api/src/tests/learning/test_learning_store.py Edu_AI/api/src/tests/learning/test_learning_service.py
git commit -m "feat: add evidence-based learning progress"
```

---

### Task 3: 提供 UI 与 Agent 共用的学习摘要

**Files:**
- Modify: `Edu_AI/api/src/app/learning/models.py`
- Modify: `Edu_AI/api/src/app/learning/service.py`
- Modify: `Edu_AI/api/src/app/schemas/learning.py`
- Modify: `Edu_AI/api/src/app/api/learning.py`
- Modify: `Edu_AI/api/src/tests/learning/test_learning_api.py`
- Modify: `Edu_AI/api/src/tests/learning/test_learning_loop_acceptance.py`
- Modify: `Edu_AI/api/src/tests/chat/test_learning_context_injection.py`

**Interfaces:**
- Produces: `LearningOverviewRecord`。
- Produces: `LearningService.get_learning_overview(course_id, user_id, actor_role)`。
- Produces: `GET /api/courses/{course_id}/learning/overview`。
- Extends: 双端 Agent context 的 `as_of/completion_basis/latest_activity_at`。

- [ ] **Step 1: 写角色投影失败测试**

```python
def test_student_overview_contains_only_own_learning(service):
    overview = service.get_learning_overview(
        course_id="course-a", user_id="student-a", actor_role="student"
    )
    assert overview.pending_tasks == 1
    assert overview.self_reported_completed_tasks == 1
    assert "student-b" not in repr(overview)


def test_teacher_overview_reports_completion_bases_without_private_chat(service):
    overview = service.get_learning_overview(
        course_id="course-a", user_id="teacher-a", actor_role="teacher"
    )
    assert overview.enrolled_students == 2
    assert overview.activity_evidenced_students == 1
    assert not hasattr(overview, "conversation_history")
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_service.py -k overview
```

Expected: FAIL，`get_learning_overview` 不存在。

- [ ] **Step 3: 实现 overview 模型与服务**

```python
@dataclass(frozen=True)
class LearningOverviewRecord:
    course_id: str
    pending_tasks: int
    in_progress_tasks: int
    self_reported_completed_tasks: int
    activity_evidenced_completed_tasks: int
    assessment_verified_completed_tasks: int
    latest_activity_at: str | None
    enrolled_students: int | None = None
```

学生计数基于当前学生的已发布任务；教师计数基于课程已发布任务汇总。不得通过前端 job store 推导学习任务数。

- [ ] **Step 4: 暴露 overview API**

```python
@router.get("/overview", response_model=LearningOverviewResponse)
def get_learning_overview(
    course_id: str,
    principal: CoursePrincipal = Depends(require_course_read),
    service: LearningService = Depends(get_learning_service),
) -> LearningOverviewResponse:
    return LearningOverviewResponse.model_validate(
        service.get_learning_overview(
            course_id=course_id,
            user_id=principal.user_id,
            actor_role="student" if principal.system_role.lower() == "student" else "teacher",
        ),
        from_attributes=True,
    )
```

- [ ] **Step 5: 扩展 Agent 上下文**

学生任务项必须包含：

```python
{
    "task_id": view.task.task_id,
    "title": view.task.title,
    "status": progress.status,
    "progress_percent": progress.progress_percent,
    "completion_basis": progress.completion_basis,
    "last_activity_at": progress.last_activity_at,
    "knowledge_point_ids": list(view.task.knowledge_point_ids),
}
```

教师汇总增加各完成口径人数和 `as_of`，默认不携带学生对话或个人知识库内容。

- [ ] **Step 6: 运行 API、上下文与闭环测试**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_api.py tests/learning/test_learning_loop_acceptance.py tests/chat/test_learning_context_injection.py
```

Expected: PASS；学生响应无他人身份，教师 overview 与任务汇总数字一致。

- [ ] **Step 7: 提交统一学习摘要**

```powershell
git add Edu_AI/api/src/app/learning/models.py Edu_AI/api/src/app/learning/service.py Edu_AI/api/src/app/schemas/learning.py Edu_AI/api/src/app/api/learning.py Edu_AI/api/src/tests/learning/test_learning_api.py Edu_AI/api/src/tests/learning/test_learning_loop_acceptance.py Edu_AI/api/src/tests/chat/test_learning_context_injection.py
git commit -m "feat: expose role-scoped learning overview"
```

---

### Task 4: 让双端 Agent 使用专用学习工具

**Files:**
- Create: `Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/learning.py`
- Create: `Edu_AI/api/src/tests/chat/runtime/test_learning_agent_tools.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/agent_tools/schemas.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/agent_tools/registry.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/control.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/nodes/executor.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/learning_context_prompt.py`
- Modify: `Edu_AI/api/src/tests/chat/runtime/test_agent_tools.py`

**Interfaces:**
- Produces: `handle_get_my_learning_progress`。
- Produces: `handle_get_course_learning_progress`。
- Renames public tool: `query_task_status` → `query_generation_job_status`。
- Consumes: `ctx.snapshot.learning_context`、`ctx.request.actor_role/course_id/owner`。

- [ ] **Step 1: 写工具权限、结果和跨域失败测试**

```python
def test_student_learning_tool_returns_only_student_projection(tool_ctx):
    tool_ctx.request.actor_role = "student"
    tool_ctx.request.course_id = "course-a"
    tool_ctx.snapshot.learning_context = {
        "projection": "student",
        "completed_tasks": [{"task_id": "lt_1", "title": "递归基础", "completion_basis": "self_reported"}],
        "pending_tasks": [],
    }
    result = execute_tool("get_my_learning_progress", {}, tool_ctx)
    assert result["ok"] is True
    assert result["payload"]["completed_tasks"][0]["task_id"] == "lt_1"


def test_student_cannot_call_teacher_learning_tool(tool_ctx):
    tool_ctx.request.actor_role = "student"
    result = execute_tool("get_course_learning_progress", {}, tool_ctx)
    assert result["ok"] is False
    assert result["error"] == "permission_denied"


def test_generation_status_rejects_learning_task_id(tool_ctx):
    result = execute_tool("query_generation_job_status", {"task_id": "lt_1"}, tool_ctx)
    assert result["ok"] is False
    assert result["error"] == "task_domain_mismatch"
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m pytest -q tests/chat/runtime/test_learning_agent_tools.py
```

Expected: FAIL，学习工具和生成任务新名称尚不存在。

- [ ] **Step 3: 实现只读学习工具**

```python
def _learning_context(ctx) -> dict:
    snapshot = getattr(ctx, "snapshot", None)
    return dict(getattr(snapshot, "learning_context", {}) or {})


def handle_get_my_learning_progress(name: str, args: dict, ctx) -> dict:
    role = str(getattr(ctx.request, "actor_role", "") or "").lower()
    context = _learning_context(ctx)
    if role != "student" or context.get("projection") != "student":
        return error_result(name, "permission_denied", "学生学习进度只能由学生本人读取")
    task_id = str(args.get("task_id") or "").strip()
    tasks = list(context.get("pending_tasks") or []) + list(context.get("completed_tasks") or [])
    if task_id:
        tasks = [item for item in tasks if item.get("task_id") == task_id]
    return ok_result(name, f"已读取 {len(tasks)} 条本人课程学习记录", {"tasks": tasks, "as_of": context.get("as_of")})


def handle_get_course_learning_progress(name: str, args: dict, ctx) -> dict:
    role = str(getattr(ctx.request, "actor_role", "teacher") or "teacher").lower()
    context = _learning_context(ctx)
    if role == "student" or context.get("projection") != "teacher":
        return error_result(name, "permission_denied", "课程学习汇总仅课程教师可读取")
    task_id = str(args.get("task_id") or "").strip()
    summaries = list(context.get("task_summaries") or [])
    if task_id:
        summaries = [item for item in summaries if item.get("task_id") == task_id]
    return ok_result(name, f"已读取 {len(summaries)} 个课程学习任务汇总", {"task_summaries": summaries, "as_of": context.get("as_of")})
```

本阶段的教师 Agent 工具只返回课程聚合信息，不接收学生明细开关，也不得从 system prompt 猜学生名单。逐人状态继续由教师学习任务页面和教师进度 API 提供。

- [ ] **Step 4: 替换工具 schema 与注册表**

公开 schema 使用明确名称：

```python
SCHEMA_GET_MY_LEARNING_PROGRESS = {
    "type": "function",
    "function": {
        "name": "get_my_learning_progress",
        "description": "读取当前学生本人在当前课程的学习任务与进度，不查询后台生成任务。",
        "parameters": {"type": "object", "properties": {"task_id": {"type": "string", "pattern": "^lt_"}}},
    },
}

SCHEMA_GET_COURSE_LEARNING_PROGRESS = {
    "type": "function",
    "function": {
        "name": "get_course_learning_progress",
        "description": "读取当前教师可编辑课程的学习任务汇总，不查询内容生成任务。",
        "parameters": {"type": "object", "properties": {"task_id": {"type": "string", "pattern": "^lt_"}}},
    },
}

SCHEMA_QUERY_GENERATION_JOB_STATUS = {
    "type": "function",
    "function": {
        "name": "query_generation_job_status",
        "description": "只读查询报告、闪卡、PPT、课堂等后台内容生成任务状态。",
        "parameters": {"type": "object", "properties": {"task_id": {"type": "string", "pattern": "^job_"}}},
    },
}
```

学生 schema 只加入 `get_my_learning_progress`；教师 schema 只加入 `get_course_learning_progress`。两种角色都可按原权限查询自己的生成任务。

- [ ] **Step 5: 增加执行期领域防错**

```python
def _reject_task_domain_mismatch(name: str, args: dict) -> dict | None:
    task_id = str(args.get("task_id") or "").strip()
    if name in {"get_my_learning_progress", "get_course_learning_progress"} and task_id and not task_id.startswith("lt_"):
        return error_result(name, "task_domain_mismatch", "课程学习工具只接受 lt_ 学习任务")
    if name in {"query_generation_job_status", "cancel_task"} and task_id.startswith("lt_"):
        return error_result(name, "task_domain_mismatch", "后台生成任务工具不能处理课程学习任务")
    return None
```

在 handler 前调用；trace 记录 `task_domain_mismatch`，不得自动跨域重试。

- [ ] **Step 6: 强化学习 system context 约束**

`build_learning_context_prompt()` 必须追加：

```text
这些是当前课程、当前角色可读取的系统学习事实。
课程学习任务 ID 以 lt_ 标识，与后台内容生成任务完全不同。
回答学习进度时只能使用本段事实或课程学习只读工具；不得使用历史 job_ 任务代替。
completed_basis=self_reported 只表示学生自报，不代表测评通过或知识点已掌握。
```

- [ ] **Step 7: 运行 Agent 工具和学习上下文测试**

Run:

```powershell
python -m pytest -q tests/chat/runtime/test_learning_agent_tools.py tests/chat/runtime/test_agent_tools.py tests/chat/test_learning_context_injection.py
```

Expected: PASS；学生无教师工具，教师无他人私聊，生成工具拒绝 `lt_...`。

- [ ] **Step 8: 提交双端 Agent 学习工具**

```powershell
git add Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/learning.py Edu_AI/api/src/app/chat/runtime/agent_tools/schemas.py Edu_AI/api/src/app/chat/runtime/agent_tools/registry.py Edu_AI/api/src/app/chat/runtime/agent_tools/handlers/control.py Edu_AI/api/src/app/chat/runtime/nodes/executor.py Edu_AI/api/src/app/chat/runtime/learning_context_prompt.py Edu_AI/api/src/tests/chat/runtime/test_learning_agent_tools.py Edu_AI/api/src/tests/chat/runtime/test_agent_tools.py Edu_AI/api/src/tests/chat/test_learning_context_injection.py
git commit -m "feat: ground agents in typed learning tools"
```

---

### Task 5: 收口双端学习界面与课程首页指标

**Files:**
- Create: `Edu_AI/src/stitch/pages/courseLearningOverview.ts`
- Create: `Edu_AI/src/stitch/pages/courseLearningOverview.test.ts`
- Modify: `Edu_AI/src/stitch/api/types.ts`
- Modify: `Edu_AI/src/stitch/api/learning.ts`
- Modify: `Edu_AI/src/stitch/pages/courseLearningPresentation.ts`
- Modify: `Edu_AI/src/stitch/pages/courseLearningPresentation.test.ts`
- Modify: `Edu_AI/src/stitch/pages/CourseLearning.tsx`
- Modify: `Edu_AI/src/stitch/pages/CourseLearning.css`
- Modify: `Edu_AI/src/stitch/pages/courseCardPresentation.ts`
- Modify: `Edu_AI/src/stitch/pages/courseCardPresentation.test.ts`
- Modify: `Edu_AI/src/stitch/pages/HomeDashboard.tsx`
- Modify: `Edu_AI/src/stitch/student/pages/StudentHome.tsx`

**Interfaces:**
- Produces: `LearningOverview` TypeScript 类型与 `getLearningOverview(courseId)`。
- Produces: `getProgressLabel(progress, status)`、`getCompletionBasisLabel(basis)`。
- Produces: 学生 `pendingLearningTaskCount` 与教师 `activeLearningTaskCount` 卡片指标。
- Consumes: Task 2/3 新增 API 字段。

- [ ] **Step 1: 写真实文案和课程指标失败测试**

```typescript
import assert from "node:assert/strict";
import test from "node:test";

import { getCompletionBasisLabel, getProgressLabel } from "./courseLearningPresentation.ts";
import { toCourseLearningMetrics } from "./courseLearningOverview.ts";

test("in-progress learning never reads as completed", () => {
  assert.equal(getProgressLabel(1, "in_progress"), "进行中 · 1%");
  assert.equal(getProgressLabel(100, "completed"), "已完成");
  assert.equal(getCompletionBasisLabel("self_reported"), "学生自报完成");
});

test("student course card separates pending learning from background jobs", () => {
  assert.deepEqual(
    toCourseLearningMetrics("student", {
      pending_tasks: 2,
      in_progress_tasks: 1,
      self_reported_completed_tasks: 0,
      activity_evidenced_completed_tasks: 0,
      assessment_verified_completed_tasks: 0,
      latest_activity_at: null,
    }, 3),
    [
      { label: "待学习任务", value: 2 },
      { label: "后台生成中", value: 3 },
    ],
  );
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
cd Edu_AI
node --import tsx --test src/stitch/pages/courseLearningPresentation.test.ts src/stitch/pages/courseLearningOverview.test.ts
```

Expected: FAIL，旧文案返回“已完成 1%”，overview 映射不存在。

- [ ] **Step 3: 扩展类型与 API 客户端**

```typescript
export type CompletionBasis =
  | "none"
  | "self_reported"
  | "activity_evidenced"
  | "assessment_verified";

export type LearningOverview = {
  course_id: string;
  pending_tasks: number;
  in_progress_tasks: number;
  self_reported_completed_tasks: number;
  activity_evidenced_completed_tasks: number;
  assessment_verified_completed_tasks: number;
  latest_activity_at: string | null;
  enrolled_students?: number | null;
};

export const getLearningOverview = (courseId: string) =>
  apiRequest<LearningOverview>(`/api/courses/${courseId}/learning/overview`);
```

- [ ] **Step 4: 修复进度与完成口径展示**

```typescript
export function getProgressLabel(
  progressPercent: number,
  status: TaskProgress["status"],
): string {
  const value = Math.min(100, Math.max(0, Math.round(Number(progressPercent) || 0)));
  if (status === "not_started") return "未开始";
  if (status === "completed" || value === 100) return "已完成";
  return `进行中 · ${value}%`;
}

export function getCompletionBasisLabel(basis: CompletionBasis): string {
  return {
    none: "暂无完成证据",
    self_reported: "学生自报完成",
    activity_evidenced: "已有活动证据",
    assessment_verified: "测评已验证",
  }[basis];
}
```

学生按钮文案改为“我已完成”；首次点击显示说明“本次将记录为学生自报完成，不代表测评通过”。

- [ ] **Step 5: 增加资源搜索与重名元数据**

`CourseLearning.tsx` 增加 `resourceQuery`、`resourceType`，每项展示：

```tsx
<strong>{materialTitle(material)}</strong>
<span>{material.material_type}</span>
<small>
  {material.created_by || "未知创建者"} · {formatUpdatedAt(material.updated_at)} · {material.material_id.slice(-8)}
</small>
```

筛选只作用于选择器显示，不改变已选 `material_id`。

- [ ] **Step 6: 课程首页并行读取学习摘要**

教师和学生加载课程 facts 时增加：

```typescript
const [documents, resources, learning] = await Promise.all([
  getKnowledgeBaseDocuments(course.id, options).catch(() => []),
  getCourseMaterials(course.id, materialOptions).catch(() => []),
  getLearningOverview(course.id).catch(() => null),
]);
```

单课程 overview 失败时显示 `—` 和“学习任务暂不可用”，不得把值默认为 0，也不得阻断其他课程卡片。

- [ ] **Step 7: 运行学习展示和课程首页单元测试**

Run:

```powershell
node --import tsx --test src/stitch/pages/courseLearningPresentation.test.ts src/stitch/pages/courseLearningOverview.test.ts src/stitch/pages/courseCardPresentation.test.ts src/stitch/student/pages/studentHomeLayout.test.ts
```

Expected: PASS；“进行中 · 1%”、自报口径、待学习数和后台生成数分别展示。

- [ ] **Step 8: 运行前端构建与 lint**

Run:

```powershell
npm run lint
npm run build
```

Expected: lint 0 errors；build 成功。既有 warning 只允许保持不增加。

- [ ] **Step 9: 提交双端学习界面**

```powershell
git add Edu_AI/src/stitch/api/types.ts Edu_AI/src/stitch/api/learning.ts Edu_AI/src/stitch/pages/courseLearningOverview.ts Edu_AI/src/stitch/pages/courseLearningOverview.test.ts Edu_AI/src/stitch/pages/courseLearningPresentation.ts Edu_AI/src/stitch/pages/courseLearningPresentation.test.ts Edu_AI/src/stitch/pages/CourseLearning.tsx Edu_AI/src/stitch/pages/CourseLearning.css Edu_AI/src/stitch/pages/courseCardPresentation.ts Edu_AI/src/stitch/pages/courseCardPresentation.test.ts Edu_AI/src/stitch/pages/HomeDashboard.tsx Edu_AI/src/stitch/student/pages/StudentHome.tsx
git commit -m "feat: show truthful learning progress across workspaces"
```

---

### Task 6: 隔离历史对话恢复失败并修正双角色入口

**Files:**
- Create: `Edu_AI/src/components/teacher/chatHistoryRecovery.ts`
- Create: `Edu_AI/src/components/teacher/chatHistoryRecovery.test.ts`
- Modify: `Edu_AI/src/components/teacher/ChatPanel.tsx`
- Modify: `Edu_AI/src/services/teacher/api.ts`
- Modify: `Edu_AI/src/stitch/pages/LoginPage.tsx`
- Modify: `Edu_AI/src/stitch/pages/Profile.tsx`
- Create: `Edu_AI/src/stitch/pages/profilePresentation.ts`
- Create: `Edu_AI/src/stitch/pages/profilePresentation.test.ts`

**Interfaces:**
- Produces: `recoverConversationFailure(currentId, failedId) -> RecoveryDecision`。
- Produces: 局部错误状态 `{conversationId, message, retryable}`。
- Preserves: 新建对话和发送新消息能力。

- [ ] **Step 1: 写恢复失败隔离测试**

```typescript
import assert from "node:assert/strict";
import test from "node:test";

import { recoverConversationFailure } from "./chatHistoryRecovery.ts";

test("failed active history is detached before a new agent turn", () => {
  assert.deepEqual(recoverConversationFailure("conv-bad", "conv-bad"), {
    nextConversationId: null,
    clearMessages: true,
    clearPendingTasks: true,
    retryable: true,
  });
});

test("failure for a non-active history does not clear current chat", () => {
  assert.equal(
    recoverConversationFailure("conv-good", "conv-bad").clearMessages,
    false,
  );
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
node --import tsx --test src/components/teacher/chatHistoryRecovery.test.ts
```

Expected: FAIL，恢复决策模块不存在。

- [ ] **Step 3: 实现恢复决策并接入 ChatPanel**

```typescript
export type RecoveryDecision = {
  nextConversationId: string | null;
  clearMessages: boolean;
  clearPendingTasks: boolean;
  retryable: boolean;
};

export function recoverConversationFailure(
  currentConversationId: string | null,
  failedConversationId: string,
): RecoveryDecision {
  const activeFailed = currentConversationId === failedConversationId;
  return {
    nextConversationId: activeFailed ? null : currentConversationId,
    clearMessages: activeFailed,
    clearPendingTasks: activeFailed,
    retryable: true,
  };
}
```

`loadConversation` catch 中应用该决策，清除当前失败对话的 `statusCard/workflow/pending task reference`，展示局部错误和“重试加载”按钮。不得在页面底部直接渲染裸错误字符串。

- [ ] **Step 4: 归一化对话 API 错误**

```typescript
export class ConversationLoadError extends Error {
  constructor(
    message: string,
    readonly retryable: boolean,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "ConversationLoadError";
  }
}
```

网络失败返回“无法加载这段历史对话，请重试”；401/403 返回“登录状态或权限已变化，请重新登录”；404 返回“这段历史对话已不存在”。

- [ ] **Step 5: 修正登录与个人中心一致性**

- 登录页角色文案固定为“平台账号”。
- 保持现有“记住账号”只恢复用户名、不持久化密码的行为，并增加回归断言。
- 个人中心课程数调用 `listCourses()` 并使用成功响应长度；失败显示“暂不可用”，不显示错误的 0。

- [ ] **Step 6: 运行恢复、登录和个人中心测试**

Run:

```powershell
node --import tsx --test src/components/teacher/chatHistoryRecovery.test.ts src/stitch/pages/profilePresentation.test.ts
npm test
```

Expected: PASS；失败历史不会成为下一轮 Agent 的 pending task 来源。

- [ ] **Step 7: 提交恢复与双角色修正**

```powershell
git add Edu_AI/src/components/teacher/chatHistoryRecovery.ts Edu_AI/src/components/teacher/chatHistoryRecovery.test.ts Edu_AI/src/components/teacher/ChatPanel.tsx Edu_AI/src/services/teacher/api.ts Edu_AI/src/stitch/pages/LoginPage.tsx Edu_AI/src/stitch/pages/Profile.tsx Edu_AI/src/stitch/pages/profilePresentation.ts Edu_AI/src/stitch/pages/profilePresentation.test.ts
git commit -m "fix: isolate failed chat history from learning turns"
```

提交前用 `git diff --cached --name-only` 确认未暂存其他窗口的文件。

---

### Task 7: 建立真实双账号 E2E 与 Agent 行为门禁

**Files:**
- Create: `Edu_AI/tests/e2e/teacher-student-learning-loop.spec.ts`
- Create: `Edu_AI/tests/e2e/fixtures/learningLoop.ts`
- Modify: `Edu_AI/api/src/tests/learning/test_learning_loop_acceptance.py`
- Modify: `Edu_AI/api/src/tests/chat/runtime/test_learning_task_domain.py`
- Modify: `Edu_AI/docs/acceptance/2026-08-10-teacher-student-interaction-loop-phase2-acceptance.md`

**Interfaces:**
- Produces: 可重复的教师/学生浏览器场景和唯一 E2E 数据前缀。
- Produces: Agent trace 断言，证明学习查询未调用生成任务工具。
- Consumes: Tasks 1–6 的公开 API 和 UI。

- [ ] **Step 1: 写 API 驱动的 E2E fixture**

```typescript
export const learningE2eTitle = `E2E-LOOP2-${Date.now()}`;

export async function loginToken(
  request: APIRequestContext,
  username: string,
  password: string,
) {
  const response = await request.post("http://127.0.0.1:8001/api/auth/login", {
    data: { username, password },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).token as string;
}
```

fixture 只创建带 `E2E-LOOP2-` 前缀的任务，记录 `task_id`，验收后按测试专用清理机制删除；正式 API 没有删除能力时，fixture 使用独立 `LEARNING_DB_PATH`，不得直接删除用户数据库行。

- [ ] **Step 2: 写教师→学生→教师闭环测试**

```typescript
test("teacher and student complete a truthful learning loop", async ({ browser }) => {
  const teacher = await browser.newContext();
  const student = await browser.newContext();
  const teacherPage = await teacher.newPage();
  const studentPage = await student.newPage();

  await loginAs(teacherPage, "teacher", "teacher123");
  await teacherPage.goto("/#learning?course_id=computational-thinking");
  await createAndPublishLearningTask(teacherPage, learningE2eTitle);

  await loginAs(studentPage, "student", "student123");
  await studentPage.goto("/#student-home");
  await expect(studentPage.getByText("待学习任务")).toBeVisible();
  await studentPage.goto("/#student-learning?course_id=computational-thinking");
  await studentPage.getByRole("button", { name: /打开资源/ }).click();
  await studentPage.goto("/#student-learning?course_id=computational-thinking");
  await expect(studentPage.getByText("进行中 · 1%")).toBeVisible();
  await studentPage.getByRole("button", { name: "我已完成" }).click();
  await expect(studentPage.getByText("学生自报完成")).toBeVisible();

  await teacherPage.reload();
  await expect(teacherPage.getByText("学生自报完成")).toBeVisible();
});
```

- [ ] **Step 3: 在同一双账号场景中继续验证 Agent 领域**

```typescript
// 追加在 Step 2 的同一个 test 内，复用已经完成学习闭环的 teacherPage/studentPage。
await askCourseAgent(teacherPage, "这门课最新学习任务完成情况怎样？只根据学习记录回答。");
await expect(teacherPage.getByText(learningE2eTitle)).toBeVisible();
await expect(teacherPage.getByText(/学生自报完成/)).toBeVisible();
expect(await lastAgentToolNames(teacherPage)).not.toContain("query_generation_job_status");

await askCourseAgent(studentPage, "我刚完成了什么学习任务？下一步做什么？");
await expect(studentPage.getByText(learningE2eTitle)).toBeVisible();
expect(await lastAgentAnswer(studentPage)).not.toMatch(/job_[a-z0-9]+/);

await teacher.close();
await student.close();
```

若真实模型输出不稳定，测试环境注入确定性 model gateway，但必须保留一条本地真实模型手工验收；确定性测试断言工具选择和结构化事实，真实模型验收断言自然语言可用性。

- [ ] **Step 4: 增加权限、幂等、重启和失败恢复场景**

必须覆盖：

```text
学生创建任务 -> 403
学生查看班级汇总 -> 403
教师代学生写事件 -> 403
重复 event_id -> created=false 且 evidence_count 不增加
打开资源后乱序 started -> 进度不回退
后端重启后重新登录 -> 任务与 completion_basis 一致
历史对话详情失败 -> 可新建对话，学习查询不含旧 job_id
```

- [ ] **Step 5: 运行目标 E2E**

Run:

```powershell
cd Edu_AI
npx playwright test tests/e2e/teacher-student-learning-loop.spec.ts --project=desktop1440
```

Expected: PASS，0 retries；失败时保留 screenshot、trace 和 API 响应摘要。

- [ ] **Step 6: 更新验收文档实测栏**

把 `Edu_AI/docs/acceptance/2026-08-10-teacher-student-interaction-loop-phase2-acceptance.md` 中每个 `未执行` 改为 `通过` 或 `不通过`，填入提交、命令、时间、证据文件。不得仅因为单元测试通过就签署 Agent 真实可用。

- [ ] **Step 7: 提交 E2E 门禁**

```powershell
git add Edu_AI/tests/e2e/teacher-student-learning-loop.spec.ts Edu_AI/tests/e2e/fixtures/learningLoop.ts Edu_AI/api/src/tests/learning/test_learning_loop_acceptance.py Edu_AI/api/src/tests/chat/runtime/test_learning_task_domain.py Edu_AI/docs/acceptance/2026-08-10-teacher-student-interaction-loop-phase2-acceptance.md
git commit -m "test: gate the real teacher student learning loop"
```

---

### Task 8: 全量回归、迁移演练与发布签字

**Files:**
- Modify: `Edu_AI/docs/acceptance/2026-08-10-teacher-student-interaction-loop-phase2-acceptance.md`
- Read: `Edu_AI/docs/acceptance/2026-08-10-teacher-student-learning-loop-real-e2e.md`

**Interfaces:**
- Produces: 最终发布结论、已知限制和可复验证据。
- Consumes: Tasks 1–7 的提交与测试结果。

- [ ] **Step 1: 运行后端目标回归**

Run:

```powershell
cd Edu_AI/api/src
python -m pytest -q tests/learning tests/chat/test_learning_context_injection.py tests/chat/runtime/test_learning_task_domain.py tests/chat/runtime/test_learning_agent_tools.py tests/chat/runtime/test_teaching_task_contract.py tests/chat/runtime/test_plan_compiler.py tests/chat/runtime/test_agent_tools.py tests/chat/runtime/test_agent_memory_restore.py
```

Expected: 0 failed；仅允许已有 deprecation warning。

- [ ] **Step 2: 运行课程、聊天和权限回归**

Run:

```powershell
python -m pytest -q tests/test_course_access.py tests/test_course_route_authorization.py tests/chat
```

Expected: 0 failed；教师生成和学生权限不回归。

- [ ] **Step 3: 运行前端全量测试、lint 和 build**

Run:

```powershell
cd Edu_AI
npm test
npm run lint
npm run build
```

Expected: tests 0 failed；lint 0 errors；build 成功。

- [ ] **Step 4: 演练旧学习库迁移**

复制验收 fixture 的旧 schema 学习库到独立临时目录，启动新服务后断言：

```text
旧任务数量不变
旧事件数量不变
旧 completed -> self_reported
重复启动不重复迁移
重启后 overview、UI 和 Agent 数字一致
```

禁止使用真实用户 `learning.db` 做破坏性迁移演练。

- [ ] **Step 5: 执行真实浏览器手工签字场景**

使用真实教师、学生测试账号和独立 E2E 学习库，逐步执行验收文档第 5–11 节。必须保存：

- 教师发布后汇总截图。
- 学生“进行中 · 1%”与“学生自报完成”截图。
- 教师 Agent 正确汇总回答与 tool trace。
- 学生 Agent 正确任务回答与 tool trace。
- 历史对话失败后仍可新建对话的截图。

- [ ] **Step 6: 填写发布结论**

只有以下条件同时成立才能写“通过”：

```text
LOOP2-FR-001..010 全部通过
LOOP2-NFR-001..004 全部通过
teacher learning query 未调用 generation job tool
student learning query 未引用历史 job_id
UI/API/Agent 对同一任务数字一致
没有新增 P0/P1
```

否则写“不通过”，列出阻断编号和复现步骤，不得使用“基本通过”。

- [ ] **Step 7: 提交最终验收记录**

```powershell
git add Edu_AI/docs/acceptance/2026-08-10-teacher-student-interaction-loop-phase2-acceptance.md
git commit -m "docs: record phase 2 learning loop acceptance"
```

---

## Plan Self-Review Result

### Requirement Coverage

| Requirement | Implementation tasks | Acceptance gate |
| --- | --- | --- |
| LOOP2-FR-001 | Tasks 1, 4 | Task 7 双端 Agent trace |
| LOOP2-FR-002 | Tasks 3, 5 | Task 7 学生首页指标 |
| LOOP2-FR-003 | Tasks 2, 3, 5 | Tasks 7–8 完成口径一致性 |
| LOOP2-FR-004 | Tasks 3, 5 | Task 7 教师汇总与逐人反馈 |
| LOOP2-FR-005 | Tasks 3, 4 | Task 7 学生 Agent 权限与回答 |
| LOOP2-FR-006 | Tasks 3, 4 | Task 7 教师 Agent 汇总与回答 |
| LOOP2-FR-007 | Tasks 1, 4 | Task 7 学习查询工具 trace |
| LOOP2-FR-008 | Task 5 | Task 7 重名资源选择 |
| LOOP2-FR-009 | Task 6 | Tasks 7–8 历史恢复失败 |
| LOOP2-FR-010 | Tasks 2, 3 | Tasks 7–8 刷新、登录、重启 |
| LOOP2-NFR-001 | Task 2 | Tasks 7–8 幂等与乱序事件 |
| LOOP2-NFR-002 | Tasks 3, 4 | Tasks 7–8 API/tool 权限 |
| LOOP2-NFR-003 | Task 4 | Task 7 结构化事实与 trace |
| LOOP2-NFR-004 | Tasks 3, 5 | Task 7 单课程摘要失败隔离 |

- Spec coverage: 上表中的全部需求均映射到实施任务与验收门禁。
- Scope: 只覆盖真实教师—学生回环；提醒、截止日期、评分、分组和完整 Memory V2 未进入本计划。
- Type consistency: `TaskDomain`、`CompletionBasis`、`LearningOverview`、三个 Agent 工具名称在各任务中一致。
- Migration safety: 旧完成只映射为 `self_reported`，迁移演练使用独立副本。
- Privacy: 学生工具只读本人；教师默认聚合；所有权限仍由认证和课程成员关系决定。
- Completeness scan: 所有任务都给出文件、测试、实现边界、验证命令和提交边界，不保留未定义步骤。
