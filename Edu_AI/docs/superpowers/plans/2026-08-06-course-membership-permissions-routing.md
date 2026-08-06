# Course Membership, Permissions, and Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the course the real shared workspace boundary: all development users are enrolled in all courses, teachers collaborate on shared course data, students are read-only, and every course page derives its context from `course_id` in the URL.

**Architecture:** Keep the existing filesystem-backed course storage, but add an atomic JSON membership repository and a single authorization service used by every course route. Preserve creator identity for audit while changing course materials from creator-only visibility to course-member visibility. On the frontend, store the authenticated user in app context and load the active course exclusively from the route.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, JSON/atomic filesystem storage, pytest, React 18, TypeScript 5.6, Vite 6, Node test runner.

## Global Constraints

- This plan implements SPEC stages 0 and 1 from `docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md`.
- `DEV_AUTO_ENROLL_ALL_COURSES=true` enrolls teachers as `editor` and students as `viewer`; it never grants `owner`.
- A frontend permission check never replaces a backend authorization check.
- URL `course_id` is authoritative; `localStorage` may only remember the most recently visited course.
- Existing course files and generated materials must remain readable throughout migration.
- Course tasks remain creator-scoped in the task center; completed course materials become course-member visible.
- Use TDD and keep each task independently reviewable.
- Do not modify or discard unrelated working-tree changes.

## Priority and Command Locations

- **P0 / release blocking:** Tasks 1–9. The shared course boundary, server-side permissions, and URL authority must exist before knowledge and UI restructuring.
- Run backend pytest commands from `D:\github\edu_ai\Edu_AI\api\src`.
- Run frontend pnpm commands from `D:\github\edu_ai` because they use `pnpm --dir Edu_AI`.
- Run every git command from repository root `D:\github\edu_ai`; therefore git paths include the `Edu_AI/` prefix.

---

## Target File Map

| File | Responsibility |
|---|---|
| `api/src/app/services/course_membership_store.py` | Atomic membership persistence and queries |
| `api/src/app/services/course_access.py` | Capability-based authorization independent of HTTP |
| `api/src/app/api/course_dependencies.py` | FastAPI dependency helpers and 401/403 mapping |
| `api/src/app/services/course_membership_bootstrap.py` | Development auto-enrollment and legacy backfill |
| `api/src/scripts/migrate_course_memberships.py` | Dry-run/apply migration command |
| `api/src/core/course_storage.py` | Course revision compare-and-swap and shared material manifests |
| `api/src/app/schemas/course.py` | Course, membership, and material API contracts |
| `api/src/app/api/courses.py` | Secured course, knowledge, resource, graph, and classroom routes |
| `api/src/app/auth.py` | Registration hook for development auto-enrollment |
| `api/src/app/bootstrap.py` | Startup membership backfill |
| `src/stitch/authSession.ts` | Auth token/user parsing without page coupling |
| `src/stitch/course/CourseRouteProvider.tsx` | URL-derived course loading and membership role context |
| `src/stitch/teacherRoutes.ts` | Canonical course route construction and parsing |
| `src/stitch/App.tsx` | Authenticated user and route provider composition |
| `src/stitch/shared.tsx` | Course shell context and permission-aware navigation |
| `src/stitch/pages/CourseDetail.tsx` | Course list/overview links with explicit IDs |
| `src/stitch/pages/CourseEdit.tsx` | Editor form and viewer read-only state |

---

### Task 1: Add the atomic course membership repository

**Files:**
- Create: `api/src/app/services/course_membership_store.py`
- Create: `api/src/tests/test_course_membership_store.py`

**Interfaces:**
- Produces: `CourseRole`, `CourseMembership`, `CourseMembershipStore.get()`, `.upsert()`, `.list_for_user()`, `.list_for_course()`, `.delete()`.
- Storage shape: `{ "schema_version": 1, "memberships": [{ "course_id": "course-1", "user_id": "teacher-a", "role": "editor", "joined_at": "2026-08-06T09:00:00+08:00", "added_by": "system" }] }` at `Config.STORAGE_ROOT / "course_memberships.json"`.

- [ ] **Step 1: Write failing repository tests**

