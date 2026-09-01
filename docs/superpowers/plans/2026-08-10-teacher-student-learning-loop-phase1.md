# Teacher–Student Learning Loop Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one complete teacher–student interaction loop where a teacher publishes a learning task from shared course resources, a student records progress, the teacher sees feedback, and both Agents receive role-appropriate structured learning context.

**Architecture:** Add a course-scoped learning domain backed by a transactional SQLite store for the current deployment, isolated behind a service interface that can later receive a PostgreSQL implementation. Learning tasks reference existing published course materials without copying them. Student actions append idempotent learning events and deterministically update task progress; Agent context is assembled from the same store, with teacher and student projections separated by role.

**Tech Stack:** FastAPI, Pydantic v2, SQLite/WAL, existing course authorization dependencies, pytest, React 19, TypeScript, Vite, existing hash router, LangGraph/ReAct and FastChatRuntime.

---

## Scope and integration contract

This plan does not implement course creation, join codes, enrollment, or member management. It consumes these existing/upstream contracts:

- a stable `course_id` in the URL and API request;
- `require_course_read` for enrolled users;
- `require_course_edit` for owners/editors;
- `CoursePrincipal.user_id`, `system_role`, and `course_role`;
- published course materials exposed by `/api/courses/{course_id}/materials?space=course`.

Before implementation, rebase the feature worktree on the branch containing the course-creation work. If that work changes only how a user joins a course, no learning-domain code should change. If it changes course membership dependency names, adapt only `app/api/learning.py`.

Phase 1 intentionally excludes numeric knowledge mastery, vector memory, private-chat summarization, teacher grading, notifications, groups, and deadlines with automated penalties. Those belong to subsequent plans after this vertical slice produces reliable events.

## File structure

### Backend files to create

- `backend/src/app/schemas/learning.py`: public request/response contracts.
- `backend/src/app/learning/models.py`: internal immutable records and enums.
- `backend/src/app/learning/store.py`: SQLite schema and transactional queries.
- `backend/src/app/learning/service.py`: task, event, progress, and aggregate business rules.
- `backend/src/app/learning/context_reader.py`: role-specific Agent memory projections.
- `backend/src/app/learning/__init__.py`: package exports.
- `backend/src/app/api/learning.py`: authenticated course-scoped HTTP routes.
- `backend/src/tests/learning/test_learning_store.py`: persistence and idempotency tests.
- `backend/src/tests/learning/test_learning_service.py`: business rule tests.
- `backend/src/tests/learning/test_learning_api.py`: authorization and response tests.
- `backend/src/tests/chat/test_learning_context_injection.py`: Agent context tests.

### Backend files to modify

- `backend/src/core/config.py`: add `LEARNING_DB_PATH`.
- `backend/src/app/bootstrap.py`: register the learning router.
- `backend/src/app/chat/domain/conversation_snapshot.py`: add `learning_context`.
- `backend/src/app/chat/orchestrator/context_builder.py`: load role-appropriate learning context.
- `backend/src/app/chat/application/route_chat_service.py`: inject the production context reader.
- `backend/src/app/chat/runtime/fast_chat_runtime.py`: include structured learning context in the system prompt.
- `backend/src/app/chat/runtime/react_agent.py`: include the same context in ReAct messages.

### Frontend files to create

- `frontend/src/stitch/api/learning.ts`: typed learning API client.
- `frontend/src/stitch/pages/CourseLearning.tsx`: shared route entry that selects teacher/student presentation.
- `frontend/src/stitch/pages/CourseLearning.css`: learning task and progress styling.
- `frontend/src/stitch/pages/courseLearningPresentation.ts`: pure formatting and permission helpers.
- `frontend/src/stitch/pages/courseLearningPresentation.test.ts`: pure helper tests.
- `frontend/src/stitch/pages/CourseLearning.test.tsx`: component interaction tests.

### Frontend files to modify

