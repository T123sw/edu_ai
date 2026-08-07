# Personal-to-Course Resource Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every newly generated resource private to its creator by default, then let teachers publish a sanitized, stable course snapshot that every member of that course can read.

**Architecture:** Keep personal originals and course publications in the existing generated-material domain, distinguished by `visibility` and stable publication provenance. Add a focused publication service for allowlisted manifest copying, artifact isolation, idempotent updates, and withdrawal; keep HTTP routes responsible only for authentication, course capability checks, and error mapping. The resource center consumes explicit `mine` and `course` list spaces and derives all labels/actions from pure presentation helpers.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, file-backed `CourseStorageManager`, pytest; React 18, TypeScript, Vite, Node test runner, Playwright visual regression.

## Global Constraints

- New generated materials default to `visibility=private`; legacy manifests missing `visibility` continue to normalize as `course`.
- A private resource is visible and mutable only by `owner_user_id`; course capabilities never bypass that boundary.
- Publishing requires the source owner and course `manage_resources`; students/viewers cannot publish.
- A publication is an independent snapshot with a stable ID and isolated artifact copies; changing the private original never changes the publication until republished.
- Publication uses an allowlist and never copies `source_snapshot`, `config_snapshot`, prompts, conversations, credentials, absolute paths, or private document content.
- `space=mine|course|all` is server-filtered after authentication; omitted `space` remains `all` for compatibility.
- Student UI is out of scope, but API authorization must enforce student read-only behavior.
- Each task ends with focused tests and an independent Git commit; unrelated dirty-worktree files are never staged.

---

## File Structure

- `api/src/core/course_storage.py`: storage normalization, visibility filtering, resource ownership checks, stable publication persistence primitives.
- `api/src/app/services/material_publication_service.py`: publication manifest allowlist, stable ID, artifact copying, idempotent publish/update/withdraw orchestration.
- `api/src/app/schemas/course.py`: publication response schema and material-space validation types.
- `api/src/app/api/courses.py`: authenticated list/publish/withdraw endpoints and resource-aware mutations.
- `api/src/tests/core/test_course_material_permissions.py`: default privacy, space filtering, ownership mutation regression tests.
- `api/src/tests/services/test_material_publication_service.py`: real-file publication, sanitization, idempotence, update, rollback, path safety and withdrawal tests.
- `api/src/tests/chat/test_course_scope_routes.py`: route contracts and cross-principal authorization tests.
- `src/stitch/api/types.ts`: typed visibility/publication metadata.
- `src/stitch/api/courses.ts`: `space` query and publish/withdraw clients.
- `src/stitch/api/courseResourceSpaces.ts`: pure UI state and action derivation.
- `src/stitch/api/courseResourceSpaces.test.ts`: behavior tests for tabs, publication state and role actions.
- `src/stitch/pages/CourseResources.tsx`: resource-space tabs, publication controls, per-space counts and feedback.
- `src/components/teacher/ChatPanel.tsx`: private-by-default generation completion copy.
- `tests/e2e/visual-regression.spec.ts-snapshots/*course-resources*`: approved responsive visual baselines.

---

### Task 1: P0 Storage Privacy and Explicit Spaces

**Files:**
- Modify: `api/src/core/course_storage.py`
- Modify: `api/src/tests/core/test_course_material_manifest.py`
- Modify: `api/src/tests/core/test_course_material_permissions.py`
- Modify: `api/src/tests/core/test_course_storage_generated_materials.py`

**Interfaces:**
- Consumes: existing `save_generated_material`, `_normalize_material_manifest`, `_material_owner_matches`.
- Produces: `MaterialSpace = Literal["mine", "course", "all"]`; `list_generated_materials(course_id, material_type=None, *, scope_type=None, scope_ids=None, aggregate=False, owner_user_id=None, space="all")`; `get_stored_generated_material(course_id, material_type, material_id)` for trusted service use; private-by-default new saves.

- [ ] **Step 1: Write the failing storage tests**

Add tests with real files and literal expectations:

