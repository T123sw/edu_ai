# Student Workspace Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏教师端现有能力的前提下，交付一个权限真实、导航清晰、基础流程可用的独立学生工作区；能够复用的认证、课程、生成、预览、任务和播放器内核继续复用，旧学生界面在新流程通过验收后彻底移除。

**Architecture:** 采用“复制展示层、复用业务内核”的双工作区结构。教师端与学生端拥有独立路由、壳层、页面编排和工具目录，共享后端授权服务、API 契约、RAG/任务协议、知识图谱画布、资源预览器和 AI 课堂播放器。后端把“课程修改能力”与“基于可读课程资料生成个人产物的能力”分离，并以系统角色、课程读取权和资源所有权三层校验保证学生只能读取课程共享内容、只能写入自己的个人空间。

**Tech Stack:** React 18、TypeScript 5.6、Vite 6、Node test runner、Playwright；FastAPI、Pydantic、pytest、现有文件型 `CourseStorageManager`、RAG/任务/资源服务。

## Global Constraints

- 本阶段只交付学生端基础功能：学习首页、AI问答、课程知识、个人知识库、AI课堂、资源管理及其权限闭环。
- 学生一级导航只能有六项：学习首页、AI问答、课程知识、个人知识库、AI课堂、资源管理。
- 不实现作业、批改、错题本、掌握度、间隔复习、学习计划、学习时长、学习记录等后续能力，也不渲染占位入口。
- 学生端不得依赖旧 `src/pages/student/`、旧 `src/components/student/`，也不得在最终形态中导入 `components/teacher/*`。
- 展示层可以从当前教师页面复制后独立修改；认证、授权、API、任务、生成提交、文档/资源预览、图谱画布和课堂播放器必须移动或保留在中立共享层复用。
- 所有上传文档、深度研究结果和生成产物默认属于当前用户，`visibility=private`；使用课程资料只记录 `course_context_id`，不改变所有权。
- 学生不能把个人文档或个人资源提交到课程；教师也不能读取学生个人文档、资源、任务或对话。
- 课程 `viewer` 仍然只有课程读取权。不得通过给 `viewer` 增加课程 `generate`、`edit` 或 `manage_resources` 权限来实现学生生成。
- 个人生成授权由后端工具目录决定；客户端角色、隐藏按钮或传入的 `actor_role` 都不能作为授权依据。
- 学生只能使用报告、PPT、思维导图、练习题、AI课堂、闪卡、课堂小游戏；教师只能使用报告、PPT、思维导图、练习题、AI课堂、教案、教学博客。
- 深度研究属于 AI问答左侧知识库模块，不是一级导航，也不是生成工具。
- 课程知识、课程共享资源和课程AI课堂对学生只读；所有写接口即使被直接调用也必须返回 `403`。
- 每个任务只提交本任务涉及的文件；不得覆盖另一个窗口或工作区中的无关改动。
- 每个任务先写失败测试，再做最小实现，运行定向测试后独立提交。

---

## File Structure

### Backend policy and personal data boundaries

- Create: `api/src/app/services/personal_tool_access.py` — 系统角色工具白名单、课程读取组合校验和工具目录生成。
- Create: `api/src/tests/services/test_personal_tool_access.py` — 教师/学生/管理员工具矩阵单元测试。
- Modify: `api/src/app/chat/api/schemas_v2.py` — 工具目录响应类型和生成预检资源类型。
- Modify: `api/src/app/chat/api/routes_v2.py` — 工具目录、预检及所有直接生成入口的服务端授权。
- Create: `api/src/tests/chat/test_personal_generation_authorization.py` — 各角色对九类生成入口的授权矩阵与越权测试。
- Create: `api/src/app/services/personal_knowledge_service.py` — 与课程修改权限无关、按 owner 隔离的个人文档聚合和写入服务。
- Create: `api/src/app/api/personal_knowledge.py` — `/api/personal-knowledge/documents` 个人知识库接口。
- Modify: `api/src/app/bootstrap.py` — 注册个人知识库路由。
- Create: `api/src/tests/services/test_personal_knowledge_service.py` — 个人文档所有权、跨课程聚合和路径安全测试。
- Create: `api/src/tests/test_personal_knowledge_api.py` — 学生上传/读取/重命名/删除/重试及跨用户拒绝测试。
- Modify: `api/src/app/api/courses.py` — 学生个人 AI课堂生成、课堂空间过滤和所有者导出权限。
- Create: `api/src/tests/test_student_classroom_permissions.py` — 学生个人课堂与教师课程课堂隔离测试。

### Shared frontend kernel

- Create: `src/stitch/shared/routes/roleRouteResolver.ts` — 登录角色默认路由和角色路由守卫的纯函数。
- Create: `src/stitch/shared/generation/generationCatalog.ts` — 后端工具目录类型、角色无关工具定义和 ID 映射。
- Create: `src/stitch/shared/generation/generationCatalog.test.ts` — 服务端目录过滤、未知工具拒绝和顺序稳定测试。
- Move: `src/components/teacher/generation/` → `src/components/generation/` — 复用现有生成定义、表单、提交和任务展示内核。
- Modify: `src/components/teacher/StudioPanel.tsx` — 改为导入中立生成内核，并使用后端返回的教师目录。
- Modify: `src/stitch/api/courses.ts` — 课程只读数据继续共享。
- Create: `src/stitch/api/personalKnowledge.ts` — 全局个人知识库客户端。
- Modify: `src/stitch/api/classroom.ts` — `space=mine|course` 列表契约。
- Create: `src/stitch/api/generationTools.ts` — 当前用户工具目录客户端。