- `frontend/src/stitch/api/types.ts`: add learning API types.
- `frontend/src/stitch/shared.tsx`: register `learning` route.
- `frontend/src/stitch/teacherRoutes.ts`: add teacher learning route.
- `frontend/src/stitch/course/courseNavigation.ts`: add course learning navigation item.
- `frontend/src/stitch/student/routes/studentRoutes.ts`: add `student-learning` route.
- `frontend/src/stitch/student/shell/studentNavigation.ts`: add 学习任务 item.
- `frontend/src/stitch/student/StudentApp.tsx`: map student route to the shared page.
- `frontend/src/stitch/shared/routes/roleCourseRouteResolver.ts`: map teacher and student learning routes.
- `frontend/src/stitch/App.tsx`: map the teacher route to the shared page.
- Corresponding existing route/navigation tests.

## Task 1: Define and persist the learning domain

**Files:**

- Create: `backend/src/app/learning/models.py`
- Create: `backend/src/app/learning/store.py`
- Create: `backend/src/app/learning/__init__.py`
- Modify: `backend/src/core/config.py`
- Test: `backend/src/tests/learning/test_learning_store.py`

- [ ] **Step 1: Write the failing store tests**

```python
from app.learning.models import LearningEventRecord, LearningTaskRecord
from app.learning.store import LearningStore


def test_store_persists_published_task_and_student_progress(tmp_path):
    store = LearningStore(tmp_path / "learning.db")
    task = LearningTaskRecord.new(
        course_id="course-1",
        title="阅读快速排序材料",
        instructions="阅读后标记完成",
        created_by="teacher-1",
        resource_refs=[{"material_type": "report", "material_id": "report-1"}],
    )
    store.create_task(task)
    store.publish_task(task.task_id, course_id="course-1", published_by="teacher-1")
    event = LearningEventRecord.new(
        event_id="evt-1",
        course_id="course-1",
        task_id=task.task_id,
        student_id="student-1",
        event_type="completed",
        progress_percent=100,
    )

    first = store.record_event(event)
    second = store.record_event(event)

    assert first.created is True
    assert second.created is False
    assert store.get_progress(task.task_id, "student-1").status == "completed"
    assert store.get_progress(task.task_id, "student-1").progress_percent == 100
```

- [ ] **Step 2: Run the test and verify the missing package failure**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_store.py
```

Expected: collection fails with `ModuleNotFoundError: No module named 'app.learning'`.

- [ ] **Step 3: Implement immutable records and enums**

```python
# app/learning/models.py
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