```python
from app.services.course_membership_store import CourseMembershipStore


def test_upsert_is_unique_and_persists(tmp_path):
    path = tmp_path / "memberships.json"
    store = CourseMembershipStore(path)
    store.upsert("course-1", "teacher-a", "editor", added_by="system")
    store.upsert("course-1", "teacher-a", "owner", added_by="admin")

    reopened = CourseMembershipStore(path)
    membership = reopened.get("course-1", "teacher-a")
    assert membership is not None
    assert membership.role == "owner"
    assert len(reopened.list_for_course("course-1")) == 1


def test_list_for_user_does_not_leak_other_users(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    store.upsert("course-1", "teacher-a", "editor", added_by="system")
    store.upsert("course-2", "student-a", "viewer", added_by="system")
    assert [item.course_id for item in store.list_for_user("teacher-a")] == ["course-1"]
```

- [ ] **Step 2: Run the tests and confirm the module is missing**

Run from `Edu_AI/api/src`:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_membership_store.py -q
```

Expected: collection fails because `app.services.course_membership_store` does not exist.

- [ ] **Step 3: Implement the repository with atomic replacement**

```python
CourseRole = Literal["owner", "editor", "viewer"]

@dataclass(frozen=True)
class CourseMembership:
    course_id: str
    user_id: str
    role: CourseRole
    joined_at: str
    added_by: str

class CourseMembershipStore:
    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._lock = threading.RLock()

    def get(self, course_id: str, user_id: str) -> CourseMembership | None:
        key = (course_id.strip(), user_id.strip())
        return next((item for item in self._read() if (item.course_id, item.user_id) == key), None)

    def upsert(self, course_id: str, user_id: str, role: CourseRole, *, added_by: str) -> CourseMembership:
        with self._lock:
            items = self._read_unlocked()
            key = (course_id.strip(), user_id.strip())
            previous = next((item for item in items if (item.course_id, item.user_id) == key), None)
            membership = CourseMembership(
                course_id=key[0], user_id=key[1], role=role,
                joined_at=previous.joined_at if previous else datetime.now(timezone.utc).isoformat(),
                added_by=added_by.strip(),
            )
            updated = [item for item in items if (item.course_id, item.user_id) != key] + [membership]
            self._write_unlocked(updated)
            return membership

    def list_for_user(self, user_id: str) -> list[CourseMembership]:
        return sorted((item for item in self._read() if item.user_id == user_id.strip()), key=lambda item: item.course_id)

    def list_for_course(self, course_id: str) -> list[CourseMembership]:
        return sorted((item for item in self._read() if item.course_id == course_id.strip()), key=lambda item: item.user_id)

    def delete(self, course_id: str, user_id: str) -> bool:
        with self._lock:
            items = self._read_unlocked()
            retained = [item for item in items if (item.course_id, item.user_id) != (course_id.strip(), user_id.strip())]
            if len(retained) == len(items):
                return False
            self._write_unlocked(retained)
            return True
```

Implement `_read()`, `_read_unlocked()`, and `_write_unlocked()` in the same file. `_write_unlocked()` serializes the exact schema above to `.<name>.<uuid>.tmp`, calls `flush()` and `os.fsync()`, then `os.replace()`. Normalize IDs with `strip()` and sort stored records by `(course_id, user_id)`.

- [ ] **Step 4: Run repository tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_membership_store.py -q
```

Expected: all tests pass and a reopened store sees the same record.

- [ ] **Step 5: Commit the repository**

```powershell
git add Edu_AI/api/src/app/services/course_membership_store.py Edu_AI/api/src/tests/test_course_membership_store.py
git commit -m "feat: add course membership repository"
```

### Task 2: Add one capability-based course authorization service

**Files:**
- Create: `api/src/app/services/course_access.py`
- Create: `api/src/app/api/course_dependencies.py`
- Create: `api/src/tests/test_course_access.py`

**Interfaces:**
- Consumes: `CourseMembershipStore.get(course_id, user_id)` from Task 1.
- Produces: `CourseCapability`, `CourseAccessService.require()`, `CoursePrincipal`, `require_course_read`, `require_course_edit`, `require_course_owner`.