### Independent student presentation layer

- Create: `src/stitch/student/StudentApp.tsx` — 学生路由表和学生页面入口。
- Create: `src/stitch/student/routes/studentRoutes.ts` — 独立 hash 路由构造/解析。
- Create: `src/stitch/student/routes/studentRoutes.test.ts` — 路由、课程 ID、视图和空间参数测试。
- Create: `src/stitch/student/routes/StudentRouteGuard.tsx` — 角色不匹配与缺少课程上下文状态。
- Create: `src/stitch/student/shell/studentNavigation.ts` — 六项正式导航定义。
- Create: `src/stitch/student/shell/studentNavigation.test.ts` — 导航数量、顺序和禁止入口测试。
- Create: `src/stitch/student/shell/StudentShell.tsx` — 学生侧栏、课程选择器、响应式壳层。
- Create: `src/stitch/student/styles/studentShell.css` — 学生工作区样式。
- Create: `src/stitch/student/pages/StudentHome.tsx` — 最近学习、课程搜索和课程卡片。
- Create: `src/stitch/student/pages/studentRecentLearning.ts` — 最近学习持久化纯函数。
- Create: `src/stitch/student/pages/studentRecentLearning.test.ts` — 真实最近路由排序和失效课程清理测试。
- Create: `src/stitch/student/pages/StudentAIWorkspace.tsx` — 学生三栏 AI问答页。
- Create: `src/stitch/student/pages/StudentCourseKnowledge.tsx` — 只读图谱/课程知识库页。
- Create: `src/stitch/student/pages/StudentPersonalKnowledge.tsx` — 全局个人知识库管理页。
- Create: `src/stitch/student/pages/StudentClassroom.tsx` — 我的AI课堂/课程AI课堂双空间。
- Create: `src/stitch/student/pages/StudentResources.tsx` — 个人生成/课程共享双空间。
- Create: `src/stitch/student/tools/StudentGenerationFactory.tsx` — 复用生成内核的学生配置层。
- Create: `src/components/student/SourcePanel.tsx` — 从当前教师 SourcePanel 复制后删除课程写操作。
- Create: `src/components/student/ChatPanel.tsx` — 从当前问答展示层复制并替换学生文案/跳转。
- Create: `src/components/student/StudentStudioPanel.tsx` — 学生工具目录容器。
- Create: `tests/e2e/student-workspace-foundation.spec.ts` — 学生基础流程和权限 E2E。

### Integration and cleanup

- Modify: `src/stitch/App.tsx` — 登录角色分流，装配 `StudentApp`，拒绝跨角色路由。
- Modify: `src/stitch/shared.tsx` — 只保留真正共享的应用上下文，不再向学生壳层注入教师导航。
- Modify: `src/stitch/course/CourseRouteProvider.tsx` — 同时解析教师/学生 URL，以显式 URL 为权威课程上下文。
- Modify: `src/stitch/course/courseNavigation.ts` — 保持教师课程导航回归，不把学生导航塞入教师配置。
- Delete after zero-reference verification: `src/pages/student/`、旧 `src/components/student/` 中被新实现替代的文件、`src/routes/AppRoutes.tsx` 中旧学生路由及对应废弃样式。

---

### Task 1: Establish the Server-Side Personal Tool Policy

**Files:**
- Create: `api/src/app/services/personal_tool_access.py`
- Create: `api/src/tests/services/test_personal_tool_access.py`

**Interfaces:**

```python
PersonalToolId = Literal[
    "report", "ppt", "mind_map", "quiz", "classroom",
    "lesson_plan", "blog", "flashcard", "game",
]

@dataclass(frozen=True)
class PersonalToolDefinition:
    tool_id: PersonalToolId
    allowed_system_roles: frozenset[str]
    required_course_capabilities: tuple[Literal["read"], ...]
    allowed_source_scopes: tuple[Literal["none", "personal", "course"], ...]
    output_scope: Literal["personal"] = "personal"
    publish_capability: None = None

def list_personal_tools_for_role(system_role: str) -> tuple[PersonalToolDefinition, ...]: ...
def require_personal_tool(system_role: str, tool_id: str) -> PersonalToolDefinition: ...
```

- [ ] **Step 1: Write the failing policy matrix tests**

Assert exact ordered IDs:

```python
assert ids("teacher") == [
    "report", "ppt", "mind_map", "quiz", "classroom",
    "lesson_plan", "blog",
]
assert ids("student") == [
    "report", "ppt", "mind_map", "quiz", "classroom",
    "flashcard", "game",
]
assert ids("admin") == ids("teacher")
```

Also assert students are denied `lesson_plan`/`blog`, teachers are denied `flashcard`/`game`, unknown roles and unknown tool IDs are denied, and every returned definition has `output_scope == "personal"` and no publish capability.

