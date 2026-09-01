# Teacher Source Panel Beautification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Beautify the teacher workspace left knowledge-base panel so it reads as a mature materials workbench with a clearer header, stronger retrieval zone, cleaner document list rhythm, and a stable upload action area without changing the underlying document workflows.

**Architecture:** Keep `SourcePanel.tsx` as the behavior owner for upload, preview, selection, rename, delete, and deep research, but extract its presentation into a clearer page-structure and a dedicated component stylesheet. Implementation must explicitly use the frontend beautification skills in sequence: `frontend-design` for the overall visual direction, `arrange` for the three-part panel rhythm and list alignment, `colorize` for restrained neutral/accent tuning, and `polish` for the final spacing, text-fit, and state pass. If `npx openskills` cannot load those skills in this environment, read the local `SKILL.md` files directly before implementation.

**Tech Stack:** React 18, TypeScript, Ant Design, component-scoped CSS, Vite, `node:test`

---

## File Structure

- Modify: `frontend/src/components/teacher/SourcePanel.tsx`
  - Replace the current inline-heavy left-panel shell with semantic class-based sections for header, retrieval zone, selection controls, document list, and upload action area while preserving current business handlers.
- Create: `frontend/src/components/teacher/SourcePanel.css`
  - Hold the dedicated visual language for the teacher source panel, including collapsed state, preview state, list-item spacing, and the fixed upload action area.
- Create: `frontend/tests/frontend/sourcePanel.layout.test.ts`
  - Add source-level regression checks for the new structural classes, section labels, and removal of the flatter inline-only shell.
- Modify: `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts`
  - Extend text-safety coverage so any new user-facing labels introduced in the source panel stay readable.

## Skill Execution Notes

Before editing implementation files, the worker must explicitly load and follow these skills:

1. `frontend-design`
   - Lock the panel’s tone to calm, professional, and materials-workbench oriented.
2. `arrange`
   - Shape the three-part panel rhythm: header, retrieval/list body, and upload footer.
3. `colorize`
   - Add restrained tinting and interaction emphasis without making the left panel noisy.
4. `polish`
   - Run a final pass on text fit, list alignment, collapsed state, and preview state continuity.

If `npx openskills read <skill>` fails for these design skills, load the local skill files instead:

```powershell
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\frontend-design\SKILL.md -TotalCount 200
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\arrange\SKILL.md -TotalCount 160
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\colorize\SKILL.md -TotalCount 160
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\polish\SKILL.md -TotalCount 180
```

Do not alter the business behavior of upload, preview, rename, delete, or deep research during this plan.

### Task 1: Add failing regressions for the beautified source-panel shell

**Files:**
- Create: `frontend/tests/frontend/sourcePanel.layout.test.ts`
- Modify: `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/frontend/sourcePanel.layout.test.ts`:

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const sourcePanel = readFileSync(
  new URL('../../src/components/teacher/SourcePanel.tsx', import.meta.url),
  'utf8',
);

assert.match(
  sourcePanel,
  /source-panel/,
  'SourcePanel should render the dedicated source-panel root class for the beautified shell',
);

assert.match(
  sourcePanel,
  /source-panel__header/,
  'SourcePanel should render a dedicated header section for the materials workbench',
);

assert.match(
  sourcePanel,
  /source-panel__tools/,
  'SourcePanel should render a dedicated retrieval tools section',
);

assert.match(
  sourcePanel,
  /source-panel__list/,
  'SourcePanel should render a dedicated document list section',
);

assert.match(
  sourcePanel,
  /source-panel__footer/,
  'SourcePanel should render a dedicated upload footer section',
);

assert.match(
  sourcePanel,
  /资料列表/,
  'SourcePanel should expose a readable 资料列表 section label',
);

assert.match(
  sourcePanel,
  /上传资料/,
  'SourcePanel should expose a readable 上传资料 section label',
);

assert.doesNotMatch(
  sourcePanel,
  /boxShadow:\s*'0 4px 12px rgba\(0,0,0,0\.08\)'/,
  'SourcePanel should stop relying on the flatter inline shell shadow once the beautified shell is implemented',
);

console.log('sourcePanel.layout tests passed');
```

Extend `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts` with:

```ts
assert.match(
  sourcePanelFile,
  /资料列表/,
  'SourcePanel should keep the document-list section label readable',
);

