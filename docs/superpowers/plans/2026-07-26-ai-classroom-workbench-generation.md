# AI Classroom Workbench Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full-width AI classroom card to the teacher chat workbench that collects a topic, submits the existing asynchronous classroom generation API, shows polling progress, and automatically opens and starts the completed classroom.

**Architecture:** Keep network contracts in the existing `stitch/api/classroom.ts` client. Add a small framework-independent flow module for polling, cancellation, retry limits, result validation, and player URL construction; put Ant Design form/state rendering in a focused `ClassroomGenerationEntry` component and mount it from `StudioPanel`. The backend requires no new production endpoint because its existing generate/job routes already provide the complete contract.

**Tech Stack:** React 18, TypeScript, Ant Design 5, Node test runner with `tsx`, FastAPI/Pydantic, pytest, Vite, ESLint.

---

## File map

- Create `Edu_AI/src/openmaic/classroomGenerationFlow.ts`: deterministic polling, cancellation, result validation, and player hash construction.
- Create `Edu_AI/src/openmaic/classroomGenerationFlow.test.ts`: unit coverage for the complete asynchronous state flow.
- Create `Edu_AI/src/components/teacher/ClassroomGenerationEntry.tsx`: full-width card, topic modal, progress, retry, and success navigation.
- Create `Edu_AI/src/components/teacher/ClassroomGenerationEntry.css`: isolated card and modal presentation.
- Modify `Edu_AI/src/components/teacher/StudioPanel.tsx`: mount the entry immediately after the workbench title divider.
- Verify `Edu_AI/src/stitch/api/classroom.ts`: reuse `generateClassroom` and `getJobStatus`; no duplicate client.
- Verify `Edu_AI/api/src/app/schemas/course.py` and `Edu_AI/api/src/app/api/courses.py`: existing `enable_tts=true`, `202` submission, and job polling contract remain unchanged.

### Task 1: Build the tested classroom generation flow

**Files:**
- Create: `Edu_AI/src/openmaic/classroomGenerationFlow.test.ts`
- Create: `Edu_AI/src/openmaic/classroomGenerationFlow.ts`

- [ ] **Step 1: Write the failing result and URL tests**

```ts
import assert from 'node:assert/strict';
import test from 'node:test';
import type { EduJob } from '../stitch/api/types.ts';
import {
  buildClassroomPlayerHash,
  waitForClassroomGenerationJob,
} from './classroomGenerationFlow.ts';

function job(status: EduJob['status'], overrides: Partial<EduJob> = {}): EduJob {
  return {
    edu_job_id: 'job-classroom-1',
    kind: 'generate_classroom',
    status,
    step: status,
    progress: status === 'succeeded' ? 100 : 10,
    message: '',
    created_at: '',
    updated_at: '',
    ...overrides,
  };
}

test('buildClassroomPlayerHash encodes course and classroom ids', () => {
  assert.equal(
    buildClassroomPlayerHash('course/一', 'classroom?二'),
    '#classroom-player?course_id=course%2F%E4%B8%80&classroom_id=classroom%3F%E4%BA%8C',
  );
});

test('waitForClassroomGenerationJob reports progress and returns the classroom result', async () => {
  const states = [
    job('running', { step: 'researching', progress: 30 }),
    job('succeeded', {
      result_ref: { course_id: 'course-1', classroom_id: 'classroom-1', scenes_count: 9 },
    }),
  ];
  const progress: number[] = [];
  const result = await waitForClassroomGenerationJob(job('queued'), {
    getStatus: async () => states.shift()!,
    sleep: async () => undefined,
    onProgress: (current) => progress.push(current.progress),
  });

  assert.equal(result.classroom_id, 'classroom-1');
  assert.deepEqual(progress, [10, 30, 100]);
});
```

- [ ] **Step 2: Run the targeted test and verify RED**

Run:

```powershell
Set-Location Edu_AI
npm test -- --test-name-pattern "buildClassroomPlayerHash|waitForClassroomGenerationJob"
```