- [ ] **Step 2: Run the tests and verify RED**

```powershell
python -m pytest api/src/tests/services/test_personal_tool_access.py -q
```

Expected: import failure because the policy module does not exist.

- [ ] **Step 3: Implement the immutable registry and explicit error**

Define `PersonalToolAccessDenied(ValueError)` carrying `tool_id` and `system_role`. Do not infer permissions from the frontend registry or from course roles. Keep `admin` aligned with teacher tools in this milestone.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the command from Step 2. Expected: all policy cases pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add -- api/src/app/services/personal_tool_access.py api/src/tests/services/test_personal_tool_access.py
git commit -m "feat: define role-scoped personal generation tools"
```

---

### Task 2: Authorize Every Direct Generation Route by Tool and Ownership

**Files:**
- Modify: `api/src/app/chat/api/schemas_v2.py`
- Modify: `api/src/app/chat/api/routes_v2.py`
- Create: `api/src/tests/chat/test_personal_generation_authorization.py`
- Modify: `api/src/tests/chat/test_generation_preflight.py`
- Modify: `api/src/tests/chat/test_routes_v2.py`

**Interfaces:**

```python
class GenerationToolDefinitionV2(BaseModel):
    tool_id: PersonalToolId
    output_scope: Literal["personal"]
    allowed_source_scopes: list[Literal["none", "personal", "course"]]
    can_publish: Literal[False] = False

class GenerationToolCatalogResponseV2(BaseModel):
    tools: list[GenerationToolDefinitionV2]

def _require_personal_generation_access(
    *, tool_id: PersonalToolId, course_id: str | None,
    current_user: dict, access_service: CourseAccessService,
) -> None: ...
```

- [ ] **Step 1: Write failing HTTP authorization tests**

Cover `GET /api/chat/v2/generation/tools`, `POST /generation/preflight`, and all direct create routes. Use authenticated teacher and student fixtures. Required assertions:

```text
student: report/ppt/graph/quiz allowed; lesson-plan/blog denied; flashcard/game allowed
teacher: report/ppt/graph/quiz/lesson-plan/blog allowed; flashcard/game denied
both: course membership read required when course_id is supplied
both: selected personal documents must belong to current user
both: selected course documents must belong to the readable current course
all successful jobs: owner == authenticated username; output visibility == private
```

For PPT, authorize both outline creation and final generation by persisting the owner/tool on the draft; a user must not finalize another user's draft.

- [ ] **Step 2: Run the route tests and verify RED**

```powershell
python -m pytest api/src/tests/chat/test_personal_generation_authorization.py api/src/tests/chat/test_generation_preflight.py api/src/tests/chat/test_routes_v2.py -q
```

Expected: the current code denies student viewers through course `generate`, exposes teacher flashcard/game, and has no catalog endpoint.

- [ ] **Step 3: Add the authenticated tool catalog**

Add `GET /api/chat/v2/generation/tools`. Derive the role only from `get_current_user`; return no labels or UI HTML, only stable capability data. Map frontend `mind_map` to the existing backend `graph` route at the API boundary, but expose `tool_id="mind_map"` consistently in the catalog.

- [ ] **Step 4: Replace course-generate checks on personal generation**

Change the helper so it first calls `require_personal_tool(role, tool_id)`, then calls `require_course_capability(course_id, current_user, "read", access_service)` only when a course context is present. Pass an explicit tool ID from every endpoint; never derive it from payload text.

Update preflight to use its existing `resource_type`. Keep course knowledge build/reindex routes on course `generate`; this change applies only to personal resource generation.

- [ ] **Step 5: Assert private output and source ownership before submission**

Keep `_validate_direct_generation_source` as the source boundary, ensure `owner` comes from the authenticated user, and ensure `GenerationCommand` receives that owner. Do not add a request field that can override owner or output visibility.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: the full nine-tool role matrix and cross-user/source tests pass.

- [ ] **Step 7: Commit Task 2**

```powershell
git add -- api/src/app/chat/api/schemas_v2.py api/src/app/chat/api/routes_v2.py api/src/tests/chat/test_personal_generation_authorization.py api/src/tests/chat/test_generation_preflight.py api/src/tests/chat/test_routes_v2.py
git commit -m "feat: enforce personal generation tool permissions"
```

---

### Task 3: Make the Personal Knowledge Base Truly Owner-Scoped

**Files:**
- Create: `api/src/app/services/personal_knowledge_service.py`
- Create: `api/src/app/api/personal_knowledge.py`
- Modify: `api/src/app/bootstrap.py`
- Modify: `api/src/app/api/courses.py`
- Create: `api/src/tests/services/test_personal_knowledge_service.py`
- Create: `api/src/tests/test_personal_knowledge_api.py`

**Interfaces:**

```text
GET    /api/personal-knowledge/documents
POST   /api/personal-knowledge/documents
GET    /api/personal-knowledge/documents/{document_id}/content
PATCH  /api/personal-knowledge/documents/{document_id}
DELETE /api/personal-knowledge/documents/{document_id}
POST   /api/personal-knowledge/documents/{document_id}/retry
```

`POST` accepts optional `course_context_id`; it is provenance only and never grants access. `GET` supports `status`, `search`, `sort`, `limit`, `offset` and returns only the current user's records across course contexts.

- [ ] **Step 1: Write failing owner-scope service tests**

Use real temporary storage. Verify one user sees personal documents uploaded from two different course contexts in one list; another student, a teacher in those courses, and a course owner see none of them. Verify filename/path traversal rejection and stable document IDs.

- [ ] **Step 2: Write failing API tests**

Assert a student viewer can upload, read, rename, delete and retry their own document without course `edit`; cannot select another user's ID; and cannot pass `library_type=course`. Assert a course-context ID requires course `read` at upload time, but later personal reads depend on owner rather than course manager rights.

- [ ] **Step 3: Run tests and verify RED**

```powershell
python -m pytest api/src/tests/services/test_personal_knowledge_service.py api/src/tests/test_personal_knowledge_api.py -q
```

- [ ] **Step 4: Implement a personal service over existing storage/index primitives**

Reuse file validation, document state transitions, index jobs and content preview logic from `KnowledgeDocumentService`. Store a normalized owner access domain `personal:<user_id>` and optional `course_context_id`. Do not create a fake course membership or scan data without owner filtering.

The old course endpoint may continue to serve teacher compatibility, but when `library_type=personal` it must delegate to the same owner service. When `library_type=course`, existing `require_course_edit` remains mandatory.

- [ ] **Step 5: Register the router and map errors consistently**

Use `401` for missing authentication, `403` for explicit forbidden scope, `404` for another user's or missing document, `409` for invalid lifecycle state, and `422` for invalid file/sort/input.

- [ ] **Step 6: Run tests and verify GREEN**

Run the command from Step 3.

- [ ] **Step 7: Commit Task 3**

```powershell
git add -- api/src/app/services/personal_knowledge_service.py api/src/app/api/personal_knowledge.py api/src/app/bootstrap.py api/src/app/api/courses.py api/src/tests/services/test_personal_knowledge_service.py api/src/tests/test_personal_knowledge_api.py
git commit -m "feat: add owner-scoped personal knowledge library"
```

---

### Task 4: Separate Personal and Course AI Classrooms

**Files:**
- Modify: `api/src/app/api/courses.py`
- Modify: `api/src/app/schemas/course.py`
- Modify: `api/src/core/course_storage.py` only if classroom space filtering is not already generic
- Create: `api/src/tests/test_student_classroom_permissions.py`
- Modify: `src/stitch/api/classroom.ts`
- Modify: `src/stitch/api/types.ts`

**Interfaces:**

```text
POST /api/courses/{course_id}/classrooms/generate
GET  /api/courses/{course_id}/classrooms?space=mine|course
POST /api/courses/{course_id}/classrooms/{id}/video/export
```

- [ ] **Step 1: Write failing classroom permission tests**

Assert a student viewer with course read and the `classroom` personal tool can generate; the saved classroom has `owner_user_id=student`, `visibility=private`; only that student sees it under `space=mine`. Assert `space=course` returns only teacher-published snapshots and is read-only. Assert student A cannot load/export/delete student B's classroom.

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m pytest api/src/tests/test_student_classroom_permissions.py api/src/tests/test_classroom_generation_sources.py api/src/tests/test_classroom_video_export.py -q
```