```python
def test_new_owned_material_defaults_to_private(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1", "report", "draft-1", {"title": "draft"},
        owner_user_id="teacher-a",
    )
    mine = manager.get_generated_material(
        "course-1", "report", "draft-1", owner_user_id="teacher-a"
    )
    assert mine["visibility"] == "private"
    assert manager.get_generated_material(
        "course-1", "report", "draft-1", owner_user_id="teacher-b"
    ) is None

def test_material_spaces_return_only_requested_visibility(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    assert manager.save_generated_material(
        "course-1", "report", "private-a", {"title": "mine"},
        owner_user_id="teacher-a", visibility="private",
    )
    assert manager.save_generated_material(
        "course-1", "report", "private-b", {"title": "other"},
        owner_user_id="teacher-b", visibility="private",
    )
    assert manager.save_generated_material(
        "course-1", "report", "shared", {"title": "shared"},
        owner_user_id="teacher-a", visibility="course",
    )
    assert [m["material_id"] for m in manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a", space="mine"
    )] == ["private-a"]
    assert [m["material_id"] for m in manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a", space="course"
    )] == ["shared"]
    assert {m["material_id"] for m in manager.list_generated_materials(
        "course-1", owner_user_id="teacher-a", space="all"
    )} == {"private-a", "shared"}
```

Update the existing manifest expectation from `course` to `private` only for newly owned saves. Keep the legacy-no-visibility test expecting `course`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m pytest api/src/tests/core/test_course_material_manifest.py api/src/tests/core/test_course_material_permissions.py api/src/tests/core/test_course_storage_generated_materials.py -q
```

Expected: failures show new saves are still `course` and `space` is not accepted.

- [ ] **Step 3: Implement the minimal storage behavior**

Implement these rules:

```python
MaterialSpace = Literal["mine", "course", "all"]

def _matches_material_space(material: dict, *, space: MaterialSpace) -> bool:
    visibility = str(material.get("visibility") or "course")
    if space == "mine":
        return visibility == "private"
    if space == "course":
        return visibility == "course"
    return True
```

In `save_generated_material`, use `private` when the call has an authenticated owner and neither the argument nor existing record provides visibility. Preserve existing visibility on updates. Reject unsupported spaces with `ValueError`. Do not change `_normalize_material_manifest`'s legacy default of `course`.

Add a trusted raw getter that normalizes but does not apply user visibility; keep it internal to Python services and never expose it directly through HTTP.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add -- api/src/core/course_storage.py api/src/tests/core/test_course_material_manifest.py api/src/tests/core/test_course_material_permissions.py api/src/tests/core/test_course_storage_generated_materials.py
git commit -m "feat: make generated resources private by default"
```

---

### Task 2: P0 Publication Domain Service

**Files:**
- Create: `api/src/app/services/material_publication_service.py`
- Create: `api/src/tests/services/test_material_publication_service.py`
- Modify: `api/src/core/course_storage.py`

**Interfaces:**
- Consumes: `CourseStorageManager`, normalized source manifest, storage lock and atomic JSON/file helpers.
- Produces:

```python
@dataclass(frozen=True)
class PublicationResult:
    action: Literal["published", "updated", "unchanged"]
    source_material_id: str
    material: dict[str, Any]

class MaterialPublicationService:
    # publish(course_id, material_type, material_id, owner_user_id)
    # returns PublicationResult or raises MaterialPublicationError
    # withdraw(course_id, material_type, published_material_id)
    # returns the removed publication manifest or raises MaterialPublicationError
```

- [ ] **Step 1: Write failing publication behavior tests**

Cover these real-file behaviors:

```python
def test_publish_creates_sanitized_independent_course_snapshot(tmp_path):
    manager, source = private_report_with_attachment(tmp_path)
    result = MaterialPublicationService(manager).publish(
        course_id="course-1", material_type="report",
        material_id=source["material_id"], owner_user_id="teacher-a",
    )
    assert result.action == "published"
    assert result.material["visibility"] == "course"
    assert result.material["owner_user_id"] is None
    assert result.material["published_from_owner_user_id"] == "teacher-a"
    assert result.material["published_from_version"] == 1
    assert "source_snapshot" not in result.material
    assert "config_snapshot" not in result.material
    assert Path(result.material["artifact_paths"][0]).parts[0:2] == (
        "generated_materials", "published"
    )

def test_republish_is_unchanged_then_updates_same_snapshot(tmp_path):
    manager, source = private_report_with_attachment(tmp_path)
    service = MaterialPublicationService(manager)
    first = service.publish(
        course_id="course-1", material_type="report",
        material_id=source["material_id"], owner_user_id="teacher-a",
    )
    unchanged = service.publish(
        course_id="course-1", material_type="report",
        material_id=source["material_id"], owner_user_id="teacher-a",
    )
    assert unchanged.action == "unchanged"
    assert unchanged.material["material_id"] == first.material["material_id"]
    assert unchanged.material["version"] == 1
    assert manager.rename_generated_material(
        "course-1", "report", source["material_id"], "revised",
        owner_user_id="teacher-a",
    )
    updated = service.publish(
        course_id="course-1", material_type="report",
        material_id=source["material_id"], owner_user_id="teacher-a",
    )
    assert updated.action == "updated"
    assert updated.material["material_id"] == first.material["material_id"]
    assert updated.material["version"] == 2
    assert updated.material["title"] == "revised"

def test_publish_rejects_non_owner_without_revealing_source(tmp_path):
    manager, source = private_report_with_attachment(tmp_path)
    with pytest.raises(MaterialPublicationError) as raised:
        MaterialPublicationService(manager).publish(
            course_id="course-1", material_type="report",
            material_id=source["material_id"], owner_user_id="teacher-b",
        )
    assert raised.value.code == "MATERIAL_NOT_FOUND"

def test_publish_rejects_artifact_path_outside_course_root(tmp_path):
    manager, source = private_report_with_attachment(tmp_path)
    manager.update_generated_material_internal(
        "course-1", "report", source["material_id"],
        {"artifact_paths": ["../outside.txt"]},
    )
    with pytest.raises(MaterialPublicationError) as raised:
        MaterialPublicationService(manager).publish(
            course_id="course-1", material_type="report",
            material_id=source["material_id"], owner_user_id="teacher-a",
        )
    assert raised.value.code == "MATERIAL_ARTIFACT_UNSAFE"

def test_withdraw_removes_snapshot_but_keeps_private_source(tmp_path):
    manager, source = private_report_with_attachment(tmp_path)
    service = MaterialPublicationService(manager)
    published = service.publish(
        course_id="course-1", material_type="report",
        material_id=source["material_id"], owner_user_id="teacher-a",
    )
    removed = service.withdraw(
        course_id="course-1", material_type="report",
        published_material_id=published.material["material_id"],
    )
    assert removed["material_id"] == published.material["material_id"]
    assert manager.get_stored_generated_material(
        "course-1", "report", published.material["material_id"]
    ) is None
    assert manager.get_generated_material(
        "course-1", "report", source["material_id"], owner_user_id="teacher-a"
    ) is not None
```

For rollback, monkeypatch the final publication-manifest write to raise `OSError("disk full")`, assert the publish call raises `MATERIAL_PUBLICATION_INVALID`, then assert the previously published manifest bytes and artifact bytes are unchanged.

Use literal secrets such as `sk-private-test-value`, `C:\\Users\\alice\\private.md`, and `PRIVATE_DOCUMENT_BODY` and assert they are absent from the serialized publication manifest and copied artifacts unless they are the final artifact content itself.

- [ ] **Step 2: Run the new service tests and verify RED**

Run:

```powershell
python -m pytest api/src/tests/services/test_material_publication_service.py -q
```

Expected: import fails because the service does not exist.

- [ ] **Step 3: Implement stable ID and allowlisted snapshot construction**

Use a deterministic ID:

```python
digest = hashlib.sha256(
    f"{course_id}\0{owner_user_id}\0{material_type}\0{source_id}".encode("utf-8")
).hexdigest()[:20]
published_id = f"published-{digest}"
```

