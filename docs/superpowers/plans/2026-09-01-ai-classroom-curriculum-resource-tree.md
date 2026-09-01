# AI Classroom Curriculum Resource Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat AI classroom list with one curriculum-based resource tree where teachers review and publish resources while students learn published versions and see versioned progress.

**Architecture:** Keep the existing knowledge graph and standard-resource records as the source of truth. Add a role-safe classroom catalog projection that merges leaf resources with teacher review summaries or the current student's progress, then render that projection through focused React tree, viewer, review, and learning components. Extend the existing resource-learning domain rather than creating a second progress subsystem: practice resources receive immutable question manifests, reading resources use explicit idempotent activity events, and all progress remains keyed by student, course, resource, and version.

**Tech Stack:** React 18, TypeScript 5.6, Vite, Node test runner, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, pytest, Playwright.

---

## Scope and file map

This is one dependent feature rather than independent products: the catalog projection depends on version-safe progress, and the UI depends on that projection. Implement tasks in order.

### Backend files

- Create `Edu_AI/api/src/app/classroom_catalog/__init__.py`: package marker.
- Create `Edu_AI/api/src/app/classroom_catalog/service.py`: compose the role-safe catalog projection.
- Create `Edu_AI/api/src/app/schemas/classroom_catalog.py`: HTTP response contracts.
- Create `Edu_AI/api/src/app/api/classroom_catalog.py`: `GET /classroom-catalog` route.
- Create `Edu_AI/api/src/alembic/versions/20260901_0020_resource_learning_activity.py`: explicit-reading event storage and completion basis.
- Modify `Edu_AI/api/src/app/bootstrap.py`: register the catalog router.
- Modify `Edu_AI/api/src/app/database/models.py`: map activity events and progress completion basis.
- Modify `Edu_AI/api/src/app/resource_learning/models.py`: add manifest completion rule and progress completion basis.
- Modify `Edu_AI/api/src/app/resource_learning/manifest.py`: build immutable practice manifests.
- Modify `Edu_AI/api/src/app/resource_learning/repository.py`: calculate practice completion and persist idempotent reading activity.
- Modify `Edu_AI/api/src/app/resource_learning/service.py`: expose explicit reading activity and keep task evidence synchronized.
- Modify `Edu_AI/api/src/app/resource_learning/task_evidence.py`: allow all standard resource types, not only classroom snapshots.
- Modify `Edu_AI/api/src/app/schemas/resource_learning.py`: add activity request and completion basis response.
- Modify `Edu_AI/api/src/app/api/resource_learning.py`: add the explicit reading activity endpoint and published-version guard.
- Modify `Edu_AI/api/src/app/standard_resources/review_service.py`: freeze practice manifests before approval becomes visible.

### Frontend files

- Create `Edu_AI/src/stitch/api/classroomCatalog.ts`: catalog request.
- Modify `Edu_AI/src/stitch/api/types.ts`: catalog and generalized progress contracts.
- Modify `Edu_AI/src/stitch/api/resourceLearning.ts`: explicit reading activity request.
- Create `Edu_AI/src/stitch/course/classroomCatalog/catalogPresentation.ts`: pure tree, status, summary, selection, and deep-link helpers.
- Create `Edu_AI/src/stitch/course/classroomCatalog/catalogPresentation.test.ts`: pure helper coverage.
- Create `Edu_AI/src/stitch/course/classroomCatalog/CurriculumResourceTree.tsx`: accessible left directory.
- Create `Edu_AI/src/stitch/course/classroomCatalog/CurriculumNodeOverview.tsx`: selected-section overview.
- Create `Edu_AI/src/stitch/course/classroomCatalog/CourseResourceViewer.tsx`: resource-type dispatch.
- Create `Edu_AI/src/stitch/course/classroomCatalog/TeacherResourceReviewPanel.tsx`: version-safe approval and rejection.
- Create `Edu_AI/src/stitch/course/classroomCatalog/StudentReadingView.tsx`: direct document preview and explicit completion.
- Create `Edu_AI/src/stitch/course/classroomCatalog/StudentPracticeView.tsx`: required-question submission.
- Create `Edu_AI/src/stitch/course/classroomCatalog/StudentResourceProgressPanel.tsx`: explanatory progress display.
- Create `Edu_AI/src/stitch/course/classroomCatalog/courseClassroomCatalog.css`: desktop, drawer, focus, status, and overflow styles.
- Rewrite `Edu_AI/src/stitch/pages/ClassroomStudio.tsx`: catalog page coordinator; generation remains a contextual modal.
- Create `Edu_AI/src/stitch/pages/classroomCatalogPage.test.ts`: source-contract checks for component boundaries and role separation.
- Modify `Edu_AI/src/openmaic/classroomGenerationFlow.ts`: preserve catalog return context in player links.
- Modify `Edu_AI/src/openmaic/classroomGenerationFlow.test.ts`: verify encoded context.
- Modify `Edu_AI/src/stitch/pages/ClassroomPlayer.tsx`: return to the originating catalog selection.
- Modify `Edu_AI/src/stitch/student/routes/studentRoutes.ts`: accept `node_id` and `resource_id`.
- Modify `Edu_AI/src/stitch/shared/routes/roleCourseRouteResolver.ts`: forward catalog targets.
- Modify the corresponding route tests.
- Modify `Edu_AI/src/stitch/pages/CourseKnowledge.tsx`: remove the duplicate student resource tree.
- Modify `Edu_AI/src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`: assert the new canonical entry.
- Modify `Edu_AI/src/stitch/pages/CourseLearning.tsx` and `courseLearningPresentation.ts`: link standard snapshots to the catalog.
- Modify `Edu_AI/src/stitch/pages/courseLearningPresentation.test.ts`: verify routing.

### Acceptance files