Expected: FAIL because `classroomGenerationFlow.ts` does not exist.

- [ ] **Step 3: Add failure, retry, missing-result, and cancellation tests**

```ts
test('continues after a transient poll failure', async () => {
  let calls = 0;
  const result = await waitForClassroomGenerationJob(job('queued'), {
    getStatus: async () => {
      calls += 1;
      if (calls === 1) throw new Error('temporary network error');
      return job('succeeded', {
        result_ref: { course_id: 'course-1', classroom_id: 'classroom-1' },
      });
    },
    sleep: async () => undefined,
  });
  assert.equal(result.classroom_id, 'classroom-1');
});

test('surfaces a failed generation job', async () => {
  await assert.rejects(
    waitForClassroomGenerationJob(job('failed', { error: '生成失败' }), {
      getStatus: async () => job('failed'),
      sleep: async () => undefined,
    }),
    /生成失败/,
  );
});

test('rejects success without a classroom result', async () => {
  await assert.rejects(
    waitForClassroomGenerationJob(job('succeeded'), {
      getStatus: async () => job('succeeded'),
      sleep: async () => undefined,
    }),
    /课堂生成完成但缺少课堂结果/,
  );
});

test('stops polling when aborted', async () => {
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    waitForClassroomGenerationJob(job('queued'), {
      signal: controller.signal,
      getStatus: async () => job('running'),
      sleep: async () => undefined,
    }),
    /课堂生成已取消/,
  );
});
```

- [ ] **Step 4: Implement the minimal framework-independent flow**

```ts
import type { EduJob } from '../stitch/api/types.ts';

export type ClassroomGenerationResultRef = NonNullable<EduJob['result_ref']> & {
  course_id: string;
  classroom_id: string;
};

export interface ClassroomGenerationDependencies {
  getStatus: (jobId: string) => Promise<EduJob>;
  sleep?: (durationMs: number) => Promise<void>;
  pollIntervalMs?: number;
  maxConsecutivePollErrors?: number;
  onProgress?: (job: EduJob) => void;
  signal?: AbortSignal;
}

function assertNotAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new Error('课堂生成已取消');
}

export function buildClassroomPlayerHash(courseId: string, classroomId: string): string {
  return `#classroom-player?course_id=${encodeURIComponent(courseId)}&classroom_id=${encodeURIComponent(classroomId)}`;
}

export async function waitForClassroomGenerationJob(
  initialJob: EduJob,
  dependencies: ClassroomGenerationDependencies,
): Promise<ClassroomGenerationResultRef> {
  const sleep =
    dependencies.sleep ??
    ((durationMs: number) => new Promise<void>((resolve) => window.setTimeout(resolve, durationMs)));
  const maxErrors = dependencies.maxConsecutivePollErrors ?? 3;
  let consecutiveErrors = 0;
  let current = initialJob;
  dependencies.onProgress?.(current);

  while (current.status === 'queued' || current.status === 'running') {
    assertNotAborted(dependencies.signal);
    await sleep(dependencies.pollIntervalMs ?? 4000);
    assertNotAborted(dependencies.signal);
    try {
      current = await dependencies.getStatus(current.edu_job_id);
      consecutiveErrors = 0;
      dependencies.onProgress?.(current);
    } catch (error) {
      assertNotAborted(dependencies.signal);
      consecutiveErrors += 1;
      if (consecutiveErrors > maxErrors) throw error;
    }
  }

  if (current.status === 'failed') {
    throw new Error(current.error || current.message || 'AI 课堂生成失败');
  }
  if (!current.result_ref?.course_id || !current.result_ref.classroom_id) {
    throw new Error('课堂生成完成但缺少课堂结果');
  }
  return current.result_ref as ClassroomGenerationResultRef;
}
```

- [ ] **Step 5: Run targeted and full frontend tests**

Run:

```powershell
Set-Location Edu_AI
npm test -- --test-name-pattern "ClassroomGeneration|classroom generation|课堂生成|buildClassroomPlayerHash"
npm test
```

Expected: targeted tests PASS; full frontend suite PASS.

- [ ] **Step 6: Commit the flow**

```powershell
git add Edu_AI/src/openmaic/classroomGenerationFlow.ts Edu_AI/src/openmaic/classroomGenerationFlow.test.ts
git commit -m "feat(classroom): add generation polling flow"
```

### Task 2: Add the full-width workbench entry and modal

**Files:**
- Create: `Edu_AI/src/components/teacher/ClassroomGenerationEntry.tsx`
- Create: `Edu_AI/src/components/teacher/ClassroomGenerationEntry.css`
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx:70-80`
- Modify: `Edu_AI/src/components/teacher/StudioPanel.tsx:2861-2890`