Build the new manifest from a top-level allowlist plus resource-type content allowlists. Explicitly add publication provenance; never start with `dict(source)`.

- [ ] **Step 4: Implement isolated artifact copying and atomic replacement**

Copy only validated course-relative files into:

```text
generated_materials/published/{material_type}/{published_id}/
```

Resolve every source against the course root and require `relative_to(course_root)`. Copy into a sibling temporary directory, write the publication manifest, then atomically replace the final directory. On failure, delete only the temporary directory and retain the previous publication.

- [ ] **Step 5: Implement idempotent update and withdrawal**

Return `unchanged` when `published_from_version` equals the current private source version. On update, retain `material_id`, increment publication `version`, replace artifacts atomically, and update the private source publication-link fields. Withdrawal deletes only publication manifest/artifacts and clears source link fields through an internal storage method.

- [ ] **Step 6: Run service and storage tests and verify GREEN**

Run:

```powershell
python -m pytest api/src/tests/services/test_material_publication_service.py api/src/tests/core/test_course_material_permissions.py api/src/tests/core/test_course_material_manifest.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 2**

```powershell
git add -- api/src/app/services/material_publication_service.py api/src/tests/services/test_material_publication_service.py api/src/core/course_storage.py
git commit -m "feat: publish private resources as course snapshots"
```

---

### Task 3: P0 Authenticated Material API and Resource-Aware Mutations

**Files:**
- Modify: `api/src/app/schemas/course.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `api/src/app/services/course_access.py`
- Modify: `api/src/tests/chat/test_course_scope_routes.py`
- Modify: `api/src/tests/test_course_access.py`

**Interfaces:**
- Consumes: `MaterialPublicationService`, `CoursePrincipal`, `ROLE_CAPABILITIES`, storage `space` filter.
- Produces:

```python
class MaterialPublicationResponse(BaseModel):
    action: Literal["published", "updated", "unchanged"]
    source_material_id: str
    material: dict[str, Any]

def can_manage_course_resources(principal: CoursePrincipal) -> bool:
    return "manage_resources" in ROLE_CAPABILITIES[principal.course_role]
```

- [ ] **Step 1: Write failing API and authorization tests**

Test route functions with real storage and literal principals. The tests must assert these exact outcomes:

```python
assert [m["material_id"] for m in get_course_materials(
    "course-1", space="mine", principal=teacher_a
)] == ["private-a"]
assert [m["material_id"] for m in get_course_materials(
    "course-1", space="course", principal=teacher_b
)] == ["shared"]

published = publish_course_material(
    "course-1", "report", "private-a", principal=teacher_a
)
assert published.action == "published"

with pytest.raises(HTTPException) as viewer_error:
    publish_course_material(
        "course-1", "report", "private-a", principal=viewer
    )
assert viewer_error.value.status_code == 403

with pytest.raises(HTTPException) as other_teacher_error:
    publish_course_material(
        "course-1", "report", "private-a", principal=teacher_b
    )
assert other_teacher_error.value.status_code == 404
```

Add separate mutation assertions: teacher B receives 404 when renaming teacher A's private resource; teacher B can rename the published course snapshot; viewer receives 403 when renaming the published snapshot; withdrawing the snapshot leaves teacher A's private source readable by teacher A.

- [ ] **Step 2: Run route tests and verify RED**

Run:

```powershell
python -m pytest api/src/tests/chat/test_course_scope_routes.py api/src/tests/test_course_access.py -q
```

Expected: missing `space`, publish and withdrawal contracts fail.

- [ ] **Step 3: Add list-space and publication routes**

Add `space: Literal["mine", "course", "all"] = "all"` to the list route. Add:

