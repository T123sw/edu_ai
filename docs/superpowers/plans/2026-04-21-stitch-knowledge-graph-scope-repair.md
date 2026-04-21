# Stitch Knowledge Graph Scope Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the stitch knowledge graph page so jumping to the AI workspace and importing documents both preserve the selected course-vs-knowledge-point scope.

**Architecture:** Keep the fix frontend-only and minimal. Reuse the shared workspace scope serializer in `src/services/teacher/workspaceScope.ts`, align the stitch knowledge graph page with the existing teacher-route behavior, and lock the regression with file-content assertion tests.

**Tech Stack:** React, TypeScript, stitch frontend pages, file-content frontend assertion tests, Node.

---

### Task 1: Lock the expected stitch behavior in tests

**Files:**
- Modify: `Edu_AI/tests/frontend/stitchKnowledgeGraph.scope-link.test.ts`
- Modify: `Edu_AI/tests/frontend/knowledgeGraph.node-course-kb-upload.test.ts`
- Modify: `Edu_AI/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`

- [ ] **Step 1: Write/update the failing assertions**

```ts
assert.match(file, /writeWorkspaceScopeToSearch/);
assert.match(file, /const isCourseRootScope = activeNode\.parentId === null;/);
assert.match(file, /scopeType:\s*isCourseRootScope \? "course" : "knowledge_point"/);
assert.match(file, /scopeId:\s*isCourseRootScope \? undefined : activeNode\.id/);
assert.doesNotMatch(file, /\?node=/);
```

- [ ] **Step 2: Run the focused assertions and verify they fail before implementation**

Run: `node Edu_AI/tests/frontend/stitchKnowledgeGraph.scope-link.test.ts`
Expected: FAIL because `src/stitch/pages/KnowledgeGraph.tsx` still uses the old `?node=` jump flow.

Run: `node Edu_AI/tests/frontend/knowledgeGraph.node-course-kb-upload.test.ts`
Expected: FAIL because the current variable naming/patterns do not yet match the scoped upload contract.

- [ ] **Step 3: Keep the textbook import assertion compatible with the real stitch type name**

```ts
assert.match(typesFile, /export type KnowledgeGraphTextbookImportResponse/);
```

- [ ] **Step 4: Re-run the textbook import assertion**

Run: `node Edu_AI/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`
Expected: PASS once the assertion matches the actual exported type name.

### Task 2: Repair stitch knowledge graph scope handling

**Files:**
- Modify: `Edu_AI/src/stitch/pages/KnowledgeGraph.tsx`
- Reference: `Edu_AI/src/services/teacher/workspaceScope.ts`
- Reference: `Edu_AI/src/pages/teacher/KnowledgeGraphPage.tsx`

- [ ] **Step 1: Import the shared workspace scope serializer**

```ts
import { writeWorkspaceScopeToSearch } from "../../services/teacher/workspaceScope";
```

- [ ] **Step 2: Introduce explicit root-scope helpers for the active node**

```ts
const isCourseRootSelected = activeNode?.parentId === null;
const isCourseRootScope = activeNode?.parentId === null;
```

- [ ] **Step 3: Replace the old node-only AI workspace link with a scoped hash**

```ts
const aiWorkspaceHref = activeNode
  ? (() => {
      const nextSearch = writeWorkspaceScopeToSearch(new URLSearchParams(), {
        scopeType: isCourseRootScope ? "course" : "knowledge_point",
        scopeId: isCourseRootScope ? undefined : activeNode.id,
        scopeLabel: isCourseRootScope ? undefined : activeNode.label,
      });
      return `${routeHref(routes.ai)}?${nextSearch.toString()}`;
    })()
  : routeHref(routes.ai);
```

- [ ] **Step 4: Align document upload logic with the same scope contract**

```ts
const targetNode = activeNode;
const isCourseRootNode = targetNode.parentId === null;

await uploadKnowledgeBaseDocument(course.id, file, {
  scopeType: isCourseRootNode ? "course" : "knowledge_point",
  scopeId: isCourseRootNode ? undefined : targetNode.id,
  libraryType: "course",
});
```

- [ ] **Step 5: Keep the selected-node document load path consistent**

```ts
const documents = await getKnowledgeBaseDocuments(course.id, {
  scopeType: node.parentId === null ? "course" : "knowledge_point",
  scopeId: node.parentId === null ? undefined : node.id,
  aggregate: false,
  libraryType: "course",
});
```

### Task 3: Verify the regression is fixed

**Files:**
- Test: `Edu_AI/tests/frontend/stitchKnowledgeGraph.scope-link.test.ts`
- Test: `Edu_AI/tests/frontend/knowledgeGraph.node-course-kb-upload.test.ts`
- Test: `Edu_AI/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`
- Test: `Edu_AI/tests/frontend/knowledgeGraph.textbook-import.test.ts`

- [ ] **Step 1: Run the scoped jump assertion**

Run: `node Edu_AI/tests/frontend/stitchKnowledgeGraph.scope-link.test.ts`
Expected: PASS with `writeWorkspaceScopeToSearch`, `scopeType`, and `scopeId` patterns present and no `?node=`.

- [ ] **Step 2: Run the scoped upload assertion**

Run: `node Edu_AI/tests/frontend/knowledgeGraph.node-course-kb-upload.test.ts`
Expected: PASS with `isCourseRootNode` driving both `scopeType` and `scopeId`.

- [ ] **Step 3: Run the textbook import assertions**

Run: `node Edu_AI/tests/frontend/stitchKnowledgeGraph.textbook-import.test.ts`
Expected: PASS.

Run: `node Edu_AI/tests/frontend/knowledgeGraph.textbook-import.test.ts`
Expected: PASS.

- [ ] **Step 4: Summarize any remaining gaps**

```txt
If browser-level manual verification is not run in this session, explicitly report that the fix is covered by focused file-content assertions rather than an interactive UI smoke test.
```
