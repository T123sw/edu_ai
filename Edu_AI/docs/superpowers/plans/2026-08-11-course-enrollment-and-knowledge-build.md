# Course Enrollment and Governed Knowledge Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete teacher-create, course-code enrollment, centralized membership, and governed three-level course knowledge-base flow with at least three qualified documents per leaf node.

**Architecture:** Extend the existing PostgreSQL course and membership models instead of creating a parallel enrollment store. Extend the merged governed knowledge-build pipeline with a semantic graph draft, staged Chinese/English acquisition, model-generated Chinese fallback, per-leaf quality gates, and atomic publication. Keep teacher and student UI additions in focused components so current uncommitted runtime-loading changes remain untouched.

**Tech Stack:** PostgreSQL 17, SQLAlchemy 2, Alembic, FastAPI, Pydantic v2, React 19, TypeScript, Vite, Node test runner, pytest, existing durable job runner and RAG v2.

## Global Constraints

- PostgreSQL remains the only structured business-data store; do not restore JSON or business SQLite writes.
- A course graph must contain at least three levels including the root: course root, semantic module/domain, leaf knowledge point.
- Do not invent empty wrapper nodes or enforce a fixed child count merely to satisfy graph depth.
- Every leaf knowledge point must reference at least three distinct ready documents before publication.
- Acquisition order is Chinese qualified sources, then English qualified sources, then model-generated Chinese supplements.
- Model-generated material must be labeled, must not fabricate citations, and must score at least 80 in an independent quality review.
- Failed builds preserve the currently published graph and documents.
- New courses auto-enroll only their creator as `owner`.
- Preserve unrelated dirty worktree changes, especially `src/stitch/App.tsx`, global job UI, runtime settings, package manifests, and Vite configuration.
- Use TDD for every production behavior: write the failing test, observe the expected failure, implement minimally, and re-run.

---

## File Structure

New focused files:

- `api/src/alembic/versions/20260811_0011_course_codes_and_membership.py`: course-code schema and backfill.
- `api/src/app/services/course_code_service.py`: code normalization and secure generation.
- `api/src/app/services/course_membership_service.py`: join and owner-management business rules.
- `api/src/app/services/course_knowledge_graph_planner.py`: three-level semantic graph draft and structural validation.
- `api/src/app/services/course_knowledge_source_acquisition.py`: staged Chinese/English acquisition state.
- `api/src/app/services/course_knowledge_generated_material.py`: model fallback and independent review.
- `src/stitch/course/members/CourseMemberPanel.tsx`: owner member management.
- `src/stitch/course/members/courseMemberPanel.css`: isolated member UI styles.
- `src/stitch/student/courseJoin.ts`: student join-form validation.
- `src/stitch/student/components/CourseJoinDialog.tsx`: student join dialog.

Existing files extended in place:

- `api/src/app/database/models.py`
- `api/src/app/persistence/postgres_repositories.py`
- `api/src/app/schemas/course.py`
- `api/src/app/api/courses.py`
- `api/src/app/services/course_membership_bootstrap.py`
- `api/src/core/config.py`
- `api/src/app/services/course_knowledge_planner.py`
- `api/src/app/services/course_knowledge_plan_builder.py`
- `api/src/app/persistence/postgres_knowledge_repository.py`
- `src/stitch/api/types.ts`
- `src/stitch/api/courses.ts`
- `src/stitch/pages/CourseDetail.tsx`
- `src/stitch/pages/CourseEdit.tsx`
- `src/stitch/student/pages/StudentHome.tsx`
- `src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx`

---

### Task 1: Add Durable Unique Course Codes

**Files:**
- Create: `api/src/alembic/versions/20260811_0011_course_codes_and_membership.py`
- Create: `api/src/app/services/course_code_service.py`
- Modify: `api/src/app/database/models.py`
- Modify: `api/src/app/persistence/postgres_repositories.py`
- Modify: `api/src/app/persistence/contracts.py`
- Test: `api/src/tests/database/test_course_code_migration.py`
- Test: `api/src/tests/services/test_course_code_service.py`
- Test: `api/src/tests/persistence/test_postgres_core_repositories.py`