```python
@router.post("/{course_id}/materials/{material_type}/{material_id}/publish")
def publish_course_material(
    course_id: str, material_type: str, material_id: str,
    principal: CoursePrincipal = Depends(require_course_manage_resources),
) -> MaterialPublicationResponse:
    result = _material_publications().publish(
        course_id=course_id, material_type=material_type,
        material_id=material_id, owner_user_id=principal.user_id,
    )
    return MaterialPublicationResponse(**dataclasses.asdict(result))

@router.delete("/{course_id}/materials/{material_type}/{material_id}/publication")
def withdraw_course_material(
    course_id: str, material_type: str, material_id: str,
    principal: CoursePrincipal = Depends(require_course_manage_resources),
) -> dict[str, bool]:
    _material_publications().withdraw(
        course_id=course_id, material_type=material_type,
        published_material_id=material_id,
    )
    return {"ok": True}
```

Map inaccessible private sources to 404 `MATERIAL_NOT_FOUND`; map unsafe artifacts to 422 `MATERIAL_ARTIFACT_UNSAFE`; use 409 for invalid publication state.

- [ ] **Step 4: Make mutations resource-aware**

Change rename, pin and delete to depend on `require_course_read`, load the authorized resource using the current principal, then enforce:

```python
if material["visibility"] == "private":
    allowed = material["owner_user_id"] == principal.user_id
else:
    allowed = can_manage_course_resources(principal)
```

Return 404 for inaccessible private resources and 403 for visible course resources lacking management permission.

- [ ] **Step 5: Protect preview/download/integrity endpoints with the same decision**

Audit every material endpoint in `courses.py` around preview, download, generated file, rename, pin, delete and integrity. Pass `principal.user_id` to storage and never call a raw getter from a route.

- [ ] **Step 6: Run route, access and storage suites and verify GREEN**

Run:

```powershell
python -m pytest api/src/tests/chat/test_course_scope_routes.py api/src/tests/test_course_access.py api/src/tests/core/test_course_material_permissions.py api/src/tests/services/test_material_publication_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 3**

```powershell
git add -- api/src/app/schemas/course.py api/src/app/api/courses.py api/src/app/services/course_access.py api/src/tests/chat/test_course_scope_routes.py api/src/tests/test_course_access.py
git commit -m "feat: expose secure material publication APIs"
```

---

### Task 4: P1 Typed Frontend Resource-Space Model

**Files:**
- Modify: `src/stitch/api/types.ts`
- Modify: `src/stitch/api/courses.ts`
- Create: `src/stitch/api/courseResourceSpaces.ts`
- Create: `src/stitch/api/courseResourceSpaces.test.ts`

**Interfaces:**
- Produces:

```typescript
export type CourseMaterialVisibility = "private" | "course";
export type CourseMaterialSpace = "mine" | "course";
export type PublicationAction = "published" | "updated" | "unchanged";

export function getCourseMaterials(
  courseId: string,
  options?: CourseMaterialsScopeOptions & { space?: CourseMaterialSpace | "all" },
): Promise<CourseMaterial[]>;

export function publishCourseMaterial(
  courseId: string, materialType: string, materialId: string,
): Promise<MaterialPublicationResponse>;
export function withdrawCourseMaterial(
  courseId: string, materialType: string, materialId: string,
): Promise<{ ok: boolean }>;
export function getMaterialPublicationPresentation(
  material: CourseMaterial, role: CourseRole | null,
): {
  visibilityLabel: string;
  primaryAction: "publish" | "update" | null;
  primaryLabel: string | null;
};
```

- [ ] **Step 1: Write failing pure behavior tests**

```typescript
test("private unpublished material offers publish", () => {
  assert.deepEqual(getMaterialPublicationPresentation(privateV1, "editor"), {
    visibilityLabel: "仅自己可见",
    primaryAction: "publish",
    primaryLabel: "发布到课程",
  });
});

test("changed private material offers update publication", () => {
  assert.equal(getMaterialPublicationPresentation({
    ...privateV1,
    version: 2,
    published_material_id: "published-1",
    published_version: 1,
  }, "editor").primaryAction, "update");
});

test("viewer never receives publication or course management actions", () => {
  assert.equal(
    getMaterialPublicationPresentation(privateV1, "viewer").primaryAction,
    null,
  );
});

