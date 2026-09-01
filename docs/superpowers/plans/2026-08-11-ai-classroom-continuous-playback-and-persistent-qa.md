# AI Classroom Continuous Playback and Persistent Q&A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove retrieval latency from live classroom Q&A, make the chat a persistent optimistic right rail, continue automatically across pages, and use one young-female TTS profile for narration and answers.

**Architecture:** Keep the existing SPEC-12 API, checkpoint, session, authorization, and answer-resume flow. Build Q&A prompts only from server-owned classroom/session data, project the in-flight turn into the UI immediately, let the player orchestrate valid page completions into `enter(next) → play()`, and pass one server-owned OpenMAIC TTS profile through both classroom-generation and live-answer paths.

**Tech Stack:** React 18, TypeScript, Node test runner, Python/FastAPI/pytest, Next.js sidecar, Vitest, OpenMAIC DSL/renderer, Qwen TTS.

---

## Preconditions

- Work in the isolated branch/worktree created for SPEC-13; do not mix unrelated main-worktree changes.
- Read [SPEC-13](../../spec/SPEC-13_AI课堂连续授课与常驻问答体验优化.md) and [ACC-13](../../acceptance/ACC-13_AI课堂连续授课与常驻问答体验优化_验收.md) before implementation.
- Use test-driven development for every task: add/modify a failing test, run it and observe the intended failure, implement the minimum change, rerun the focused test, then commit.
- Do not add an alternative RAG flag or retain a dormant live-Q&A retrieval branch. This feature has one deterministic no-retrieval path.
- Do not regenerate existing classroom audio as part of migration.

## Task 1: Remove RAG from the live Q&A backend

**Files:**

- Modify: `backend/src/app/services/classroom_qa_prompt.py`
- Modify: `backend/src/app/services/classroom_qa_service.py`
- Modify: `backend/src/tests/test_classroom_qa_prompt.py`
- Modify: `backend/src/tests/test_classroom_qa_service.py`

- [ ] Add a failing prompt test that constructs `ClassroomQaContext` without `rag_answer`, asserts current/previous speech and recent turns are present, and asserts all retrieval labels are absent:

```python
assert "当前场景完整讲稿" in prompt
assert "课程知识库参考" not in prompt
assert "RAG" not in prompt
```

- [ ] Replace the existing service retrieval test with a dependency that raises if called, then submit a turn and assert the turn still completes:

```python
def forbidden_retrieval(*_args, **_kwargs):
    raise AssertionError("live classroom Q&A must not retrieve")
```

The final service constructor must no longer accept or invoke this dependency; the temporary raising stub is only used to demonstrate the old behavior before changing the constructor.

- [ ] Run the focused tests and confirm they fail for the old `rag_answer` field/call:

```powershell
Set-Location backend
python -m pytest src/tests/test_classroom_qa_prompt.py src/tests/test_classroom_qa_service.py -q
```

- [ ] Remove `rag_answer` from `ClassroomQaContext`, remove the knowledge-base prompt block, and change the boundary instruction to say that unsupported facts must be acknowledged and redirected to the current lesson.

- [ ] Remove `rag_search`, `_search_course_knowledge`, `_rag_answer`, `rag_ms`, and `rag_degraded` from `ClassroomQaService`. Time local context/prompt construction as `context_ms`; retain `llm_ms`, `tts_ms`, `total_ms`, result, and stable error information.

- [ ] Rerun the focused tests and the static absence gate:

```powershell
Set-Location backend
python -m pytest src/tests/test_classroom_qa_prompt.py src/tests/test_classroom_qa_service.py -q
rg -n "rag_search|rag_answer|_search_course_knowledge|课程知识库参考|rag_ms|rag_degraded" src/app/services/classroom_qa_prompt.py src/app/services/classroom_qa_service.py
```

Expected: pytest passes; `rg` has no matches and exits 1.

- [ ] Commit:

```powershell
git add backend/src/app/services/classroom_qa_prompt.py backend/src/app/services/classroom_qa_service.py backend/src/tests/test_classroom_qa_prompt.py backend/src/tests/test_classroom_qa_service.py
git commit -m "perf(classroom): remove retrieval from live qa"
```

## Task 2: Replace open/closed Q&A state with a persistent optimistic turn

**Files:**

- Modify: `frontend/src/stitch/classroomQa/classroomQaState.ts`
- Modify: `frontend/src/stitch/classroomQa/classroomQaState.test.ts`

- [ ] Add failing reducer tests for the initial `ready` phase, immediate `activeTurn`, server reconciliation by `clientTurnId`, retry retention, and duplicate prevention:

```ts
assert.equal(initialClassroomQaState.phase, "ready");
assert.deepEqual(selectVisibleTurns(submitting).map((turn) => turn.question), ["为什么选这个基准值？"]);
assert.equal(selectVisibleTurns(received).length, 1);
```

- [ ] Run the state tests and confirm the old `closed/drafting/isOpen` model fails:

```powershell
Set-Location Edu_AI
npm test -- src/stitch/classroomQa/classroomQaState.test.ts
```

- [ ] Change the phase union to `ready | submitting | loading_audio | playing_answer | resuming | error`; remove `isOpen` and open/close transitions.

- [ ] Define an optimistic active-turn view model containing at least `clientTurnId`, `question`, `status`, and `errorCode`. Add a pure `selectVisibleTurns` that appends it only when no durable turn has the same `clientTurnId`.

- [ ] Ensure a failed turn retains its question and ID; `retry` re-enters `submitting`, while `abandon` clears it only after the resume path begins.

- [ ] Rerun the focused state tests and commit:

```powershell
Set-Location Edu_AI
npm test -- src/stitch/classroomQa/classroomQaState.test.ts
Set-Location ..
git add frontend/src/stitch/classroomQa/classroomQaState.ts frontend/src/stitch/classroomQa/classroomQaState.test.ts
git commit -m "feat(classroom): model persistent optimistic qa"
```

## Task 3: Interrupt on submit instead of on input/open

**Files:**

- Modify: `frontend/src/stitch/classroomQa/useClassroomInterruption.ts`
- Modify: `frontend/src/stitch/classroomQa/useClassroomInterruption.test.ts`

- [ ] Add failing hook-orchestrator tests proving that initialization/focus/typing never call `suspend`, while a valid submit calls operations in this order:

```text
checkpoint/suspend → optimistic dispatch → request → answer audio → resume
```

Also assert the optimistic dispatch occurs before the request promise resolves.

- [ ] Add failure tests: invalid question does not suspend; checkpoint failure preserves the draft; POST failure preserves the active turn and checkpoint; retry reuses the same `clientTurnId`; abandon resumes once.

- [ ] Run the focused tests and observe failures caused by `openQuestion()` and the drafting-only submit guard:

```powershell
Set-Location Edu_AI
npm test -- src/stitch/classroomQa/useClassroomInterruption.test.ts
```

- [ ] Remove `openQuestion`/`closeQuestion` orchestration. Expose an always-ready `submitQuestion(question)` that validates, synchronously suspends/captures the latest checkpoint, creates the optimistic turn, and then starts I/O.

- [ ] Keep request cancellation, stale-page protection, authenticated audio blob loading, browser-TTS fallback, object-URL cleanup, and exactly-once resume semantics from SPEC-12.

- [ ] Rerun the focused tests and commit:

```powershell
Set-Location Edu_AI
npm test -- src/stitch/classroomQa/useClassroomInterruption.test.ts
Set-Location ..
git add frontend/src/stitch/classroomQa/useClassroomInterruption.ts frontend/src/stitch/classroomQa/useClassroomInterruption.test.ts
git commit -m "feat(classroom): interrupt lecture when question is sent"
```

## Task 4: Build the persistent right-rail conversation UI