- [ ] **Step 1: Add a failing placement regression test**

Append to `Edu_AI/src/openmaic/classroomGenerationFlow.test.ts`:

```ts
import { readFile } from 'node:fs/promises';

test('StudioPanel mounts the AI classroom entry before the generation grids', async () => {
  const source = await readFile(
    new URL('../components/teacher/StudioPanel.tsx', import.meta.url),
    'utf8',
  );
  const entryIndex = source.indexOf('<ClassroomGenerationEntry');
  const gridIndex = source.indexOf('className="studio-panel__primary-grid"');
  assert.ok(entryIndex >= 0, 'AI classroom entry is missing');
  assert.ok(gridIndex >= 0, 'generation grid is missing');
  assert.ok(entryIndex < gridIndex, 'AI classroom entry must precede other generation cards');
});
```

- [ ] **Step 2: Run the placement test and verify RED**

Run:

```powershell
Set-Location Edu_AI
npm test -- --test-name-pattern "StudioPanel mounts"
```

Expected: FAIL with `AI classroom entry is missing`.

- [ ] **Step 3: Create the focused entry component**

Implement `ClassroomGenerationEntry.tsx` with these exact state transitions:

```tsx
import { useEffect, useRef, useState } from 'react';
import { Button, Input, Modal, Progress, Typography, message } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { generateClassroom, getJobStatus, CLASSROOM_STEP_LABELS } from '../../stitch/api/classroom';
import type { EduJob } from '../../stitch/api/types';
import {
  buildClassroomPlayerHash,
  waitForClassroomGenerationJob,
} from '../../openmaic/classroomGenerationFlow';
import './ClassroomGenerationEntry.css';

const { Text } = Typography;

export function ClassroomGenerationEntry({ courseId }: { courseId?: string }) {
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState('');
  const [job, setJob] = useState<EduJob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  function openModal() {
    if (!courseId) {
      message.warning('请先选择一门课程');
      return;
    }
    setError(null);
    setJob(null);
    setOpen(true);
  }

  function closeModal() {
    if (submitting) return;
    abortRef.current?.abort();
    setOpen(false);
  }

  async function submit() {
    const requirement = topic.trim();
    if (!courseId || !requirement || submitting) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setSubmitting(true);
    setError(null);
    try {
      const initial = await generateClassroom(courseId, {
        requirement,
        enable_tts: true,
      });
      const result = await waitForClassroomGenerationJob(initial, {
        getStatus: getJobStatus,
        signal: controller.signal,
        onProgress: setJob,
      });
      setOpen(false);
      window.location.hash = buildClassroomPlayerHash(result.course_id, result.classroom_id);
    } catch (caught) {
      if (!controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : 'AI 课堂生成失败，请重试');
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setSubmitting(false);
      }
    }
  }

  return (
    <>
      <section className="classroom-generation-entry" aria-label="AI 课堂生成">
        <div className="classroom-generation-entry__icon"><PlayCircleOutlined /></div>
        <div className="classroom-generation-entry__copy">
          <strong>AI 课堂</strong>
          <span>输入主题，自动生成可播放、可导出的课堂。</span>
        </div>
        <Button type="primary" onClick={openModal} disabled={!courseId}>开始备课</Button>
      </section>
      <Modal
        title="生成 AI 课堂"
        open={open}
        onCancel={closeModal}
        footer={null}
        closable={!submitting}
        maskClosable={!submitting}
        destroyOnClose={false}
      >
        <Input.TextArea
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
          placeholder="例如：讲解冒泡排序的基本原理、过程和时间复杂度"
          rows={4}
          disabled={submitting}
          maxLength={500}
          showCount
        />
        {job ? (
          <div className="classroom-generation-entry__progress">
            <div>
              <Text strong>{CLASSROOM_STEP_LABELS[job.step] ?? job.step}</Text>
              <Text type="secondary">{job.progress}%</Text>
            </div>
            <Progress percent={job.progress} status="active" />
            <Text type="secondary">{job.message}</Text>
          </div>
        ) : null}
        {error ? <Text type="danger">{error}</Text> : null}
        <div className="classroom-generation-entry__modal-actions">
          <Button onClick={closeModal} disabled={submitting}>取消</Button>
          <Button type="primary" loading={submitting} disabled={!topic.trim()} onClick={() => void submit()}>
            {submitting ? '正在生成课堂' : error ? '重新生成' : '开始生成'}
          </Button>
        </div>
      </Modal>
    </>
  );
}
```