test("course material is labelled shared", () => {
  const presentation = getMaterialPublicationPresentation({
    ...privateV1,
    visibility: "course",
    owner_user_id: null,
    published_from_owner_user_id: "teacher-a",
  }, "editor");
  assert.equal(presentation.visibilityLabel, "课程共享");
  assert.equal(presentation.primaryAction, null);
});
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
node --import tsx --test src/stitch/api/courseResourceSpaces.test.ts
```

Expected: module/functions do not exist.

- [ ] **Step 3: Implement types, clients and pure presentation helpers**

Add publication fields to `CourseMaterial`; append `space` to list query; add POST publish and DELETE publication clients. Keep role/action decisions in the pure helper, not inline in JSX.

- [ ] **Step 4: Run tests and verify GREEN**

Run the command from Step 2. Expected: all tests pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add -- src/stitch/api/types.ts src/stitch/api/courses.ts src/stitch/api/courseResourceSpaces.ts src/stitch/api/courseResourceSpaces.test.ts
git commit -m "feat: model personal and shared resource spaces"
```

---

### Task 5: P1 Course Resource Center UI

**Files:**
- Modify: `src/stitch/pages/CourseResources.tsx`
- Modify: `src/stitch/pages/courseResourcesManagement.test.ts`

**Interfaces:**
- Consumes: `useCourseRoute().courseRole`, `getCourseMaterials(courseId, { space })`, publication clients and presentation helper.
- Produces: accessible `mine/course` tab state, split counts, publication/update/withdraw flows and private/shared status labels.

- [ ] **Step 1: Add a failing UI-state regression test around extracted behavior**

Add `applyPublicationResult(personalMaterials, sharedMaterials, result)` to `courseResourceSpaces.ts`. Test that it preserves the private source array and inserts or replaces only the matching stable ID in the shared array.

- [ ] **Step 2: Run focused frontend tests and verify RED**

Run:

```powershell
node --import tsx --test src/stitch/api/courseResourceSpaces.test.ts src/stitch/pages/courseResourcesManagement.test.ts
```

Expected: publication state behavior is absent.

- [ ] **Step 3: Implement the two resource spaces**

Add `resourceSpace` state defaulting to `mine`; load each space explicitly; retain per-space caches/counts; render:

```tsx
<div role="tablist" aria-label="资源空间">
  <button role="tab" aria-selected={resourceSpace === "mine"}>我的资源</button>
  <button role="tab" aria-selected={resourceSpace === "course"}>课程共享</button>
</div>
```

Keep resource-type filters secondary. Clear or reselect `activeKey` safely when switching space.

- [ ] **Step 4: Implement publication actions and feedback**

Private resource: render “发布到课程”, “更新发布” or non-clickable “已发布”. Course snapshot: teachers with `manage_resources` get “撤回课程”; viewers get no mutation controls. Disable duplicate submission; preserve active selection on errors; confirm withdrawal with copy that the personal original remains.

- [ ] **Step 5: Run focused tests, ESLint and build**

Run:

```powershell
node --import tsx --test src/stitch/api/courseResourceSpaces.test.ts src/stitch/pages/courseResourcesManagement.test.ts
pnpm exec eslint src/stitch/pages/CourseResources.tsx src/stitch/api/courseResourceSpaces.ts src/stitch/api/courses.ts src/stitch/api/types.ts
pnpm build
```

Expected: tests pass, ESLint exits 0, build exits 0.

- [ ] **Step 6: Commit Task 5**

```powershell
git add -- src/stitch/pages/CourseResources.tsx src/stitch/pages/courseResourcesManagement.test.ts src/stitch/api/courseResourceSpaces.ts src/stitch/api/courseResourceSpaces.test.ts
git commit -m "feat: separate personal and shared course resources"
```

---

### Task 6: P1 Generation Feedback and Responsive Visual Acceptance

**Files:**
- Modify: `src/components/teacher/ChatPanel.tsx`
- Create: `src/components/teacher/generationSavedMessage.ts`
- Create: `src/components/teacher/generationSavedMessage.test.ts`
- Modify: `tests/e2e/visual-regression.spec.ts-snapshots/*course-resources*`
- Create: `docs/superpowers/verification/2026-08-07-personal-resource-publication-verification.md`