assert.match(
  sourcePanelFile,
  /上传资料/,
  'SourcePanel should keep the upload section label readable',
);
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
node --test tests/frontend/sourcePanel.layout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts
```

Expected: FAIL because the current source panel does not yet contain the new structural classes or the added section labels.

- [ ] **Step 3: Commit the red test checkpoint**

```bash
git add frontend/tests/frontend/sourcePanel.layout.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts
git commit -m "test: cover beautified teacher source panel"
```

### Task 2: Move the source-panel shell to explicit semantic sections

**Files:**
- Modify: `frontend/src/components/teacher/SourcePanel.tsx`

- [ ] **Step 1: Load the required beautification skills**

Run one of these paths:

```bash
npx openskills read frontend-design
npx openskills read arrange
npx openskills read colorize
```

If those commands fail, run:

```powershell
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\frontend-design\SKILL.md -TotalCount 200
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\arrange\SKILL.md -TotalCount 160
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\colorize\SKILL.md -TotalCount 160
```

Expected: the design guidance is available before editing the component.

- [ ] **Step 2: Import the dedicated stylesheet**

Add this import near the top of `frontend/src/components/teacher/SourcePanel.tsx`:

```ts
import './SourcePanel.css';
```

- [ ] **Step 3: Rebuild the collapsed shell with class-based structure**

Replace the current collapsed root wrapper with a semantic shell:

```tsx
return (
  <div className="source-panel source-panel--collapsed">
    <div className="source-panel__collapsed-top">
      <Button
        type="text"
        icon={<RightOutlined />}
        onClick={onToggleCollapsed}
        aria-label="展开知识库"
        className="source-panel__collapse-trigger"
      />
    </div>
    <div className="source-panel__collapsed-list">
      {fileIcons.length > 0 ? fileIcons : (
        <Text type="secondary" className="source-panel__collapsed-empty">暂无文档</Text>
      )}
    </div>
  </div>
);
```

- [ ] **Step 4: Rebuild the normal expanded shell into header / tools / list / footer**

Refactor the main expanded return block into explicit sections:

```tsx
return (
  <div className="source-panel">
    <div className="source-panel__header">
      <div className="source-panel__header-main">
        <Title level={5} className="source-panel__title">知识库</Title>
      </div>
      <Button
        type="text"
        icon={<LeftOutlined />}
        onClick={onToggleCollapsed}
        aria-label="折叠知识库"
        className="source-panel__collapse-trigger"
      />
    </div>

    <div className="source-panel__tools">
      <Button
        type="default"
        icon={<SearchOutlined />}
        size="large"
        onClick={handleResearch}
        className="source-panel__research-button"
      >
        深度研究搜索
      </Button>
    </div>

    <div className="source-panel__list-section">
      <div className="source-panel__list-toolbar">
        <span className="source-panel__section-label">资料列表</span>
        <div className="source-panel__select-all">
          <span className="source-panel__select-all-text">选择所有来源</span>
          <Checkbox checked={selectAllChecked} onChange={(e) => handleSelectAll(e.target.checked)} />
        </div>
      </div>

      <div className="source-panel__list">
        {/* keep Spin and file list mapping here */}
      </div>
    </div>

    <div className="source-panel__footer">
      <span className="source-panel__section-label">上传资料</span>
      <input ... />
      <Button icon={<UploadOutlined />} type="default" onClick={handleAddSourceClick} size="large" block loading={videoUploading}>
        上传文档/图片/视频
      </Button>
    </div>
  </div>
);
```

Rules for this step:

1. Preserve `handleResearch`, `handleSelectAll`, `handleAddSourceClick`, `handleFileChange`, `openPreview`, `openRenameModal`, and `handleDeleteFile` exactly as the behavior source.
2. Do not change the preview mode logic except for class names if needed later.
3. Do not remove the existing Ant Design controls.

- [ ] **Step 5: Refine each file-row wrapper into class-based list items**

Inside the `fileList.map(...)` block, convert the inline row into a semantic item shell:

```tsx
<div key={file.key} className="source-panel__item">
  <div
    className="source-panel__item-main"
    onClick={() => openPreview(file.key)}
    title="点击预览文档"
  >
    <span className="source-panel__item-icon">{getFileIcon(file.type, file.title, 16)}</span>
    <span className="source-panel__item-title">{file.title}</span>
  </div>
  <div className="source-panel__item-actions">
    <Dropdown menu={{ items: menuItems }} trigger={['click']} placement="bottomRight">
      <Button
        type="text"
        icon={<MoreOutlined />}
        size="small"
        className="source-panel__item-more"
        onClick={(e) => e.stopPropagation()}
      />
    </Dropdown>
    <Checkbox
      checked={checkedKeys.includes(file.key)}
      onChange={(e) => {
        e.stopPropagation();
        onCheck(file.key, e.target.checked);
      }}
      className="source-panel__item-checkbox"
    />
  </div>
</div>
```

- [ ] **Step 6: Run targeted tests to verify the structure passes**

Run:

```bash
node --test tests/frontend/sourcePanel.layout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts tests/frontend/sourcePanel.rag-participation.test.ts
```

Expected: PASS for the new layout assertions, readable copy assertions, and the existing checkbox participation guard.

- [ ] **Step 7: Commit the structural refactor**

```bash
git add frontend/src/components/teacher/SourcePanel.tsx frontend/tests/frontend/sourcePanel.layout.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts
git commit -m "feat: restructure teacher source panel shell"
```

### Task 3: Add the dedicated source-panel stylesheet and align preview mode

**Files:**
- Create: `frontend/src/components/teacher/SourcePanel.css`
- Modify: `frontend/src/components/teacher/SourcePanel.tsx`

- [ ] **Step 1: Create the dedicated stylesheet**

Create `frontend/src/components/teacher/SourcePanel.css` with the beautified shell rules:

```css
.source-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  position: relative;
  padding: 20px;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(247, 250, 252, 0.98) 100%);
}