TaskStatus = Literal["draft", "published", "closed"]
ProgressStatus = Literal["not_started", "in_progress", "completed"]
LearningEventType = Literal["started", "resource_opened", "progress_updated", "completed"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LearningTaskRecord:
    task_id: str
    course_id: str
    title: str
    instructions: str
    created_by: str
    resource_refs: list[dict[str, str]] = field(default_factory=list)
    knowledge_point_ids: list[str] = field(default_factory=list)
    status: TaskStatus = "draft"
    created_at: str = field(default_factory=utc_now)
    published_at: str | None = None

    @classmethod
    def new(cls, **values):
        return cls(task_id=f"lt_{uuid4().hex}", **values)


@dataclass(frozen=True)
class LearningEventRecord:
    event_id: str
    course_id: str
    task_id: str
    student_id: str
    event_type: LearningEventType
    progress_percent: int
    resource_ref: dict[str, str] | None = None
    occurred_at: str = field(default_factory=utc_now)

    @classmethod
    def new(cls, **values):
        return cls(**values)


@dataclass(frozen=True)
class TaskProgressRecord:
    task_id: str
    course_id: str
    student_id: str
    status: ProgressStatus
    progress_percent: int
    started_at: str | None
    completed_at: str | None
    updated_at: str


@dataclass(frozen=True)
class EventWriteResult:
    created: bool
    progress: TaskProgressRecord
```

- [ ] **Step 4: Implement the SQLite store**

Create `LearningStore` with one connection per store, `check_same_thread=False`, an `RLock`, WAL mode, foreign keys, and these tables:

```sql
CREATE TABLE IF NOT EXISTS learning_tasks (
  task_id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL,
  title TEXT NOT NULL,
  instructions TEXT NOT NULL,
  created_by TEXT NOT NULL,
  resource_refs_json TEXT NOT NULL,
  knowledge_point_ids_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  published_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_learning_tasks_course_status
ON learning_tasks(course_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS learning_events (
  event_id TEXT PRIMARY KEY,
  course_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  progress_percent INTEGER NOT NULL,
  resource_ref_json TEXT,
  occurred_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES learning_tasks(task_id)
);

CREATE TABLE IF NOT EXISTS task_progress (
  task_id TEXT NOT NULL,
  course_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  status TEXT NOT NULL,
  progress_percent INTEGER NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(task_id, student_id),
  FOREIGN KEY(task_id) REFERENCES learning_tasks(task_id)
);
```

`record_event()` must use `BEGIN IMMEDIATE`, `INSERT OR IGNORE`, and update progress only when the event insert succeeds. Progress is monotonic in Phase 1: `max(existing, incoming)`. A `completed` event forces 100 and `completed`; a positive non-completed event sets `in_progress`.

- [ ] **Step 5: Add the configured database path and package export**

```python
# core/config.py
LEARNING_DB_PATH = Path(
    os.getenv("LEARNING_DB_PATH", Path(__file__).resolve().parents[2] / "data" / "learning.db")
)

# app/learning/__init__.py
from .store import LearningStore

__all__ = ["LearningStore"]
```

- [ ] **Step 6: Run store tests**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_store.py
```

Expected: all store tests pass, including duplicate event idempotency, course filtering, restart persistence, and monotonic progress.

- [ ] **Step 7: Commit the learning store**

```powershell
git add backend/src/app/learning backend/src/core/config.py backend/src/tests/learning/test_learning_store.py
git commit -m "feat: add durable course learning store"
```

## Task 2: Add learning business rules and public schemas

**Files:**

- Create: `backend/src/app/schemas/learning.py`
- Create: `backend/src/app/learning/service.py`
- Test: `backend/src/tests/learning/test_learning_service.py`

- [ ] **Step 1: Write failing service tests**

```python
def test_student_cannot_record_event_for_draft_task(service):
    task = service.create_task(
        course_id="course-1",
        teacher_id="teacher-1",
        title="任务",
        instructions="完成材料",
        resource_refs=[],
        knowledge_point_ids=[],
    )

    with pytest.raises(LearningRuleError) as error:
        service.record_student_event(
            course_id="course-1",
            task_id=task.task_id,
            student_id="student-1",
            event_id="evt-1",
            event_type="started",
            progress_percent=1,
            resource_ref=None,
        )

    assert error.value.code == "TASK_NOT_PUBLISHED"


def test_task_rejects_private_or_missing_material(service, material_lookup):
    material_lookup.return_value = None
    with pytest.raises(LearningRuleError) as error:
        service.create_task(
            course_id="course-1",
            teacher_id="teacher-1",
            title="任务",
            instructions="完成材料",
            resource_refs=[{"material_type": "report", "material_id": "missing"}],
            knowledge_point_ids=[],
        )
    assert error.value.code == "COURSE_RESOURCE_NOT_FOUND"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_service.py
```

Expected: imports fail because `LearningService` and schemas do not exist.

- [ ] **Step 3: Add Pydantic contracts**

Define the following exact public models in `app/schemas/learning.py`:

```python
class LearningResourceRef(BaseModel):
    material_type: str = Field(min_length=1, max_length=64)
    material_id: str = Field(min_length=1, max_length=160)

class LearningTaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=4000)
    resource_refs: list[LearningResourceRef] = Field(default_factory=list, max_length=20)
    knowledge_point_ids: list[str] = Field(default_factory=list, max_length=50)

class LearningTaskResponse(BaseModel):
    task_id: str
    course_id: str
    title: str
    instructions: str
    resource_refs: list[LearningResourceRef]
    knowledge_point_ids: list[str]
    status: Literal["draft", "published", "closed"]
    created_by: str
    created_at: str
    published_at: str | None = None
    my_progress: "TaskProgressResponse | None" = None

class LearningEventRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=160)
    event_type: Literal["started", "resource_opened", "progress_updated", "completed"]
    progress_percent: int = Field(ge=0, le=100)
    resource_ref: LearningResourceRef | None = None

class TaskProgressResponse(BaseModel):
    task_id: str
    student_id: str
    status: Literal["not_started", "in_progress", "completed"]
    progress_percent: int
    started_at: str | None
    completed_at: str | None
    updated_at: str | None

class CourseLearningSummaryResponse(BaseModel):
    course_id: str
    task_id: str
    enrolled_students: int
    started_students: int
    completed_students: int
    completion_rate: float
    progress: list[TaskProgressResponse]
```

- [ ] **Step 4: Implement `LearningService`**

The service accepts a `LearningStore`, a material lookup callable, and a membership-list callable. It must:

- validate that referenced materials exist in the same course and have `visibility == "course"`;
- publish only tasks in the same course;
- return only published tasks to students;
- reject student events for draft/closed tasks;
- reject resource events whose reference is not attached to the task;
- compute `completion_rate = completed_students / enrolled_students`, returning `0.0` for an empty course;
- include enrolled viewers with `not_started` progress in teacher summaries.
- expose `get_student_agent_context(course_id, student_id, limit)` returning `{projection: "student", pending_tasks, completed_tasks}` with only that student's progress;
- expose `get_teacher_agent_context(course_id, teacher_id, limit)` returning `{projection: "teacher", task_summaries}` after verifying that `teacher_id` is an owner/editor through the injected membership lookup.

Use a typed `LearningRuleError(code, message)` and never expose raw SQLite errors through the API.

- [ ] **Step 5: Run service tests**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_service.py
```

Expected: all rule, material-reference, publication, progress, and aggregate tests pass.

- [ ] **Step 6: Commit the service layer**

```powershell
git add backend/src/app/schemas/learning.py backend/src/app/learning/service.py backend/src/tests/learning/test_learning_service.py
git commit -m "feat: add course learning task rules"
```

## Task 3: Expose authorized learning APIs

**Files:**

- Create: `backend/src/app/api/learning.py`
- Modify: `backend/src/app/bootstrap.py`
- Test: `backend/src/tests/learning/test_learning_api.py`

- [ ] **Step 1: Write API authorization tests**

```python
def test_teacher_publishes_and_student_records_completion(client, teacher_token, student_token):
    created = client.post(
        "/api/courses/course-1/learning/tasks",
        headers=teacher_token,
        json={"title": "学习快速排序", "instructions": "阅读材料", "resource_refs": [], "knowledge_point_ids": []},
    )
    assert created.status_code == 201
    task_id = created.json()["task_id"]

    assert client.post(
        f"/api/courses/course-1/learning/tasks/{task_id}/publish",
        headers=teacher_token,
    ).status_code == 200

    completed = client.post(
        f"/api/courses/course-1/learning/tasks/{task_id}/events",
        headers=student_token,
        json={"event_id": "evt-complete-1", "event_type": "completed", "progress_percent": 100},
    )
    assert completed.status_code == 200
    assert completed.json()["progress_percent"] == 100

    summary = client.get(
        f"/api/courses/course-1/learning/tasks/{task_id}/progress",
        headers=teacher_token,
    )
    assert summary.status_code == 200
    assert summary.json()["completed_students"] == 1


def test_student_cannot_create_task(client, student_token):
    response = client.post(
        "/api/courses/course-1/learning/tasks",
        headers=student_token,
        json={"title": "越权任务", "resource_refs": [], "knowledge_point_ids": []},
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Run the tests and verify 404 failures**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_api.py
```

Expected: route calls return 404 because the router is not registered.

- [ ] **Step 3: Implement the router**

Create an `APIRouter(prefix="/api/courses/{course_id}/learning", tags=["learning"])` with:

```text
POST   /tasks                         teacher/editor creates draft
GET    /tasks                         teacher gets all; student gets published plus my_progress
POST   /tasks/{task_id}/publish       teacher/editor publishes
POST   /tasks/{task_id}/events        enrolled student appends own event
GET    /tasks/{task_id}/progress      teacher/editor gets course aggregate
```

Use `require_course_edit` for create, publish, and aggregate. Use `require_course_read` for list and events, then require `principal.system_role == "student"` on event writes. Convert `LearningRuleError` codes to stable HTTP responses:

```python
STATUS_BY_CODE = {
    "TASK_NOT_FOUND": 404,
    "COURSE_RESOURCE_NOT_FOUND": 422,
    "TASK_NOT_PUBLISHED": 409,
    "TASK_CLOSED": 409,
    "RESOURCE_NOT_ATTACHED": 422,
}
```

- [ ] **Step 4: Register the router**

In `app/bootstrap.py`, lazily import `app.api.learning.router` beside the courses router and call `app.include_router(learning_router)` immediately after `courses_router`.

- [ ] **Step 5: Run API and existing authorization tests**

Run:

```powershell
python -m pytest -q tests/learning/test_learning_api.py tests/test_course_route_authorization.py tests/test_course_access.py
```

Expected: all tests pass; a non-member receives 403, a student cannot create/publish/view aggregates, and a teacher cannot write a student event.

- [ ] **Step 6: Commit the API**

```powershell
git add backend/src/app/api/learning.py backend/src/app/bootstrap.py backend/src/tests/learning/test_learning_api.py
git commit -m "feat: expose authorized course learning APIs"
```

## Task 4: Add the typed frontend learning client

**Files:**

- Create: `frontend/src/stitch/api/learning.ts`
- Modify: `frontend/src/stitch/api/types.ts`
- Test: `frontend/src/stitch/pages/courseLearningPresentation.test.ts`
- Create: `frontend/src/stitch/pages/courseLearningPresentation.ts`

- [ ] **Step 1: Add pure presentation tests**

```typescript
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { getLearningTaskPrimaryAction, getProgressLabel } from "./courseLearningPresentation";

describe("course learning presentation", () => {
  it("shows publish to teachers for a draft", () => {
    assert.equal(getLearningTaskPrimaryAction("teacher", { status: "draft", my_progress: null }), "publish");
  });
  it("shows continue to students for an in-progress task", () => {
    assert.equal(getLearningTaskPrimaryAction("student", { status: "published", my_progress: { status: "in_progress", progress_percent: 40 } }), "continue");
    assert.equal(getProgressLabel(40), "已完成 40%");
  });
});
```

- [ ] **Step 2: Run the helper test and verify missing-module failure**

Run:

```powershell
npx tsx --test src/stitch/pages/courseLearningPresentation.test.ts
```

Expected: test fails because the helper file does not exist.

- [ ] **Step 3: Add exact frontend types**

Add `LearningResourceRef`, `LearningTask`, `TaskProgress`, `CourseLearningSummary`, `LearningTaskCreatePayload`, and `LearningEventPayload` to `stitch/api/types.ts`, mirroring the backend field names exactly.

- [ ] **Step 4: Implement API functions**

```typescript
export const listLearningTasks = (courseId: string) =>
  apiRequest<LearningTask[]>(`/api/courses/${courseId}/learning/tasks`);

export const createLearningTask = (courseId: string, payload: LearningTaskCreatePayload) =>
  apiRequest<LearningTask>(`/api/courses/${courseId}/learning/tasks`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const publishLearningTask = (courseId: string, taskId: string) =>
  apiRequest<LearningTask>(`/api/courses/${courseId}/learning/tasks/${taskId}/publish`, { method: "POST" });

export const recordLearningEvent = (courseId: string, taskId: string, payload: LearningEventPayload) =>
  apiRequest<TaskProgress>(`/api/courses/${courseId}/learning/tasks/${taskId}/events`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getLearningTaskProgress = (courseId: string, taskId: string) =>
  apiRequest<CourseLearningSummary>(`/api/courses/${courseId}/learning/tasks/${taskId}/progress`);
```

- [ ] **Step 5: Implement and test presentation helpers**

`getLearningTaskPrimaryAction` returns `publish`, `start`, `continue`, `completed`, or `none`. `getProgressLabel` clamps to 0–100 and returns `未开始`, `已完成`, or `已完成 N%`.

Run:

```powershell
npx tsx --test src/stitch/pages/courseLearningPresentation.test.ts
```

Expected: all helper tests pass.

- [ ] **Step 6: Commit the frontend client**

```powershell
git add frontend/src/stitch/api/learning.ts frontend/src/stitch/api/types.ts frontend/src/stitch/pages/courseLearningPresentation.ts frontend/src/stitch/pages/courseLearningPresentation.test.ts
git commit -m "feat: add typed learning interaction client"
```

## Task 5: Build the teacher and student learning workspace

**Files:**

- Create: `frontend/src/stitch/pages/CourseLearning.tsx`
- Create: `frontend/src/stitch/pages/CourseLearning.css`
- Create: `frontend/src/stitch/pages/CourseLearning.test.tsx`
- Modify: route, navigation, and page-map files listed in the file structure
- Modify: corresponding existing route/navigation tests

- [ ] **Step 1: Extend route tests first**

Add assertions that:

```typescript
assert.equal(buildTeacherCourseHash("learning", "course-1"), "#learning?course_id=course-1");
assert.equal(buildStudentHash("student-learning", { courseId: "course-1" }), "#student-learning?course_id=course-1");
assert.equal(buildRoleCourseHash("student", "learning", "course-1"), "#student-learning?course_id=course-1");
```

Also assert that course navigation contains `{ id: "learning", label: "学习任务" }` for owner, editor, and viewer roles.

- [ ] **Step 2: Run route tests and verify type/expectation failures**

Run:

```powershell
npx tsx --test src/stitch/teacherRoutes.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/course/courseNavigation.test.ts src/stitch/shared/routes/roleCourseRouteResolver.test.ts
```

Expected: TypeScript compilation fails because the learning routes do not exist.

- [ ] **Step 3: Add the teacher and student route mappings**

Add `"learning"` to `TeacherCourseRoute`, `"student-learning"` to `StudentRoute`, and the role mapping. Add this shared course navigation item between course overview and AI workspace:

```typescript
{ id: "learning", label: "学习任务", icon: "fact_check", hrefRoute: "learning", routes: ["learning"] }
```

For the student shell, use:

```typescript
{ route: "student-learning", label: "学习任务", icon: "fact_check", requiresCourse: true }
```

- [ ] **Step 4: Write the failing component behavior test**

Mock the typed API client and assert:

- teacher sees `新建学习任务`, can choose only course-shared materials, creates a draft, and publishes it;
- student never sees create/publish controls;
- opening a student task records one `started` event with a stable event id for that click;
- pressing `标记完成` records a `completed` event and renders `已完成`;
- teacher selecting a published task loads aggregate progress.

- [ ] **Step 5: Implement `CourseLearningPage`**

Use `useAuthSession()` and `useCourseRoute()` to choose presentation. The teacher view contains:

- a task list with Draft/Published badges;
- a `新建学习任务` dialog;
- title, instructions, shared-resource multi-select, and knowledge point ID input;
- publish button;
- summary cards for enrolled, started, completed, completion rate;
- per-student progress rows.

The student view contains:

- published task cards only;
- instructions and linked course resources;
- progress bar;
- `开始学习`/`继续学习` and `标记完成` actions;
- an empty state explaining that resources remain browsable even when no task is assigned.

Do not copy material content into task state. Resource links must use existing material route builders with `space=course`, `material_type`, and `material_id`.

- [ ] **Step 6: Run component and route tests**

Run:

```powershell
npx tsx --test src/stitch/pages/CourseLearning.test.tsx src/stitch/teacherRoutes.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/course/courseNavigation.test.ts src/stitch/shared/routes/roleCourseRouteResolver.test.ts
```

Expected: all tests pass.

- [ ] **Step 7: Run the frontend quality gates**

Run:

```powershell
npm run lint
npm run build
```

Expected: both commands exit 0 with no TypeScript errors.

- [ ] **Step 8: Commit the dual-end UI**

```powershell
git add frontend/src/stitch
git commit -m "feat: add teacher student learning workspace"
```

## Task 6: Inject structured learning context into both Agents

**Files:**

- Create: `backend/src/app/learning/context_reader.py`
- Modify: `backend/src/app/chat/domain/conversation_snapshot.py`
- Modify: `backend/src/app/chat/orchestrator/context_builder.py`
- Modify: `backend/src/app/chat/application/route_chat_service.py`
- Modify: `backend/src/app/chat/runtime/fast_chat_runtime.py`
- Modify: `backend/src/app/chat/runtime/react_agent.py`
- Test: `backend/src/tests/chat/test_learning_context_injection.py`

- [ ] **Step 1: Write failing role-boundary tests**

```python
def test_student_context_contains_only_own_learning_state(reader):
    context = reader.read(user_id="student-1", course_id="course-1", actor_role="student")
    assert context["projection"] == "student"
    assert context["pending_tasks"][0]["title"] == "学习快速排序"
    assert "students" not in context


def test_teacher_context_contains_aggregate_not_private_conversations(reader):
    context = reader.read(user_id="teacher-1", course_id="course-1", actor_role="teacher")
    assert context["projection"] == "teacher"
    assert context["task_summaries"][0]["completed_students"] == 1
    serialized = json.dumps(context, ensure_ascii=False)
    assert "conversation" not in serialized
    assert "private" not in serialized
```

Add prompt-capture tests for FastChatRuntime and ReActAgent asserting the student prompt contains `【当前学习状态】` and never contains another student id.

- [ ] **Step 2: Run tests and verify missing-reader failure**

Run:

```powershell
python -m pytest -q tests/chat/test_learning_context_injection.py
```

Expected: import or assertion failures because no production learning context exists.

- [ ] **Step 3: Implement `LearningContextReader`**

The reader signature is:

```python
class LearningContextReader:
    def __init__(self, service: LearningService):
        self._service = service

    def read(self, *, user_id: str, course_id: str, actor_role: str) -> dict:
        if actor_role == "student":
            return self._service.get_student_agent_context(
                course_id=course_id,
                student_id=user_id,
                limit=10,
            )
        return self._service.get_teacher_agent_context(
            course_id=course_id,
            teacher_id=user_id,
            limit=10,
        )
```

Student projection returns up to 10 published tasks, own progress, attached resource references, and knowledge point IDs. Teacher projection returns up to 10 published tasks and aggregate counts only. It must not read conversation storage.

- [ ] **Step 4: Add learning context to snapshots**

Add `learning_context: dict = Field(default_factory=dict)` to `ConversationSnapshot`. Extend `ContextBuilder` with `learning_context_reader`; when `request.owner` and `request.course_id` exist, call it with `request.actor_role`. On any reader failure, use `{}` and allow chat to continue.

- [ ] **Step 5: Wire the production reader**

Create one process-level learning store/service factory in `app/learning/__init__.py` and pass `LearningContextReader` into `ContextBuilder` from `RouteChatService._build_chat_app_service`. Do not construct a SQLite connection per request.

- [ ] **Step 6: Render privacy-minimal Agent context**

Add one formatter shared by FastChatRuntime and ReActAgent:

```python
def build_learning_context_prompt(context: dict) -> str:
    if not context:
        return ""
    return (
        "【当前学习状态】\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        + "\n这些是系统记录的学习事实；不得补造未提供的完成情况、成绩或掌握度。"
    )
```

FastChatRuntime appends it to `system_content`; ReActAgent appends it as a second system message. Never put this context into the user message because it must not be treated as user-authored evidence.

- [ ] **Step 7: Run Agent and memory regression tests**

Run:

```powershell
python -m pytest -q tests/chat/test_learning_context_injection.py tests/chat/runtime/test_agent_three_layer_memory.py tests/chat/test_context_builder.py tests/chat/test_fast_chat_runtime.py
```

Expected: all tests pass and prompt-capture fixtures show role-separated structured context.

- [ ] **Step 8: Commit Agent learning context**

```powershell
git add backend/src/app/learning/context_reader.py backend/src/app/chat backend/src/tests/chat/test_learning_context_injection.py
git commit -m "feat: ground both agents in learning progress"
```

## Task 7: Fix current Agent working-memory restore precedence

**Files:**

- Modify: `backend/src/app/chat/runtime/react_agent.py`
- Test: `backend/src/tests/chat/runtime/test_agent_memory_restore.py`

- [ ] **Step 1: Write a failing two-turn restore test**

The test must run two `ReActAgent.run_stream()` calls in the same process. After turn 1 persists `agent_memory.working_memory.active_topic`, turn 2 must capture the messages sent to the model and assert that the memory system message contains the active topic. Run the same test after replacing the graph with a fresh graph instance to cover restart recovery.

- [ ] **Step 2: Run the test and verify the live-checkpoint precedence failure**

Run:

```powershell
python -m pytest -q tests/chat/runtime/test_agent_memory_restore.py
```

Expected before the fix: the same-process second turn does not contain the newly persisted active topic.

- [ ] **Step 3: Make `agent_memory` durable-authoritative**

Merge checkpoint and durable state by key category:

```python
durable_state = self.agent_run_store.load(
    conv_id,
    owner_user_id=username,
    course_id=course_id,
)
checkpoint_state = {**durable_state, **checkpoint_state}
if durable_state.get("agent_memory"):
    checkpoint_state["agent_memory"] = durable_state["agent_memory"]
```

After `update_agent_memory`, call `self._graph.update_state(config, {"agent_memory": values["agent_memory"]})` before saving the durable snapshot so both stores converge.

- [ ] **Step 4: Run restore and existing runtime tests**

Run:

```powershell
python -m pytest -q tests/chat/runtime/test_agent_memory_restore.py tests/chat/runtime/test_agent_run_persistence.py tests/chat/runtime/test_agent_three_layer_memory.py
```

Expected: all tests pass in same-process and restart scenarios.

- [ ] **Step 5: Commit the reliability fix**

```powershell
git add backend/src/app/chat/runtime/react_agent.py backend/src/tests/chat/runtime/test_agent_memory_restore.py
git commit -m "fix: restore latest agent working memory"
```

## Task 8: Run the vertical-slice acceptance suite

**Files:**

- Create: `backend/src/tests/learning/test_learning_loop_acceptance.py`
- Modify: `docs/superpowers/specs/2026-08-10-agent-memory-v2-design-cn.md` only if implementation evidence changes a documented decision

- [ ] **Step 1: Add a backend acceptance test**

The test must create one teacher and one enrolled student, create and publish a task, record `started` and `completed`, assert teacher aggregate completion, open a new student conversation, and capture the Agent prompt containing completed progress.

- [ ] **Step 2: Run focused backend tests**

Run:

```powershell
python -m pytest -q tests/learning tests/chat/test_learning_context_injection.py tests/chat/runtime/test_agent_memory_restore.py
```

Expected: all tests pass.

- [ ] **Step 3: Run full backend tests relevant to touched modules**

Run:

```powershell
python -m pytest -q tests/test_course_access.py tests/test_course_route_authorization.py tests/chat tests/learning
```

Expected: all tests pass; record any pre-existing unrelated failure separately rather than weakening assertions.

- [ ] **Step 4: Run frontend tests and build**

Run:

```powershell
npx tsx --test src/stitch/**/*.test.ts src/stitch/**/*.test.tsx
npm run lint
npm run build
```

Expected: all commands exit 0.

- [ ] **Step 5: Perform manual role smoke checks**

Verify in the app:

1. Teacher can create and publish a task from a shared material.
2. Student sees the published task but no teacher controls.
3. Student opens the resource and completes the task.
4. Teacher sees one completed student and the correct completion rate.
5. Student Agent mentions the completed task only when relevant.
6. Teacher Agent sees aggregate progress and does not receive private student conversation text.
7. Refresh and backend restart preserve the result.

- [ ] **Step 6: Commit acceptance coverage**

```powershell
git add backend/src/tests/learning/test_learning_loop_acceptance.py
git commit -m "test: cover teacher student learning loop"
```

## Plan self-review result

- Spec coverage: Phase 1 covers resource/task separation, publish/consume, event/progress feedback, role boundaries, cross-conversation Agent context, and current working-memory reliability.
- Deferred by explicit scope: knowledge mastery scoring, semantic/vector long-term memory, private-dialogue consolidation, grading, notifications, and temporal graphs.
- Type consistency: API and frontend use `task_id`, `resource_refs`, `knowledge_point_ids`, `event_id`, `event_type`, `progress_percent`, and `my_progress` consistently.
- Conflict boundary: no course creation, join-code, enrollment-write, or member-management files are created or modified.