- [ ] **Step 3: Replace `require_course_generate` only on personal classroom actions**

Use `require_course_read` plus `require_personal_tool(principal.system_role, "classroom")` for generate and owner export. Keep course publication, withdrawal and course-content mutations behind `manage_resources`. Pass authenticated owner to source validation and job submission.

- [ ] **Step 4: Add explicit list spaces**

Validate `space` as `mine|course`, default to `mine` for the student page client, and delegate to existing material visibility filtering. Never return `all` to the student UI.

- [ ] **Step 5: Update the typed client and run frontend API tests**

Add:

```ts
export function listClassrooms(
  courseId: string,
  space: "mine" | "course",
): Promise<ClassroomMaterial[]>;
```

Run:

```powershell
npm test -- --test-name-pattern="classroom|course material"
```

- [ ] **Step 6: Run all focused tests and verify GREEN**

Run Steps 2 and 5 again.

- [ ] **Step 7: Commit Task 4**

```powershell
git add -- api/src/app/api/courses.py api/src/app/schemas/course.py api/src/core/course_storage.py api/src/tests/test_student_classroom_permissions.py src/stitch/api/classroom.ts src/stitch/api/types.ts
git commit -m "feat: isolate personal and course ai classrooms"
```

---

### Task 5: Add Student Routes, Role Guard, and Six-Item Shell

**Files:**
- Create: `src/stitch/student/routes/studentRoutes.ts`
- Create: `src/stitch/student/routes/studentRoutes.test.ts`
- Create: `src/stitch/student/routes/StudentRouteGuard.tsx`
- Create: `src/stitch/student/shell/studentNavigation.ts`
- Create: `src/stitch/student/shell/studentNavigation.test.ts`
- Create: `src/stitch/student/shell/StudentShell.tsx`
- Create: `src/stitch/student/styles/studentShell.css`
- Create: `src/stitch/shared/routes/roleRouteResolver.ts`
- Create: `src/stitch/shared/routes/roleRouteResolver.test.ts`
- Modify: `src/stitch/course/CourseRouteProvider.tsx`

