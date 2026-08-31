# Knowledge Resource Detail and Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让教师从课程知识节点直接查看标准学习资源、进入 AI 课堂播放器，并通过待审核资源。

**Architecture:** 在标准资源展示层增加纯函数，统一决定课堂跳转、弹窗详情、内容提取和审核按钮可见性；`KnowledgeNodeCourseResources` 负责目录刷新与审核状态，独立弹窗组件负责非课堂资源详情。后端继续使用现有标准资源目录和单项审核接口。

**Tech Stack:** React 18、TypeScript、Vite、Node test runner、Playwright、现有 FastAPI 接口

---

## File Structure

- Modify: `Edu_AI/src/stitch/course/knowledge/standardLearningResourcesPresentation.ts` — 资源打开目标、正文和审核可见性的纯函数。
- Modify: `Edu_AI/src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts` — 纯函数单元测试。
- Create: `Edu_AI/src/stitch/course/knowledge/KnowledgeNodeResourceDialog.tsx` — 学习指南和练习详情弹窗。
- Modify: `Edu_AI/src/stitch/course/knowledge/KnowledgeNodeCourseResources.tsx` — 点击分流、审核提交和目录刷新。
- Modify: `Edu_AI/src/stitch/course/knowledge/KnowledgeDocumentsView.tsx` — 传递课程编辑权限。
- Modify: `Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts` — 组件接线回归测试。
- Modify: `Edu_AI/src/stitch/styles.css` — 资源操作区和详情弹窗样式。
- Modify: `Edu_AI/tests/e2e/fixtures/apiRoutes.ts` — 待审核资源与审核后状态夹具。
- Modify: `Edu_AI/tests/e2e/course-knowledge.spec.ts` — 详情、审核与课堂跳转浏览器验收。

### Task 1: Standard Resource Presentation Decisions

**Files:**
- Modify: `Edu_AI/src/stitch/course/knowledge/standardLearningResourcesPresentation.ts`
- Test: `Edu_AI/src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts`

- [ ] **Step 1: Write the failing presentation tests**

Add `StandardResourceSlot` to the type imports and add:

```ts
import {
  canApproveStandardResource,
  getStandardResourceDetailTarget,
  standardResourceBody,
} from "./standardLearningResourcesPresentation";

const slot = (overrides: Partial<StandardResourceSlot>): StandardResourceSlot => ({
  standard_kind: "study_guide",
  material_type: "report",
  material_id: "guide-1",
  review_status: "pending",
  resource: { material_id: "guide-1", material_type: "report" },
  ...overrides,
});

test("standard classrooms open the existing classroom player", () => {
  assert.deepEqual(
    getStandardResourceDetailTarget("course/中文", slot({
      standard_kind: "classroom",
      material_type: "classroom",
      material_id: "classroom-1",
    })),
    {
      kind: "route",
      href: "#classroom-player?course_id=course%2F%E4%B8%AD%E6%96%87&classroom_id=classroom-1",
    },
  );
});

test("guides and practice resources open in a detail dialog", () => {
  assert.deepEqual(getStandardResourceDetailTarget("course-1", slot({})), { kind: "dialog" });
  assert.deepEqual(getStandardResourceDetailTarget("course-1", slot({
    standard_kind: "practice",
    material_type: "quiz",
  })), { kind: "dialog" });
});

test("resource body supports markdown and structured content", () => {
  assert.equal(standardResourceBody(slot({
    resource: { material_id: "guide-1", material_type: "report", final_markdown: "# 学习指南" },
  })), "# 学习指南");
  assert.match(standardResourceBody(slot({
    resource: { material_id: "quiz-1", material_type: "quiz", content: { questions: [{ stem: "1 + 1" }] } },
  })), /1 \+ 1/);
});

test("only managers can approve pending resources", () => {
  assert.equal(canApproveStandardResource(true, slot({ review_status: "pending" })), true);
  assert.equal(canApproveStandardResource(false, slot({ review_status: "pending" })), false);
  assert.equal(canApproveStandardResource(true, slot({ review_status: "approved" })), false);
});
```

