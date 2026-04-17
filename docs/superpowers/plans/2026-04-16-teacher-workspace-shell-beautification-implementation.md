# Teacher Workspace Shell Beautification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the teacher workspace shell so the current `#workspace` entry feels like a mature, layered teaching workbench with a stronger top context bar, calmer surfaces, and clearer center-column focus while keeping the existing three-column workflow intact.

**Architecture:** Keep the current `AIWorkspacePage` structure and shared `AiStudioPage.css` styling surface, then refine only the page-level shell: the app background, top context bar, outer workbench container, panel treatments, spacing rhythm, and center-column emphasis. Implementation must explicitly use frontend beautification skills in sequence: `frontend-design` for overall visual language, `arrange` for layout rhythm and focus, `colorize` for restrained palette work, and `polish` for final consistency checks.

**Tech Stack:** React 18, TypeScript, Tailwind utility classes in `AIWorkspace.tsx`, shared CSS in `AiStudioPage.css`, Zustand state, Vite, `node:test`

---

## File Structure

- Modify: `Edu_AI/src/stitch/pages/AIWorkspace.tsx`
  - Refine the entry page shell, top context bar framing, main workbench wrapper, and center-column emphasis.
- Modify: `Edu_AI/src/pages/teacher/AiStudioPage.css`
  - Update shared workspace shell tokens and panel styles for calmer backgrounds, tighter borders, cleaner spacing, and stronger visual hierarchy.
- Modify: `Edu_AI/tests/frontend/aiWorkspaceEntryLayout.test.ts`
  - Add source-level regression checks for the upgraded workspace shell classes and removal of the flatter previous framing.
- Modify: `Edu_AI/tests/frontend/aiStudioLayout.test.ts`
  - Update source-level assertions so the shared shell styles reflect the new beautified design direction.

## Skill Execution Notes

Before editing implementation files, the worker must explicitly load and follow these skills:

1. `frontend-design`
   - Lock the light-mode-first, calm, product-grade visual direction.
2. `arrange`
   - Tune spacing rhythm, outer wrapper hierarchy, and center-column focus.
3. `colorize`
   - Introduce restrained neutral tinting and more purposeful accent usage without making the page noisy.
4. `polish`
   - Run a final pass on borders, shadows, spacing, responsiveness, and text fit.

Do not expand into `SourcePanel`, `ChatPanel`, or `StudioPanel` internals during this plan.

### Task 1: Add failing layout regressions for the beautified shell

**Files:**
- Modify: `Edu_AI/tests/frontend/aiWorkspaceEntryLayout.test.ts`
- Modify: `Edu_AI/tests/frontend/aiStudioLayout.test.ts`

- [ ] **Step 1: Write the failing tests**

Update `Edu_AI/tests/frontend/aiWorkspaceEntryLayout.test.ts` so it asserts the entry page includes the new shell classes and drops the flatter wrapper treatment:

```ts
assert.match(
  aiWorkspaceFile,
  /ai-workspace-shell/,
  'AIWorkspace should render the dedicated beautified workspace shell wrapper',
);

assert.match(
  aiWorkspaceFile,
  /ai-workspace-shell__main/,
  'AIWorkspace should render the layered main workbench wrapper',
);

assert.match(
  aiWorkspaceFile,
  /ai-workspace-shell__frame/,
  'AIWorkspace should render the framed three-column work area',
);

assert.doesNotMatch(
  aiWorkspaceFile,
  /rounded-\\[24px\\] border border-\\[var\\(--shell-border\\)\\] bg-\\[rgba\\(255,255,255,0\\.46\\)\\]/,
  'AIWorkspace should replace the flatter temporary frame classes with the new beautified shell classes',
);
```

Update `Edu_AI/tests/frontend/aiStudioLayout.test.ts` so it asserts the shared CSS contains the new shell selectors and refined styling targets:

```ts
assert.match(
  aiStudioCssFile,
  /\\.ai-workspace-shell/,
  'AiStudioPage.css should define the dedicated workspace shell wrapper',
);

assert.match(
  aiStudioCssFile,
  /\\.ai-workspace-shell__frame/,
  'AiStudioPage.css should style the layered workbench frame',
);

assert.match(
  aiStudioCssFile,
  /radial-gradient\\(circle at top/,
  'AiStudioPage.css should introduce a subtle layered background for the beautified shell',
);

assert.match(
  aiStudioCssFile,
  /box-shadow:\\s*0 24px 60px/,
  'AiStudioPage.css should give the workbench frame a deeper but still restrained shadow',
);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/frontend/aiWorkspaceEntryLayout.test.ts tests/frontend/aiStudioLayout.test.ts`

Expected: FAIL because the current entry page and shared CSS do not yet contain the new beautified shell wrapper classes or styling.

- [ ] **Step 3: Commit the red test snapshot**

```bash
git add Edu_AI/tests/frontend/aiWorkspaceEntryLayout.test.ts Edu_AI/tests/frontend/aiStudioLayout.test.ts
git commit -m "test: cover beautified teacher workspace shell"
```

### Task 2: Rebuild the entry page shell with stronger page-level hierarchy

**Files:**
- Modify: `Edu_AI/src/stitch/pages/AIWorkspace.tsx`

- [ ] **Step 1: Load the required beautification skills**

Run:

```bash
npx openskills read frontend-design
npx openskills read arrange
npx openskills read colorize
```

Expected: skill instructions are available before any layout edits begin.

- [ ] **Step 2: Implement the layered page shell in `AIWorkspace.tsx`**

Replace the temporary outer wrapper and main frame with explicit shell classes while keeping the same `pageStyle`, store usage, and three-panel rendering:

```tsx
return (
  <AppSurface className="ai-workspace-shell flex min-h-screen">
    <SidebarDock className="ai-workspace-shell__sidebar h-screen px-5 py-6">
      <div className="mb-6">
        <SidebarBackLink />
        <h1 className="text-xl font-black tracking-tight text-[var(--accent-strong)]">
          {courseLabel}
        </h1>
        <p className="mt-1 text-sm text-[var(--muted-text)]">教师 AI 工作台</p>
      </div>
      <SidebarNav activeRoute={routes.ai} />
    </SidebarDock>

    <main className="ai-workspace-shell__main flex h-screen min-h-0 flex-1 flex-col overflow-hidden">
      <section className="ai-studio-context-bar ai-workspace-shell__context" aria-label="当前问答上下文">
        {/* keep current course / knowledge point content */}
      </section>

      <div className="ai-workspace-shell__frame">
        <div className="ai-studio-page workspace-ai-studio-page h-full min-h-0" style={pageStyle}>
          {/* keep SourcePanel / ChatPanel / StudioPanel structure unchanged */}
        </div>
      </div>
    </main>
  </AppSurface>
);
```

Notes:

1. Keep the existing `courseLabel`, `knowledgePointLabel`, collapse toggles, and preview width logic unchanged.
2. Remove the temporary inline `bg-[#eef1f4]`, `rounded-[24px]`, and raw `bg-[rgba(...)]` frame classes once replaced by the shared shell classes.
3. Do not edit the panel internals.

- [ ] **Step 3: Run source-level tests to verify the page wiring passes**

Run: `node --test tests/frontend/aiWorkspaceEntryLayout.test.ts`

Expected: PASS with `aiWorkspaceEntryLayout tests passed`

- [ ] **Step 4: Commit the page-shell structure change**

```bash
git add Edu_AI/src/stitch/pages/AIWorkspace.tsx
git commit -m "feat: upgrade teacher workspace shell structure"
```

### Task 3: Refresh the shared shell styling for hierarchy, rhythm, and restraint

**Files:**
- Modify: `Edu_AI/src/pages/teacher/AiStudioPage.css`

- [ ] **Step 1: Implement the beautified shell styles**

Update `Edu_AI/src/pages/teacher/AiStudioPage.css` so it adds dedicated workspace shell selectors and upgrades the shared page-level styles:

```css
.ai-workspace-shell {
  min-height: 100%;
  background:
    radial-gradient(circle at top left, rgba(211, 223, 255, 0.48), transparent 24%),
    radial-gradient(circle at top right, rgba(191, 219, 254, 0.34), transparent 18%),
    linear-gradient(180deg, #f3f6fb 0%, #eef2f7 100%);
}

.ai-workspace-shell__sidebar {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(244, 247, 252, 0.98) 100%);
  border-right: 1px solid rgba(148, 163, 184, 0.16);
}

.ai-workspace-shell__main {
  padding: 18px 18px 20px;
}

.ai-workspace-shell__context {
  margin-bottom: 14px;
  min-height: 58px;
  padding: 0 18px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.05);
}

.ai-workspace-shell__frame {
  flex: 1;
  min-height: 0;
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.58) 0%, rgba(248, 250, 252, 0.78) 100%);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
}

.ai-studio-page {
  gap: 14px;
}

.ai-panel {
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%);
  box-shadow: 0 14px 36px rgba(15, 23, 42, 0.06);
}

.ai-studio-content .ai-panel {
  border-color: rgba(59, 130, 246, 0.14);
  box-shadow: 0 18px 40px rgba(37, 99, 235, 0.08);
}
```

Also keep the existing responsive rules, but adapt them to the new shell classes:

```css
@media (max-width: 992px) {
  .ai-workspace-shell__main {
    padding: 12px;
  }

  .ai-workspace-shell__frame {
    padding: 8px;
    border-radius: 20px;
  }
}
```

- [ ] **Step 2: Re-run the shared shell regression tests**

Run: `node --test tests/frontend/aiWorkspaceEntryLayout.test.ts tests/frontend/aiStudioLayout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts`

Expected: PASS with all three test files reporting success.

- [ ] **Step 3: Build the frontend to verify the page compiles**

Run: `npm run build`

Expected: PASS with Vite build output and no TypeScript or CSS errors.

- [ ] **Step 4: Commit the beautified shell styling**

```bash
git add Edu_AI/src/pages/teacher/AiStudioPage.css Edu_AI/tests/frontend/aiWorkspaceEntryLayout.test.ts Edu_AI/tests/frontend/aiStudioLayout.test.ts
git commit -m "style: beautify teacher workspace shell"
```

### Task 4: Final polish and verification pass

**Files:**
- Modify: `Edu_AI/src/stitch/pages/AIWorkspace.tsx` (if small polish tweaks are needed)
- Modify: `Edu_AI/src/pages/teacher/AiStudioPage.css` (if small polish tweaks are needed)

- [ ] **Step 1: Load the final polish skill**

Run:

```bash
npx openskills read polish
```

Expected: final consistency checklist is available before the last pass.

- [ ] **Step 2: Check and fix final polish details**

Verify and adjust only if needed:

1. Top context bar text still fits for long course and knowledge-point labels.
2. Center panel reads as the visual anchor without making side panels look disabled.
3. Background tinting stays subtle and does not make the page read as purple-blue or glassy.
4. Mobile breakpoint still hides side panels and keeps the context bar readable.

Example tweak scope:

```css
.ai-studio-context-bar__value {
  max-width: min(32vw, 420px);
}

.ai-studio-sider .ai-panel {
  background: rgba(255, 255, 255, 0.94);
}
```

- [ ] **Step 3: Run the full targeted verification set**

Run:

```bash
node --test tests/frontend/aiWorkspaceEntryLayout.test.ts tests/frontend/aiStudioLayout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts
npm run build
```

Expected:

1. All targeted frontend tests PASS.
2. Vite build PASS.

- [ ] **Step 4: Commit the polish pass**

```bash
git add Edu_AI/src/stitch/pages/AIWorkspace.tsx Edu_AI/src/pages/teacher/AiStudioPage.css
git commit -m "style: polish teacher workspace workbench shell"
```

## Self-Review

### Spec coverage

- Top context bar strengthened: covered by Task 2 and Task 3.
- Page background, frame, spacing, and panel hierarchy: covered by Task 3.
- Stronger center-column focus with restrained side panels: covered by Task 3 and Task 4.
- No deep inner-panel rewrites: enforced by the file scope and task notes.
- Explicit use of frontend beautification skills during implementation: covered by the Skill Execution Notes plus Task 2 and Task 4.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task includes exact files, commands, and expected outcomes.

### Type and path consistency

- Implementation stays within `AIWorkspace.tsx` and `AiStudioPage.css`, matching the approved spec.
- Tests target the current `#workspace` entry page and shared shell styling, not the inner panel implementations.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-16-teacher-workspace-shell-beautification-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
