# Teacher QA Workbench Visual Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the teacher AI studio shell so it shows the current course and knowledge point at the top while making the three-column workspace cleaner, calmer, and more product-grade without restructuring the inner panels.

**Architecture:** Keep the existing three-column `AiStudioPage` layout and add a lightweight page-level context bar above it. Source the course label from `useCourseStore.currentCourse`, source the knowledge point label from the explicit `statusCard.topics` state already stored in `useStore`, and confine the visual refresh to `AiStudioPage` plus page-scoped helpers and tests.

**Tech Stack:** React 18, TypeScript, Zustand, Ant Design, Vite, CSS, `node:test`

---

## File Structure

- Create: `frontend/src/pages/teacher/aiStudioContext.ts`
  - Page-scoped helpers that derive the display labels for the top context bar.
- Modify: `frontend/src/pages/teacher/AiStudioPage.tsx`
  - Add the context bar, wire it to store state, and keep the existing dynamic grid behavior.
- Modify: `frontend/src/pages/teacher/AiStudioPage.css`
  - Replace the current decorative shell styling with the calmer page background, context bar, and cleaner panel treatments.
- Create: `frontend/tests/frontend/aiStudioContext.test.ts`
  - Unit coverage for the context-label derivation logic.
- Create: `frontend/tests/frontend/aiStudioLayout.test.ts`
  - Source-level regression checks for the new top context bar and refreshed shell styling.
- Modify: `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts`
  - Extend the existing text-safety checks so the new user-facing labels stay readable.

### Task 1: Add page-level context label helpers

**Files:**
- Create: `frontend/src/pages/teacher/aiStudioContext.ts`
- Test: `frontend/tests/frontend/aiStudioContext.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import assert from 'node:assert/strict';

import {
  getAiStudioCourseLabel,
  getAiStudioKnowledgePointLabel,
} from '../../src/pages/teacher/aiStudioContext.ts';

assert.equal(
  getAiStudioCourseLabel({ title: '操作系统' } as any, 'course-1'),
  '操作系统',
);

assert.equal(
  getAiStudioCourseLabel(null, 'course-1'),
  'course-1',
);

assert.equal(
  getAiStudioCourseLabel(null, ''),
  '未指定课程',
);

assert.equal(
  getAiStudioKnowledgePointLabel({ topics: ['进程调度', '线程'] } as any),
  '进程调度',
);

assert.equal(
  getAiStudioKnowledgePointLabel({ topics: ['   ', '线程'] } as any),
  '线程',
);

assert.equal(
  getAiStudioKnowledgePointLabel(null),
  '未指定知识点',
);

console.log('aiStudioContext tests passed');
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/frontend/aiStudioContext.test.ts`  
Expected: FAIL with `Cannot find module '../../src/pages/teacher/aiStudioContext.ts'` or missing export errors.

- [ ] **Step 3: Write minimal implementation**

```ts
import type { StatusCardV2 } from '../../services/teacher/chatV2';
import type { Course } from '../../store/course/useCourseStore';

export function getAiStudioCourseLabel(currentCourse: Course | null, courseId?: string): string {
  const title = String(currentCourse?.title || '').trim();
  if (title) {
    return title;
  }

  const fallbackCourseId = String(courseId || '').trim();
  return fallbackCourseId || '未指定课程';
}

export function getAiStudioKnowledgePointLabel(statusCard: StatusCardV2 | null): string {
  const firstTopic = Array.isArray(statusCard?.topics)
    ? statusCard.topics.map((item) => String(item || '').trim()).find(Boolean)
    : '';

  return firstTopic || '未指定知识点';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/frontend/aiStudioContext.test.ts`  
Expected: PASS with `aiStudioContext tests passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/teacher/aiStudioContext.ts frontend/tests/frontend/aiStudioContext.test.ts
git commit -m "feat: add ai studio context label helpers"
```

### Task 2: Add the top context bar to the AI studio page

**Files:**
- Modify: `frontend/src/pages/teacher/AiStudioPage.tsx`
- Create: `frontend/tests/frontend/aiStudioLayout.test.ts`
- Modify: `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts`

- [ ] **Step 1: Write the failing tests**