- [ ] **Step 1: Write the access matrix tests**

```python
import pytest
from app.services.course_access import CourseAccessDenied, CourseAccessService
from app.services.course_membership_store import CourseMembershipStore


@pytest.fixture
def store(tmp_path):
    return CourseMembershipStore(tmp_path / "memberships.json")


@pytest.mark.parametrize(
    ("role", "capability", "allowed"),
    [
        ("viewer", "read", True),
        ("viewer", "edit", False),
        ("viewer", "generate", False),
        ("editor", "edit", True),
        ("editor", "manage_members", False),
        ("owner", "manage_members", True),
    ],
)
def test_course_access_matrix(store, role, capability, allowed):
    store.upsert("course-1", "user-a", role, added_by="system")
    service = CourseAccessService(store)
    if allowed:
    assert service.require("course-1", {"username": "user-a", "role": "teacher"}, capability).course_role == role
    else:
        with pytest.raises(CourseAccessDenied):
            service.require("course-1", {"username": "user-a", "role": "teacher"}, capability)
```

- [ ] **Step 2: Verify the access tests fail**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_access.py -q
```

Expected: import failure for `course_access`.

- [ ] **Step 3: Implement the service and HTTP adapters**

```python
CourseCapability = Literal["read", "edit", "generate", "manage_resources", "manage_members", "delete_course"]

ROLE_CAPABILITIES = {
    "viewer": frozenset({"read"}),
    "editor": frozenset({"read", "edit", "generate", "manage_resources"}),
    "owner": frozenset({"read", "edit", "generate", "manage_resources", "manage_members", "delete_course"}),
}

@dataclass(frozen=True)
class CoursePrincipal:
    course_id: str
    user_id: str
    system_role: str
    course_role: CourseRole

class CourseAccessService:
    def __init__(self, store: CourseMembershipStore):
        self._store = store

    def require(self, course_id: str, user: Mapping[str, Any], capability: CourseCapability) -> CoursePrincipal:
        user_id = str(user.get("username") or "").strip()
        membership = self._store.get(course_id, user_id)
        if membership is None or capability not in ROLE_CAPABILITIES[membership.role]:
            raise CourseAccessDenied(course_id=course_id, user_id=user_id, capability=capability)
        return CoursePrincipal(
            course_id=course_id,
            user_id=user_id,
            system_role=str(user.get("role") or ""),
            course_role=membership.role,
        )
```

In `course_dependencies.py`, map missing membership and denied capability to HTTP 403. Authentication continues to come from `app.auth.get_current_user`; do not return 404 to conceal courses in this small development environment.

- [ ] **Step 4: Run access and dependency tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_access.py -q
```

Expected: the full role/capability matrix passes.

- [ ] **Step 5: Commit the authorization boundary**

```powershell
git add Edu_AI/api/src/app/services/course_access.py Edu_AI/api/src/app/api/course_dependencies.py Edu_AI/api/src/tests/test_course_access.py
git commit -m "feat: enforce course capabilities"
```

### Task 3: Backfill memberships and implement development auto-enrollment

**Files:**
- Modify: `api/src/core/config.py`
- Create: `api/src/app/services/course_membership_bootstrap.py`
- Create: `api/src/scripts/migrate_course_memberships.py`
- Modify: `api/src/app/bootstrap.py`
- Modify: `api/src/app/auth.py`
- Create: `api/src/tests/test_course_membership_bootstrap.py`

**Interfaces:**
- Consumes: `CourseMembershipStore` and `user_storage.list_users()`.
- Produces: `CourseMembershipBootstrap.sync_existing()`, `.on_user_created()`, `.on_course_created()`.

- [ ] **Step 1: Write auto-enrollment tests**

```python
def test_sync_existing_assigns_development_roles(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    bootstrap = CourseMembershipBootstrap(store=store, enabled=True)
    summary = bootstrap.sync_existing(
        users=[{"username": "t1", "role": "teacher"}, {"username": "s1", "role": "student"}],
        course_ids=["c1", "c2"],
    )
    assert summary.created == 4
    assert bootstrap.store.get("c1", "t1").role == "editor"
    assert bootstrap.store.get("c1", "s1").role == "viewer"


def test_disabled_mode_creates_nothing(tmp_path):
    store = CourseMembershipStore(tmp_path / "memberships.json")
    bootstrap = CourseMembershipBootstrap(store=store, enabled=False)
    assert bootstrap.sync_existing(users=[{"username": "t1", "role": "teacher"}], course_ids=["c1"]).created == 0
```