**Interfaces:**

```ts
export type StudentRoute =
  | "student-home" | "student-ai" | "student-course-knowledge"
  | "student-personal-knowledge" | "student-classroom" | "student-resources";

export function buildStudentHash(
  route: StudentRoute,
  options?: { courseId?: string; view?: "structure" | "documents"; space?: "mine" | "course" },
): string;

export function readStudentLocation(hash: string): {
  route: StudentRoute | null;
  courseId: string | null;
  view?: "structure" | "documents";
  space?: "mine" | "course";
};
```

- [ ] **Step 1: Write failing pure-function tests**

Assert all six routes, URL encoding, missing/`undefined` course IDs, allowed `view`/`space` defaults, and role defaults (`student → #student-home`, `teacher/admin → #home`). Assert students cannot resolve teacher feature routes and teachers cannot remain on student routes after login.

- [ ] **Step 2: Write the navigation contract test**

Assert exact labels and order:

```ts
["学习首页", "AI问答", "课程知识", "个人知识库", "AI课堂", "资源管理"]
```

Assert no item contains 课程详情、课程设置、快捷开始、最近个人资料、作业或学习记录。

- [ ] **Step 3: Run tests and verify RED**

```powershell
npm test -- --test-name-pattern="student route|student navigation|role route"
```

- [ ] **Step 4: Implement the shell and explicit course context**

The shell loads `listCourses()`, renders a real course selector on course-dependent pages, writes the selected `course_id` into the target URL, and treats URL as authoritative. `student-personal-knowledge` does not require a course. Missing course context renders “请选择课程” rather than a stale remembered course.

- [ ] **Step 5: Extend `CourseRouteProvider` without coupling namespaces**

Parse both `readTeacherCourseId` and `readStudentLocation`; preserve current teacher-home remembered-course behavior only for teacher routes. Add regression tests for current teacher URLs.

- [ ] **Step 6: Run tests and verify GREEN**

Run Step 3 plus:

```powershell
npm test -- --test-name-pattern="teacher route|course route"
```

- [ ] **Step 7: Commit Task 5**

```powershell
git add -- src/stitch/student/routes src/stitch/student/shell src/stitch/student/styles/studentShell.css src/stitch/shared/routes src/stitch/course/CourseRouteProvider.tsx
git commit -m "feat: add isolated student routes and navigation shell"
```

---

### Task 6: Build the Student Learning Home with Real Recent Learning

**Files:**
- Create: `src/stitch/student/pages/StudentHome.tsx`
- Create: `src/stitch/student/pages/studentRecentLearning.ts`
- Create: `src/stitch/student/pages/studentRecentLearning.test.ts`
- Create: `src/stitch/student/styles/studentHome.css`
- Reference, do not import as a page: `src/stitch/pages/HomeDashboard.tsx`
- Reuse: `src/stitch/api/courses.ts`

- [ ] **Step 1: Write failing recent-learning tests**

Define a versioned local record containing only `courseId`, `lastRoute`, `visitedAt`. Assert deduplication by course, descending real timestamp order, maximum five entries, removal of courses no longer returned by `listCourses`, and allowed student route sanitization.

- [ ] **Step 2: Run the test and verify RED**

```powershell
npm test -- --test-name-pattern="recent learning"
```

- [ ] **Step 3: Copy the current course-card presentation into a student page**

Reuse `listCourses`, `backendCourseToSummary`, course-card presentation helpers and shared loading/error components. Remove create/edit/manage actions and any random progress or fabricated study time. Primary card action is “进入学习” and navigates to `#student-ai?course_id=...`.

- [ ] **Step 4: Add real search, empty and failure states**

Search only title/description. If no courses, explain that the student has not joined a course; do not show sample cards. “最近学习” appears only when valid records exist.

- [ ] **Step 5: Run focused tests and build**

```powershell
npm test -- --test-name-pattern="recent learning|course card"
npm run build
```

- [ ] **Step 6: Commit Task 6**

```powershell
git add -- src/stitch/student/pages/StudentHome.tsx src/stitch/student/pages/studentRecentLearning.ts src/stitch/student/pages/studentRecentLearning.test.ts src/stitch/student/styles/studentHome.css
git commit -m "feat: build student learning home"
```

---

### Task 7: Move the Generation Core to Shared Code and Load Role Catalogs

**Files:**
- Move: `src/components/teacher/generation/` → `src/components/generation/`
- Create: `src/stitch/api/generationTools.ts`
- Create: `src/stitch/shared/generation/generationCatalog.ts`
- Create: `src/stitch/shared/generation/generationCatalog.test.ts`
- Modify: `src/components/generation/GenerationFactory.tsx`
- Modify: `src/components/generation/generationRegistry.ts`
- Modify: `src/components/generation/useGenerationSubmission.ts`
- Modify: `src/components/teacher/StudioPanel.tsx`
- Modify: imports in all generation tests and pages

**Interfaces:**