**Files:**

- Modify: `frontend/src/stitch/classroomQa/ClassroomQaPanel.tsx`
- Modify: `frontend/src/stitch/classroomQa/ClassroomQaPanel.css`
- Modify: `frontend/src/stitch/classroomQa/ClassroomQaPanel.test.ts`
- Modify: `frontend/src/stitch/pages/ClassroomPlayer.tsx`
- Modify: `frontend/src/stitch/styles.css`

- [ ] Add failing component/source tests that assert:

  - the panel renders without an open button, close button, overlay, or `role="dialog"`;
  - `selectVisibleTurns` renders the active student question before a server answer;
  - the student row has a distinct right-aligned class and the AI row has a left-aligned class;
  - pending/error controls are attached to the active turn;
  - `ClassroomPlayer` renders the panel inside the workspace and no longer renders the “讲解提词” aside or transcript secondary panel.

- [ ] Run the focused UI tests and confirm failure:

```powershell
Set-Location Edu_AI
npm test -- src/stitch/classroomQa/ClassroomQaPanel.test.ts
```

- [ ] Refactor the panel into a normal `<aside aria-label="课堂实时问答">`; always show history, status, composer, character count, send, retry, and abandon/continue controls as applicable.

- [ ] Clear the textarea only after a valid checkpoint and optimistic turn are created. Disable send while a turn is active but preserve any subsequently typed draft.

- [ ] Implement message layout: student row `justify-content:flex-end` with avatar after bubble; AI row `justify-content:flex-start` with avatar before bubble; bubble `max-width:82%`, wrapping enabled.

- [ ] Move the panel into `.classroom-console__workspace`, delete the page-prompt/transcript panel state and controls, and delete the floating panel instance.

- [ ] Implement responsive grid behavior from SPEC-13: desktop three columns with a 340–380px Q&A rail, presentation two columns, and `<960px` Q&A below the stage in document flow.

- [ ] Rerun focused tests plus lint and commit:

```powershell
Set-Location Edu_AI
npm test -- src/stitch/classroomQa/ClassroomQaPanel.test.ts src/stitch/classroomQa/classroomQaState.test.ts src/stitch/classroomQa/useClassroomInterruption.test.ts
npm run lint
Set-Location ..
git add frontend/src/stitch/classroomQa frontend/src/stitch/pages/ClassroomPlayer.tsx frontend/src
git commit -m "feat(classroom): replace prompt overlay with persistent qa rail"
```

Before committing, inspect `git diff --cached --name-only` and unstage any unrelated file accidentally included by the broad stylesheet add.

## Task 5: Auto-play the next page after a valid completion

**Files:**

- Modify: `frontend/src/openmaic/pagePlaybackController.ts`
- Modify: `frontend/src/openmaic/pagePlaybackController.test.ts`
- Modify: `frontend/src/stitch/pages/ClassroomPlayer.tsx`
- Add: `frontend/src/stitch/classroomQa/classroomAutoplay.ts`
- Add: `frontend/src/stitch/classroomQa/classroomAutoplay.test.ts`

- [ ] Add controller tests asserting `complete` returns `true` only once for the current playing scene/revision and returns `false` for stale, repeated, non-playing, and already-navigated completions.

- [ ] Add a pure orchestration helper test with fake `enter` and `play` calls:

```ts
assert.deepEqual(events, ["complete:1", "enter:2", "play:2"]);
```

Cover last-page completion, `complete=false`, failed `enter`, and the sequence after a Q&A resume.

- [ ] Run focused tests and confirm the old void/non-navigation behavior fails:

```powershell
Set-Location Edu_AI
npm test -- src/openmaic/pagePlaybackController.test.ts src/stitch/classroomQa/classroomAutoplay.test.ts
```

- [ ] Return a boolean from `complete`. Keep it synchronous and make every invalid/stale path return `false` without mutation.