- [ ] **Step 2: Run the test and verify RED**

Run from `Edu_AI`:

```powershell
pnpm test -- src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts
```

Expected: FAIL because the three imported helpers do not exist.

- [ ] **Step 3: Implement the minimal pure helpers**

Import the existing `buildClassroomPlayerHash` and `StandardResourceSlot`, then add:

```ts
export function getStandardResourceDetailTarget(
  courseId: string,
  slot: StandardResourceSlot,
): { kind: "route"; href: string } | { kind: "dialog" } {
  return slot.standard_kind === "classroom"
    ? { kind: "route", href: buildClassroomPlayerHash(courseId, slot.material_id) }
    : { kind: "dialog" };
}

export function standardResourceBody(slot: StandardResourceSlot): string {
  const resource = (slot.resource || {}) as Record<string, unknown>;
  for (const key of ["final_markdown", "markdown", "report_content", "text", "content"]) {
    const value = resource[key];
    if (typeof value === "string" && value.trim()) return value;
    if (value && typeof value === "object") return JSON.stringify(value, null, 2);
  }
  return "该课程资料已经生成，暂无可展示的正文内容。";
}

export function canApproveStandardResource(
  canManage: boolean,
  slot: StandardResourceSlot,
): boolean {
  return canManage && slot.review_status === "pending" && Boolean(slot.resource);
}
```

- [ ] **Step 4: Run the test and verify GREEN**

Run:

```powershell
pnpm test -- src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts
```

Expected: all tests in the file PASS.

- [ ] **Step 5: Commit the presentation behavior**

```powershell
git add -- src/stitch/course/knowledge/standardLearningResourcesPresentation.ts src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts
git commit -m "test: define knowledge resource detail behavior"
```

### Task 2: Detail Dialog and Single-Resource Approval

**Files:**
- Create: `Edu_AI/src/stitch/course/knowledge/KnowledgeNodeResourceDialog.tsx`
- Modify: `Edu_AI/src/stitch/course/knowledge/KnowledgeNodeCourseResources.tsx`
- Modify: `Edu_AI/src/stitch/course/knowledge/KnowledgeDocumentsView.tsx`
- Modify: `Edu_AI/src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts`
- Modify: `Edu_AI/src/stitch/styles.css`

- [ ] **Step 1: Write failing component wiring assertions**

In `courseKnowledgeBuildIntegration.test.ts`, read the new dialog source and add:

```ts
const resourceDialog = await readFile(new URL("./KnowledgeNodeResourceDialog.tsx", import.meta.url), "utf8");
assert.match(source, /canManage=\{canUpload\}/);
assert.match(nodeResources, /reviewStandardResource/);
assert.match(nodeResources, /getStandardResourceDetailTarget/);
assert.match(nodeResources, /<KnowledgeNodeResourceDialog/);
assert.match(resourceDialog, /role="dialog"/);
assert.match(resourceDialog, /aria-modal="true"/);
assert.match(resourceDialog, /通过审核/);
assert.match(resourceDialog, /Escape/);
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
pnpm test -- src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
```

Expected: FAIL because `KnowledgeNodeResourceDialog.tsx` and the new wiring do not exist.

- [ ] **Step 3: Create the detail dialog**

Create `KnowledgeNodeResourceDialog.tsx` with the following interface and behavior:

```tsx
export function KnowledgeNodeResourceDialog({
  leafTitle,
  slot,
  canManage,
  busy,
  onApprove,
  onClose,
}: {
  leafTitle: string;
  slot: StandardResourceSlot;
  canManage: boolean;
  busy: boolean;
  onApprove: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const meta = STANDARD_RESOURCE_KIND_META[slot.standard_kind];
  const title = String(slot.resource?.title || `${leafTitle}${meta.label}`);
  return (
    <div className="knowledge-resource-dialog__backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="knowledge-resource-dialog" role="dialog" aria-modal="true" aria-labelledby="knowledge-resource-dialog-title">
        <header>
          <div><span>{leafTitle} · {meta.label}</span><h2 id="knowledge-resource-dialog-title">{title}</h2></div>
          <button type="button" aria-label="关闭资源详情" onClick={onClose}><MaterialIcon name="close" /></button>
        </header>
        <div className="knowledge-resource-dialog__body"><pre>{standardResourceBody(slot)}</pre></div>
        <footer>
          <span>{standardReviewLabel(slot.review_status)}</span>
          <div>
            <button type="button" onClick={onClose}>关闭</button>
            {canApproveStandardResource(canManage, slot) ? (
              <button type="button" className="is-primary" disabled={busy} onClick={onApprove}>
                <MaterialIcon name="check_circle" />{busy ? "正在通过…" : "通过审核"}
              </button>
            ) : null}
          </div>
        </footer>
      </section>
    </div>
  );
}
```

Include the imports for React `useEffect`, the slot type, `MaterialIcon`, and the presentation helpers referenced above.

- [ ] **Step 4: Wire explicit open and approve actions**

In `KnowledgeNodeCourseResources.tsx`:

- Accept `canManage: boolean`.
- Replace `expandedMaterialId` with `selectedResource`.
- Move the catalog loader into `useCallback` so post-review refresh reuses it.
- Import `reviewStandardResource`, `KnowledgeNodeResourceDialog`, `getStandardResourceDetailTarget`, and `canApproveStandardResource`.
- Add:

```tsx
function openResource(leaf: StandardResourceLeaf, slot: StandardResourceSlot) {
  const target = getStandardResourceDetailTarget(courseId, slot);
  if (target.kind === "route") {
    window.location.hash = target.href;
  } else {
    setSelectedResource({ leaf, slot });
  }
}

async function approve(slot: StandardResourceSlot) {
  if (!canApproveStandardResource(canManage, slot) || working) return;
  setWorking(true);
  setError("");
  try {
    await reviewStandardResource(courseId, slot.material_id, "approved");
    setSelectedResource(null);
    await loadCatalog();
  } catch (reason) {
    setError(reason instanceof Error ? reason.message : "审核操作失败，请稍后重试");
  } finally {
    setWorking(false);
  }
}
```

The resource summary calls `openResource`. A separate sibling approval button calls `event.stopPropagation()` and then `approve(slot)`, so approving a classroom never navigates. Render `KnowledgeNodeResourceDialog` only when `selectedResource` is non-null.

- [ ] **Step 5: Pass the existing permission**

Update `KnowledgeDocumentsView.tsx`:

```tsx
<KnowledgeNodeCourseResources
  courseId={courseId || ""}
  nodeLabel={selectedNode?.label || "课程"}
  scopeNodeIds={scopeNodeIds}
  canManage={canUpload}
/>
```

- [ ] **Step 6: Add scoped styles**

Add row action and dialog styles to `stitch/styles.css`:

```css
.knowledge-node-resource { display: flex; align-items: stretch; background: white; }
.knowledge-node-resource__summary { flex: 1; min-width: 0; }
.knowledge-node-resource__actions { display: flex; align-items: center; gap: 8px; padding: 8px 12px 8px 0; }
.knowledge-node-resource__approve { border: 1px solid #b9d5ff; border-radius: 10px; background: #edf4ff; padding: 8px 11px; color: #245edb; font-weight: 750; cursor: pointer; }
.knowledge-resource-dialog__backdrop { position: fixed; inset: 0; z-index: 1200; display: grid; place-items: center; background: rgb(15 23 42 / 45%); padding: 24px; }
.knowledge-resource-dialog { display: flex; width: min(900px, 100%); max-height: min(82vh, 760px); flex-direction: column; overflow: hidden; border-radius: 18px; background: white; box-shadow: 0 24px 80px rgb(15 23 42 / 25%); }
.knowledge-resource-dialog > header, .knowledge-resource-dialog > footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 22px; }
.knowledge-resource-dialog__body { min-height: 0; overflow: auto; border-block: 1px solid #e7edf7; background: #f8faff; padding: 20px 22px; }
.knowledge-resource-dialog__body pre { margin: 0; color: #334155; font: 13px/1.75 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
```