```ts
export type GenerationToolId =
  | "report" | "ppt" | "mind_map" | "quiz" | "classroom"
  | "lesson_plan" | "blog" | "flashcard" | "game";

export type GenerationFactoryProps = {
  courseId?: string;
  allowedTools: readonly GenerationToolId[];
  resultHref: (material: { courseId?: string; materialId?: string }) => string;
  sourceLibraries: readonly ("personal" | "course")[];
};
```

- [ ] **Step 1: Update registry tests first**

Assert the neutral registry still contains nine definitions, but rendering requires an allowlist supplied by the authenticated server catalog. Assert unknown/duplicate tool IDs are ignored. Add exact teacher and student UI expectations matching the backend matrix.

- [ ] **Step 2: Run tests and verify RED**

```powershell
npm test -- --test-name-pattern="generation registry|generation catalog|generation factory"
```

- [ ] **Step 3: Move, do not duplicate, stable generation internals**

Use `git mv` for definitions, forms, source selector, submission hook, job presentation and CSS. Update imports mechanically. Keep endpoint payloads and task recovery behavior unchanged.

- [ ] **Step 4: Parameterize role-specific presentation**

Remove direct `buildTeacherCourseHash` and teacher-store dependencies from the neutral factory. Inject result routing and selected source IDs. Load both personal and course document lists through shared API clients, preserving owner/source validation server-side.

- [ ] **Step 5: Make teacher UI consume the server teacher catalog**

Teacher StudioPanel should now show seven tools and must no longer offer flashcards or classroom games. Keep lesson plan and teaching blog. A catalog failure renders a retryable error, not the unfiltered nine-tool registry.

- [ ] **Step 6: Run focused tests, lint and build**

```powershell
npm test -- --test-name-pattern="generation|studio panel"
npm run lint
npm run build
```

- [ ] **Step 7: Commit Task 7**

```powershell
git add -A -- src/components/generation src/components/teacher/generation src/components/teacher/StudioPanel.tsx src/stitch/api/generationTools.ts src/stitch/shared/generation
git commit -m "refactor: share the role-scoped generation core"
```

---

### Task 8: Build Student AI Q&A with Deep Research and Student Tools

**Files:**
- Create: `src/stitch/student/pages/StudentAIWorkspace.tsx`
- Create: `src/components/student/SourcePanel.tsx`
- Create: `src/components/student/ChatPanel.tsx`
- Create: `src/components/student/StudentStudioPanel.tsx`
- Create: `src/stitch/student/tools/StudentGenerationFactory.tsx`
- Create: `src/stitch/student/styles/studentAIWorkspace.css`
- Reuse: shared chat API, RAG, citation, job and generation modules
- Reference while copying: `src/stitch/pages/AIWorkspace.tsx`, `src/components/teacher/SourcePanel.tsx`, `src/components/teacher/ChatPanel.tsx`

- [ ] **Step 1: Add source-panel contract tests**

Test exported pure action derivation rather than brittle source text. For student course library, allowed actions are select/preview only. For own personal library, allowed actions include upload/rename/delete/retry/select. Assert `add_to_course`, course upload, course delete, reindex and graph-association actions are absent.

- [ ] **Step 2: Add workspace layout and tool tests**

Assert the page has three regions, personal/course library tabs, deep-research input in the left panel, chat/RAG/Web controls in the center, and exactly the seven student tools on the right. Deep research must not appear as a tool or navigation item.

- [ ] **Step 3: Run tests and verify RED**

```powershell
npm test -- --test-name-pattern="student source|student ai workspace|student generation"
```

- [ ] **Step 4: Copy the presentation layer and remove course writes**

Copy current visible interaction and responsive behavior into student-owned files. Route personal uploads and research persistence through `/api/personal-knowledge`; route course reads through existing course APIs. Preserve citation rendering, selected-document state, Web/RAG toggles, job progress and error feedback.

- [ ] **Step 5: Connect the shared generation factory**

Load `GET /api/chat/v2/generation/tools`; pass only returned IDs to `StudentGenerationFactory`; result links go to `#student-resources?space=mine` and keep `course_id` only as optional context.

- [ ] **Step 6: Verify responsive behavior and build**

At 1440px show three columns. At 1024/1280px use the existing collapsible source/tool panels without horizontal page overflow. Run:

```powershell
npm test -- --test-name-pattern="student source|student ai workspace|student generation"
npm run lint
npm run build
```

- [ ] **Step 7: Commit Task 8**

```powershell
git add -- src/stitch/student/pages/StudentAIWorkspace.tsx src/stitch/student/tools/StudentGenerationFactory.tsx src/stitch/student/styles/studentAIWorkspace.css src/components/student/SourcePanel.tsx src/components/student/ChatPanel.tsx src/components/student/StudentStudioPanel.tsx
git commit -m "feat: build student ai question workspace"
```

---

### Task 9: Build Read-Only Course Knowledge and Personal Knowledge Pages

**Files:**
- Create: `src/stitch/student/pages/StudentCourseKnowledge.tsx`
- Create: `src/stitch/student/pages/StudentPersonalKnowledge.tsx`
- Create: `src/stitch/student/pages/studentKnowledgeActions.ts`
- Create: `src/stitch/student/pages/studentKnowledgeActions.test.ts`
- Create: `src/stitch/api/personalKnowledge.ts`
- Create: `src/stitch/student/styles/studentKnowledge.css`
- Reuse: `src/stitch/course/knowledge/*`, shared document preview and graph canvas