- [ ] Implement `completeAndAdvance` (or an equivalently named pure helper) to await `enter(next)` before `play()`, stop on the last page, and propagate one error without recursive retry.

- [ ] Wire renderer `onComplete` in `ClassroomPlayer` to this helper using the callback's captured scene index/revision. Ensure a later page cannot be skipped by an older renderer callback.

- [ ] Rerun tests and commit:

```powershell
Set-Location Edu_AI
npm test -- src/openmaic/pagePlaybackController.test.ts src/stitch/classroomQa/classroomAutoplay.test.ts
Set-Location ..
git add frontend/src/openmaic/pagePlaybackController.ts frontend/src/openmaic/pagePlaybackController.test.ts frontend/src/stitch/classroomQa/classroomAutoplay.ts frontend/src/stitch/classroomQa/classroomAutoplay.test.ts frontend/src/stitch/pages/ClassroomPlayer.tsx
git commit -m "feat(classroom): autoplay the next lesson page"
```

## Task 6: Define one backend-owned classroom speech profile

**Files:**

- Modify: `backend/src/core/config.py`
- Modify: `backend/src/app/integrations/openmaic/client.py`
- Modify: `backend/src/app/services/classroom_qa_tts.py`
- Add: `backend/src/app/services/openmaic_tts_service.py`
- Modify: `backend/src/tests/test_openmaic_client.py`
- Modify: `backend/src/tests/test_classroom_qa_service.py`
- Add: `backend/src/tests/test_openmaic_tts_service.py`

- [ ] Add failing tests that expect `generate_classroom` to emit all explicit fields:

```python
assert request_json["ttsProviderId"] == "qwen-tts"
assert request_json["ttsVoice"] == "Cherry"
assert request_json["ttsSpeed"] == 1.0
```

- [ ] Add shared synthesis tests for provider/voice/speed, base64 decoding, format allowlist, 10 MiB limit, timeouts, and provider error mapping. Assert the Q&A wrapper delegates to the shared service with the configured profile.

- [ ] Run focused backend tests and confirm missing generation fields/shared service failures:

```powershell
Set-Location backend
python -m pytest src/tests/test_openmaic_client.py src/tests/test_openmaic_tts_service.py src/tests/test_classroom_qa_service.py -q
```

- [ ] Keep the existing `OPENMAIC_LIVE_TTS_*` names for compatibility, but document/configure them as the profile used by both classroom narration and live answers. Do not accept these values from browser requests.

- [ ] Extract OpenMAIC `/api/generate/tts` request/decode/validation into `OpenMaicTtsService`. Keep `ClassroomQaTtsService` as a thin domain wrapper if its interface is useful to existing callers.

- [ ] Extend `OpenMaicClient.generate_classroom` to require or receive provider, voice, and speed from server config and serialize the camelCase sidecar fields.

- [ ] Rerun focused tests and commit:

```powershell
Set-Location backend
python -m pytest src/tests/test_openmaic_client.py src/tests/test_openmaic_tts_service.py src/tests/test_classroom_qa_service.py -q
Set-Location ../..
git add backend/src/core/config.py backend/src/app/integrations/openmaic/client.py backend/src/app/services/classroom_qa_tts.py backend/src/app/services/openmaic_tts_service.py backend/src/tests/test_openmaic_client.py backend/src/tests/test_openmaic_tts_service.py backend/src/tests/test_classroom_qa_service.py
git commit -m "refactor(classroom): share the openmaic speech profile"
```

## Task 7: Make sidecar classroom generation honor the explicit speech profile

**Files:**

- Modify: `openmaic-sidecar/app/api/generate-classroom/route.ts`
- Modify: `openmaic-sidecar/lib/server/classroom-generation.ts`
- Modify: `openmaic-sidecar/lib/server/classroom-media-generation.ts`
- Modify: `openmaic-sidecar/tests/server/classroom-media-generation.test.ts`
- Add: `openmaic-sidecar/tests/server/classroom-generation-tts-profile.test.ts`