- [ ] **Step 4: Add isolated full-width card styles**

Create `ClassroomGenerationEntry.css` with a single-row card, blue-violet accent,
responsive wrapping under narrow widths, a progress block, and right-aligned modal
actions. Use the existing CSS variables and Ant Design button classes; do not add
global element selectors.

```css
.classroom-generation-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(238, 242, 255, 0.96), rgba(239, 246, 255, 0.9));
}

.classroom-generation-entry__icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  border-radius: 12px;
  background: #4f46e5;
  color: #fff;
  font-size: 19px;
}

.classroom-generation-entry__copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  color: #0f172a;
}

.classroom-generation-entry__copy span {
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.classroom-generation-entry__progress {
  display: grid;
  gap: 8px;
  margin-top: 18px;
  padding: 14px;
  border-radius: 12px;
  background: #f8fafc;
}

.classroom-generation-entry__progress > div:first-child,
.classroom-generation-entry__modal-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.classroom-generation-entry__modal-actions {
  margin-top: 20px;
}

@media (max-width: 1280px) {
  .classroom-generation-entry {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .classroom-generation-entry > .ant-btn {
    width: 100%;
  }
}
```

- [ ] **Step 5: Mount the entry immediately below the title divider**

Import and render in `StudioPanel.tsx`:

```tsx
import { ClassroomGenerationEntry } from './ClassroomGenerationEntry';
```

```tsx
<div className="studio-panel__divider" />
<ClassroomGenerationEntry courseId={courseId} />
```

Keep all existing report/lesson-plan/quiz/game modals and generation grids unchanged.

- [ ] **Step 6: Run placement, flow, and full frontend tests**

Run:

```powershell
Set-Location Edu_AI
npm test -- --test-name-pattern "StudioPanel mounts|classroom generation|ClassroomGeneration|buildClassroomPlayerHash"
npm test
```

Expected: all targeted tests PASS and the full suite PASS.

- [ ] **Step 7: Commit the UI integration**

```powershell
git add Edu_AI/src/components/teacher/ClassroomGenerationEntry.tsx Edu_AI/src/components/teacher/ClassroomGenerationEntry.css Edu_AI/src/components/teacher/StudioPanel.tsx Edu_AI/src/openmaic/classroomGenerationFlow.test.ts
git commit -m "feat(frontend): generate AI classroom from chat workbench"
```

### Task 3: Verify the existing backend contract and production frontend

