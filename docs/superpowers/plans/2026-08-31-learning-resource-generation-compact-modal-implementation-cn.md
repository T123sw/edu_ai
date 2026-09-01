# 学习资源生成紧凑弹窗 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把学习资源生成从长内嵌页面改为固定高度弹窗，通过章节折叠、单行知识点、按需详情和固定操作栏提高批量选择效率。

**Architecture:** `CourseKnowledgeBuildCard` 只管理弹窗开关，`LearningResourceGenerationPanel` 使用现有 Ant Design `Modal` 提供可访问的模态外壳。`StandardLearningResources` 新增 `compact` 模式并继续拥有目录、选择、生成批次、审核和重试状态；学生只读模式保持原样。

**Tech Stack:** React 18、TypeScript、Ant Design 5、CSS、Node test runner、Playwright。

---

## 文件结构

- 修改 `frontend/src/stitch/course/knowledge/LearningResourceGenerationPanel.tsx`：将内嵌区域改为 Ant Design 模态弹窗。
- 修改 `frontend/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx`：入口按钮打开弹窗，不再在文档流中插入长面板。
- 修改 `frontend/src/stitch/course/knowledge/StandardLearningResources.tsx`：增加紧凑模式、章节选择、单行状态摘要和单详情展开。
- 修改 `frontend/src/stitch/course/knowledge/standardLearningResources.css`：紧凑列表、固定底栏和响应式样式。
- 修改 `frontend/src/stitch/course/knowledge/CourseKnowledgeBuildCard.css`：删除旧内嵌面板样式，增加弹窗外壳样式。
- 修改 `frontend/src/stitch/course/knowledge/standardLearningResourcesPresentation.ts`：增加可独立测试的选择统计和章节选择函数。
- 修改对应单元测试与 `frontend/tests/e2e/course-knowledge.spec.ts`：覆盖弹窗、折叠、单详情和固定操作栏。

### Task 1: 用纯函数锁定选择统计与章节批量选择

**Files:**
- Modify: `frontend/src/stitch/course/knowledge/standardLearningResourcesPresentation.ts`
- Modify: `frontend/src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts`

- [ ] **Step 1: 写失败测试**

在测试文件中加入：

```ts
import {
  groupStandardResourceLeaves,
  standardBatchProgress,
  standardReviewLabel,
  standardSelectionSummary,
  toggleStandardResourceLeafScope,
} from "./standardLearningResourcesPresentation";

test("selection summary reports knowledge points and three resources per point", () => {
  assert.deepEqual(standardSelectionSummary(4), {
    leafCount: 4,
    resourceCount: 12,
    label: "已选择 4 个知识点，将生成 12 项资源",
  });
});

test("chapter selection adds and removes only that chapter scope", () => {
  const current = new Set(["outside"]);
  const selected = toggleStandardResourceLeafScope(current, ["a", "b"]);
  assert.deepEqual([...selected], ["outside", "a", "b"]);
  assert.deepEqual([...toggleStandardResourceLeafScope(selected, ["a", "b"])], ["outside"]);
});
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts`

Expected: FAIL，提示两个导出函数不存在。

- [ ] **Step 3: 添加最小实现**

在呈现模块末尾加入：

