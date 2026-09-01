# OpenMAIC Phase 3 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Phase 3 with a tested LessonTimeline foundation, complete speech/focus/video playback semantics, Chinese rendering acceptance, and synchronized migration documentation.

**Architecture:** Add a pure timeline contract/compiler beside the existing OpenMAIC player, then make playback consume the compiled action ordering while recording measured wall-clock timings. Keep media ownership in the page, expose video control through an injected registry, and preserve the three A→B seams: injected clock, effect-local time, and `renderVideo`.

**Tech Stack:** React 18, TypeScript 5, Vite 6, Node test runner + tsx, `@openmaic/dsl`, `@openmaic/renderer`, FastAPI/pytest for existing classroom APIs.

---

### Task 1: Restore repeatable frontend quality gates

**Files:**
- Create: `Edu_AI/eslint.config.js`
- Modify: `frontend/package.json`
- Modify: `Edu_AI/package-lock.json`

- [ ] **Step 1: Install the TypeScript-aware ESLint flat-config dependency**

Run:

```powershell
cd Edu_AI
npm install --save-dev typescript-eslint@8.65.0 tsx@4.21.0
```

Expected: `package.json` and `package-lock.json` contain exact compatible tooling; no production dependency changes.

- [ ] **Step 2: Add the frontend test command**

Add:

```json
"test": "node --import tsx --test \"src/**/*.test.ts\""
```

- [ ] **Step 3: Add a flat ESLint configuration**

Create `eslint.config.js` using `typescript-eslint` recommended rules, `eslint-plugin-react-hooks`, and `eslint-plugin-react-refresh`; ignore `dist`, `node_modules`, and vendored/generated files. Configure browser globals explicitly and keep the existing hooks/refresh behavior.

- [ ] **Step 4: Run the gates**

Run:

```powershell
npm test
npm run lint
npm run build
```

Expected: existing Node tests pass; lint reaches source files and reports only actionable source findings; production build exits 0.

- [ ] **Step 5: Commit**

```powershell
git add Edu_AI/eslint.config.js frontend/package.json Edu_AI/package-lock.json
git commit -m "test(frontend): restore TypeScript quality gates"
```

### Task 2: Define and compile LessonTimeline

**Files:**
- Create: `frontend/src/openmaic/timeline.ts`
- Create: `frontend/src/openmaic/timeline.test.ts`

- [ ] **Step 1: Write failing contract/compiler tests**

Cover these exact behaviors:

```ts
test('compiles stable clip ids and absolute scene offsets', ...)
test('pairs pending spotlight and laser clips with the following speech', ...)
test('keeps synchronous actions serial while focus actions do not advance time', ...)
test('uses fixed duration for orphan focus actions', ...)
test('skips live-only discussion actions in the linear timeline', ...)
test('keeps source actions immutable', ...)
```

Run:

```powershell
npm test -- src/openmaic/timeline.test.ts
```

Expected: FAIL because `timeline.ts` does not exist.

- [ ] **Step 2: Implement the canonical timeline types**

Export `LessonTimeline`, `SceneSegment`, `TimelineClip`, `RenderConfig`, `TimelineDurationSource`, `TimelineTrack`, and `TimelineActionType`. Match `docs/课件视频_统一时间线契约与AB演进预留设计_2026-06-30.md` exactly, including `render`, `concurrentWith`, and stable source IDs.

- [ ] **Step 3: Implement the pure compiler**

Export:

```ts
compileLessonTimeline(input: {
  lessonId: string;
  scenes: TimelineSourceScene[];
  viewport?: { width: number; height: number; ratio: number };
  actionDurationsMs?: Readonly<Record<string, number>>;
  orphanFocusDurationMs?: number;
}): LessonTimeline
```

Rules:

- sort scenes by `order`, without mutating input;
- derive `clip.id` as `${action.id}:clip`;
- map speech to narration, spotlight/laser to focus, `play_video` to media, whiteboard/widget actions to visual;
- hold focus actions at the current cursor and bind them to the next speech window;
- advance the cursor only for synchronous linear actions;
- skip `discussion`;
- make `scene.startMs` and lesson `durationMs` explicit;
- use 1920×1080, 30 fps, H.264/MP4, muted embedded media, and sidecar SRT defaults.

- [ ] **Step 4: Verify red-green and full frontend gates**

Run:

```powershell
npm test
npm run lint
npm run build
```