- [ ] **Step 1: Write failing action-policy tests**

For course documents/nodes, allow search, select, preview, expand/collapse, pan/zoom and jump-to-AI; deny upload, rename, delete, retry/reindex, attach-to-node, save graph and textbook import. For personal documents owned by current user, allow upload, preview, rename, delete, retry and jump-to-AI; deny add-to-course.

- [ ] **Step 2: Run tests and verify RED**

```powershell
npm test -- --test-name-pattern="student knowledge actions"
```

- [ ] **Step 3: Build the course knowledge wrapper**

Copy the current two-view page shell and reuse neutral graph/document renderers. Route `view=structure|documents` through `studentRoutes`. Do not merely disable write buttons; do not render them. Jump-to-AI must include current `course_id` and optional knowledge-node context.

- [ ] **Step 4: Build the global personal knowledge page**

Use `/api/personal-knowledge/documents`; do not require or silently pick a current course. Implement real upload/index-state/preview/rename/delete/retry and empty/error states. Do not duplicate the deep-research entry here.

- [ ] **Step 5: Run focused frontend and backend tests**

```powershell
npm test -- --test-name-pattern="student knowledge|knowledge graph|knowledge document"
python -m pytest api/src/tests/test_personal_knowledge_api.py api/src/tests/test_course_route_authorization.py -q
npm run build
```

- [ ] **Step 6: Commit Task 9**

```powershell
git add -- src/stitch/student/pages/StudentCourseKnowledge.tsx src/stitch/student/pages/StudentPersonalKnowledge.tsx src/stitch/student/pages/studentKnowledgeActions.ts src/stitch/student/pages/studentKnowledgeActions.test.ts src/stitch/api/personalKnowledge.ts src/stitch/student/styles/studentKnowledge.css
git commit -m "feat: add student knowledge spaces"
```

---

### Task 10: Build Student Resource Management and AI Classroom Pages

**Files:**
- Create: `src/stitch/student/pages/StudentResources.tsx`
- Create: `src/stitch/student/pages/StudentClassroom.tsx`
- Create: `src/stitch/student/pages/studentResourceActions.ts`
- Create: `src/stitch/student/pages/studentResourceActions.test.ts`
- Create: `src/stitch/student/styles/studentResources.css`
- Create: `src/stitch/student/styles/studentClassroom.css`
- Reuse: `src/stitch/pages/courseMaterialPreviewData.ts`, resource preview adapters, `src/stitch/pages/ClassroomPlayer.tsx`, OpenMAIC renderer/player

- [ ] **Step 1: Write failing space/action tests**

Assert personal resources allow preview/download/rename/delete/regenerate and never publish/withdraw. Course shared resources allow preview and permitted download only. Assert `space=mine|course` changes the API query and no combined/all mode exists. Apply the same rules to AI classrooms, with create available only in “我的AI课堂”.

- [ ] **Step 2: Run tests and verify RED**

```powershell
npm test -- --test-name-pattern="student resource|student classroom"
```

- [ ] **Step 3: Copy and simplify the current resource page**

Use tabs “个人生成/课程共享”, existing previews and material actions. Course shared cards must display publication metadata and no mutation menu. Regenerate opens the allowed student generator with source/config provenance where available.

- [ ] **Step 4: Copy and simplify the current classroom page**

Use tabs “我的AI课堂/课程AI课堂”. Reuse the current generation form, task polling, player and video artifact behavior. Do not duplicate the renderer. A student-created classroom must appear in personal resources as the same material ID; a published teacher classroom must appear only in the course tab.

- [ ] **Step 5: Run focused tests and build**

```powershell
npm test -- --test-name-pattern="student resource|student classroom|course material preview|classroom"
npm run lint
npm run build
```

- [ ] **Step 6: Commit Task 10**

```powershell
git add -- src/stitch/student/pages/StudentResources.tsx src/stitch/student/pages/StudentClassroom.tsx src/stitch/student/pages/studentResourceActions.ts src/stitch/student/pages/studentResourceActions.test.ts src/stitch/student/styles/studentResources.css src/stitch/student/styles/studentClassroom.css
git commit -m "feat: add student resources and ai classrooms"
```

---

### Task 11: Integrate Role Routing and Remove the Legacy Student Interface

**Files:**
- Create: `src/stitch/student/StudentApp.tsx`
- Modify: `src/stitch/App.tsx`
- Modify: `src/stitch/shared.tsx`
- Modify: `src/stitch/authSession.ts` if a typed role helper is needed
- Delete after checks: `src/pages/student/`
- Delete/replace after checks: legacy `src/components/student/`
- Modify: `src/routes/AppRoutes.tsx` to remove legacy student routes, or delete it only if `rg` proves it is unused
- Create: `tests/e2e/student-workspace-foundation.spec.ts`

- [ ] **Step 1: Write failing role-routing tests**

Assert student login/no hash goes to `#student-home`; teacher/admin keep `#home`; student entering `#home`, `#ai`, `#edit`, `#settings` or teacher course routes is redirected before the teacher page mounts; teacher entering `#student-*` returns to teacher home. Preserve dev-only render routes only under their existing explicit fixture guard.