- Create `Edu_AI/tests/e2e/classroom-catalog.spec.ts`: teacher catalog, review, responsive directory, and preview acceptance.
- Modify `Edu_AI/tests/e2e/fixtures/apiRoutes.ts`: deterministic teacher catalog fixtures.
- Modify `Edu_AI/tests/e2e/resource-learning.spec.ts`: student entry, return context, and versioned progress acceptance.
- Update `docs/acceptance/README.md` and create `docs/acceptance/AI课堂课程目录化验收_2026-09-01.md`: commands and evidence locations.

---

### Task 1: Freeze practice manifests and calculate question-only completion

**Files:**
- Modify: `Edu_AI/api/src/app/resource_learning/models.py`
- Modify: `Edu_AI/api/src/app/resource_learning/manifest.py`
- Modify: `Edu_AI/api/src/app/resource_learning/repository.py`
- Modify: `Edu_AI/api/src/app/standard_resources/review_service.py`
- Test: `Edu_AI/api/src/tests/resource_learning/test_manifest.py`
- Test: `Edu_AI/api/src/tests/resource_learning/test_service.py`
- Test: `Edu_AI/api/src/tests/standard_resources/test_review_service.py`

- [ ] **Step 1: Write failing practice-manifest tests**

Append tests that require stable question IDs, immutable scoring values, and a question-only completion rule:

```python
def test_practice_manifest_uses_required_questions_without_explanation() -> None:
    manifest = build_practice_learning_manifest({
        "course_id": "course-1",
        "material_id": "practice-1",
        "version": 2,
        "content": {"questions": [
            {"id": "q1", "type": "single", "answer": "B", "required": True},
            {"id": "q2", "type": "blank", "answer": "递归", "required": True},
        ]},
    })

    assert manifest.completion_rule == "questions_only"
    assert manifest.explanation_total_ms == 0
    assert manifest.required_question_ids == ("q1", "q2")
```

Add a service test that submits wrong but non-empty answers and expects `completed` after all required IDs are present:

```python
progress = service.submit_questions(
    "course-1", "practice-1", 2, "student-1",
    {"q1": "A", "q2": "错误答案"}, "practice-submit-1",
)
assert progress.status == "completed"
assert progress.answered_question_count == 2
assert progress.correct_count_latest == 0
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run from `Edu_AI/api/src`:

```powershell
python -m pytest tests/resource_learning/test_manifest.py tests/resource_learning/test_service.py tests/standard_resources/test_review_service.py -q
```

Expected: FAIL because `build_practice_learning_manifest` and `completion_rule` do not exist and practice approval does not freeze a manifest.

- [ ] **Step 3: Implement the manifest completion rule**

Add the last dataclass field with a backward-compatible default:

```python
CompletionRule = Literal["classroom", "questions_only"]

@dataclass(frozen=True)
class ResourceLearningManifestRecord:
    manifest_id: str
    course_id: str
    resource_id: str
    resource_version: int
    content_hash: str
    mode: ManifestMode
    scenes: tuple[ManifestScene, ...]
    questions: tuple[ManifestQuestion, ...]
    created_at: str
    completion_rule: CompletionRule = "classroom"
```

In `manifest.py`, implement a practice builder that reuses `_question_record`, `_canonical_hash`, and the existing deterministic manifest identity:

```python
def build_practice_learning_manifest(
    payload: Mapping[str, Any], *, created_at: datetime | None = None,
) -> ResourceLearningManifestRecord:
    course_id = str(payload.get("course_id") or "").strip()
    resource_id = str(payload.get("material_id") or payload.get("resource_id") or "").strip()
    resource_version = int(payload.get("version") or 0)
    if not course_id or not resource_id or resource_version <= 0:
        raise ValueError("course_id, material_id/resource_id and a positive version are required")
    content = _as_mapping(payload.get("content"))
    raw_questions = payload.get("questions") or content.get("questions") or ()
    scene_id = f"practice-{resource_id}-v{resource_version}"
    questions = tuple(
        question
        for item in _as_sequence(raw_questions)
        if (question := _question_record(_as_mapping(item), scene_id=scene_id)) is not None
    )
    required = tuple(item for item in questions if item.required)
    if not required:
        raise ValueError("practice resource requires at least one stable required question")
    identity = f"{course_id}:{resource_id}:{resource_version}"
    timestamp = created_at or datetime.now(UTC)
    return ResourceLearningManifestRecord(
        manifest_id=f"rlm_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}",
        course_id=course_id,
        resource_id=resource_id,
        resource_version=resource_version,
        content_hash=_canonical_hash(payload),
        mode="completable",
        scenes=(ManifestScene(scene_id, "exercise", 0, (), tuple(q.question_id for q in required)),),
        questions=questions,
        created_at=timestamp.isoformat(),
        completion_rule="questions_only",
    )