Expected: timeline tests and existing tests pass; lint/build exit 0.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/openmaic/timeline.ts frontend/src/openmaic/timeline.test.ts
git commit -m "feat(player): compile OpenMAIC actions into lesson timeline"
```

### Task 3: Record measured playback timings and consume timeline order

**Files:**
- Create: `frontend/src/openmaic/timelineRecorder.ts`
- Create: `frontend/src/openmaic/timelineRecorder.test.ts`
- Modify: `frontend/src/openmaic/playbackEngine.ts`
- Create: `frontend/src/openmaic/playbackEngine.test.ts`
- Modify: `frontend/src/openmaic/SlidePlayer.tsx`

- [ ] **Step 1: Write failing recorder and engine tests**

Cover:

```ts
test('records measured action start and end relative to each scene', ...)
test('preserves stable source and clip ids in measured output', ...)
test('uses only the injected ClockSource for playback timestamps', ...)
test('emits action end after synchronous execution and before advancing', ...)
test('stops stale runs without emitting later timeline events', ...)
```

Expected: FAIL because recorder and action-end callbacks are missing.

- [ ] **Step 2: Implement `TimelineRecorder`**

Accept a compiled timeline and provide:

```ts
onActionStart(actionId: string, sceneId: string, timeMs: number): void
onActionEnd(actionId: string, sceneId: string, timeMs: number): void
snapshot(): LessonTimeline
```

`snapshot()` must return a new object, set measured clips to `durationSource: 'measured'`, recompute scene/lesson durations, and leave the compiled template immutable.

- [ ] **Step 3: Make `PlaybackEngine` timeline-aware**

Compile or accept a `LessonTimeline`, use its `actionId` ordering to locate source actions, emit start/end timestamps from the injected `ClockSource`, and expose `onTimelineChange`. Do not call `performance.now()` or `Date.now()` in the engine.

- [ ] **Step 4: Wire the single-slide player**

Compile its scene once, attach a recorder, retain `renderVideo`, and expose optional `onTimelineChange(timeline)` so Phase 5 can persist measured playback without changing player internals.

- [ ] **Step 5: Verify and commit**

Run all frontend tests, lint, and build; then:

```powershell
git add frontend/src/openmaic
git commit -m "feat(player): record measured lesson timelines"
```

### Task 4: Complete narration fallback and focus concurrency

**Files:**
- Modify: `frontend/src/openmaic/actionEngine.ts`
- Create: `frontend/src/openmaic/actionEngine.test.ts`

- [ ] **Step 1: Write failing regression tests**

Cover:

```ts
test('falls back to browser TTS when audio loading or playback fails', ...)
test('falls back to reading dwell when browser TTS is unavailable', ...)
test('keeps paired focus active until real narration ends', ...)
test('clears orphan focus after the fixed timeout', ...)
test('cancels audio, speech synthesis, and timers on dispose', ...)
```

- [ ] **Step 2: Return explicit audio outcomes**

Change the audio helper to distinguish `ended` from `failed`. On failure, continue to browser TTS; if browser TTS is unavailable/fails, wait for the deterministic reading-time dwell. Ensure cleanup resolves the current action and releases media resources.

- [ ] **Step 3: Bind focus lifetime to narration completion**

Use the compiled `concurrentWith` relationship or explicit playback context. Do not rely on a hard-coded timeout for paired effects; clear them when their paired narration ends. Keep the fixed timeout only for orphan focus.

- [ ] **Step 4: Verify and commit**

Run frontend tests, lint, and build; commit:

```powershell
git add frontend/src/openmaic/actionEngine.ts frontend/src/openmaic/actionEngine.test.ts
git commit -m "fix(player): make narration fallback and focus timing deterministic"
```

### Task 5: Implement controlled embedded-video playback

**Files:**
- Create: `frontend/src/openmaic/videoRegistry.ts`
- Create: `frontend/src/openmaic/videoRegistry.test.ts`
- Modify: `frontend/src/openmaic/actionEngine.ts`
- Modify: `frontend/src/openmaic/SlidePlayer.tsx`
- Create or modify: `frontend/src/stitch/pages/_dev/PlayerSmoke.tsx`

- [ ] **Step 1: Write failing registry/action tests**

Cover registration/unregistration, missing element degradation, `play_video` waiting for `ended`, error completion, and disposal.

- [ ] **Step 2: Implement injected video control**

`renderVideo` must register the native video element by stable element ID. `ActionEngine` receives a video controller and handles `play_video` synchronously. Video elements must not autoplay before their action; embedded audio defaults to muted.

- [ ] **Step 3: Extend the smoke fixture**

Add a real video element and `play_video` action. Include visible data attributes showing registered/playing/completed state for browser acceptance.

- [ ] **Step 4: Verify and commit**

Run frontend tests, lint, build, and browser smoke; commit:

```powershell
git add frontend/src/openmaic frontend/src/stitch/pages/_dev/PlayerSmoke.tsx
git commit -m "feat(player): control embedded video through timeline actions"
```

### Task 6: Finish Chinese rendering and Phase 3 acceptance

**Files:**
- Modify: `frontend/src/stitch/pages/_dev/PlayerSmoke.tsx`
- Modify: `docs/spec/SPEC-08_前端集成_DSL与Renderer播放.md`
- Modify: `docs/acceptance/ACC-08_前端集成播放_验收.md`
- Modify: `docs/acceptance/README.md`
- Modify: `项目总览地图.md`

- [ ] **Step 1: Add the Chinese acceptance fixture**

The fixture must render:

- Chinese text with an explicit local/system fallback stack headed by `Noto Sans SC`;
- a LaTeX formula with adjacent Chinese explanation;
- Chinese `speech` with `voice`/`speed`;
- a visible fallback-font probe and missing-element focus case.

- [ ] **Step 2: Run automated and browser acceptance**

Run:

```powershell
npm test
npm run lint
npm run build
```

Then use the local browser page to verify no tofu glyphs, formula layout, natural Chinese narration, authenticated generated audio, missing-audio fallback, spotlight/laser overlap, video timing, scene cleanup, and no uncaught errors.

- [ ] **Step 3: Update the documentation truthfully**

Mark only evidenced AC-08 items complete. Record commands, counts, browser fixture, date, and remaining non-blockers. Update the map’s Phase 3 state and current date.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/stitch/pages/_dev/PlayerSmoke.tsx docs 项目总览地图.md
git commit -m "docs(migration): close Phase 3 interaction classroom acceptance"
```

### Task 7: Phase 3 regression gate

**Files:**
- No new files expected

- [ ] **Step 1: Run full relevant verification**

```powershell
cd Edu_AI
npm test
npm run lint
npm run build

cd backend/src
conda run -n edu-ai python -m pytest tests/test_classroom_media.py tests/test_classroom_service.py tests/test_classroom_validation.py -q
```

Expected: all commands exit 0, with no new warnings caused by Phase 3 changes.

- [ ] **Step 2: Audit requirements**

Re-read `SPEC-08`, `ACC-08`, the implementation total plan Phase 3 row, and the A→B seam document. Verify each requirement against code/tests or record a blocker rather than declaring Phase 3 complete.