- [ ] **Step 2: Run and observe the missing bootstrap class**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_membership_bootstrap.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement configuration, hooks, and migration CLI**

Add to `Config`:

```python
DEV_AUTO_ENROLL_ALL_COURSES = os.getenv("DEV_AUTO_ENROLL_ALL_COURSES", "1").strip().lower() in {"1", "true", "yes", "on"}
COURSE_MEMBERSHIPS_FILE = Path(os.getenv("COURSE_MEMBERSHIPS_FILE", STORAGE_ROOT / "course_memberships.json"))
```

The CLI must support only explicit modes:

```powershell
D:\anaconda\envs\edu-ai\python.exe -m scripts.migrate_course_memberships --dry-run
D:\anaconda\envs\edu-ai\python.exe -m scripts.migrate_course_memberships --apply
```

Call `sync_existing()` once during FastAPI lifespan startup, after default courses exist and before workers start. After a successful public registration call `on_user_created(user)`. Course creation integration is added in Task 4.

- [ ] **Step 4: Verify idempotency and disabled behavior**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_membership_bootstrap.py -q
```

Expected: running `sync_existing()` twice produces zero new records on the second run.

- [ ] **Step 5: Commit auto-enrollment**

```powershell
git add Edu_AI/api/src/core/config.py Edu_AI/api/src/app/services/course_membership_bootstrap.py Edu_AI/api/src/scripts/migrate_course_memberships.py Edu_AI/api/src/app/bootstrap.py Edu_AI/api/src/app/auth.py Edu_AI/api/src/tests/test_course_membership_bootstrap.py
git commit -m "feat: auto enroll development course members"
```

### Task 4: Add revision-safe course CRUD and secure the course list

**Files:**
- Modify: `api/src/core/course_storage.py:535-566`
- Modify: `api/src/app/schemas/course.py:13-22`
- Modify: `api/src/app/api/courses.py:116-183`
- Modify: `api/src/app/services/course_service.py`
- Create: `api/src/tests/course_api_test_support.py`
- Create: `api/src/tests/test_course_crud_permissions.py`

**Interfaces:**
- Consumes: `CourseAccessService`, membership bootstrap from Tasks 2–3.
- Produces: course response fields `revision`, `membership_role`, `created_by`, `created_at`, `updated_at`; `CourseUpdateRequest` with editable fields plus `expected_revision`; compare-and-swap update.

- [ ] **Step 1: Write secured CRUD and stale revision tests**

```python
def test_course_list_requires_auth_and_returns_membership_role(course_api):
    anonymous = course_api.anonymous().get("/api/courses")
    response = course_api.client_for("teacher-a", "teacher").get("/api/courses")
    assert anonymous.status_code == 401
    assert response.status_code == 200
    assert response.json()[0]["membership_role"] == "editor"


def test_stale_course_revision_returns_409(course_api):
    client = course_api.client_for("teacher-a", "teacher")
    course = client.get("/api/courses/course-1").json()
    first = client.put("/api/courses/course-1", json=course_update_payload(course, title="First"))
    stale = client.put("/api/courses/course-1", json=course_update_payload(course, title="Stale"))
    assert first.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "COURSE_REVISION_CONFLICT"
```

- [ ] **Step 2: Run the CRUD tests and confirm current public access fails expectations**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_crud_permissions.py -q
```

Expected: anonymous list currently returns 200 and stale writes overwrite.

- [ ] **Step 3: Implement compare-and-swap and membership-filtered responses**

Add a storage result instead of a boolean-only write:

```python
class CourseRevisionConflict(RuntimeError):
    def __init__(self, course_id: str, expected: int, actual: int):
        super().__init__(f"course {course_id} revision conflict: expected {expected}, actual {actual}")
        self.course_id = course_id
        self.expected = expected
        self.actual = actual

def update_course_info(self, course_id: str, course_info: dict[str, Any], *, expected_revision: int) -> dict[str, Any]:
    with self._storage_lock():
        current = self.get_course_info(course_id) or {}
        if int(current.get("revision") or 0) != expected_revision:
            raise CourseRevisionConflict(course_id)
        now = datetime.now().isoformat()
        updated = {**current, **course_info, "revision": expected_revision + 1, "updated_at": now}
        self._write_json(self.get_course_dir(course_id) / "course_info.json", updated)
        return updated
```

Legacy courses normalize to revision `0`. `list_courses()` filters through `list_for_user()`. `create_course()` records `created_by`, creates the caller as `owner`, then invokes development auto-enrollment without downgrading the owner.

In `course_api_test_support.py`, implement `CourseApiTestFactory` with one shared temporary `CourseStorageManager`, membership store, and access service. `client_for(username, system_role)` builds a small FastAPI app containing `courses.router`, overrides `get_current_user` with that identity, and injects the shared stores; `anonymous()` builds the same app without an auth override. Also implement `course_update_payload(course, title=course["title"])` to copy only `title`, `description`, `icon`, `color`, `objectives`, `knowledgeGraph`, and `expected_revision=course["revision"]`. Expose a local pytest fixture as `course_api = CourseApiTestFactory(tmp_path)` in each test file that uses it.

- [ ] **Step 4: Run CRUD and existing course scope tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_crud_permissions.py tests/chat/test_course_scope_routes.py -q
```

Expected: 401/403/409 behavior passes and existing scope filters remain green.

- [ ] **Step 5: Commit secured course CRUD**

```powershell
git add Edu_AI/api/src/core/course_storage.py Edu_AI/api/src/app/schemas/course.py Edu_AI/api/src/app/api/courses.py Edu_AI/api/src/app/services/course_service.py Edu_AI/api/src/tests/course_api_test_support.py Edu_AI/api/src/tests/test_course_crud_permissions.py
git commit -m "feat: secure revisioned course CRUD"
```

### Task 5: Change generated materials from creator-only to course-member visibility

**Files:**
- Modify: `api/src/core/course_storage.py:706-940`
- Modify: `api/src/app/schemas/course.py`
- Modify: `api/src/app/api/courses.py:186-369`
- Modify: `api/src/app/services/generation_task_handlers.py:330-415`
- Modify: `api/src/app/services/job_reconciliation_service.py`
- Replace tests: `api/src/tests/core/test_course_material_permissions.py`
- Modify: `api/src/tests/core/test_course_material_manifest.py`

**Interfaces:**
- Consumes: course authorization from Task 2.
- Produces: manifest fields `created_by`, `visibility`, `source_mode`, `source_snapshot`; storage queries no longer use owner as the course visibility filter.

- [ ] **Step 1: Replace owner-isolation tests with course visibility tests**

```python
def test_course_material_is_readable_by_another_course_editor(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1", "quiz", "quiz-1", {"title": "Shared"},
        owner_user_id="teacher-a", visibility="course",
    )
    material = manager.get_generated_material("course-1", "quiz", "quiz-1")
    assert material["created_by"] == "teacher-a"
    assert material["visibility"] == "course"


def test_private_material_still_requires_creator(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1", "quiz", "draft-1", {"title": "Private draft"},
        owner_user_id="teacher-a", visibility="private",
    )
    assert manager.get_generated_material("course-1", "quiz", "draft-1", requester_user_id="teacher-b") is None
```

- [ ] **Step 2: Run the material tests and confirm current owner filtering fails**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/core/test_course_material_permissions.py -q
```

Expected: the shared editor read fails under current `_material_owner_matches` behavior.

- [ ] **Step 3: Implement new manifest semantics and legacy normalization**

Extend `save_generated_material()` with:

```python
visibility: Literal["course", "private"] = "course"
```

Normalize legacy `owner_user_id` to `created_by`, retain `owner_user_id` as a read-compatible alias for one release, and treat legacy owned formal materials as `visibility="course"`. API routes call `course_access.require(course_id, current_user, "read")` or `course_access.require(course_id, current_user, "manage_resources")` before storage access. Private lookup additionally supplies `requester_user_id`.