Also add hover, disabled, close/footer button, and small-screen rules matching neighboring modal controls.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run:

```powershell
pnpm test -- src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts
```

Expected: both test files PASS.

- [ ] **Step 8: Commit the UI implementation**

```powershell
git add -- src/stitch/course/knowledge/KnowledgeNodeResourceDialog.tsx src/stitch/course/knowledge/KnowledgeNodeCourseResources.tsx src/stitch/course/knowledge/KnowledgeDocumentsView.tsx src/stitch/course/knowledge/courseKnowledgeBuildIntegration.test.ts src/stitch/styles.css
git commit -m "feat: review learning resources from knowledge nodes"
```

### Task 3: Browser Regression Coverage and Final Verification

**Files:**
- Modify: `Edu_AI/tests/e2e/fixtures/apiRoutes.ts`
- Modify: `Edu_AI/tests/e2e/course-knowledge.spec.ts`

- [ ] **Step 1: Add mutable standard-resource fixture state**

Inside `installTeacherApiRoutes`, initialize:

```ts
const standardReviewStatuses = {
  classroom: "pending",
  study_guide: "pending",
  practice: "pending",
};
```

Return generated resources for `mechanics`: a classroom with `stage.name`, a guide with `final_markdown`, and a practice with structured `content`. Use the current status values on every `GET /standard-resources`.

Handle the review endpoint before generic material routes:

```ts
if (request.method() === "POST" && path.endsWith("/standard-mechanics-guide/review")) {
  standardReviewStatuses.study_guide = "approved";
  return json(route, {
    course_id: physicsCourse.id,
    material_type: "report",
    material_id: "standard-mechanics-guide",
    version: 1,
    current_review_status: "approved",
    approved_version: 1,
  });
}
```

- [ ] **Step 2: Write browser tests**

Add:

```ts
test("teacher opens a generated guide and approves it from the detail dialog", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("button", { name: /力学学习指南/ }).click();
  const dialog = teacherPage.getByRole("dialog", { name: /力学学习指南/ });
  await expect(dialog).toContainText("# 力学学习指南");
  await dialog.getByRole("button", { name: "通过审核" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(teacherPage.getByRole("button", { name: /力学学习指南/ })).toContainText("已发布");
});

test("generated AI classroom opens the classroom player", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("button", { name: /力学互动课堂/ }).click();
  await expect(teacherPage).toHaveURL(/#classroom-player\?course_id=course-physics&classroom_id=standard-mechanics-classroom$/);
});
```

- [ ] **Step 3: Run the browser test and verify RED**

Run from `Edu_AI`:

```powershell
pnpm exec playwright test tests/e2e/course-knowledge.spec.ts
```

Expected before implementation/fixture completion: the new tests FAIL because the resource dialog or state transition is absent.

- [ ] **Step 4: Complete the fixture and verify GREEN**

Run the same Playwright command. Expected: all tests in `course-knowledge.spec.ts` PASS.

- [ ] **Step 5: Run full frontend verification**

```powershell
pnpm test
pnpm lint
pnpm build
```

Expected: unit tests PASS, ESLint exits 0, and Vite production build completes successfully.

- [ ] **Step 6: Review and commit only in-scope files**

```powershell
git diff --check
git status --short
git diff -- src/stitch/course/knowledge src/stitch/styles.css tests/e2e/course-knowledge.spec.ts tests/e2e/fixtures/apiRoutes.ts
git add -- tests/e2e/fixtures/apiRoutes.ts tests/e2e/course-knowledge.spec.ts
git commit -m "test: cover knowledge resource review flow"
```

Confirm that the existing unrelated changes under `Edu_AI/api/src` are not staged.