Add `frontend/tests/frontend/aiStudioLayout.test.ts`:

```ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const aiStudioPageFile = readFileSync(
  new URL('../../src/pages/teacher/AiStudioPage.tsx', import.meta.url),
  'utf8',
);

assert.match(
  aiStudioPageFile,
  /当前课程/,
  'AiStudioPage should render a visible 当前课程 label in the top context bar',
);

assert.match(
  aiStudioPageFile,
  /当前知识点/,
  'AiStudioPage should render a visible 当前知识点 label in the top context bar',
);

assert.match(
  aiStudioPageFile,
  /ai-studio-context-bar/,
  'AiStudioPage should render the context bar shell class before the three-column workspace',
);

assert.match(
  aiStudioPageFile,
  /getAiStudioCourseLabel/,
  'AiStudioPage should use the page-scoped course label helper',
);

assert.match(
  aiStudioPageFile,
  /getAiStudioKnowledgePointLabel/,
  'AiStudioPage should use the page-scoped knowledge point label helper',
);

console.log('aiStudioLayout tests passed');
```

Extend `frontend/tests/frontend/teacherWorkspace.text-safety.test.ts` with:

```ts
const aiStudioPageFile = readFileSync(
  new URL('../../src/pages/teacher/AiStudioPage.tsx', import.meta.url),
  'utf8',
);

assert.match(
  aiStudioPageFile,
  /当前课程/,
  'AiStudioPage should keep the current-course label readable',
);

assert.match(
  aiStudioPageFile,
  /当前知识点/,
  'AiStudioPage should keep the current-knowledge-point label readable',
);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/frontend/aiStudioLayout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts`  
Expected: FAIL because `AiStudioPage.tsx` does not yet contain the new labels, helper calls, or context bar class.

- [ ] **Step 3: Write minimal implementation**

Update `frontend/src/pages/teacher/AiStudioPage.tsx` to pull state from both stores and render the top bar ahead of the grid:

```tsx
import React, { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import SourcePanel from '../../components/teacher/SourcePanel';
import ChatPanel from '../../components/teacher/ChatPanel';
import StudioPanel from '../../components/teacher/StudioPanel';
import { useCourseStore } from '../../store/course/useCourseStore';
import { useStore } from '../../store/teacher/useStore';
import {
  getAiStudioCourseLabel,
  getAiStudioKnowledgePointLabel,
} from './aiStudioContext';
import './AiStudioPage.css';

export default function AiStudioPage() {
  const { courseId } = useParams();
  const currentCourse = useCourseStore((state) => state.currentCourse);
  const statusCard = useStore((state) => state.statusCard);
  const courseLabel = getAiStudioCourseLabel(currentCourse, courseId);
  const knowledgePointLabel = getAiStudioKnowledgePointLabel(statusCard);

  // keep existing width and preview logic here

  return (
    <div className="ai-studio-shell workspace-ai-studio-page">
      <section className="ai-studio-context-bar" aria-label="当前问答上下文">
        <div className="ai-studio-context-bar__item">
          <span className="ai-studio-context-bar__label">当前课程</span>
          <span className="ai-studio-context-bar__value" title={courseLabel}>{courseLabel}</span>
        </div>

        <span className="ai-studio-context-bar__divider" aria-hidden="true" />

        <div className="ai-studio-context-bar__item">
          <span className="ai-studio-context-bar__label">当前知识点</span>
          <span className="ai-studio-context-bar__value" title={knowledgePointLabel}>{knowledgePointLabel}</span>
        </div>
      </section>

      <div className="ai-studio-page" style={pageStyle}>
        {/* keep existing SourcePanel / ChatPanel / StudioPanel rendering */}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/frontend/aiStudioLayout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts`  
Expected: PASS with both `aiStudioLayout tests passed` and `teacherWorkspace.text-safety tests passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/teacher/AiStudioPage.tsx frontend/tests/frontend/aiStudioLayout.test.ts frontend/tests/frontend/teacherWorkspace.text-safety.test.ts
git commit -m "feat: add ai studio top context bar"
```

### Task 3: Refresh the page shell styling and verify the full frontend build