- [ ] **Step 4: Run material, manifest, completion, and reconciliation tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/core/test_course_material_permissions.py tests/core/test_course_material_manifest.py tests/test_job_completion_service.py tests/test_job_reconciliation_service.py -q
```

Expected: shared materials are visible to course editors; provenance and read-back validation still pass.

- [ ] **Step 5: Commit shared course resources**

```powershell
git add Edu_AI/api/src/core/course_storage.py Edu_AI/api/src/app/schemas/course.py Edu_AI/api/src/app/api/courses.py Edu_AI/api/src/app/services/generation_task_handlers.py Edu_AI/api/src/app/services/job_reconciliation_service.py Edu_AI/api/src/tests/core/test_course_material_permissions.py Edu_AI/api/src/tests/core/test_course_material_manifest.py
git commit -m "feat: share generated materials with course members"
```

### Task 6: Apply authorization to knowledge graph, knowledge base, and AI classroom routes

**Files:**
- Modify: `api/src/app/api/courses.py:371-1100`
- Modify: `api/src/app/services/classroom_service.py`
- Modify: `api/src/app/services/classroom_job_service.py`
- Create: `api/src/tests/test_course_route_authorization.py`

**Interfaces:**
- Consumes: `CourseAccessService.require()` and `CoursePrincipal`.
- Produces: consistent 401/403 behavior for every endpoint under `/api/courses/{course_id}/`.

- [ ] **Step 1: Add a parameterized route authorization test**

```python
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/courses/course-1/knowledge-base/documents"),
        ("put", "/api/courses/course-1/knowledge-graph"),
        ("post", "/api/courses/course-1/classrooms/generate"),
        ("delete", "/api/courses/course-1/materials/report/report-1"),
    ],
)
def test_viewer_cannot_mutate_course_content(course_api, method, path):
    viewer = course_api.client_for("student-a", "student")
    response = getattr(viewer, method)(path, json={})
    assert response.status_code == 403
```

- [ ] **Step 2: Run the authorization test and capture currently open routes**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_route_authorization.py -q
```

Expected: at least knowledge graph or course CRUD mutation is incorrectly allowed.

- [ ] **Step 3: Add read/edit/generate/manage checks route by route**

Use this mapping:

```text
GET knowledge/material/classroom/graph -> read
POST/PUT/DELETE knowledge or graph -> edit
POST generation/classroom generation -> generate
PATCH/DELETE/PIN/RENAME material -> manage_resources
DELETE course or membership mutation -> owner-only capability
```

Do not pass `owner_user_id` to filter course resources. Continue recording it as the creator of tasks and artifacts.

- [ ] **Step 4: Run all course, classroom, graph, and material tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_route_authorization.py tests/chat/test_course_scope_routes.py tests/chat/test_textbook_knowledge_graph_routes.py tests/test_classroom_job_service.py tests/core/test_course_material_permissions.py -q
```

Expected: viewer writes return 403 and editor workflows remain successful.

- [ ] **Step 5: Commit complete course route authorization**

```powershell
git add Edu_AI/api/src/app/api/courses.py Edu_AI/api/src/app/services/classroom_service.py Edu_AI/api/src/app/services/classroom_job_service.py Edu_AI/api/src/tests/test_course_route_authorization.py
git commit -m "feat: authorize all course content routes"
```

### Task 7: Store authenticated user and expose URL-derived course context

**Files:**
- Create: `src/stitch/authSession.ts`
- Create: `src/stitch/course/CourseRouteProvider.tsx`
- Create: `src/stitch/course/coursePermissions.ts`
- Modify: `src/stitch/App.tsx:108-260`
- Modify: `src/stitch/shared.tsx:42-105`
- Modify: `src/stitch/api/types.ts`
- Modify: `src/stitch/api/courses.ts`
- Create: `src/stitch/course/CourseRouteProvider.test.ts`

**Interfaces:**
- Consumes: course response `membership_role` and login response `user`.
- Produces: `useCourseRoute()` and `canCourse(role, capability)`.

- [ ] **Step 1: Write route authority and permission tests**

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import { resolveCourseRouteState } from "./CourseRouteProvider";
import { canCourse } from "./coursePermissions";

test("URL course wins over remembered course", () => {
  assert.equal(resolveCourseRouteState("#ai?course_id=course-b", "course-a").courseId, "course-b");
});

test("viewer is read-only", () => {
  assert.equal(canCourse("viewer", "read"), true);
  assert.equal(canCourse("viewer", "edit"), false);
});
```