**Interfaces:**
- Produces: `normalize_course_code(value: object) -> str`
- Produces: `generate_course_code(exists: Callable[[str], bool], length: int = 8) -> str`
- Produces: `PostgresCourseRepository.get_by_course_code(course_code: str) -> dict[str, Any] | None`
- Produces: `PostgresCourseRepository.rotate_course_code(course_id: str, course_code: str) -> dict[str, Any]`

- [ ] **Step 1: Write migration and service tests that fail because the field and module do not exist**

```python
def test_normalize_course_code_accepts_human_formatting():
    assert normalize_course_code(" k7m9-q2wp ") == "K7M9Q2WP"


def test_generate_course_code_uses_unambiguous_unique_characters():
    code = generate_course_code(lambda candidate: candidate == "ABCDEFGH")
    assert len(code) == 8
    assert set(code) <= set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
    assert code != "ABCDEFGH"
```

Migration test creates the schema at `20260810_0010`, upgrades to `20260811_0011`, and asserts that every existing course has a non-empty unique `course_code` and the unique index exists.

- [ ] **Step 2: Run the failing tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_code_service.py tests/database/test_course_code_migration.py tests/persistence/test_postgres_core_repositories.py -q
```

Expected failure: missing service module, missing model field, or missing migration revision.

- [ ] **Step 3: Implement the migration, SQLAlchemy field, code service, and repository methods**

Use `secrets.choice()` with the exact alphabet in Global Constraints. Normalize before lookup and storage. Retry generation on repository collision. Migration backfill may use a deterministic uppercase hash for legacy rows, but the final column and index must be non-null and unique.

- [ ] **Step 4: Run focused tests and Alembic drift check**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_code_service.py tests/database/test_course_code_migration.py tests/persistence/test_postgres_core_repositories.py -q
D:\anaconda\envs\edu-ai\python.exe -m alembic -c alembic.ini check
```

- [ ] **Step 5: Commit only Task 1 files**

```powershell
git add Edu_AI/api/src/alembic/versions/20260811_0011_course_codes_and_membership.py Edu_AI/api/src/app/services/course_code_service.py Edu_AI/api/src/app/database/models.py Edu_AI/api/src/app/persistence/postgres_repositories.py Edu_AI/api/src/app/persistence/contracts.py Edu_AI/api/src/tests/database/test_course_code_migration.py Edu_AI/api/src/tests/services/test_course_code_service.py Edu_AI/api/src/tests/persistence/test_postgres_core_repositories.py
git commit -m "feat: add durable course codes"
```

### Task 2: Implement Student Join and Owner Member Management

