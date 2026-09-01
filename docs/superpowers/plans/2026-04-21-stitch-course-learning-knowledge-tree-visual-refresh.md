# Stitch Course Learning Knowledge Tree Visual Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the `课程学习` page knowledge tree so parent/child relationships are visually obvious, duplicate labels are removed, and the active learning path is easier to scan.

**Architecture:** Keep the existing knowledge graph data shape and selection behavior intact, but refactor `renderStructureNode` in `frontend/src/stitch/pages/VideoPlayer.tsx` so root and top-level nodes render as stronger cards while nested nodes render as indented tree items with guide lines. Add a small text helper to suppress repeated summaries and add text-level regression tests that lock the new hierarchy, indentation, and reduced-noise rendering structure.

**Tech Stack:** React 18, TypeScript, Tailwind utility classes in JSX, Node-based regex/assert frontend tests

---

### Task 1: Lock the New Tree Layout Contract with a Failing Test

**Files:**
- Create: `frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts`
- Test: `frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../../src/stitch/pages/VideoPlayer.tsx", import.meta.url), "utf8");

assert.match(
  page,
  /function shouldShowStructureSummary\(/,
  "VideoPlayer should define a helper that suppresses duplicate node summaries",
);

assert.match(
  page,
  /const isRootNode = depth === 0;/,
  "VideoPlayer should treat the root node as a dedicated visual tier",
);

assert.match(
  page,
  /const isBranchNode = depth === 1;/,
  "VideoPlayer should treat first-level children as branch cards",
);

assert.match(
  page,
  /style=\{\{ marginLeft: depth > 0 \? `\$\{depth \* 18\}px` : "0px" \}\}/,
  "VideoPlayer should indent nested nodes by depth so parent-child structure is obvious",
);

assert.match(
  page,
  /className="relative ml-4 space-y-2 border-l border-\[rgba\(37,99,235,0\.12\)\] pl-4"/,
  "VideoPlayer should render nested children inside a guided subtree lane",
);

assert.match(
  page,
  /shouldShowStructureSummary\(node\) \?/,
  "VideoPlayer should only render helper text when it adds information beyond the title",
);

console.log("videoPlayer.knowledge-tree-visual-refresh tests passed");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts`

