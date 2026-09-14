# 课程知识库 Agent 工作流程实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建课程自动交接到课程知识库 Agent，使 Agent 能规划、查询和显式重试知识库构建，同时保留人工确认、质量门禁与原子发布。

**Architecture:** FastAPI 和 Harness 工具共用无 HTTP 依赖的课程知识库应用服务；Harness 将工具事实投影为结构化 `knowledge_plan` 与 workflow；前端课程创建成功后排入普通会话请求并进入当前课程 AI 工作区。正式构建继续使用现有持久化任务。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、PostgreSQL repository、DeepSeek Harness、React 18、TypeScript、Zustand、Node test runner、Playwright。

**Spec:** `docs/superpowers/specs/2026-09-10-course-knowledge-agent-workflow-design-cn.md`

## Global Constraints

- 模型不能确认或发布课程知识库。
- 只有教师当前消息明确要求重试时，Agent 才能调用重试工具。
- 新建课程事务不等待模型，Agent 交接失败不回滚课程。
- 增量保存、确认、启动和发布继续执行 revision 与 baseline 校验。
- 规划成功只表示 `awaiting_review`；只有真实任务成功且存在 `published_version` 才表示完成。
- 不修改或覆盖工作区中与本功能无关的未提交改动。

---

### Task 1: 建立应用服务边界

**Files:**
- Create: `backend/src/app/services/course_knowledge_application.py`
- Modify: `backend/src/app/api/courses.py`
- Test: `backend/src/tests/services/test_course_knowledge_application.py`

**Interfaces:**
- Consumes: `get_postgres_knowledge_repository()`、课程 storage manager、`generate_proposal()`、`submit_course_knowledge_plan_build_job()`。
- Produces: `CourseKnowledgeApplicationService.create_draft()`、`.plan()`、`.status()`、`.retry()` 和稳定的状态投影字典。

- [x] **Step 1: 写首次规划和复用 build 的失败测试**

```python
def test_plan_creates_draft_without_build_id_and_updates_existing_with_revision():
    service = CourseKnowledgeApplicationService(manager=manager, repository=repo,
        proposal_generator=proposal_generator, build_submitter=submitter)
    created = service.plan(course_id="course-1", actor_user_id="teacher",
        requirements="面向大一", build_id=None, expected_revision=None)
    revised = service.plan(course_id="course-1", actor_user_id="teacher",
        requirements="缩小到 16 学时", build_id=created["build_id"],
        expected_revision=created["revision"])
    assert created["status"] == "awaiting_review"
    assert revised["revision"] > created["revision"]
```

- [x] **Step 2: 运行测试并确认因模块不存在而失败**

Run: `cd backend/src && python -m pytest tests/services/test_course_knowledge_application.py -q`  
Expected: FAIL/collection error，缺少 `course_knowledge_application`。

- [x] **Step 3: 实现最小应用服务和状态投影**

```python
class CourseKnowledgeApplicationService:
    def plan(self, *, course_id, actor_user_id, requirements,
             build_id=None, expected_revision=None):
        build = self.create_draft(...) if build_id is None else self._get(...)
        if build_id is not None and expected_revision is None:
            raise ValueError("修改方案需要指定当前 revision")
        updated = self.proposal_generator(...)
        return self.project(updated, status_override="awaiting_review")
```

- [x] **Step 4: 增加状态、跨课程和重试边界测试**

```python
def test_retry_only_accepts_failed_or_blocked_build():
    repo.build["status"] = "running"
    with pytest.raises(ValueError, match="失败或阻塞"):
        service.retry(course_id="course-1", actor_user_id="teacher", build_id="kb-1")
```

- [x] **Step 5: 让 API 草稿创建复用应用服务并跑回归**

Run: `cd backend/src && python -m pytest tests/services/test_course_knowledge_application.py tests/test_course_knowledge_build_workflow.py -q`  
Expected: PASS；若接口 fixture 无隔离数据库则单独记录环境阻断，不把它误报成产品失败。

### Task 2: 扩展 Agent 工具与 Skill