**Files:**
- Modify: `frontend/src/pages/teacher/AiStudioPage.css`
- Modify: `frontend/tests/frontend/aiStudioLayout.test.ts`

- [ ] **Step 1: Write the failing CSS assertions**

Extend `frontend/tests/frontend/aiStudioLayout.test.ts`:

```ts
const aiStudioCssFile = readFileSync(
  new URL('../../src/pages/teacher/AiStudioPage.css', import.meta.url),
  'utf8',
);

assert.match(
  aiStudioCssFile,
  /\.ai-studio-shell/,
  'AiStudioPage.css should define the outer studio shell',
);

assert.match(
  aiStudioCssFile,
  /\.ai-studio-context-bar/,
  'AiStudioPage.css should style the top context bar',
);

assert.match(
  aiStudioCssFile,
  /background:\s*linear-gradient\(180deg,\s*#f4f6f8 0%,\s*#eef1f4 100%\)/,
  'AiStudioPage.css should use the calmer neutral page background',
);

assert.match(
  aiStudioCssFile,
  /border-radius:\s*18px/,
  'AiStudioPage.css should tighten panel corner radius for a more product-grade shell',
);

assert.doesNotMatch(
  aiStudioCssFile,
  /backdrop-filter:\s*blur/i,
  'AiStudioPage.css should remove the previous glassmorphism blur treatment',
);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/frontend/aiStudioLayout.test.ts`  
Expected: FAIL because the CSS file does not yet define the new shell classes or remove the blur styling.

- [ ] **Step 3: Write minimal implementation**

Update `frontend/src/pages/teacher/AiStudioPage.css`:

```css
.ai-studio-shell {
  min-height: 100%;
  margin: -16px;
  padding: 16px 18px 18px;
  background: linear-gradient(180deg, #f4f6f8 0%, #eef1f4 100%);
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-sizing: border-box;
}

.workspace-ai-studio-page {
  height: 100%;
  min-height: 0;
}

.ai-studio-context-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 52px;
  padding: 0 16px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
}

.ai-studio-context-bar__item {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.ai-studio-context-bar__label {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.ai-studio-context-bar__value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.ai-studio-context-bar__divider {
  width: 1px;
  height: 18px;
  background: rgba(148, 163, 184, 0.4);
}

.ai-studio-page {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 12px;
  min-width: 0;
  overflow: hidden;
}

.ai-panel {
  position: relative;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
}

.ai-panel::before {
  content: none;
}

@media (max-width: 992px) {
  .ai-studio-shell {
    margin: -12px;
    padding: 12px;
  }

  .ai-studio-context-bar {
    flex-wrap: wrap;
    row-gap: 8px;
    min-height: auto;
    padding: 12px 14px;
  }

  .ai-studio-context-bar__divider {
    display: none;
  }
}
```

- [ ] **Step 4: Run tests and build to verify they pass**

Run: `node --test tests/frontend/aiStudioContext.test.ts tests/frontend/aiStudioLayout.test.ts tests/frontend/teacherWorkspace.text-safety.test.ts`  
Expected: PASS with all three frontend checks succeeding

Run: `npm run build` (from `Edu_AI`)  
Expected: Vite production build completes successfully

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/teacher/AiStudioPage.css frontend/tests/frontend/aiStudioLayout.test.ts
git commit -m "style: refresh ai studio workspace shell"
```

## Self-Review Notes

- Spec coverage:
  - Top context bar: covered by Task 2
  - Course and knowledge-point sourcing with explicit fallback: covered by Task 1 and Task 2
  - Preserve three-column structure: Task 2 modifies only `AiStudioPage.tsx`
  - Visual refresh of background, spacing, border, radius, shadow: covered by Task 3
  - Responsive fallback and no glassmorphism blur: covered by Task 3
- Placeholder scan:
  - No `TODO`, `TBD`, or hand-wavy “style appropriately” instructions remain
  - Every code-changing step contains concrete snippets
- Type consistency:
  - Helper names are consistent across tests and page integration
  - State sources are fixed to `useCourseStore.currentCourse` and `useStore.statusCard`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-16-teacher-qa-workbench-visual-refresh-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