```

Persist `completion_rule` inside `manifest_json`, read missing values as `classroom`, and update `_recalculate_progress`:

```python
completed = (
    manifest.mode == "completable"
    and answered == required
    and (
        manifest.completion_rule == "questions_only"
        or explanation_percent >= 80.0
    )
)
```

In `StandardResourceReviewService.review`, build a classroom manifest for `classroom`, a practice manifest for `practice`, and no manifest for `study_guide`; pass the resulting immutable manifest into the existing transactional review repository.

- [ ] **Step 4: Run focused and regression tests**

```powershell
python -m pytest tests/resource_learning tests/standard_resources/test_review_service.py -q
```

Expected: PASS; classroom still requires 80% plus all questions, while practice completes after all required questions are submitted.

- [ ] **Step 5: Commit the manifest slice**

```powershell
git add Edu_AI/api/src/app/resource_learning Edu_AI/api/src/app/standard_resources/review_service.py Edu_AI/api/src/tests/resource_learning Edu_AI/api/src/tests/standard_resources/test_review_service.py
git commit -m "feat: track practice resource completion"
```

---

### Task 2: Add idempotent explicit-reading progress

**Files:**
- Create: `Edu_AI/api/src/alembic/versions/20260901_0020_resource_learning_activity.py`
- Modify: `Edu_AI/api/src/app/database/models.py`
- Modify: `Edu_AI/api/src/app/resource_learning/models.py`
- Modify: `Edu_AI/api/src/app/resource_learning/repository.py`
- Modify: `Edu_AI/api/src/app/resource_learning/service.py`
- Modify: `Edu_AI/api/src/app/resource_learning/task_evidence.py`
- Modify: `Edu_AI/api/src/app/schemas/resource_learning.py`
- Modify: `Edu_AI/api/src/app/api/resource_learning.py`
- Test: `Edu_AI/api/src/tests/resource_learning/test_database_schema.py`
- Test: `Edu_AI/api/src/tests/resource_learning/test_repository.py`
- Test: `Edu_AI/api/src/tests/resource_learning/test_api.py`
- Test: `Edu_AI/api/src/tests/resource_learning/test_task_evidence.py`

- [ ] **Step 1: Write failing schema, repository, API, and task-evidence tests**

Require the new table and progress field:

```python
assert "resource_learning_activity_events" in inspector.get_table_names()
columns = {item["name"] for item in inspector.get_columns("resource_learning_progress")}
assert "completion_basis" in columns
```

Require monotonic, idempotent explicit reading:

```python
first = repository.record_explicit_activity(
    course_id="course-1", resource_id="guide-1", resource_version=1,
    student_id="student-1", event_id="read-1", action="opened", now=NOW,
)
again = repository.record_explicit_activity(
    course_id="course-1", resource_id="guide-1", resource_version=1,
    student_id="student-1", event_id="read-1", action="opened", now=NOW,
)
done = repository.record_explicit_activity(
    course_id="course-1", resource_id="guide-1", resource_version=1,
    student_id="student-1", event_id="read-2", action="completed", now=LATER,
)
assert first.status == again.status == "in_progress"
assert done.status == "completed"
assert done.completion_basis == "explicit_read"
```

Add an API test that posts `opened` and `completed`, rejects an unapproved version, and verifies a second student cannot read the first student's record.

- [ ] **Step 2: Run tests and confirm the missing persistence path**

```powershell
python -m pytest tests/resource_learning/test_database_schema.py tests/resource_learning/test_repository.py tests/resource_learning/test_api.py tests/resource_learning/test_task_evidence.py -q
```

Expected: FAIL because the activity table, endpoint, repository method, and generalized task evidence do not exist.

- [ ] **Step 3: Add the migration and ORM models**

Create revision `20260901_0020` with `down_revision = "20260831_0019"`. Its upgrade must add nullable `completion_basis` to `resource_learning_progress` and create:

```python
op.create_table(
    "resource_learning_activity_events",
    sa.Column("event_id", sa.String(200), primary_key=True),
    sa.Column("student_id", sa.String(160), nullable=False),
    sa.Column("course_id", sa.String(200), nullable=False),
    sa.Column("resource_id", sa.String(240), nullable=False),
    sa.Column("resource_version", sa.Integer(), nullable=False),
    sa.Column("action", sa.String(32), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
)
```

Downgrade must drop the table before dropping `completion_basis`. Mirror the table in `ResourceLearningActivityEventModel` and add `completion_basis: Mapped[str | None]` to `ResourceLearningProgressModel`.

- [ ] **Step 4: Implement repository, service, schema, endpoint, and evidence behavior**

Implement `record_explicit_activity` as one transaction: return the existing projection when `event_id` already exists; otherwise insert the event, create a zero-metric progress row without requiring a manifest, set `in_progress` for `opened`, set monotonic `completed` for `completed`, and set `completion_basis = "explicit_read"`. Add `completion_basis: str | None = None` as the final field of `ResourceLearningProgressRecord`. When `_recalculate_progress` handles a manifest-backed resource, set `completion_basis = "required_questions_submitted"` for `questions_only` and `completion_basis = "classroom_requirements"` for `classroom`.

Expose this request contract:

```python
class ResourceLearningActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=200)
    action: Literal["opened", "completed"]
    occurred_at: datetime
```

Add:

```text
POST /api/courses/{course_id}/resources/{resource_id}/versions/{version}/learning/activity
```

Before recording, resolve the standard material and require `standard_kind == "study_guide"` and `approved_version == version`; return 404 for an unpublished or cross-course target. Add `completion_basis` to `ResourceLearningProgressResponse`, make `_safe_manifest` return `None` for valid manifest-less reading progress, and call `TaskResourceEvidenceAdapter.satisfy_for_progress` after completion.

Rename `_classroom_refs` to `_standard_refs` in `task_evidence.py` and include snapshots whose `origin_type == "standard"` and source type is one of `classroom`, `report`, or `quiz`.

- [ ] **Step 5: Run migration and learning-domain tests**

```powershell
python -m pytest tests/resource_learning tests/learning/test_task_resource_snapshots.py -q
```

Expected: PASS with duplicate activity IDs producing no duplicate event and every standard resource type able to satisfy same-version task evidence.

- [ ] **Step 6: Commit explicit-reading progress**

```powershell
git add Edu_AI/api/src/alembic/versions/20260901_0020_resource_learning_activity.py Edu_AI/api/src/app/database/models.py Edu_AI/api/src/app/resource_learning Edu_AI/api/src/app/schemas/resource_learning.py Edu_AI/api/src/app/api/resource_learning.py Edu_AI/api/src/tests/resource_learning Edu_AI/api/src/tests/learning/test_task_resource_snapshots.py
git commit -m "feat: record explicit reading progress"
```

---

### Task 3: Add the role-safe classroom catalog projection

**Files:**
- Create: `Edu_AI/api/src/app/classroom_catalog/__init__.py`
- Create: `Edu_AI/api/src/app/classroom_catalog/service.py`
- Create: `Edu_AI/api/src/app/schemas/classroom_catalog.py`
- Create: `Edu_AI/api/src/app/api/classroom_catalog.py`
- Modify: `Edu_AI/api/src/app/bootstrap.py`
- Test: `Edu_AI/api/src/tests/classroom_catalog/test_service.py`
- Test: `Edu_AI/api/src/tests/classroom_catalog/test_api.py`

- [ ] **Step 1: Write failing projection tests**

Seed one leaf with a published guide v1 and pending v2 plus an unpublished practice. Assert:

```python
teacher = service.build(course_id="course-1", mode="manage", student_id=None)
student = service.build(course_id="course-1", mode="learn", student_id="student-1")