- [ ] **Step 2: Run the focused frontend tests**

```powershell
pnpm --dir Edu_AI test -- src/stitch/course/CourseRouteProvider.test.ts
```

Expected: missing module failure.

- [ ] **Step 3: Implement session and course route contexts**

```typescript
export type CourseRole = "owner" | "editor" | "viewer";
export type AuthUser = { username: string; role: "admin" | "teacher" | "student" };

export type CourseRouteValue = {
  courseId: string | null;
  course: BackendCourse | null;
  courseRole: CourseRole | null;
  loading: boolean;
  error: ApiError | null;
  reload: () => Promise<void>;
};
```

`App.tsx` initializes `AuthUser` from verified token/login response, mounts `CourseRouteProvider`, and removes the effect that asynchronously overwrites `selectedCourse` after a route is already rendered. Remembered course is only consulted when navigating from `#home` without a course ID.

- [ ] **Step 4: Run route, auth restore, and production build checks**

```powershell
pnpm --dir Edu_AI test -- src/stitch/course/CourseRouteProvider.test.ts src/stitch/teacherRoutes.test.ts
pnpm --dir Edu_AI build
```

Expected: tests pass and TypeScript build succeeds.

- [ ] **Step 5: Commit the route contexts**

```powershell
git add Edu_AI/src/stitch/authSession.ts Edu_AI/src/stitch/course/CourseRouteProvider.tsx Edu_AI/src/stitch/course/coursePermissions.ts Edu_AI/src/stitch/App.tsx Edu_AI/src/stitch/shared.tsx Edu_AI/src/stitch/api/types.ts Edu_AI/src/stitch/api/courses.ts Edu_AI/src/stitch/course/CourseRouteProvider.test.ts
git commit -m "feat: derive course context from route"
```

### Task 8: Fix canonical course links and render viewer-safe pages

**Files:**
- Modify: `src/stitch/teacherRoutes.ts`
- Modify: `src/stitch/teacherRoutes.test.ts`
- Modify: `src/stitch/pages/CourseDetail.tsx`
- Modify: `src/stitch/pages/CourseEdit.tsx`
- Modify: `src/stitch/pages/KnowledgeGraph.tsx`
- Modify: `src/stitch/pages/ClassroomStudio.tsx`
- Modify: `src/stitch/pages/ClassroomPlayer.tsx`
- Modify: `tests/frontend/knowledgeGraphWorkspaceJump.test.ts`
- Create: `tests/frontend/coursePermissionRendering.test.ts`

**Interfaces:**
- Consumes: `useCourseRoute()`, `canCourse()`, `buildTeacherCourseHash()`.
- Produces: stable deep links and read-only viewer rendering.

- [ ] **Step 1: Extend route tests for every course page**

```typescript
test("course detail and graph workspace links preserve course identity", () => {
  assert.equal(buildTeacherCourseHash("course-detail", "course / 中文"), "#course-detail?course_id=course+%2F+%E4%B8%AD%E6%96%87");
  assert.equal(readTeacherCourseId("#course-detail?course_id=course-1"), "course-1");
});
```

Add source assertions proving `KnowledgeGraph.tsx` passes `course_id`, `ClassroomStudio.tsx` returns to `course-detail`, and viewer pages do not render a save trigger.

- [ ] **Step 2: Run route and rendering tests to reproduce failures**

```powershell
pnpm --dir Edu_AI test -- src/stitch/teacherRoutes.test.ts tests/frontend/knowledgeGraphWorkspaceJump.test.ts tests/frontend/coursePermissionRendering.test.ts
```

Expected: `course-detail` is not accepted by the current route type; return targets or viewer controls fail assertions.