**Files:**
- Modify: `backend/src/app/chat/harness/knowledge_tools.py`
- Modify: `backend/src/app/chat/harness/skills/edu-course-knowledge/SKILL.md`
- Test: `backend/src/tests/chat/test_harness_course_knowledge.py`

**Interfaces:**
- Consumes: Task 1 的 `CourseKnowledgeApplicationService`。
- Produces: `plan_course_knowledge`、`query_course_knowledge_build`、`retry_course_knowledge_build` 三个 MCP 工具。

- [x] **Step 1: 写工具 schema、权限和会话恢复失败测试**

```python
def test_query_uses_session_knowledge_plan_and_retry_requires_explicit_tool_call():
    tools.session.data["knowledge_plan"] = {"build_id": "kb-1", "revision": 2}
    status = tools.query_course_knowledge_build(QueryKnowledgeBuildArgs())
    assert status["build_id"] == "kb-1"
    assert "retry_course_knowledge_build" in KNOWLEDGE_TOOLS
```

- [x] **Step 2: 运行测试，确认 query/retry 工具缺失**

Run: `cd backend/src && python -m pytest tests/chat/test_harness_course_knowledge.py -q`  
Expected: FAIL，无法导入新 args 或工具。

- [x] **Step 3: 实现三个工具并统一调用应用服务**

工具每次先执行 `require(course_id, identity, "generate")`；query 缺少 build ID 时读取会话；plan/query/retry 都刷新 `session.data["knowledge_plan"]`。

- [x] **Step 4: 写 Skill 合同测试，再修改 Skill**

```python
def test_skill_requires_query_before_completion_and_explicit_retry():
    text = SKILL.read_text()
    assert "query_course_knowledge_build" in text
    assert "明确要求重试" in text
    assert "published_version" in text
    assert "不能确认或发布" in text
```

- [x] **Step 5: 跑工具和 Harness 相关回归**

Run: `cd backend/src && python -m pytest tests/chat/test_harness_course_knowledge.py tests/chat/test_harness_runtime.py -q`

### Task 3: 结构化投影知识库方案与状态

**Files:**
- Modify: `backend/src/app/chat/harness/runtime.py`
- Modify: `backend/src/app/chat/api/schemas_v2.py`
- Modify: `frontend/src/services/teacher/chatV2.ts`
- Test: `backend/src/tests/chat/test_harness_course_knowledge.py`
- Test: `backend/src/tests/chat/test_schemas_v2_api.py`

**Interfaces:**
- Consumes: 工具结果中的 `build_id`、`revision`、`status`、`summary`、`review_url`、`published_version`。
- Produces: `ChatResponseV2.knowledge_plan`、`action=knowledge.*`、`workflow.type=course_knowledge_base`。

- [x] **Step 1: 写四种状态的结果投影失败测试**

```python
@pytest.mark.parametrize((status, workflow), [
    ("awaiting_review", "awaiting_confirm"),
    ("running", "running"),
    ("failed", "failed"),
    ("succeeded", "completed"),
])
def test_result_projects_course_knowledge_status(status, workflow): ...
```

- [x] **Step 2: 运行测试并确认当前返回 `chat.reply`/`workflow=None`**

- [x] **Step 3: 新增纯函数投影并接入 `_result`**

规划结果固定生成可点击审核链接；查询结果仅在 `succeeded` 且 `published_version` 存在时生成完成文案。

- [x] **Step 4: 扩展后端 schema 和 TypeScript response 类型**

```python
class ChatResponseV2(BaseModel):
    knowledge_plan: Optional[Dict[str, Any]] = None
```

- [x] **Step 5: 跑 schema、runtime 和 TypeScript 契约测试**

Run: `cd backend/src && python -m pytest tests/chat/test_harness_course_knowledge.py tests/chat/test_harness_runtime.py tests/chat/test_schemas_v2_api.py -q`

### Task 4: 新建课程自动交接 Agent

**Files:**
- Create: `frontend/src/stitch/course/courseKnowledgeAgentHandoff.ts`
- Create: `frontend/src/stitch/course/courseKnowledgeAgentHandoff.test.ts`
- Modify: `frontend/src/stitch/pages/HomeDashboard.tsx`
- Modify: `frontend/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts`