assert teacher["leaves"][0]["summary"] == {"pending": 2, "published": 1}
assert teacher["leaves"][0]["resources"][0]["current_version"] == 2
assert teacher["leaves"][0]["resources"][0]["approved_version"] == 1
assert [item["material_id"] for item in student["leaves"][0]["resources"]] == ["guide-1"]
assert student["leaves"][0]["learning_summary"] == {"completed": 1, "total": 1}
```

API tests must verify an editor receives `mode=manage`, a viewer receives `mode=learn`, the viewer response contains no pending title or rejection reason, and an unaffiliated principal receives the existing course access denial.

- [ ] **Step 2: Run tests and confirm the route is absent**

```powershell
python -m pytest tests/classroom_catalog -q
```

Expected: FAIL because the package and endpoint do not exist.

- [ ] **Step 3: Implement the catalog composer**

`ClassroomCatalogService` takes a `StandardResourceService` and `ResourceLearningService`. Build from `list_course_resources(course_id, can_manage=mode == "manage")`, index student progress by `(resource_id, resource_version)`, and emit compact progress only:

```python
def _compact_progress(progress) -> dict | None:
    if progress is None:
        return None
    return {
        "resource_id": progress.resource_id,
        "resource_version": progress.resource_version,
        "status": progress.status,
        "completion_basis": progress.completion_basis,
        "explanation_coverage_percent": progress.explanation_coverage_percent,
        "answered_question_count": progress.answered_question_count,
        "required_question_count": progress.required_question_count,
        "completed_at": progress.completed_at,
        "last_activity_at": progress.last_activity_at,
    }
```

For teacher leaves, count current `pending` slots and slots with a non-null `approved_version`. For student leaves, count slots and `completed` projections. Preserve `leaf_id`, `chapter_id`, `chapter_title`, `path_titles`, resource order, current resource content for teachers, and approved-version content for students.

- [ ] **Step 4: Add Pydantic contracts and the route**

Create `ClassroomCatalogResourceResponse`, `ClassroomCatalogLeafResponse`, and `ClassroomCatalogResponse` with `mode: Literal["manage", "learn"]`. The route must use `require_course_read`, choose mode from `principal.course_role in {"owner", "editor"}`, pass `principal.user_id` only for learn mode, and return:

```text
GET /api/courses/{course_id}/classroom-catalog
```

Register `classroom_catalog_router` beside `standard_resources_router` and `resource_learning_router` in `bootstrap.py`.

- [ ] **Step 5: Run catalog and authorization tests**

```powershell
python -m pytest tests/classroom_catalog tests/test_course_route_authorization.py -q
```

Expected: PASS; student payloads contain only approved resources and the caller's compact progress.

- [ ] **Step 6: Commit the catalog API**

```powershell
git add Edu_AI/api/src/app/classroom_catalog Edu_AI/api/src/app/schemas/classroom_catalog.py Edu_AI/api/src/app/api/classroom_catalog.py Edu_AI/api/src/app/bootstrap.py Edu_AI/api/src/tests/classroom_catalog
git commit -m "feat: expose role-safe classroom catalog"
```

---

### Task 4: Add frontend catalog contracts, tree construction, and deep links

**Files:**
- Create: `Edu_AI/src/stitch/api/classroomCatalog.ts`
- Modify: `Edu_AI/src/stitch/api/types.ts`
- Modify: `Edu_AI/src/stitch/api/resourceLearning.ts`
- Create: `Edu_AI/src/stitch/course/classroomCatalog/catalogPresentation.ts`
- Create: `Edu_AI/src/stitch/course/classroomCatalog/catalogPresentation.test.ts`
- Modify: `Edu_AI/src/stitch/student/routes/studentRoutes.ts`
- Modify: `Edu_AI/src/stitch/student/routes/studentRoutes.test.ts`
- Modify: `Edu_AI/src/stitch/shared/routes/roleCourseRouteResolver.ts`
- Modify: `Edu_AI/src/stitch/shared/routes/roleCourseRouteResolver.test.ts`

- [ ] **Step 1: Write failing pure TypeScript tests**

Cover arbitrary-depth `path_titles`, current selection, search filtering, status labels, student summaries, and both role routes:

```ts
const tree = buildCurriculumResourceTree([
  leaf("leaf-1", ["数据结构", "第一章", "1.1 线性表"]),
  leaf("leaf-2", ["数据结构", "第一章", "1.2 栈"]),
]);
assert.equal(tree[0].title, "第一章");
assert.deepEqual(tree[0].children.map((item) => item.title), ["1.1 线性表", "1.2 栈"]);

assert.equal(
  buildCatalogHash("student", "course/一", "leaf-1", "guide-1"),
  "#student-classroom?course_id=course%2F%E4%B8%80&node_id=leaf-1&resource_id=guide-1",
);
assert.deepEqual(readCatalogTarget(locationHash), { nodeId: "leaf-1", resourceId: "guide-1" });
```

Also assert a leaf with no published resources reports `暂无资料`, while a 2/3 leaf reports `已完成 2/3`.

Require `filterCurriculumTree(tree, "栈")` to retain the complete ancestor path to `1.2 栈`, exclude unmatched sibling leaves, and return the unmodified tree for a blank query.

- [ ] **Step 2: Run the tests and confirm missing exports**

Run from `Edu_AI`:

```powershell
node --import tsx --test src/stitch/course/classroomCatalog/catalogPresentation.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/shared/routes/roleCourseRouteResolver.test.ts
```

Expected: FAIL because catalog types, helpers, and route parameters are absent.

- [ ] **Step 3: Add exact API contracts**

Define these discriminated contracts in `types.ts`:

```ts
export type ClassroomCatalogProgress = Pick<ResourceLearningProgress,
  "resource_id" | "resource_version" | "status" | "completion_basis" |
  "explanation_coverage_percent" | "answered_question_count" |
  "required_question_count" | "completed_at" | "last_activity_at">;