**Files:**
- Verify only: `Edu_AI/src/stitch/api/classroom.ts`
- Verify only: `Edu_AI/api/src/app/schemas/course.py`
- Verify only: `Edu_AI/api/src/app/api/courses.py`
- Verify only: `Edu_AI/api/src/app/api/jobs.py`

- [ ] **Step 1: Run classroom generation and job-service backend tests**

Run:

```powershell
Set-Location Edu_AI/api/src
python -m pytest tests/test_classroom_job_service.py tests/test_classroom_service.py tests/test_classroom_persistence.py tests/test_classroom_media.py -q
```

Expected: all selected tests PASS.

- [ ] **Step 2: Confirm the frontend API and backend schema agree**

Check these exact contract points:

```text
POST /api/courses/{course_id}/classrooms/generate
request: { requirement: string, enable_tts: true }
response: HTTP 202 + EduJob
GET /api/jobs/{edu_job_id}
success: status=succeeded and result_ref.course_id/classroom_id
```

Expected: no production backend changes are needed. If a mismatch is found, add a
failing backend test before changing the route or schema.

- [ ] **Step 3: Run production gates**

Run:

```powershell
Set-Location Edu_AI
npm run lint
npm run build
```

Expected: ESLint has 0 errors (existing warnings allowed); Vite production build succeeds.

- [ ] **Step 4: Browser-verify the complete user flow**

Run the existing backend and frontend using the documented local commands, log in with
the existing test teacher account, select a course, and open `#ai`.

Verify:

```text
1. The full-width AI classroom card is the first card below "生成式工厂".
2. "开始备课" opens the topic modal.
3. Blank topics cannot submit.
4. A real topic submits once and displays queued/running step and percentage.
5. Success navigates to #classroom-player with encoded course_id/classroom_id.
6. The first slide starts automatically and scenes advance.
7. The player still exposes PPTX and MP4 export actions.
8. Browser console has 0 errors caused by this flow.
```

- [ ] **Step 5: Commit any verification-only documentation update**

If no code changes were required, update the design document’s verification section with
the exact test counts and browser result, then commit:

```powershell
git add docs/superpowers/specs/2026-07-26-ai-classroom-entry-button-design-cn.md
git commit -m "docs(frontend): record classroom workbench acceptance"
```

### Task 4: Merge the completed migration branch into main

**Files:**
- No source edits expected.

- [ ] **Step 1: Invoke completion verification and code-review skills**

Use `superpowers:verification-before-completion` and
`superpowers:requesting-code-review`. Resolve any actionable finding with a failing
test first, rerun the relevant gate, and commit the fix separately.

- [ ] **Step 2: Confirm both worktrees are clean and identify the merge base**

Run:

```powershell
git -C C:\Users\Tang\.config\superpowers\worktrees\edu_ai\openmaic-migration-completion status --short --branch
git -C D:\github\edu_ai status --short --branch
git -C D:\github\edu_ai merge-base main codex/openmaic-migration-completion
```

Expected: both worktrees are clean; `D:\github\edu_ai` is on `main`.

- [ ] **Step 3: Merge without rewriting the staged migration history**

Run from `D:\github\edu_ai`:

```powershell
git merge --ff-only codex/openmaic-migration-completion
```

Expected: fast-forward succeeds and all per-stage commits remain intact. If `main` moved
and fast-forward is impossible, stop and inspect the divergence before creating a merge
commit.

- [ ] **Step 4: Re-run the release gates on main**

Run the full frontend tests, lint, build, and focused classroom backend suite from the
main worktree. Also run the repository’s documented migration static gate.

Expected: results match the feature worktree. Any known pre-existing full-backend
failures must be reported separately and must not be represented as caused by this merge.

- [ ] **Step 5: Clean up only after verified integration**

After main verification succeeds:

```powershell
git worktree remove C:\Users\Tang\.config\superpowers\worktrees\edu_ai\openmaic-migration-completion
git branch -d codex/openmaic-migration-completion
```

Expected: the merged worktree and local feature branch are removed; `main` retains all
migration and classroom-entry commits.