- [ ] Add route/generation tests for accepted `ttsProviderId`, `ttsVoice`, and `ttsSpeed`; reject an unknown/disabled provider and verify secrets/base URL are neither accepted nor forwarded.

- [ ] Add a media-generation test with two enabled providers where the configured profile is second; assert the configured ID and `Cherry` are used, proving code no longer selects the first provider.

- [ ] Run focused Vitest tests and confirm failure:

```powershell
Set-Location openmaic-sidecar
pnpm test -- tests/server/classroom-media-generation.test.ts tests/server/classroom-generation-tts-profile.test.ts
```

- [ ] Extend the input type and route allowlist with the three profile fields. Validate `ttsSpeed` against the same safe bounds used by `/api/generate/tts`.

- [ ] Resolve the requested provider only from server-managed provider configuration, require it to be enabled, and pass the resolved provider plus voice/speed into `generateTTSForClassroom`.

- [ ] Remove first-enabled-provider selection from this path. Do not silently switch voices when the requested provider is unavailable.

- [ ] Rerun focused tests and commit:

```powershell
Set-Location openmaic-sidecar
pnpm test -- tests/server/classroom-media-generation.test.ts tests/server/classroom-generation-tts-profile.test.ts
Set-Location ..
git add openmaic-sidecar/app/api/generate-classroom/route.ts openmaic-sidecar/lib/server/classroom-generation.ts openmaic-sidecar/lib/server/classroom-media-generation.ts openmaic-sidecar/tests/server/classroom-media-generation.test.ts openmaic-sidecar/tests/server/classroom-generation-tts-profile.test.ts
git commit -m "feat(sidecar): honor explicit classroom tts profile"
```

## Task 8: Route missing narration through the same profile

**Files:**

- Modify: `backend/src/app/services/classroom_media.py`
- Modify: `backend/src/tests/test_classroom_media.py`
- Modify callers located by `rg -n "synthesize_classroom_speech_audio" backend/src`

- [ ] Add failing tests that inject the shared OpenMAIC TTS service, synthesize two missing speech actions, and assert both use `qwen-tts / Cherry / 1.0`. Add a guard asserting no request is sent to `/audio/speech` and no `alloy` default appears.

- [ ] Preserve tests for existing audio URLs, atomic writes, safe filenames, and partial failure behavior.

- [ ] Run the focused media tests and confirm the old OpenAI-compatible path fails the profile assertions:

```powershell
Set-Location backend
python -m pytest src/tests/test_classroom_media.py -q
```

- [ ] Refactor `synthesize_classroom_speech_audio` to call `OpenMaicTtsService` and persist returned bytes using existing storage/rewrite rules. Existing non-empty narration URLs remain untouched.

- [ ] Pass the configured shared service through production callers; remove dead OpenAI speech configuration only when no other feature consumes it, verified with `rg` before deletion.

- [ ] Rerun tests and commit:

```powershell
Set-Location backend
python -m pytest src/tests/test_classroom_media.py src/tests/test_openmaic_tts_service.py src/tests/test_openmaic_client.py -q
Set-Location ../..
git add backend/src/app/services/classroom_media.py backend/src/tests/test_classroom_media.py backend/src/app
git diff --cached --name-only
git commit -m "fix(classroom): use shared voice for missing narration"
```

Unstage any unrelated file before committing.

## Task 9: Add the integrated browser acceptance path

**Files:**

- Add: `frontend/e2e/classroom-persistent-qa.spec.ts`
- Modify: `frontend/playwright.config.ts` only if the existing web-server configuration cannot run this spec
- Modify: `docs/acceptance/ACC-13_AI课堂连续授课与常驻问答体验优化_验收.md` to record actual evidence

- [ ] Add a deterministic Playwright route-stub test that delays the QA POST and verifies the student bubble is already visible while the request is pending, then returns an answer and verifies left/right alignment through bounding boxes.