export type ClassroomCatalogResource = StandardResourceSlot & {
  progress?: ClassroomCatalogProgress | null;
};

export type ClassroomCatalogLeaf = Omit<StandardResourceLeaf, "slots"> & {
  resources: ClassroomCatalogResource[];
  summary?: { pending: number; published: number };
  learning_summary?: { completed: number; total: number };
};

export type ClassroomCatalog = {
  course_id: string;
  mode: "manage" | "learn";
  leaves: ClassroomCatalogLeaf[];
};
```

Add `getClassroomCatalog(courseId)` and `recordReadingActivity(courseId, resourceId, version, payload)` API functions. Extend `ResourceLearningProgress` with `completion_basis?: "classroom_requirements" | "required_questions_submitted" | "explicit_read" | null`.

- [ ] **Step 4: Implement pure presentation and routing helpers**

`buildCurriculumResourceTree` must drop the course-root title when `path_titles.length > 1`, preserve source order, key branch nodes by the accumulated path, and key leaves by `leaf_id`. Export `filterCurriculumTree`, `catalogResourceLabel`, `catalogResourceStatus`, `catalogLeafSummary`, `readCatalogTarget`, and `buildCatalogHash`.

Extend student and role route targets with exact query keys `node_id` and `resource_id`; never encode catalog selection into `scopeId` or `material_id`.

- [ ] **Step 5: Run the focused frontend tests**

```powershell
node --import tsx --test src/stitch/course/classroomCatalog/catalogPresentation.test.ts src/stitch/student/routes/studentRoutes.test.ts src/stitch/shared/routes/roleCourseRouteResolver.test.ts
```

Expected: PASS with Chinese IDs and titles safely encoded and round-tripped.

- [ ] **Step 6: Commit contracts and helpers**

```powershell
git add Edu_AI/src/stitch/api Edu_AI/src/stitch/course/classroomCatalog/catalogPresentation.ts Edu_AI/src/stitch/course/classroomCatalog/catalogPresentation.test.ts Edu_AI/src/stitch/student/routes Edu_AI/src/stitch/shared/routes
git commit -m "feat: add classroom catalog presentation model"
```

---

### Task 5: Build the responsive curriculum directory page

**Files:**
- Create: `Edu_AI/src/stitch/course/classroomCatalog/CurriculumResourceTree.tsx`
- Create: `Edu_AI/src/stitch/course/classroomCatalog/CurriculumNodeOverview.tsx`
- Create: `Edu_AI/src/stitch/course/classroomCatalog/courseClassroomCatalog.css`
- Rewrite: `Edu_AI/src/stitch/pages/ClassroomStudio.tsx`
- Create: `Edu_AI/src/stitch/pages/classroomCatalogPage.test.ts`

- [ ] **Step 1: Write failing page-boundary tests**

The source-contract test must require:

```ts
assert.match(page, /getClassroomCatalog/);
assert.match(page, /<CurriculumResourceTree/);
assert.match(page, /<CurriculumNodeOverview/);
assert.match(page, /<CourseResourceViewer/);
assert.match(page, /LearningResourceGenerationPanel/);
assert.doesNotMatch(page, /getCourseMaterials\(courseId, \{ materialType: "classroom"/);
assert.doesNotMatch(page, /已生成的课件/);
```

Require the tree source to contain `role="tree"`, `role="treeitem"`, `aria-expanded`, visible text statuses, roving `tabIndex`, handlers for `ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`, `Home`, and `End`, plus a mobile “课程目录” control.

- [ ] **Step 2: Run the test and confirm the old flat page fails**

```powershell
node --import tsx --test src/stitch/pages/classroomCatalogPage.test.ts
```

Expected: FAIL because `ClassroomStudio.tsx` still renders the flat generation/list page.

- [ ] **Step 3: Implement the directory and node overview**

`CurriculumResourceTree` accepts only data and callbacks:

```ts
type CurriculumResourceTreeProps = {
  nodes: CurriculumTreeNode[];
  selectedNodeId: string | null;
  selectedResourceId: string | null;
  openKeys: ReadonlySet<string>;
  onToggle: (key: string) => void;
  onSelectNode: (nodeId: string) => void;
  onSelectResource: (nodeId: string, resourceId: string) => void;
};
```

It must not fetch, review, submit answers, or mutate progress. `CurriculumNodeOverview` receives the selected leaf and mode, then shows resource counts plus either teacher review summary and generation action or student learning coverage and continue action.

- [ ] **Step 4: Rewrite `ClassroomStudioPage` as the coordinator**

Load `getClassroomCatalog`, derive and search-filter tree nodes, restore URL selection, keep ancestor branches open, and update the hash with `history.replaceState` when selection changes. Render:

```tsx
<main className="course-classroom-catalog">
  <header className="course-classroom-catalog__toolbar">...</header>
  <div className="course-classroom-catalog__layout">
    <aside className={drawerOpen ? "is-open" : ""}>...</aside>
    <section className="course-classroom-catalog__content">...</section>
  </div>
</main>
```

Teacher-only “生成学习资源” opens the existing `LearningResourceGenerationPanel`; closing or completing generation reloads the catalog. Students never receive the button. First entry shows course overview and expands the first branch without automatically playing media. First load uses a directory-shaped skeleton; catalog failure shows a retry action; resource-view failure remains inside the content panel; progress failure leaves published content accessible with “进度暂时无法同步”.

- [ ] **Step 5: Implement layout and accessibility styles**

Use `grid-template-columns: clamp(300px, 28vw, 420px) minmax(0, 1fr)`, independent vertical scrolling, visible focus rings, wrapping long titles, and text-bearing status pills. Implement roving focus so arrow keys move among visible tree items, right expands, left collapses or focuses the parent, and Home/End move to the first/last visible item. At `max-width: 900px`, render the directory as a fixed drawer controlled by “课程目录”; preserve the selected path above content.

- [ ] **Step 6: Run page, route, lint, and build checks**

```powershell
node --import tsx --test src/stitch/pages/classroomCatalogPage.test.ts src/stitch/course/classroomCatalog/catalogPresentation.test.ts
pnpm lint
pnpm build
```

Expected: all commands succeed; the production build has no TypeScript errors, and keyboard selection never triggers media playback automatically.

- [ ] **Step 7: Commit the catalog shell**

```powershell
git add Edu_AI/src/stitch/course/classroomCatalog Edu_AI/src/stitch/pages/ClassroomStudio.tsx Edu_AI/src/stitch/pages/classroomCatalogPage.test.ts
git commit -m "feat: build curriculum classroom directory"
```

---

### Task 6: Integrate teacher preview, version-safe review, and publishing

**Files:**
- Create: `Edu_AI/src/stitch/course/classroomCatalog/CourseResourceViewer.tsx`
- Create: `Edu_AI/src/stitch/course/classroomCatalog/TeacherResourceReviewPanel.tsx`
- Modify: `Edu_AI/src/stitch/pages/ClassroomStudio.tsx`
- Modify: `Edu_AI/src/stitch/course/classroomCatalog/catalogPresentation.ts`
- Modify: `Edu_AI/src/stitch/course/classroomCatalog/catalogPresentation.test.ts`
- Modify: `Edu_AI/src/stitch/pages/classroomCatalogPage.test.ts`

- [ ] **Step 1: Write failing review-state tests**

Require `teacherReviewState` to distinguish a plain published version from “published v2, pending v3”:

```ts
assert.deepEqual(teacherReviewState(resource({
  review_status: "pending", current_version: 3, approved_version: 2,
})), {
  label: "已发布第 2 版 · 第 3 版待审核",
  canReview: true,
  previewVersion: 3,
});
```

The page source test must require independent click targets for resource selection and review submission, a rejection-reason field, disabled submitting state, and `CourseMaterialArtifactPreview` reuse.

- [ ] **Step 2: Run focused tests and confirm failure**

```powershell
node --import tsx --test src/stitch/course/classroomCatalog/catalogPresentation.test.ts src/stitch/pages/classroomCatalogPage.test.ts
```

Expected: FAIL because the viewer and review panel do not exist.

- [ ] **Step 3: Implement resource-type dispatch**

`CourseResourceViewer` must use this exact dispatch:

```tsx
if (resource.standard_kind === "classroom") {
  return <ClassroomCatalogCard resource={resource} mode={mode} nodeId={nodeId} />;
}
if (mode === "learn" && resource.standard_kind === "study_guide") {
  return <StudentReadingView resource={resource} />;
}
if (mode === "learn" && resource.standard_kind === "practice") {
  return <StudentPracticeView resource={resource} />;
}
return <CourseMaterialArtifactPreview material={resource.resource!} />;
```

Teacher classroom cards link to the existing player without `resource_version`, ensuring preview does not start student tracking. Reports and practice reuse `CourseMaterialArtifactPreview`.

- [ ] **Step 4: Implement review actions**

`TeacherResourceReviewPanel` accepts the selected resource, `onChanged`, and `onError`. Show `批准并发布` and `退回修改` only for `pending`; require a trimmed rejection reason before calling:

```ts
await reviewStandardResource(courseId, resource.material_id, decision, reason.trim());
await onChanged(resource.material_id);
```

Keep the preview visible on failure, prevent duplicate submission, announce success, and reload the catalog after success. Show current and approved version numbers together when they differ.

- [ ] **Step 5: Run frontend checks**

```powershell
node --import tsx --test src/stitch/course/classroomCatalog/catalogPresentation.test.ts src/stitch/pages/classroomCatalogPage.test.ts src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts
pnpm lint
pnpm build
```

Expected: PASS; existing compact generation and standard review helpers remain valid.

- [ ] **Step 6: Commit teacher workflow**

```powershell
git add Edu_AI/src/stitch/course/classroomCatalog Edu_AI/src/stitch/pages/ClassroomStudio.tsx Edu_AI/src/stitch/pages/classroomCatalogPage.test.ts
git commit -m "feat: review resources from classroom catalog"
```

---

### Task 7: Integrate student document, practice, classroom, and progress flows

**Files:**
- Create: `Edu_AI/src/stitch/course/classroomCatalog/StudentReadingView.tsx`
- Create: `Edu_AI/src/stitch/course/classroomCatalog/StudentPracticeView.tsx`
- Create: `Edu_AI/src/stitch/course/classroomCatalog/StudentResourceProgressPanel.tsx`
- Modify: `Edu_AI/src/stitch/course/classroomCatalog/CourseResourceViewer.tsx`
- Modify: `Edu_AI/src/openmaic/classroomGenerationFlow.ts`
- Modify: `Edu_AI/src/openmaic/classroomGenerationFlow.test.ts`
- Modify: `Edu_AI/src/stitch/pages/ClassroomPlayer.tsx`
- Modify: `Edu_AI/src/stitch/pages/classroomResourceLearning.test.ts`
- Modify: `Edu_AI/src/stitch/pages/ClassroomStudio.tsx`

- [ ] **Step 1: Write failing student-flow tests**

Extend the player-link test:

```ts
assert.equal(
  buildClassroomPlayerHash("course-1", "classroom-1", {
    resourceVersion: 3,
    catalogNodeId: "leaf-1",
    catalogResourceId: "classroom-1",
  }),
  "#classroom-player?course_id=course-1&classroom_id=classroom-1&resource_version=3&catalog_node_id=leaf-1&catalog_resource_id=classroom-1",
);
```

Add source-contract assertions that `StudentReadingView` records `opened` once per mount, exposes `完成阅读`, and never computes completion from elapsed time; assert `StudentPracticeView` sends all non-empty answers through `submitResourceQuestions` and renders the returned status.

- [ ] **Step 2: Run the tests and confirm missing learning views**

```powershell
node --import tsx --test src/openmaic/classroomGenerationFlow.test.ts src/stitch/pages/classroomResourceLearning.test.ts src/stitch/pages/classroomCatalogPage.test.ts
```

Expected: FAIL because player context options and student resource views are absent.

- [ ] **Step 3: Implement explicit reading**

On first successful render of an approved guide, send one event whose ID is persisted for the current resource/version in session storage. The button sends a new `completed` event and replaces local progress with the server response:

```ts
await recordReadingActivity(courseId, resource.material_id, version, {
  event_id: activityEventId(resource.material_id, version, action),
  action,
  occurred_at: new Date().toISOString(),
});
```

Render the content with `CourseMaterialArtifactPreview`; show `学习中`, `已完成`, or `待同步`. Never use a timer as completion evidence.

- [ ] **Step 4: Implement practice submission**

Use `getQuizQuestions(resource.resource!)` for stable question order. Render radio controls for option questions and text inputs for other questions. Disable submission until every required question has a non-empty answer. Call `submitResourceQuestions` with a stable per-click idempotency key, then show answered count, required count, correctness feedback, and `已完成` when returned by the server. Do not label wrong answers as resource failure.

- [ ] **Step 5: Preserve classroom return context**

Extend `buildClassroomPlayerHash` with optional `resourceVersion`, `catalogNodeId`, and `catalogResourceId`. Parse `catalog_node_id` and `catalog_resource_id` in `ClassroomPlayerPage`; build the back link with `buildRoleCourseHash(..., "classroom-studio", ..., { node_id, resource_id })`. Teacher preview omits version; student learning includes the exact approved version.

- [ ] **Step 6: Run focused and full frontend verification**

```powershell
node --import tsx --test src/openmaic/classroomGenerationFlow.test.ts src/stitch/pages/classroomResourceLearning.test.ts src/stitch/pages/classroomCatalogPage.test.ts src/stitch/course/classroomCatalog/catalogPresentation.test.ts
pnpm test
pnpm lint
pnpm build
```

Expected: all commands pass; student progress is type-specific and classroom tracking remains student-and-version-only.

- [ ] **Step 7: Commit student learning flows**

```powershell
git add Edu_AI/src/stitch/course/classroomCatalog Edu_AI/src/openmaic/classroomGenerationFlow.ts Edu_AI/src/openmaic/classroomGenerationFlow.test.ts Edu_AI/src/stitch/pages/ClassroomPlayer.tsx Edu_AI/src/stitch/pages/classroomResourceLearning.test.ts Edu_AI/src/stitch/pages/ClassroomStudio.tsx
git commit -m "feat: learn catalog resources by type"
```

---

### Task 8: Make the catalog canonical and remove duplicate resource entry points

**Files:**
- Modify: `Edu_AI/src/stitch/pages/CourseKnowledge.tsx`
- Modify: `Edu_AI/src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`
- Modify: `Edu_AI/src/stitch/pages/courseLearningPresentation.ts`
- Modify: `Edu_AI/src/stitch/pages/courseLearningPresentation.test.ts`
- Modify: `Edu_AI/src/stitch/pages/CourseLearning.tsx`
- Modify: `Edu_AI/src/stitch/student/pages/studentRecentLearning.ts`
- Modify: `Edu_AI/src/stitch/student/pages/studentRecentLearning.test.ts`

- [ ] **Step 1: Write failing canonical-entry tests**

Update the knowledge-page assertion:

```ts
assert.doesNotMatch(knowledgePage, /<StandardLearningResources\s+readOnly/);
assert.match(knowledgePage, /<KnowledgeDocumentsView\s+readOnly=\{isStudent\}/);
```

Add a routing helper test:

```ts
assert.equal(
  buildLearningResourceHref("student", "course-1", {
    origin_type: "standard", scope_id: "leaf-1",
    material_id: "guide-1", material_type: "report",
  }),
  "#student-classroom?course_id=course-1&node_id=leaf-1&resource_id=guide-1",
);
```

Also assert non-standard shared resources continue to route to `student-resources` or `resources`.

- [ ] **Step 2: Run tests and confirm the duplicate entry remains**

```powershell
node --import tsx --test src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts src/stitch/pages/courseLearningPresentation.test.ts src/stitch/student/pages/studentRecentLearning.test.ts
```

Expected: FAIL because the student knowledge page still renders `StandardLearningResources` and task links still target resource management.

- [ ] **Step 3: Remove duplicate rendering and centralize task links**

Keep `CourseKnowledgePage` limited to `KnowledgeDocumentsView`. Add `buildLearningResourceHref` to `courseLearningPresentation.ts`: standard resources route to the classroom catalog using `scope_id` as `node_id`; other resources retain the current resources-page route. Use the helper in teacher `ResourceLinks` and student `openResource` when no immutable task snapshot is being shown.

- [ ] **Step 4: Update recent-learning behavior**

Treat `student-classroom` as the course's resource-learning destination. Preserve current recent-course tracking, but label that route “AI课堂” and ensure returning from recent learning opens the catalog rather than course knowledge.

- [ ] **Step 5: Run navigation regression tests**

```powershell
node --import tsx --test src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts src/stitch/pages/courseLearningPresentation.test.ts src/stitch/student/pages/studentRecentLearning.test.ts src/stitch/student/routes/studentRoutes.test.ts
pnpm test
```

Expected: PASS; course knowledge, resource management, learning tasks, and AI classroom now have distinct responsibilities.

- [ ] **Step 6: Commit entry-point cleanup**

```powershell
git add Edu_AI/src/stitch/pages/CourseKnowledge.tsx Edu_AI/src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts Edu_AI/src/stitch/pages/CourseLearning.tsx Edu_AI/src/stitch/pages/courseLearningPresentation.ts Edu_AI/src/stitch/pages/courseLearningPresentation.test.ts Edu_AI/src/stitch/student/pages/studentRecentLearning.ts Edu_AI/src/stitch/student/pages/studentRecentLearning.test.ts
git commit -m "refactor: make AI classroom the resource learning entry"
```

---

### Task 9: Add browser acceptance, migration verification, and release evidence

**Files:**
- Create: `Edu_AI/tests/e2e/classroom-catalog.spec.ts`
- Modify: `Edu_AI/tests/e2e/fixtures/apiRoutes.ts`
- Modify: `Edu_AI/tests/e2e/resource-learning.spec.ts`
- Create: `docs/acceptance/AI课堂课程目录化验收_2026-09-01.md`
- Modify: `docs/acceptance/README.md`

- [ ] **Step 1: Add deterministic teacher catalog fixtures**

Extend `installTeacherApiRoutes` with `GET /classroom-catalog` returning two chapters, a pending guide, published classroom, rejected practice, and a leaf with no generated resources. The review POST must mutate fixture state so the next catalog read returns `approved_version: 1` and `review_status: "approved"`.

- [ ] **Step 2: Write teacher browser acceptance**

The new Playwright spec must verify:

```ts
await teacherPage.goto("/#classroom-studio?course_id=course-physics");
await expect(teacherPage.getByRole("tree", { name: "课程目录" })).toBeVisible();
await teacherPage.getByRole("treeitem", { name: /力学/ }).click();
await teacherPage.getByText("力学学习指南").click();
await expect(teacherPage.getByRole("heading", { name: "力学学习指南" })).toBeVisible();
await teacherPage.getByRole("button", { name: "批准并发布" }).click();
await expect(teacherPage.getByText("已发布")).toBeVisible();
```

At 1024px, open the “课程目录” drawer, select a resource, assert the drawer closes, and assert document content does not create horizontal page overflow. At desktop width, focus the tree and use ArrowRight/ArrowDown/Enter to select a resource; verify the visible focus and selected state move without automatic playback.

- [ ] **Step 3: Update real student resource-learning acceptance**

Change the entry URL in `resource-learning.spec.ts` from `student-course-knowledge` to `student-classroom`. Locate the seeded leaf in the new tree, verify the player back button returns to the same `node_id` and `resource_id`, and retain all existing checks for 80% coverage, required questions, wrong-answer completion, restart recovery, and version isolation.

- [ ] **Step 4: Run backend schema and focused browser acceptance**

From `Edu_AI/api/src`:

```powershell
python -m pytest tests/resource_learning/test_database_schema.py tests/resource_learning tests/classroom_catalog tests/standard_resources -q
```

From `Edu_AI`:

```powershell
pnpm exec playwright test tests/e2e/classroom-catalog.spec.ts --project=desktop1366 --project=compact1024
pnpm exec playwright test tests/e2e/resource-learning.spec.ts --project=desktop1366
```

Expected: backend suites pass; teacher catalog passes at desktop and compact widths; the real student loop passes with the new catalog entry.

- [ ] **Step 5: Run the complete release gate**

```powershell
cd D:\Edu_AI_1\Edu_AI\api\src
python -m pytest -q
cd D:\Edu_AI_1\Edu_AI
pnpm test
pnpm lint
pnpm build
pnpm exec playwright test tests/e2e/classroom-catalog.spec.ts tests/e2e/resource-learning.spec.ts tests/e2e/course-shell.spec.ts --project=desktop1366 --project=compact1024
```

Expected: every command exits 0. Record actual command output, screenshots, known environmental requirements, and the exact commit in `docs/acceptance/AI课堂课程目录化验收_2026-09-01.md`; link it from `docs/acceptance/README.md`.

- [ ] **Step 6: Commit acceptance evidence**

```powershell
git add Edu_AI/tests/e2e docs/acceptance
git commit -m "test: verify curriculum classroom workflow"
```

---

## Spec coverage matrix

| Design requirement | Implementation task |
| --- | --- |
| One curriculum resource tree | Tasks 3–5 |
| Shared tree, role-specific projection | Tasks 3–5 |
| Teacher preview, reject, approve and publish | Tasks 1, 3, 6 |
| Student sees published versions only | Tasks 3, 4, 7 |
| AI classroom opens existing player | Tasks 6–7 |
| Documents preview in place and complete explicitly | Tasks 2, 6–7 |
| Practice completes after all required submissions | Tasks 1, 7 |
| Version isolation and old published version continuity | Tasks 1–3, 7, 9 |
| Resource, section, and course learning coverage | Tasks 3–5 |
| Deep links and player return context | Tasks 4, 7–8 |
| Remove duplicate student resource entry | Task 8 |
| Permission, idempotency, sanitization, accessibility | Tasks 2–7, 9 |
| Responsive directory and failure isolation | Tasks 5, 9 |
| Automated and real end-to-end evidence | Task 9 |

## Execution notes

- Preserve unrelated user changes; stage only files listed by the current task.
- Do not combine teacher review state with student progress state in a shared enum.
- Do not create a synthetic mastery percentage. Directory summaries remain completed-resource counts.
- Do not let teacher preview create `resource_version` tracking parameters.
- Do not expose pending material content in the student catalog response, even briefly.
- If an existing test encodes the old duplicated entry, update it in Task 8 rather than maintaining two canonical student paths.