Expected: `AssertionError` because `VideoPlayer.tsx` does not yet define the duplicate-summary helper or the new indented tree structure.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts
git commit -m "test: cover course learning knowledge tree refresh"
```

### Task 2: Refactor the Knowledge Tree Renderer for Clear Parent/Child Hierarchy

**Files:**
- Modify: `frontend/src/stitch/pages/VideoPlayer.tsx`
- Test: `frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts`

- [ ] **Step 1: Add the summary dedupe helper near the other local helpers**

```ts
function shouldShowStructureSummary(node: KnowledgeGraphNode) {
  const summary = String(node.data?.summary || "").trim();
  const label = String(node.label || "").trim();
  if (!summary) return false;
  return summary !== label;
}
```

- [ ] **Step 2: Refactor `renderStructureNode` to introduce visual tiers and indentation**

Replace the current `renderStructureNode` body with a tiered renderer shaped like this:

```tsx
function renderStructureNode(node: KnowledgeGraphNode, depth = 0): ReactNode {
  const hasChildren = Boolean(node.children?.length);
  const expanded = expandedStructureIds.has(node.id);
  const active = activeStructureId === node.id;
  const isRootNode = depth === 0;
  const isBranchNode = depth === 1;
  const summaryVisible = shouldShowStructureSummary(node);

  return (
    <div key={node.id} className="space-y-2" style={{ marginLeft: depth > 0 ? `${depth * 18}px` : "0px" }}>
      <div
        className={`relative transition ${
          isRootNode
            ? "rounded-[20px] border px-4 py-4"
            : isBranchNode
              ? "rounded-[18px] border px-4 py-3.5"
              : "rounded-[14px] border px-3.5 py-3"
        } ${
          active
            ? "border-[var(--accent-border)] bg-[var(--accent-soft)] shadow-[0_12px_24px_var(--accent-shadow)]"
            : "border-[var(--shell-border)] bg-white hover:border-[rgba(37,99,235,0.24)] hover:bg-[rgba(248,250,255,0.96)]"
        }`}
      >
        {active ? <span className="absolute inset-y-3 left-0 w-1 rounded-full bg-[var(--accent)]" /> : null}

        <div className="flex items-start gap-3">
          {hasChildren ? (
            <button
              type="button"
              onClick={() => toggleStructureNode(node.id)}
              className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full border border-[var(--shell-border)] bg-[var(--surface-elevated)] text-[var(--accent-strong)]"
            >
              <MaterialIcon name={expanded ? "expand_less" : "expand_more"} className="text-sm" />
            </button>
          ) : (
            <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[rgba(37,99,235,0.08)] text-[var(--accent-strong)]">
              <span className="h-2.5 w-2.5 rounded-full bg-current" />
            </div>
          )}

          <button type="button" onClick={() => handleStructureSelect(node)} className="min-w-0 flex-1 text-left">
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-[rgba(37,99,235,0.08)] px-2.5 py-1 text-[10px] font-bold tracking-[0.12em] text-[var(--accent-strong)]">
                {nodeTypeLabel(node)}
              </span>
            </div>
            <p className={`${isRootNode ? "mt-2 text-lg" : "mt-1.5 text-[15px]"} font-bold leading-6 text-[var(--app-text)]`}>
              {node.label}
            </p>
            {summaryVisible ? (
              <p className="mt-1 text-xs leading-5 text-[var(--muted-text)]">{node.data?.summary}</p>
            ) : null}
          </button>
        </div>
      </div>

      {hasChildren && expanded ? (
        <div className="relative ml-4 space-y-2 border-l border-[rgba(37,99,235,0.12)] pl-4">
          {node.children!.map((child) => renderStructureNode(child, depth + 1))}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 3: Run the new test to verify it passes**

Run: `node frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts`

Expected: `videoPlayer.knowledge-tree-visual-refresh tests passed`

- [ ] **Step 4: Run existing nearby tests to guard against regressions**

Run:

```bash
node frontend/tests/frontend/videoPlayer.knowledge-point-materials.test.ts
node frontend/tests/frontend/videoPlayer.course-material-scroll-layout.test.ts
```

Expected:

- `videoPlayer.knowledge-point-materials tests passed`
- `videoPlayer.course-material-scroll-layout tests passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stitch/pages/VideoPlayer.tsx frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts
git commit -m "feat: refresh course learning knowledge tree styling"
```

### Task 3: Tighten the Container Rhythm Around the Updated Tree

**Files:**
- Modify: `frontend/src/stitch/pages/VideoPlayer.tsx`
- Test: `frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts`

- [ ] **Step 1: Lightly tune the left-side shell copy block so the refreshed tree breathes**

Adjust only the wrapper around the tree list:

```tsx
<div className="mt-4 space-y-2.5">
  {graphLoading ? (
    <div className="rounded-[18px] bg-[var(--surface-subtle)] px-4 py-4 text-sm text-[var(--muted-text)]">
      ...
    </div>
  ) : structureRoot ? (
    renderStructureNode(structureRoot)
  ) : (
    <div className="rounded-[18px] bg-[var(--surface-subtle)] px-4 py-4 text-sm text-[var(--muted-text)]">
      ...
    </div>
  )}
</div>
```

This keeps the summary header separate from the new hierarchical tree rhythm.

- [ ] **Step 2: Re-run the tree refresh test**

Run: `node frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts`

Expected: `videoPlayer.knowledge-tree-visual-refresh tests passed`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stitch/pages/VideoPlayer.tsx
git commit -m "style: refine course learning tree spacing"
```

### Task 4: Final Verification Sweep

**Files:**
- Verify: `frontend/src/stitch/pages/VideoPlayer.tsx`
- Verify: `frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts`
- Verify: `frontend/tests/frontend/videoPlayer.knowledge-point-materials.test.ts`
- Verify: `frontend/tests/frontend/videoPlayer.course-material-scroll-layout.test.ts`
- Verify: `frontend/tests/frontend/videoPlayer.ppt-preview.test.ts`
- Verify: `frontend/tests/frontend/videoPlayer.material-doc-export.test.ts`

- [ ] **Step 1: Run the complete focused verification set**

Run:

```bash
node frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts
node frontend/tests/frontend/videoPlayer.knowledge-point-materials.test.ts
node frontend/tests/frontend/videoPlayer.course-material-scroll-layout.test.ts
node frontend/tests/frontend/videoPlayer.ppt-preview.test.ts
node frontend/tests/frontend/videoPlayer.material-doc-export.test.ts
```

Expected:

- `videoPlayer.knowledge-tree-visual-refresh tests passed`
- `videoPlayer.knowledge-point-materials tests passed`
- `videoPlayer.course-material-scroll-layout tests passed`
- `videoPlayer.ppt-preview tests passed`
- `videoPlayer.material-doc-export tests passed`

- [ ] **Step 2: Review the final diff for unintended scope growth**

Run:

```bash
git diff -- frontend/src/stitch/pages/VideoPlayer.tsx frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts
```

Expected: only tree-visual hierarchy, duplicate-summary suppression, and nearby spacing adjustments are present.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stitch/pages/VideoPlayer.tsx frontend/tests/frontend/videoPlayer.knowledge-tree-visual-refresh.test.ts
git commit -m "test: verify course learning knowledge tree refresh"
```