**Interfaces:**
- Consumes: completed private resource result and resource-center route target.
- Produces: consistent private-default completion copy and visual/verification evidence.

- [ ] **Step 1: Write a failing completion-copy behavior test**

Create the message builder and assert the user-visible result:

```typescript
assert.equal(
  buildGenerationSavedMessage({ visibility: "private" }),
  "生成完成，已保存到“我的资源”，仅你可见。",
);
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
node --import tsx --test src/components/teacher/generationSavedMessage.test.ts
```

Expected: import fails because the message builder does not exist.

- [ ] **Step 3: Update completion feedback and remove conflicting copy**

Search all frontend user-facing strings for “保存到课程资源” and update only generation-completion messages. Do not rename the navigation destination “课程资源”.

- [ ] **Step 4: Inspect the real resource center in the browser**

Verify teacher A private, teacher B shared and viewer states where available. At minimum inspect 1024×768, 1366×768, 1440×900 and 1920×1080. Confirm no horizontal overflow, clipped action buttons, ambiguous active tab or stale detail selection.

- [ ] **Step 5: Update and re-run course-resource visual baselines**

Run:

```powershell
$env:PLAYWRIGHT_VISUAL_PAGE='course-resources'; pnpm exec playwright test tests/e2e/visual-regression.spec.ts --update-snapshots
$env:PLAYWRIGHT_VISUAL_PAGE='course-resources'; pnpm exec playwright test tests/e2e/visual-regression.spec.ts
```

Expected: supported light/dark resource-center projects pass; configured unsupported combinations are skipped only by existing policy.

- [ ] **Step 6: Commit Task 6**

```powershell
git add -- src/components/teacher/ChatPanel.tsx src/components/teacher/generationSavedMessage.ts src/components/teacher/generationSavedMessage.test.ts tests/e2e/visual-regression.spec.ts-snapshots docs/superpowers/verification/2026-08-07-personal-resource-publication-verification.md
git commit -m "test: verify personal resource publication flow"
```

Stage only the exact changed message test, approved resource snapshots and verification document; do not stage unrelated files under `src`.

---

### Task 7: Full Verification and Requirements Audit

**Files:**
- Modify: `docs/superpowers/verification/2026-08-07-personal-resource-publication-verification.md`

**Interfaces:**
- Consumes: every preceding task and the approved design acceptance list.
- Produces: reproducible verification evidence and final clean task commits.

- [ ] **Step 1: Run the complete focused backend suite**

```powershell
python -m pytest api/src/tests/core/test_course_material_manifest.py api/src/tests/core/test_course_material_permissions.py api/src/tests/core/test_course_storage_generated_materials.py api/src/tests/services/test_material_publication_service.py api/src/tests/chat/test_course_scope_routes.py api/src/tests/test_course_access.py -q
```

- [ ] **Step 2: Run the complete frontend unit suite, lint and build**

```powershell
pnpm test
pnpm lint
pnpm build
```

- [ ] **Step 3: Run the resource-center visual suite without updating snapshots**

```powershell
$env:PLAYWRIGHT_VISUAL_PAGE='course-resources'; pnpm exec playwright test tests/e2e/visual-regression.spec.ts
```

- [ ] **Step 4: Audit every SPEC acceptance item**

Record pass/fail evidence for P0 items 1–14 and P1 items 1–9. Any failure remains open; do not mark the feature complete or weaken the acceptance criterion.

- [ ] **Step 5: Check diff boundaries and commit verification evidence**

```powershell
git diff --check
git status --short
git add -- docs/superpowers/verification/2026-08-07-personal-resource-publication-verification.md
git commit -m "docs: record resource publication verification"
```

- [ ] **Step 6: Final handoff**

Report task-by-task commits, exact test counts, any existing unrelated dirty files left untouched, and the remaining P2 audit/version-history work. Do not merge, push or delete worktrees without explicit user authorization.