.source-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.source-panel__title.ant-typography {
  margin: 0;
  font-weight: 700;
  font-size: 18px;
  color: #0f172a;
}

.source-panel__tools {
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.9);
}

.source-panel__research-button {
  width: 100%;
  justify-content: center;
}

.source-panel__list-section {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
}

.source-panel__list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.source-panel__section-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.source-panel__select-all {
  display: flex;
  align-items: center;
  gap: 10px;
}

.source-panel__list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.source-panel__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 12px;
  transition: background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}

.source-panel__item + .source-panel__item {
  margin-top: 6px;
}

.source-panel__item:hover {
  background: rgba(248, 250, 252, 0.96);
  border-color: rgba(148, 163, 184, 0.16);
}

.source-panel__item-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
  cursor: pointer;
}

.source-panel__item-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-panel__item-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.source-panel__footer {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(226, 232, 240, 0.9);
}
```

- [ ] **Step 2: Style preview mode with the same visual language**

In `SourcePanel.tsx`, replace the preview wrapper’s inline root shell with a class-based root:

```tsx
return (
  <div className="source-panel source-panel--preview">
    <div className="source-panel__preview-header">
      {/* keep current back button, icon, and title */}
    </div>
    <div className="source-panel__preview-body">
      {/* keep current preview Spin and content */}
    </div>
  </div>
);
```

Add the preview-mode CSS to `SourcePanel.css`:

```css
.source-panel--preview {
  padding: 20px;
}

.source-panel__preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.source-panel__preview-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 8px;
}

.source-panel--collapsed {
  padding: 12px 10px;
  align-items: center;
}
```

- [ ] **Step 3: Preserve image-preview behavior with a focused regression run**

Run:

```bash
node --test tests/frontend/sourcePanel.image-preview.test.ts tests/frontend/sourcePanel.rag-participation.test.ts
```

Expected: PASS, proving the visual refactor did not disturb image preview or checkbox-based participation behavior.

- [ ] **Step 4: Commit the stylesheet pass**

```bash
git add frontend/src/components/teacher/SourcePanel.tsx frontend/src/components/teacher/SourcePanel.css
git commit -m "style: beautify teacher source panel"
```

### Task 4: Final polish and verification pass

**Files:**
- Modify: `frontend/src/components/teacher/SourcePanel.tsx` (if needed)
- Modify: `frontend/src/components/teacher/SourcePanel.css` (if needed)

- [ ] **Step 1: Load the final polish skill**

Run one of these paths:

```bash
npx openskills read polish
```

If unavailable, run:

```powershell
Get-Content C:\Users\Administrator\.codex\impeccable\.codex\skills\polish\SKILL.md -TotalCount 180
```

- [ ] **Step 2: Make only the final polish tweaks that verification reveals**

Check and adjust:

1. Long file names still truncate cleanly in both normal and preview-adjacent states.
2. The upload footer stays visually anchored below the scrollable list.
3. Collapsed mode icons remain centered and readable.
4. The retrieval zone and list toolbar feel connected but not crowded.

Example tweak scope:

```css
.source-panel__item-title {
  font-size: 14px;
  line-height: 1.45;
}

.source-panel__collapsed-list {
  width: 100%;
  align-items: center;
}
```

- [ ] **Step 3: Run the full targeted verification set**

Run:

```bash
node --test tests/frontend/sourcePanel.layout.test.ts tests/frontend/sourcePanel.image-preview.test.ts tests/frontend/sourcePanel.rag-participation.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts
npm run build
```

Expected:

1. All targeted frontend tests PASS.
2. Vite build PASS.

- [ ] **Step 4: Commit the polish pass**

```bash
git add frontend/src/components/teacher/SourcePanel.tsx frontend/src/components/teacher/SourcePanel.css frontend/tests/frontend/sourcePanel.layout.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts
git commit -m "style: polish teacher source panel"
```

## Self-Review

### Spec coverage

- Three-part panel rhythm: covered by Task 2 and Task 3.
- Stronger header, retrieval zone, list section, and upload footer: covered by Task 2 and Task 3.
- Better list readability and action alignment: covered by Task 2 and Task 3.
- No data-flow or business-logic rewrites: enforced by the file scope and task notes.
- Explicit use of frontend beautification skills during implementation: covered by Skill Execution Notes and the first step of Tasks 2 and 4.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task includes exact files, commands, and expected outcomes.

### Type and path consistency

- The plan keeps behavior inside `SourcePanel.tsx` and moves only presentation into `SourcePanel.css`.
- Regression coverage includes new layout assertions and preserves existing preview/participation expectations.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-16-teacher-source-panel-beautification-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