**Files:**
- Create: `api/src/app/services/course_membership_service.py`
- Modify: `api/src/app/schemas/course.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `api/src/app/persistence/postgres_repositories.py`
- Test: `api/src/tests/services/test_course_membership_service.py`
- Test: `api/src/tests/test_course_membership_routes.py`
- Modify: `api/src/tests/course_api_test_support.py`

**Interfaces:**
- Produces: `CourseJoinRequest(course_code: str)`
- Produces: `CourseMemberCreateRequest(user_id: str, role: Literal["editor", "viewer"])`
- Produces: `CourseMemberUpdateRequest(role: Literal["editor", "viewer"])`
- Produces: `CourseMemberInfo(user_id, username, system_role, course_role, joined_at, added_by)`
- Produces: `CourseMembershipService.join_student(course_code, current_user)`
- Produces: `CourseMembershipService.list_members(course_id, principal)`
- Produces: `CourseMembershipService.add_member(...)`, `update_member(...)`, `remove_member(...)`, `rotate_code(...)`

- [ ] **Step 1: Write route tests for join, idempotency, permissions, role validation, removal, and code rotation**

```python
def test_student_joins_with_course_code_and_repeat_is_idempotent(course_api):
    student = course_api.client_for("student-b", "student")
    first = student.post("/api/courses/join", json={"course_code": "ABCD-2345"})
    second = student.post("/api/courses/join", json={"course_code": "abcd2345"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["membership_role"] == "viewer"
    assert course_api.memberships.list_for_course("course-1").count(
        course_api.memberships.get("course-1", "student-b")
    ) == 1


def test_non_owner_cannot_read_or_mutate_members(course_api):
    assert course_api.client_for("teacher-b", "teacher").get(
        "/api/courses/course-1/members"
    ).status_code == 403


def test_owner_cannot_remove_course_creator(course_api):
    response = course_api.client_for("teacher-a", "teacher").delete(
        "/api/courses/course-1/members/teacher-a"
    )
    assert response.status_code == 409
```

Also test invalid codes, teacher use of the student join route, student promotion to editor, disabled users, missing users, repeated member addition, and access denial immediately after removal.

- [ ] **Step 2: Run tests and confirm routes are missing**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_membership_service.py tests/test_course_membership_routes.py -q
```

- [ ] **Step 3: Implement service rules and register static `/join` before dynamic `/{course_id}` routes**

Return a uniform 404 for invalid course codes. Fetch user summaries through the PostgreSQL user repository and return only allowlisted fields. Use the existing `manage_members` owner capability. Do not expose password hashes or raw user payloads.

- [ ] **Step 4: Run membership, access, CRUD, and learning tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_membership_service.py tests/test_course_membership_routes.py tests/test_course_access.py tests/test_course_crud_permissions.py tests/learning -q
```

- [ ] **Step 5: Commit Task 2**

```powershell
git add Edu_AI/api/src/app/services/course_membership_service.py Edu_AI/api/src/app/schemas/course.py Edu_AI/api/src/app/api/courses.py Edu_AI/api/src/app/persistence/postgres_repositories.py Edu_AI/api/src/tests/services/test_course_membership_service.py Edu_AI/api/src/tests/test_course_membership_routes.py Edu_AI/api/src/tests/course_api_test_support.py
git commit -m "feat: manage course enrollment and members"
```

### Task 3: Make Course Creation Owner-Only by Default

**Files:**
- Modify: `api/src/core/config.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `api/src/app/services/course_membership_bootstrap.py`
- Modify: `api/src/tests/test_course_crud_permissions.py`
- Modify: `api/src/tests/test_course_membership_bootstrap.py`

**Interfaces:**
- Consumes: course-code generation from Task 1.
- Produces: create response with optional `course_code` for the owner.
- Produces: `DEV_AUTO_ENROLL_ALL_COURSES` default `False`; explicit `true` remains available only for isolated development fixtures.

- [ ] **Step 1: Change the existing creation test expectation so only the creator is enrolled**

```python
def test_new_course_enrolls_only_creator_as_owner(course_api):
    response = course_api.client_for("teacher-a", "teacher").post(
        "/api/courses", json=valid_course_payload()
    )
    course_id = response.json()["id"]
    assert response.json()["course_code"]
    assert course_api.memberships.get(course_id, "teacher-a").role == "owner"
    assert course_api.memberships.get(course_id, "teacher-b") is None
    assert course_api.memberships.get(course_id, "student-a") is None
```

- [ ] **Step 2: Run the test and observe current automatic enrollment failure**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_crud_permissions.py::test_new_course_enrolls_only_creator_as_owner tests/test_course_membership_bootstrap.py -q
```

- [ ] **Step 3: Generate course code during creation and disable auto-enrollment by default**

Keep the explicit bootstrap feature functional when a test or development environment sets `DEV_AUTO_ENROLL_ALL_COURSES=true`. Remove unconditional `on_course_created()` effects from the normal production path.

- [ ] **Step 4: Run course CRUD and bootstrap regression**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_crud_permissions.py tests/test_course_membership_bootstrap.py tests/test_course_collaboration_acceptance.py -q
```

- [ ] **Step 5: Commit Task 3**

```powershell
git add Edu_AI/api/src/core/config.py Edu_AI/api/src/app/api/courses.py Edu_AI/api/src/app/services/course_membership_bootstrap.py Edu_AI/api/src/tests/test_course_crud_permissions.py Edu_AI/api/src/tests/test_course_membership_bootstrap.py
git commit -m "fix: stop automatic course enrollment"
```

### Task 4: Add Teacher Course-Code and Member Management UI

**Files:**
- Create: `src/stitch/course/members/CourseMemberPanel.tsx`
- Create: `src/stitch/course/members/courseMemberPanel.css`
- Create: `src/stitch/course/members/courseMemberPresentation.ts`
- Create: `src/stitch/course/members/courseMemberPresentation.test.ts`
- Modify: `src/stitch/api/types.ts`
- Modify: `src/stitch/api/courses.ts`
- Modify: `src/stitch/pages/CourseEdit.tsx`
- Modify: `src/stitch/pages/CourseDetail.tsx`

**Interfaces:**
- Produces: `listCourseMembers`, `addCourseMember`, `updateCourseMember`, `removeCourseMember`, `rotateCourseCode`.
- Produces: `CourseMemberPanel({courseId, initialCourseCode})` rendered only for `owner`.

- [ ] **Step 1: Write presentation and component behavior tests**

```typescript
test("student users can only be offered viewer membership", () => {
  assert.deepEqual(memberRoleOptions({ system_role: "student" }), [
    { value: "viewer", label: "学生 / 只读成员" },
  ]);
});

test("course creator cannot receive remove or role-change actions", () => {
  assert.deepEqual(memberActions({ course_role: "owner", is_course_creator: true }), []);
});
```

Add a rendered-page test proving viewers and editors do not mount the member panel and owners do.

- [ ] **Step 2: Run tests and observe missing API and component failures**

```powershell
pnpm test -- src/stitch/course/members/courseMemberPresentation.test.ts tests/frontend/coursePermissionRendering.test.ts
```

- [ ] **Step 3: Implement typed API calls and focused member panel**

The panel displays the course code, copy and rotate controls, member rows, an add-member form, role changes, and removal confirmation. Use component-local CSS. Do not modify `src/stitch/App.tsx` or global lazy-loading code.

- [ ] **Step 4: Run focused tests and production build**

```powershell
pnpm test -- src/stitch/course/members/courseMemberPresentation.test.ts tests/frontend/coursePermissionRendering.test.ts
pnpm build
```

- [ ] **Step 5: Commit Task 4**

```powershell
git add Edu_AI/src/stitch/course/members Edu_AI/src/stitch/api/types.ts Edu_AI/src/stitch/api/courses.ts Edu_AI/src/stitch/pages/CourseEdit.tsx Edu_AI/src/stitch/pages/CourseDetail.tsx
git commit -m "feat: add teacher course member management"
```

### Task 5: Add Student Course-Code Join UI

**Files:**
- Create: `src/stitch/student/courseJoin.ts`
- Create: `src/stitch/student/courseJoin.test.ts`
- Create: `src/stitch/student/components/CourseJoinDialog.tsx`
- Create: `src/stitch/student/components/courseJoinDialog.css`
- Modify: `src/stitch/student/pages/StudentHome.tsx`
- Modify: `src/stitch/api/courses.ts`
- Modify: `src/stitch/api/types.ts`

**Interfaces:**
- Produces: `normalizeCourseCodeInput(value: string) -> string`
- Produces: `joinCourse(courseCode: string) -> Promise<BackendCourse>`
- Produces: `CourseJoinDialog({open, onClose, onJoined})`

- [ ] **Step 1: Write validation and home-flow tests**

```typescript
test("course code input removes spaces and hyphens and uppercases", () => {
  assert.equal(normalizeCourseCodeInput(" k7m9-q2wp "), "K7M9Q2WP");
});

test("invalid course code is rejected before the request", () => {
  assert.equal(validateCourseCodeInput("123"), "请输入 8 位课程码");
});
```

Add a student-home integration test that asserts the joined course is appended once and the target hash is a student course-detail route.

- [ ] **Step 2: Run tests and observe missing join flow**

```powershell
pnpm test -- src/stitch/student/courseJoin.test.ts src/stitch/student/pages/StudentHome.test.ts
```

- [ ] **Step 3: Implement dialog and refresh/navigation behavior**

Show user-facing messages for invalid code, already joined, network failure, and success. Never expose backend stack traces or teacher-only actions.

- [ ] **Step 4: Run student route, permission, and build checks**

```powershell
pnpm test -- src/stitch/student/courseJoin.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/student/studentCapabilityRendering.test.ts
pnpm build
```

- [ ] **Step 5: Commit Task 5**

```powershell
git add Edu_AI/src/stitch/student/courseJoin.ts Edu_AI/src/stitch/student/courseJoin.test.ts Edu_AI/src/stitch/student/components/CourseJoinDialog.tsx Edu_AI/src/stitch/student/components/courseJoinDialog.css Edu_AI/src/stitch/student/pages/StudentHome.tsx Edu_AI/src/stitch/api/courses.ts Edu_AI/src/stitch/api/types.ts
git commit -m "feat: let students join courses by code"
```

### Task 6: Plan and Validate a Semantic Three-Level Graph

**Files:**
- Create: `api/src/app/services/course_knowledge_graph_planner.py`
- Create: `api/src/tests/services/test_course_knowledge_graph_planner.py`
- Modify: `api/src/app/services/course_knowledge_planner.py`
- Modify: `api/src/tests/services/test_course_knowledge_planner.py`
- Modify: `api/src/app/persistence/postgres_knowledge_repository.py`

**Interfaces:**
- Produces: `plan_course_graph(course: Mapping[str, Any], model=None) -> dict[str, Any]`
- Produces: `validate_course_graph_draft(graph: Mapping[str, Any]) -> GraphValidationResult`
- Produces: `iter_leaf_topics(graph) -> tuple[CourseKnowledgeTopic, ...]`

- [ ] **Step 1: Write graph tests with literal hand-checked fixtures**

```python
def test_small_course_graph_has_root_module_and_leaf_without_empty_wrappers():
    graph = plan_course_graph({
        "id": "python-control",
        "title": "Python 控制流程入门",
        "description": "学习条件判断和循环控制",
        "objectives": ["条件判断", "循环控制"],
    })
    result = validate_course_graph_draft(graph)
    assert result.valid is True
    assert result.minimum_depth >= 3
    assert {leaf["label"] for leaf in result.leaves} == {"条件判断", "循环控制"}


def test_graph_rejects_root_to_leaf_two_level_shape():
    result = validate_course_graph_draft({
        "root": {"id": "root", "label": "课程", "children": [
            {"id": "leaf", "label": "条件判断", "children": []}
        ]}
    })
    assert result.valid is False
    assert "GRAPH_MINIMUM_DEPTH" in result.error_codes
```

Also test duplicate IDs, cycles, unreachable nodes, meaningless wrapper labels, and a valid graph deeper than three levels.

- [ ] **Step 2: Run tests and observe current two-level graph failure**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_knowledge_graph_planner.py tests/services/test_course_knowledge_planner.py -q
```

- [ ] **Step 3: Implement graph planning, deterministic fallback, validation, and leaf extraction**

Use course objectives and description to make real module groupings. A model result is accepted only after schema and semantic validation. A deterministic fallback must still produce course root, meaningful module, and leaves. If the course lacks enough semantic information, return a planning error that asks the teacher to improve initialization data.

- [ ] **Step 4: Persist `graph_draft` and `leaf_topics` in the build plan and run tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_knowledge_graph_planner.py tests/services/test_course_knowledge_planner.py tests/persistence/test_postgres_knowledge_repository.py -q
```

- [ ] **Step 5: Commit Task 6**

```powershell
git add Edu_AI/api/src/app/services/course_knowledge_graph_planner.py Edu_AI/api/src/tests/services/test_course_knowledge_graph_planner.py Edu_AI/api/src/app/services/course_knowledge_planner.py Edu_AI/api/src/tests/services/test_course_knowledge_planner.py Edu_AI/api/src/app/persistence/postgres_knowledge_repository.py
git commit -m "feat: plan semantic three-level course graphs"
```

### Task 7: Acquire Chinese Sources Before English Sources

**Files:**
- Create: `api/src/app/services/course_knowledge_source_acquisition.py`
- Create: `api/src/tests/services/test_course_knowledge_source_acquisition.py`
- Modify: `api/src/app/services/course_knowledge_planner.py`
- Modify: `api/src/app/services/course_knowledge_plan_builder.py`
- Modify: `api/src/app/schemas/course.py`

**Interfaces:**
- Produces: `acquire_leaf_sources(topic, search_provider, target_count=3) -> SourceAcquisitionResult`
- Produces ordered stage records: `zh`, `en`, `generated`.

- [ ] **Step 1: Write staged acquisition tests**

```python
def test_english_search_runs_only_when_chinese_sources_are_below_target():
    calls = []
    result = acquire_leaf_sources(
        TOPIC,
        search_provider=lambda query, limit: calls.append(query) or (
            TWO_CHINESE_RESULTS if "中文" in query else TWO_ENGLISH_RESULTS
        ),
        target_count=3,
    )
    assert result.ready_candidates[:2] == TWO_CHINESE_RESULTS
    assert result.ready_candidates[2] == TWO_ENGLISH_RESULTS[0]
    assert result.stage_order == ("zh", "en")


def test_three_chinese_sources_skip_english_search():
    calls = []
    result = acquire_leaf_sources(
        TOPIC,
        search_provider=lambda query, limit: calls.append(query) or THREE_CHINESE_RESULTS,
    )
    assert len(calls) == 1
    assert result.stage_order == ("zh",)
```

Also test duplicate URL rejection per leaf, license rejection, irrelevant result rejection, and independent acquisition for different leaves.

- [ ] **Step 2: Run tests and confirm the existing single mixed search fails ordering**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_knowledge_source_acquisition.py tests/services/test_course_knowledge_planner.py -q
```

- [ ] **Step 3: Implement staged search and persist audit records**

Do not count search candidates as coverage. Coverage is calculated only after successful fetch, persistence, and RAG import. Preserve language, license, authority, relevance, rejection reason, and stage.

- [ ] **Step 4: Run planner, builder, and repository tests**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_knowledge_source_acquisition.py tests/services/test_course_knowledge_planner.py tests/services/test_course_knowledge_plan_builder.py tests/persistence/test_postgres_knowledge_repository.py -q
```

- [ ] **Step 5: Commit Task 7**

```powershell
git add Edu_AI/api/src/app/services/course_knowledge_source_acquisition.py Edu_AI/api/src/tests/services/test_course_knowledge_source_acquisition.py Edu_AI/api/src/app/services/course_knowledge_planner.py Edu_AI/api/src/app/services/course_knowledge_plan_builder.py Edu_AI/api/src/app/schemas/course.py
git commit -m "feat: prioritize Chinese course sources"
```

### Task 8: Generate and Review Missing Leaf Materials

**Files:**
- Create: `api/src/app/services/course_knowledge_generated_material.py`
- Create: `api/src/tests/services/test_course_knowledge_generated_material.py`
- Modify: `api/src/app/services/course_knowledge_plan_builder.py`
- Modify: `api/src/app/services/platform_task_handlers.py`
- Modify: `api/src/app/persistence/postgres_knowledge_repository.py`
- Modify: `api/src/tests/services/test_course_knowledge_plan_builder.py`

**Interfaces:**
- Produces: `generate_leaf_supplement(topic, course, material_kind, model) -> GeneratedMaterial`
- Produces: `review_generated_material(material, topic, course, reviewer_model) -> GeneratedMaterialReview`
- Produces: `fill_leaf_document_gap(..., target_count=3, max_regenerations=1)`

- [ ] **Step 1: Write failing generation and per-leaf publication tests**

```python
def test_builder_generates_one_labeled_chinese_supplement_for_two_ready_sources():
    result = run_build_with_sources(ready_by_leaf={"conditional": TWO_READY_DOCS})
    docs = result.documents_by_leaf["conditional"]
    assert len(docs) == 3
    assert docs[-1]["source_type"] == "model_generated"
    assert docs[-1]["content_language"] == "zh-CN"
    assert docs[-1]["quality_review"]["score"] >= 80
    assert docs[-1]["source_url"] is None


def test_builder_blocks_publish_when_one_leaf_stays_below_three_documents():
    repository = RecordingRepository()
    with pytest.raises(RuntimeError, match="叶级知识点资料不足"):
        run_build_with_sources(
            ready_by_leaf={"conditional": THREE_READY_DOCS, "loop": ONE_READY_DOC},
            generated_review_score=79,
            repository=repository,
        )
    assert repository.publish_calls == []
```

Also test fabricated URL rejection, missing required sections, fewer than 800 Chinese characters, one allowed regeneration, model outage, and generated-document metadata persistence.

- [ ] **Step 2: Run tests and observe missing fallback and weak global quality gate failures**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_knowledge_generated_material.py tests/services/test_course_knowledge_plan_builder.py -q
```

- [ ] **Step 3: Implement generation, independent review, RAG import, and leaf coverage accounting**

Generate complementary material kinds in order: concept lecture, worked example, misconceptions and practice. Use separate generation and review prompts even if the configured provider resolves to the same model. Store prompt version and review result. Never synthesize source URLs or licenses.

- [ ] **Step 4: Replace global coverage gate with graph, per-leaf, priority-trace, generated-quality, and index-integrity gates**

Build the published graph from `graph_draft`, attach document IDs only to leaves, and set root metrics with total node, leaf, Chinese, English, generated, and document counts. Publish only after all required checks pass.

- [ ] **Step 5: Run builder, repository, job, graph, and RAG regression**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/services/test_course_knowledge_generated_material.py tests/services/test_course_knowledge_plan_builder.py tests/persistence/test_postgres_knowledge_repository.py tests/course_graph tests/retrieval -q
```

- [ ] **Step 6: Commit Task 8**

```powershell
git add Edu_AI/api/src/app/services/course_knowledge_generated_material.py Edu_AI/api/src/tests/services/test_course_knowledge_generated_material.py Edu_AI/api/src/app/services/course_knowledge_plan_builder.py Edu_AI/api/src/app/services/platform_task_handlers.py Edu_AI/api/src/app/persistence/postgres_knowledge_repository.py Edu_AI/api/src/tests/services/test_course_knowledge_plan_builder.py
git commit -m "feat: guarantee qualified leaf knowledge coverage"
```

### Task 9: Present Build Coverage and Provenance in the Teacher UI

**Files:**
- Modify: `src/stitch/api/types.ts`
- Modify: `src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx`
- Create: `src/stitch/course/knowledge/courseKnowledgeCoverage.ts`
- Create: `src/stitch/course/knowledge/courseKnowledgeCoverage.test.ts`
- Modify: `src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts`

**Interfaces:**
- Produces: per-leaf presentation with `zhCount`, `enCount`, `generatedCount`, `total`, `status`.
- Consumes: build metrics and quality checks from Task 8.

- [ ] **Step 1: Write presentation tests**

```typescript
test("leaf coverage distinguishes Chinese English and AI supplements", () => {
  assert.deepEqual(presentLeafCoverage({
    leaf_title: "条件判断",
    zh_count: 2,
    en_count: 0,
    generated_count: 1,
    document_count: 3,
  }), {
    title: "条件判断",
    summary: "中文 2 · 英文 0 · AI 补充 1",
    complete: true,
  });
});
```

- [ ] **Step 2: Run tests and confirm current card lacks leaf coverage**

```powershell
pnpm test -- src/stitch/course/knowledge/courseKnowledgeCoverage.test.ts src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
```

- [ ] **Step 3: Extend the card without changing student write permissions**

Show graph depth, module count, leaf count, per-leaf coverage, source-language totals, AI supplement labels, blocked reasons, quality score, and version. The student knowledge page remains read-only and does not mount planning or build buttons.

- [ ] **Step 4: Run focused tests, full frontend tests, and build**

```powershell
pnpm test -- src/stitch/course/knowledge/courseKnowledgeCoverage.test.ts src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts src/stitch/student/studentCapabilityRendering.test.ts
pnpm test
pnpm build
```

- [ ] **Step 5: Commit Task 9**

```powershell
git add Edu_AI/src/stitch/api/types.ts Edu_AI/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx Edu_AI/src/stitch/course/knowledge/courseKnowledgeCoverage.ts Edu_AI/src/stitch/course/knowledge/courseKnowledgeCoverage.test.ts Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
git commit -m "feat: show course knowledge coverage quality"
```

### Task 10: Automated Acceptance and Real Teacher/Student E2E

**Files:**
- Create: `api/src/tests/test_course_creation_enrollment_knowledge_build_acceptance.py`
- Create: `tests/e2e/course-creation-enrollment-knowledge-build.real.spec.ts`
- Modify: `docs/acceptance/2026-08-11-course-creation-enrollment-knowledge-build.md`

**Interfaces:**
- Consumes all earlier tasks.
- Produces durable automated and human-readable acceptance evidence.

- [ ] **Step 1: Write backend acceptance with real service boundaries and controlled external adapters**

The scenario creates a teacher course, verifies only the owner is enrolled, joins a student by course code, lists the student from the owner endpoint, builds a three-level graph with two leaves, supplies fewer than three web documents for one leaf to exercise model fallback, publishes, and verifies each leaf has three ready document IDs.

- [ ] **Step 2: Run acceptance before any manual test**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_creation_enrollment_knowledge_build_acceptance.py -q
```

- [ ] **Step 3: Apply migration and run complete affected backend suite**

```powershell
D:\anaconda\envs\edu-ai\python.exe -m alembic -c alembic.ini upgrade head
D:\anaconda\envs\edu-ai\python.exe -m alembic -c alembic.ini current
D:\anaconda\envs\edu-ai\python.exe -m alembic -c alembic.ini check
D:\anaconda\envs\edu-ai\python.exe -m pytest tests/test_course_crud_permissions.py tests/test_course_membership_routes.py tests/test_course_creation_enrollment_knowledge_build_acceptance.py tests/services/test_course_code_service.py tests/services/test_course_membership_service.py tests/services/test_course_knowledge_graph_planner.py tests/services/test_course_knowledge_source_acquisition.py tests/services/test_course_knowledge_generated_material.py tests/services/test_course_knowledge_plan_builder.py tests/persistence/test_postgres_core_repositories.py tests/persistence/test_postgres_knowledge_repository.py -q
```

- [ ] **Step 4: Run full frontend quality gate**

```powershell
pnpm test
pnpm build
```

- [ ] **Step 5: Execute real browser E2E with an actual small course**

Use the teacher UI to create “Python 控制流程入门” with two explicit leaf topics. Record the generated course ID and course code. Use the student UI to join with that code. Return to the teacher UI and verify the student appears in member management. Start the knowledge build, wait for terminal success, and inspect the graph and document views from both roles.

- [ ] **Step 6: Query PostgreSQL and APIs for non-visual invariants**

Verify:

```text
course_code is unique
teacher membership = owner
student membership = viewer
minimum graph depth >= 3
every leaf has >= 3 distinct ready document ids
each model-generated document has no source_url and has review score >= 80
teacher and student graph payload versions match
```

- [ ] **Step 7: Complete the acceptance document with real IDs and evidence**

Record test course ID, course code, build ID, graph version, module count, leaf count, per-leaf Chinese/English/generated counts, automated test totals, browser console errors, and any warnings. Keep the course for user inspection.

- [ ] **Step 8: Commit acceptance evidence**

```powershell
git add Edu_AI/api/src/tests/test_course_creation_enrollment_knowledge_build_acceptance.py Edu_AI/tests/e2e/course-creation-enrollment-knowledge-build.real.spec.ts Edu_AI/docs/acceptance/2026-08-11-course-creation-enrollment-knowledge-build.md
git commit -m "test: verify course enrollment and knowledge build e2e"
```

---

## Final Verification Gate

Before reporting completion, run fresh commands and read their full output:

```powershell
git status --short
git diff --check

Set-Location D:\github\edu_ai\Edu_AI\api\src
D:\anaconda\envs\edu-ai\python.exe -m alembic -c alembic.ini current
D:\anaconda\envs\edu-ai\python.exe -m alembic -c alembic.ini check
D:\anaconda\envs\edu-ai\python.exe -m pytest -q

Set-Location D:\github\edu_ai\Edu_AI
pnpm test
pnpm build
```

Then re-read the design completion criteria and map each requirement to automated, database/API, and browser evidence. Do not claim completion if any leaf lacks three ready documents, the graph depth is below three, or the student can access a teacher mutation.