- [ ] Cover persistent rail placement at 1440×900 and 390×844, no “讲解提词” panel, no overlay over stage controls, and disabled repeat submit while active.

- [ ] Use a deterministic three-scene fixture to assert scene 1 → 2 → 3 automatically, the last scene does not wrap, and a stale completion cannot skip a scene.

- [ ] Run the deterministic browser spec:

```powershell
Set-Location Edu_AI
npx playwright test e2e/classroom-persistent-qa.spec.ts
```

- [ ] Start the real frontend/backend/sidecar stack and execute ACC-13 cases B1–B8. Create or regenerate a classroom so narration is not served from historical audio cache.

- [ ] Save screenshots, relevant request/log excerpts, generated classroom ID, provider/voice/speed evidence, and manual listening results in ACC-13. Do not mark subjective voice quality as passed only from configuration.

- [ ] Commit deterministic E2E and evidence updates:

```powershell
git add frontend/e2e/classroom-persistent-qa.spec.ts frontend/playwright.config.ts docs/acceptance/ACC-13_AI课堂连续授课与常驻问答体验优化_验收.md
git diff --cached --name-only
git commit -m "test(classroom): cover persistent qa and continuous playback"
```

## Task 10: Run regressions and sign off documentation

**Files:**

- Modify: `docs/spec/SPEC-13_AI课堂连续授课与常驻问答体验优化.md`
- Modify: `docs/spec/README.md`
- Modify: `docs/acceptance/ACC-13_AI课堂连续授课与常驻问答体验优化_验收.md`
- Modify: `docs/acceptance/README.md`
- Modify: `项目总览地图.md`

- [ ] Run the backend Q&A/media regression suite:

```powershell
Set-Location backend
python -m pytest src/tests/test_classroom_qa_prompt.py src/tests/test_classroom_qa_store.py src/tests/test_classroom_qa_service.py src/tests/test_classroom_qa_routes.py src/tests/test_openmaic_client.py src/tests/test_openmaic_tts_service.py src/tests/test_classroom_media.py -q
```

- [ ] Run full frontend tests, lint, and build:

```powershell
Set-Location Edu_AI
npm test
npm run lint
npm run build
```

- [ ] Run sidecar focused tests, lint, and build:

```powershell
Set-Location openmaic-sidecar
pnpm test -- tests/server/classroom-media-generation.test.ts tests/server/classroom-generation-tts-profile.test.ts
pnpm lint
pnpm build
```

- [ ] Run the retired-path static gates from ACC-13 and confirm no live-Q&A RAG symbol, page prompt UI, first-provider narration fallback, or `alloy` classroom fallback remains.

- [ ] Fill every ACC-13 result/evidence cell with command output, screenshot path, log excerpt, or an explicit failure. If any mandatory case fails, keep SPEC-13/ACC-13 status as not passed.

- [ ] Only after all mandatory cases pass, change SPEC-13 status to completed, ACC-13 to passed, and update both indexes plus `项目总览地图.md`.

- [ ] Check formatting and commit sign-off:

```powershell
git diff --check
git status --short
git add docs/spec/SPEC-13_AI课堂连续授课与常驻问答体验优化.md docs/spec/README.md docs/acceptance/ACC-13_AI课堂连续授课与常驻问答体验优化_验收.md docs/acceptance/README.md 项目总览地图.md
git commit -m "docs(classroom): sign off continuous qa experience"
```

## Final delivery gate

- [ ] `git status --short` contains no unintended changes.
- [ ] `git log --oneline --decorate -10` shows the task commits in order.
- [ ] ACC-13 contains real evidence for no-RAG behavior, optimistic rendering, responsive layout, three-page autoplay, Q&A interruption/resume, and shared TTS profile.
- [ ] Existing stored narration was not mass-modified.
- [ ] The final handoff names any non-blocking limitations and never reports ACC-13 as passed while mandatory evidence is missing.