**Interfaces:**
- Consumes: `BackendCourse`、`useStore.setQueuedMessage()`、`buildTeacherCourseHash("ai", course.id)`。
- Produces: `buildNewCourseKnowledgeAgentPrompt(course)` 和创建后的单次 Agent 交接。

- [x] **Step 1: 写提示词和路由失败测试**

```typescript
test("new course handoff includes authoritative course fields", () => {
  const prompt = buildNewCourseKnowledgeAgentPrompt(course);
  assert.match(prompt, /课程知识库/);
  assert.match(prompt, /不要直接发布/);
  assert.match(prompt, new RegExp(course.title));
});
```

- [x] **Step 2: 运行测试并确认 helper 不存在**

Run: `cd frontend && pnpm exec tsx --test src/stitch/course/courseKnowledgeAgentHandoff.test.ts`

- [x] **Step 3: 实现纯 helper，并在 `courseCreated` 中排入消息后跳转 AI 工作区**

```typescript
setQueuedMessage(buildNewCourseKnowledgeAgentPrompt(course));
window.location.hash = buildTeacherCourseHash("ai", course.id);
```

- [x] **Step 4: 更新旧集成测试，只断言当前 proposal 向导**

移除对未挂载 `CourseKnowledgeBuildConfigStep`、`updateCourseKnowledgeBuildDraft` 和 `generateCourseKnowledgeGraphDraft` 的断言；增加 `generateCourseKnowledgeProposal` 和 `selectCourseKnowledgeProposal` 断言。

- [x] **Step 5: 跑前端聚焦测试、lint 和 build**

Run: `cd frontend && pnpm exec tsx --test src/stitch/course/courseKnowledgeAgentHandoff.test.ts src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts`  
Run: `cd frontend && pnpm exec eslint src/stitch/course/courseKnowledgeAgentHandoff.ts src/stitch/pages/HomeDashboard.tsx`  
Run: `cd frontend && pnpm build`

### Task 5: 端到端验收与文档回填

**Files:**
- Create: `frontend/tests/e2e/course-knowledge-agent-workflow.spec.ts`
- Modify: `frontend/tests/e2e/fixtures/apiRoutes.ts`（仅当共享 fixture 需要新路由）
- Modify: `docs/acceptance/2026-09-10-course-knowledge-agent-workflow-acceptance-cn.md`
- Modify: `docs/acceptance/README.md`
- Modify: `docs/spec/README.md`
- Modify: `项目总览地图.md`

**Interfaces:**
- Consumes: 正式课程创建 UI、聊天 SSE 契约、知识库审核页面和现有构建 API。
- Produces: 可重复的浏览器 E2E 和验收证据。

- [x] **Step 1: 写失败的浏览器测试**

测试创建课程后 URL 进入 `#ai?course_id=...`、聊天请求包含课程知识库规划文本、SSE 结果含审核链接、点击后打开对应 `build_id` 的知识库向导。

- [x] **Step 2: 运行单用例并确认旧行为停留在课程详情**

Run: `cd frontend && pnpm exec playwright test tests/e2e/course-knowledge-agent-workflow.spec.ts --project=desktop1366`

- [x] **Step 3: 完成 fixture 与选择器的最小实现，重新运行浏览器测试**

- [x] **Step 4: 执行完整聚焦验证**

Run: `cd backend/src && python -m pytest tests/services/test_course_knowledge_application.py tests/services/test_course_knowledge_proposals.py tests/services/test_course_knowledge_graph_incremental.py tests/services/test_course_knowledge_quality_gate.py tests/chat/test_harness_course_knowledge.py tests/chat/test_harness_runtime.py tests/chat/test_schemas_v2_api.py -q`  
Run: `cd frontend && pnpm test`  
Run: `cd frontend && pnpm build`  
Run: `cd frontend && pnpm exec playwright test tests/e2e/course-knowledge-agent-workflow.spec.ts --project=desktop1366`

- [x] **Step 5: 回填验收结果和限制**

记录每条命令、通过数、失败数、运行环境、截图/trace 路径和未执行的真实外网/真实模型检查；不得把 mock E2E 描述成生产实测。