- [ ] **Step 3: Replace implicit/fallback links and gate mutations**

Add `course-detail` to `TeacherCourseRoute`. Build every course link with `buildTeacherCourseHash`. In `CourseEdit`, render values as text for viewers and do not mount the submit button. If a role changes while the page is open, discard unsaved editor state and switch to read-only.

- [ ] **Step 4: Run frontend regression and build**

```powershell
pnpm --dir Edu_AI test
pnpm --dir Edu_AI build
```

Expected: all Node tests and the Vite production build pass.

- [ ] **Step 5: Commit canonical navigation and permission rendering**

```powershell
git add Edu_AI/src/stitch/teacherRoutes.ts Edu_AI/src/stitch/teacherRoutes.test.ts Edu_AI/src/stitch/pages/CourseDetail.tsx Edu_AI/src/stitch/pages/CourseEdit.tsx Edu_AI/src/stitch/pages/KnowledgeGraph.tsx Edu_AI/src/stitch/pages/ClassroomStudio.tsx Edu_AI/src/stitch/pages/ClassroomPlayer.tsx Edu_AI/tests/frontend/knowledgeGraphWorkspaceJump.test.ts Edu_AI/tests/frontend/coursePermissionRendering.test.ts
git commit -m "fix: preserve course identity across teacher routes"
```

### Task 9: Run the two-teacher/one-student acceptance gate

**Files:**
- Create: `api/src/tests/test_course_collaboration_acceptance.py`
- Create: `tests/frontend/courseRouteAcceptance.test.ts`
- Modify: `docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md` only to check verified Stage 0–1 items after evidence exists.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: executable acceptance coverage for shared edits, shared resources, viewer denial, and route reload behavior.

- [ ] **Step 1: Write the backend collaboration scenario**

```python
def test_two_teachers_share_course_and_student_is_read_only(course_api):
    teacher_a = course_api.client_for("teacher-a", "teacher")
    teacher_b = course_api.client_for("teacher-b", "teacher")
    student = course_api.client_for("student-a", "student")
    course = teacher_a.get("/api/courses/course-1").json()
    updated = teacher_a.put("/api/courses/course-1", json=course_update_payload(course, title="Shared title"))
    assert updated.status_code == 200
    assert teacher_b.get("/api/courses/course-1").json()["title"] == "Shared title"
    assert student.put("/api/courses/course-1", json=course_update_payload(updated.json(), title="Forbidden edit")).status_code == 403
```

Extend it with a saved report material created by A and read by B.

- [ ] **Step 2: Run focused acceptance tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_collaboration_acceptance.py -q
pnpm --dir Edu_AI test -- tests/frontend/courseRouteAcceptance.test.ts
```

Expected: both acceptance files pass.

- [ ] **Step 3: Run the full affected backend suite**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_membership_store.py tests/test_course_access.py tests/test_course_membership_bootstrap.py tests/test_course_crud_permissions.py tests/test_course_route_authorization.py tests/test_course_collaboration_acceptance.py tests/core/test_course_material_permissions.py tests/chat/test_course_scope_routes.py -q
```

Expected: all tests pass with no live server or network dependency.

- [ ] **Step 4: Run the full frontend quality gate**

```powershell
pnpm --dir Edu_AI test
pnpm --dir Edu_AI lint
pnpm --dir Edu_AI build
```

Expected: tests, lint, and build pass; any pre-existing unrelated warning is recorded separately and not hidden.

- [ ] **Step 5: Commit acceptance evidence**

```powershell
git add Edu_AI/api/src/tests/test_course_collaboration_acceptance.py Edu_AI/tests/frontend/courseRouteAcceptance.test.ts Edu_AI/docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md
git commit -m "test: verify shared course collaboration"
```

---

## Plan 1 Completion Gate

Do not start Plan 2 until all of the following are evidenced:

- Two teacher accounts read the same course and shared course materials.
- Student writes are rejected by the backend, not only hidden in the UI.
- Anonymous course access returns 401.
- Stale course writes return 409.
- Development auto-enrollment is idempotent and can be disabled.
- Hard refresh and copied URLs preserve the requested course.
- Full affected backend tests, frontend tests, lint, and build pass.