```ts
export function standardSelectionSummary(selectedLeafCount: number) {
  const leafCount = Math.max(0, selectedLeafCount);
  const resourceCount = leafCount * 3;
  return {
    leafCount,
    resourceCount,
    label: `已选择 ${leafCount} 个知识点，将生成 ${resourceCount} 项资源`,
  };
}

export function toggleStandardResourceLeafScope(
  current: ReadonlySet<string>,
  scopeLeafIds: readonly string[],
) {
  const next = new Set(current);
  const scopeIsSelected = scopeLeafIds.length > 0 && scopeLeafIds.every((leafId) => next.has(leafId));
  for (const leafId of scopeLeafIds) {
    if (scopeIsSelected) next.delete(leafId);
    else next.add(leafId);
  }
  return next;
}
```

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts`

Expected: PASS。

### Task 2: 把入口改为真正的模态弹窗

**Files:**
- Modify: `frontend/src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`
- Modify: `frontend/src/stitch/course/knowledge/LearningResourceGenerationPanel.tsx`
- Modify: `frontend/src/stitch/course/knowledge/CourseKnowledgeBuildCard.tsx`
- Modify: `frontend/src/stitch/course/knowledge/CourseKnowledgeBuildCard.css`

- [ ] **Step 1: 写弹窗结构失败测试**

把原有“页内展开”断言改为：

```ts
test("knowledge build card opens learning resource generation in a compact modal", async () => {
  const [card, panel] = await Promise.all([
    source("./CourseKnowledgeBuildCard.tsx"),
    source("./LearningResourceGenerationPanel.tsx"),
  ]);

  assert.match(card, /const \[resourceConfigOpen, setResourceConfigOpen\] = useState\(false\)/);
  assert.match(card, /aria-expanded=\{resourceConfigOpen\}/);
  assert.match(panel, /import \{ Modal \} from ["']antd["']/);
  assert.match(panel, /<Modal[\s\S]*open[\s\S]*width=\{1080\}/);
  assert.match(panel, /destroyOnHidden/);
  assert.match(panel, /<StandardLearningResources\s+compact\s+onCancel=\{onClose\}/);
  assert.doesNotMatch(panel, /aria-modal=["']false["']/);
});
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

Expected: FAIL，因为当前面板仍是 `aria-modal="false"` 的内嵌 section。

- [ ] **Step 3: 实现模态外壳**

将 `LearningResourceGenerationPanel.tsx` 改为：

```tsx
import { Modal } from "antd";

import { StandardLearningResources } from "./StandardLearningResources";

type Props = {
  onClose: () => void;
};

export function LearningResourceGenerationPanel({ onClose }: Props) {
  return (
    <Modal
      className="learning-resource-modal"
      title="学习资源生成"
      open
      centered
      width={1080}
      footer={null}
      destroyOnHidden
      onCancel={onClose}
    >
      <p className="learning-resource-modal__intro">
        选择知识点，批量生成 AI 课堂、学习指南和练习。提交后可关闭窗口，任务会在后台继续处理。
      </p>
      <StandardLearningResources compact onCancel={onClose} />
    </Modal>
  );
}
```

`CourseKnowledgeBuildCard` 的入口按钮和条件渲染保持以下形式，从而在打开学习资源弹窗时关闭知识库向导：

```tsx
<button
  type="button"
  className="course-kb-builder__secondary"
  aria-expanded={resourceConfigOpen}
  onClick={() => {
    setWizardOpen(false);
    setResourceConfigOpen((open) => !open);
  }}
>
  <MaterialIcon name="auto_awesome" />
  学习资源生成
</button>

{resourceConfigOpen ? (
  <LearningResourceGenerationPanel onClose={() => setResourceConfigOpen(false)} />
) : null}
```

删除 `.course-kb-resource-panel*` 样式，并加入：

```css
.learning-resource-modal .ant-modal-content {
  display: flex;
  max-height: min(82vh, 820px);
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.learning-resource-modal .ant-modal-header {
  flex: 0 0 auto;
  margin: 0;
  padding: 18px 22px 10px;
}

.learning-resource-modal .ant-modal-body {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.learning-resource-modal__intro {
  flex: 0 0 auto;
  margin: 0;
  padding: 0 22px 14px;
  color: var(--course-shell-muted);
  line-height: 1.6;
}
```

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

Expected: PASS。

### Task 3: 实现章节折叠与紧凑知识点行

**Files:**
- Modify: `frontend/src/stitch/course/knowledge/StandardLearningResources.tsx`
- Modify: `frontend/src/stitch/course/knowledge/standardLearningResources.css`
- Modify: `frontend/src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

- [ ] **Step 1: 添加紧凑模式失败断言**

在导航测试中加入：

```ts
test("compact resources use progressive disclosure and a fixed action bar", async () => {
  const resources = await source("./StandardLearningResources.tsx");
  assert.match(resources, /compact\s*=\s*false/);
  assert.match(resources, /expandedLeafId/);
  assert.match(resources, /openChapterIds/);
  assert.match(resources, /standard-resource-leaf__compact-row/);
  assert.match(resources, /standard-resources__compact-footer/);
  assert.match(resources, /查看详情/);
  assert.match(resources, /toggleStandardResourceLeafScope/);
});
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts`

Expected: FAIL，缺少紧凑模式状态和标记。

- [ ] **Step 3: 扩展组件接口与状态**

把呈现函数导入扩展为：

```tsx
import {
  groupStandardResourceLeaves,
  STANDARD_RESOURCE_KIND_META,
  standardBatchProgress,
  standardReviewLabel,
  standardSelectionSummary,
  toggleStandardResourceLeafScope,
} from "./standardLearningResourcesPresentation";
```

将组件签名和状态扩展为：

```tsx
type StandardLearningResourcesProps = {
  readOnly?: boolean;
  compact?: boolean;
  onCancel?: () => void;
};

export function StandardLearningResources({
  readOnly = false,
  compact = false,
  onCancel,
}: StandardLearningResourcesProps) {
  const { courseId, courseRole } = useCourseRoute();
  const canManage = !readOnly && (courseRole === "owner" || courseRole === "editor");
  const [leaves, setLeaves] = useState<StandardResourceLeaf[]>([]);
  const [selectedLeafIds, setSelectedLeafIds] = useState<Set<string>>(new Set());
  const [batch, setBatch] = useState<StandardResourceBatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [expandedLeafId, setExpandedLeafId] = useState<string | null>(null);
  const [openChapterIds, setOpenChapterIds] = useState<Set<string>>(new Set());
```

现有 `loadCatalog`、目录加载 effect 和批次轮询 effect 继续位于这些状态之后。`groups` 声明后初始化第一个章节：

```tsx
const groups = useMemo(() => groupStandardResourceLeaves(leaves), [leaves]);

useEffect(() => {
  if (!compact || groups.length === 0) return;
  setOpenChapterIds((current) => current.size ? current : new Set([groups[0].chapterId]));
}, [compact, groups]);
```

根容器使用明确的紧凑修饰类，并在紧凑模式隐藏原有大标题和顶部生成工具栏：

```tsx
<section
  className={`standard-resources${compact ? " standard-resources--compact" : ""}`}
  aria-labelledby={compact ? undefined : "standard-resources-title"}
  aria-label={compact ? "学习资源生成配置" : undefined}
>
  {!compact ? (
    <header className="standard-resources__header">
      <div>
        <span className="standard-resources__eyebrow">按知识点组织</span>
        <h2 id="standard-resources-title">标准学习资源</h2>
        <p>
          {canManage
            ? "系统只为叶子知识点生成 AI 课堂、学习指南和练习；审核通过后学生才能看到。"
            : "这里汇集教师审核发布的课堂、学习指南和练习。"}
        </p>
      </div>
      {canManage && leaves.length > 0 ? (
        <div className="standard-resources__toolbar">
          <button
            type="button"
            className="standard-resources__select-all"
            onClick={() => setSelectedLeafIds(
              selectedCount === leaves.length
                ? new Set()
                : new Set(leaves.map((leaf) => leaf.leaf_id)),
            )}
          >
            {selectedCount === leaves.length ? "取消全选" : "选择全部知识点"}
          </button>
          <button
            type="button"
            className="standard-resources__generate"
            disabled={!selectedCount || working}
            onClick={() => void generateSelected()}
          >
            <MaterialIcon name="auto_awesome" />
            {working ? "正在提交…" : `生成 ${selectedCount * 3} 项资源`}
          </button>
        </div>
      ) : null}
    </header>
  ) : null}
```

用纯函数替换叶子和范围选择：

```tsx
function toggleLeaf(leafId: string) {
  setSelectedLeafIds((current) => toggleStandardResourceLeafScope(current, [leafId]));
}

function toggleChapter(leafIds: readonly string[]) {
  setSelectedLeafIds((current) => toggleStandardResourceLeafScope(current, leafIds));
}
```

- [ ] **Step 4: 渲染紧凑章节和知识点行**

在 `compact && canManage` 分支中为每个章节渲染以下结构；非紧凑分支继续使用原有章节与资源卡片：

```tsx
<section className="standard-resource-chapter standard-resource-chapter--compact">
  <header className="standard-resource-chapter__compact-header">
    <button
      type="button"
      aria-expanded={openChapterIds.has(group.chapterId)}
      onClick={() => setOpenChapterIds((current) => {
        const next = new Set(current);
        if (next.has(group.chapterId)) next.delete(group.chapterId);
        else next.add(group.chapterId);
        return next;
      })}
    >
      <MaterialIcon name={openChapterIds.has(group.chapterId) ? "expand_less" : "chevron_right"} />
      <strong>{group.chapterTitle}</strong>
      <span>{group.leaves.length} 个知识点</span>
    </button>
    <button type="button" onClick={() => toggleChapter(group.leaves.map((leaf) => leaf.leaf_id))}>
      {group.leaves.every((leaf) => selectedLeafIds.has(leaf.leaf_id)) ? "取消本章" : "全选本章"}
    </button>
  </header>
  {openChapterIds.has(group.chapterId) ? (
    <div className="standard-resource-chapter__compact-leaves">
      {group.leaves.map((leaf) => (
        <section key={leaf.leaf_id} className="standard-resource-leaf standard-resource-leaf--compact">
          <div className="standard-resource-leaf__compact-row">
            <label>
              <input type="checkbox" checked={selectedLeafIds.has(leaf.leaf_id)} onChange={() => toggleLeaf(leaf.leaf_id)} />
              <span><strong>{leaf.title}</strong><small title={leaf.path_titles.join(" / ")}>{leaf.path_titles.join(" / ")}</small></span>
            </label>
            <div className="standard-resource-leaf__status-summary">
              {leaf.slots.map((slot) => (
                <span key={slot.standard_kind}>
                  {STANDARD_RESOURCE_KIND_META[slot.standard_kind].label} · {standardReviewLabel(slot.review_status)}
                </span>
              ))}
            </div>
            <button type="button" aria-expanded={expandedLeafId === leaf.leaf_id} onClick={() => setExpandedLeafId((current) => current === leaf.leaf_id ? null : leaf.leaf_id)}>
              {expandedLeafId === leaf.leaf_id ? "收起详情" : "查看详情"}
            </button>
          </div>
          {expandedLeafId === leaf.leaf_id ? (
            <div className="standard-resource-leaf__slots standard-resource-leaf__slots--compact">
              {leaf.slots.map((slot) => (
                <ResourceSlotCard key={slot.standard_kind} slot={slot} canManage={canManage} busy={working} onReview={(target, decision) => void review(target, decision)} />
              ))}
            </div>
          ) : null}
        </section>
      ))}
    </div>
  ) : null}
</section>
```

- [ ] **Step 5: 添加固定操作栏**

紧凑分支末尾加入：

```tsx
<footer className="standard-resources__compact-footer">
  <div>
    <strong>{standardSelectionSummary(selectedCount).label}</strong>
    <button type="button" onClick={() => setSelectedLeafIds(
      selectedCount === leaves.length ? new Set() : new Set(leaves.map((leaf) => leaf.leaf_id)),
    )}>
      {selectedCount === leaves.length ? "取消全选" : "选择全部知识点"}
    </button>
  </div>
  <div>
    <button type="button" className="standard-resources__compact-cancel" onClick={onCancel}>取消</button>
    <button type="button" className="standard-resources__generate" disabled={!selectedCount || working} onClick={() => void generateSelected()}>
      <MaterialIcon name="auto_awesome" />
      {working ? "正在提交…" : `开始生成 ${selectedCount * 3} 项资源`}
    </button>
  </div>
</footer>
```

- [ ] **Step 6: 添加布局样式**

在 CSS 中加入完整的紧凑布局约束：

```css
.standard-resources--compact { display:flex; min-height:0; flex:1; flex-direction:column; margin:0; padding:0; border:0; border-radius:0; }
.standard-resources--compact .standard-resources__chapters { min-height:0; flex:1; overflow-y:auto; padding:0 22px 16px; }
.standard-resource-chapter--compact { margin-top:10px; border-radius:10px; }
.standard-resource-chapter__compact-header { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:10px 12px; background:var(--surface-subtle,#f8fafc); }
.standard-resource-chapter__compact-header button { display:inline-flex; align-items:center; gap:7px; border:0; background:transparent; color:var(--app-text,#1e293b); }
.standard-resource-chapter__compact-header button:first-child { min-width:0; flex:1; text-align:left; }
.standard-resource-chapter__compact-header span { color:var(--app-text-muted,#64748b); font-size:12px; }
.standard-resource-chapter__compact-leaves { padding:0 12px; }
.standard-resource-leaf--compact { padding:0; }
.standard-resource-leaf--compact + .standard-resource-leaf--compact { margin:0; border-top:1px solid var(--app-border,#e2e8f0); }
.standard-resource-leaf__compact-row { display:grid; grid-template-columns:minmax(220px,1fr) minmax(360px,1.35fr) auto; align-items:center; gap:14px; min-height:58px; }
.standard-resource-leaf__compact-row > label { display:flex; min-width:0; align-items:center; gap:9px; }
.standard-resource-leaf__compact-row > label > span { min-width:0; }
.standard-resource-leaf__compact-row strong,.standard-resource-leaf__compact-row small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.standard-resource-leaf__compact-row small { margin-top:2px; color:var(--app-text-muted,#64748b); font-size:11px; }
.standard-resource-leaf__status-summary { display:flex; min-width:0; flex-wrap:wrap; gap:5px; }
.standard-resource-leaf__status-summary span { border-radius:999px; background:#f1f5f9; padding:4px 7px; color:#475569; font-size:11px; }
.standard-resource-leaf__slots--compact { margin:0 0 12px 28px; }
.standard-resources__compact-footer { display:flex; flex:0 0 auto; align-items:center; justify-content:space-between; gap:16px; border-top:1px solid var(--app-border,#e2e8f0); padding:13px 22px; background:var(--surface-card,#fff); box-shadow:0 -8px 24px rgb(15 23 42 / 6%); }
.standard-resources__compact-footer > div { display:flex; align-items:center; gap:10px; }
.standard-resources__compact-footer button { min-height:38px; border-radius:9px; padding:8px 12px; }
@media (max-width:720px) { .learning-resource-modal { max-width:calc(100vw - 16px); margin:8px auto; } .standard-resource-leaf__compact-row { grid-template-columns:1fr auto; padding:10px 0; } .standard-resource-leaf__status-summary { grid-column:1 / -1; } .standard-resources__compact-footer { align-items:stretch; flex-direction:column; } .standard-resources__compact-footer > div { justify-content:space-between; } }
```

- [ ] **Step 7: 运行单元测试确认 GREEN**

Run: `cd Edu_AI && pnpm test -- src/stitch/course/knowledge/learningResourceGenerationNavigation.test.ts src/stitch/course/knowledge/standardLearningResourcesPresentation.test.ts`

Expected: PASS。

### Task 4: 浏览器验收与完整验证

**Files:**
- Modify: `frontend/tests/e2e/fixtures/apiRoutes.ts`
- Modify: `frontend/tests/e2e/course-knowledge.spec.ts`

- [ ] **Step 1: 扩展测试目录为两个章节**

在标准资源夹具的 `leaves` 中追加：

```ts
{
  leaf_id: "optics",
  title: "几何光学",
  chapter_id: "optics-chapter",
  chapter_title: "光学",
  path_titles: ["大学物理", "光学", "几何光学"],
  slots: [
    { standard_kind: "classroom", material_type: "classroom", material_id: "standard-optics-classroom", review_status: "not_generated", resource: null },
    { standard_kind: "study_guide", material_type: "report", material_id: "standard-optics-guide", review_status: "not_generated", resource: null },
    { standard_kind: "practice", material_type: "quiz", material_id: "standard-optics-practice", review_status: "not_generated", resource: null },
  ],
}
```

- [ ] **Step 2: 把入口验收改为紧凑弹窗行为**

在浏览器测试文件中加入以下完整用例：

```ts
test("learning resource generation uses a compact progressive-disclosure modal", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  const pageHeight = await teacherPage.evaluate(() => document.documentElement.scrollHeight);
  await teacherPage.getByRole("button", { name: "学习资源生成" }).click();

  const dialog = teacherPage.getByRole("dialog", { name: "学习资源生成" });
  await expect(dialog).toBeVisible();
  expect(await teacherPage.evaluate(() => document.documentElement.scrollHeight)).toBe(pageHeight);
  await expect(dialog.locator(".standard-resource-card")).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: /大学物理/ })).toHaveAttribute("aria-expanded", "true");
  await expect(dialog.getByRole("button", { name: /光学/ })).toHaveAttribute("aria-expanded", "false");

  await dialog.getByRole("checkbox", { name: "力学" }).check();
  await expect(dialog.getByText("已选择 1 个知识点，将生成 3 项资源")).toBeVisible();
  await dialog.getByRole("button", { name: "查看详情" }).click();
  await expect(dialog.locator(".standard-resource-card")).toHaveCount(3);
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(dialog).toHaveCount(0);
});
```

- [ ] **Step 3: 运行浏览器测试**

Run: `cd Edu_AI && pnpm exec playwright test tests/e2e/course-knowledge.spec.ts`

Expected: 所有课程知识测试在桌面和紧凑尺寸通过。

- [ ] **Step 4: 运行完整测试和构建**

Run: `cd Edu_AI && pnpm test`

Expected: 全部测试通过，失败数为 0。

Run: `cd Edu_AI && pnpm build`

Expected: 构建成功，无 TypeScript 或 Vite 错误。