- [ ] **Step 2: Write the E2E happy path and negative path**

Happy path: login as student → learning home → enter course → ask with course material → open personal KB → create one allowed personal resource → see it in personal resources → view published course resource → play published course AI classroom.

Negative path: no course settings/detail, no course KB write actions, no publish action, no lesson plan/blog; direct forbidden API calls return `403`; another student's private IDs return `404`.

- [ ] **Step 3: Run tests and verify RED**

```powershell
npm test -- --test-name-pattern="role route|student"
npm run test:e2e -- tests/e2e/student-workspace-foundation.spec.ts
```

- [ ] **Step 4: Mount `StudentApp` behind authenticated role resolution**

Do not add all student routes to the teacher `pages` array. `App.tsx` resolves the verified role first, then delegates to teacher or student route tables. Keep authentication and global job manager shared.

- [ ] **Step 5: Prove zero references before deleting old UI**

Run:

```powershell
rg -n "src/pages/student|pages/student|components/student|AppRoutes" src tests
```

Classify every hit. Update new intentional `components/student` imports to the new files; remove all imports of the legacy pages. Delete only files with zero live imports. Do not delete shared preview/rendering code merely because it was first used by the old student UI.

- [ ] **Step 6: Run the full frontend gate**

```powershell
npm test
npm run lint
npm run build
npm run test:e2e -- tests/e2e/student-workspace-foundation.spec.ts tests/e2e/course-shell.spec.ts tests/e2e/resources-and-classroom.spec.ts
```

- [ ] **Step 7: Run the backend permission and ownership gate**

```powershell
python -m pytest api/src/tests/services/test_personal_tool_access.py api/src/tests/chat/test_personal_generation_authorization.py api/src/tests/test_personal_knowledge_api.py api/src/tests/test_student_classroom_permissions.py api/src/tests/test_course_access.py api/src/tests/test_course_route_authorization.py api/src/tests/core/test_course_material_permissions.py api/src/tests/services/test_material_publication_service.py -q
```

- [ ] **Step 8: Check diff hygiene and forbidden dependencies**

```powershell
rg -n "components/teacher|pages/teacher|stitch/pages/(AIWorkspace|HomeDashboard|CourseKnowledge|CourseResources|ClassroomStudio)" src/stitch/student src/components/student
git diff --check
git status --short
```

Expected: no student-to-teacher imports, no whitespace errors, and only planned files changed.

- [ ] **Step 9: Commit Task 11**

```powershell
git add -A -- src/stitch/student src/stitch/App.tsx src/stitch/shared.tsx src/stitch/authSession.ts src/pages/student src/components/student src/routes/AppRoutes.tsx tests/e2e/student-workspace-foundation.spec.ts
git commit -m "feat: launch the isolated student workspace"
```

---

### Task 12: Execute and Record Final Acceptance

**Files:**
- Modify: `docs/acceptance/2026-08-09-student-workspace-foundation-acceptance.md`
- Create: `docs/acceptance/screenshots/student-workspace-foundation/` only for captured evidence

- [ ] **Step 1: Execute every automated command in the acceptance document**

Record exact pass/fail counts and timestamps. Do not write “通过” from expectation alone.

- [ ] **Step 2: Execute the teacher/student cross-account manual matrix**

Use at least two students and one teacher in the same course. Confirm personal documents/resources/tasks are mutually invisible, course snapshots are visible, and direct forbidden HTTP requests are rejected.

- [ ] **Step 3: Capture only meaningful UI evidence**

Capture 1440px and 1024px for learning home, AI问答 three-panel/collapsed layouts, course knowledge read-only state, personal knowledge, resource dual spaces and classroom dual spaces. Do not create screenshots for empty placeholders.

- [ ] **Step 4: Fill the acceptance conclusion**

Mark the milestone accepted only when every P0 blocking item passes. List any non-blocking issue with owner and follow-up, without silently lowering the criteria.

- [ ] **Step 5: Commit the verified acceptance record**

```powershell
git add -- docs/acceptance/2026-08-09-student-workspace-foundation-acceptance.md docs/acceptance/screenshots/student-workspace-foundation
git commit -m "test: record student workspace foundation acceptance"
```

---

## Plan Self-Review

- Scope coverage: six student pages, role routing, personal generation, course read-only content, personal knowledge, AI课堂, resources and legacy cleanup are all assigned to tasks.
- Permission coverage: system role, course read capability and personal ownership are tested independently; no task grants course write/generate to `viewer`.
- Reuse coverage: shared generation flow, API clients, graph canvas, previews, jobs and classroom player are preserved; only role-specific presentation is copied.
- Regression coverage: teacher routes, teacher tool catalog, course permissions, publication service and classroom player all retain focused regression commands.
- Placeholder audit: no product TODO, fake card, fake metric or future navigation entry is introduced.
- Type consistency: `mind_map` is the public tool ID and maps explicitly to the existing `graph` backend endpoint; `space` is consistently `mine|course`; output scope is consistently `personal`.
- Deletion safety: old student UI is deleted only after new routes pass and `rg` proves no live references.

