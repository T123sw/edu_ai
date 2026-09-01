# System Functional End-to-End Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the cleaned Windows repository through deterministic and live end-to-end checks for conversation, deep search, teaching-material generation, and AI classroom flows without changing product behavior.

**Architecture:** Run the repository-owned unit/integration and Playwright suites first, then start the canonical three-service stack and exercise authenticated live API workflows with an isolated QA teacher and course. Classify every result as pass, product defect, external-provider/configuration blocker, or unverified; stop all managed processes and save an evidence report at the end.

**Tech Stack:** PowerShell 7, `start.bat`/`stop.bat`, Python 3.12, pytest, Node.js 24, pnpm 10, Playwright, FastAPI, OpenMAIC.

---

### Task 1: Establish a clean runtime baseline

**Files:**
- Read: `start.bat`
- Read: `stop.bat`
- Read: `.env`

- [x] **Step 1: Confirm the Git baseline**

Run: `git status --short && git log -1 --oneline --decorate`

Expected: only this acceptance plan is untracked or modified; the launcher acceptance tag still resolves.

- [x] **Step 2: Check the launcher without starting services**

Run: `cmd.exe /d /c start.bat --check --no-browser`

Expected: exit code 0 and versions for Python 3.12, Node.js 22+, and pnpm 10.

- [x] **Step 3: Record provider readiness without printing secrets**

Inspect only whether required key values are non-empty. Deep search requires `BOCHA_API_KEY` or `TAVILY_API_KEY`; model workflows require one configured chat/model provider. Never print values.

### Task 2: Run deterministic backend coverage for the four product areas

**Files:**
- Test: `backend/src/tests/chat/test_routes_v2.py`
- Test: `backend/src/tests/chat/test_reply_service_v2.py`
- Test: `backend/src/tests/chat/test_deepsearch_service_websearch.py`
- Test: `backend/src/tests/chat/test_deepsearch_importer.py`
- Test: `backend/src/tests/acceptance/test_generation_reliability_matrix.py`
- Test: `backend/src/tests/test_classroom_service.py`
- Test: `backend/src/tests/test_classroom_job_service.py`
- Test: `backend/src/tests/test_classroom_qa_routes.py`

- [x] **Step 1: Run the targeted pytest suite**

Run from `backend/src`:

```powershell
python -m pytest tests/chat/test_routes_v2.py tests/chat/test_reply_service_v2.py tests/chat/test_deepsearch_service_websearch.py tests/chat/test_deepsearch_importer.py tests/acceptance/test_generation_reliability_matrix.py tests/test_classroom_service.py tests/test_classroom_job_service.py tests/test_classroom_qa_routes.py -q
```

Expected: zero failed tests. Record skips separately from passes.

### Task 3: Run deterministic browser workflows

**Files:**
- Test: `frontend/tests/e2e/generation-factory-shell.spec.ts`
- Test: `frontend/tests/e2e/generation-text-resources.spec.ts`
- Test: `frontend/tests/e2e/generation-visual-resources.spec.ts`
- Test: `frontend/tests/e2e/generation-practice-resources.spec.ts`
- Test: `frontend/tests/e2e/resources-and-classroom.spec.ts`
- Test: `frontend/tests/e2e/classroom-persistent-qa.spec.ts`
- Test: `frontend/tests/e2e/classroom-catalog.spec.ts`

- [x] **Step 1: Start the canonical stack**

Run: `cmd.exe /d /c start.bat --no-browser`

Expected: health checks pass for ports 3000, 8001, and 5173.

- [x] **Step 2: Execute the targeted Playwright suite on desktop1366**

Run from `frontend`:

```powershell
corepack pnpm exec playwright test tests/e2e/generation-factory-shell.spec.ts tests/e2e/generation-text-resources.spec.ts tests/e2e/generation-visual-resources.spec.ts tests/e2e/generation-practice-resources.spec.ts tests/e2e/resources-and-classroom.spec.ts tests/e2e/classroom-persistent-qa.spec.ts tests/e2e/classroom-catalog.spec.ts --project=desktop1366
```

Expected: zero failures. These tests prove UI behavior and request contracts; they do not count as live-provider success.

### Task 4: Exercise authenticated live conversation and deep search

**Files:**
- Read: `backend/src/app/auth.py`
- Read: `backend/src/app/chat/api/routes_v2.py`
- Read: `backend/src/app/api/deepsearch.py`

- [x] **Step 1: Register an isolated QA teacher**

POST a unique username to `/api/auth/register` with role `teacher`; retain the bearer token only in process memory.

Expected: HTTP 200 with a bearer token.

- [x] **Step 2: Send a real model-backed conversation turn**

POST `/api/chat/v2/reply` with:

```json
{"question":"请用两句话解释牛顿第二定律，并给出一个生活例子。","allow_rag":false,"allow_web":false}
```

Expected: HTTP 200, non-empty assistant text, and a conversation identifier. Any provider error is recorded with its sanitized error type.

- [x] **Step 3: Run basic deep search without saving to knowledge base**

POST `/agent/deepsearch-and-crawl` with:

```json
{"query":"人工智能教育 2026 教学应用","depth":"basic","max_urls":3,"crawl_timeout":20,"save_to_kb":false}
```

Expected when configured: HTTP 200, `ok=true`, a batch identifier, and at least one result. Missing Bocha/Tavily configuration is a configuration blocker, not a pass.

### Task 5: Exercise live material and AI classroom generation

**Files:**
- Read: `backend/src/app/api/courses.py`
- Read: `backend/src/app/chat/api/routes_v2.py`
- Read: `backend/src/app/api/jobs.py`

- [x] **Step 1: Create an isolated QA course**

POST `/api/courses` with a unique `id`, title `系统功能端到端验收`, a short description, icon `school`, and color `#2563eb`.

Expected: HTTP 200 and membership role `owner`.

- [x] **Step 2: Submit a real report generation task**

POST `/api/chat/v2/report/direct` with `source_mode=none`, the QA course ID, a short report question, and visuals disabled.

Expected: HTTP 202 with `edu_job_id`; poll `/api/jobs/{edu_job_id}` until `done` or `failed`. A done job must expose a persisted report artifact.

- [x] **Step 3: Submit a minimal real AI classroom task**

POST `/api/courses/{course_id}/classrooms/generate` with `source_mode=none`, one scene, five minutes, web search/TTS/visuals disabled, and a short Newton-law requirement.

Expected: HTTP 202 with `edu_job_id`; poll until `done` or `failed`. A done job must expose a classroom ID readable from `/api/courses/{course_id}/classrooms/{classroom_id}`.

### Task 6: Classify results, stop services, and record evidence

**Files:**
- Create: `docs/operations/qa/2026-09-01-system-functional-e2e-acceptance.md`

- [x] **Step 1: Stop the canonical stack**

Run: `cmd.exe /d /c stop.bat`

Expected: ports 3000, 8001, and 5173 are free; the PID manifest and temporary command files are gone.

- [x] **Step 2: Write the acceptance matrix**

Record deterministic test counts, live HTTP status, sanitized failure messages, generated artifact/job identifiers, elapsed time, and the final classification for each product area. Do not include tokens, passwords, API keys, or full provider responses containing private data.

- [x] **Step 3: Preserve evidence in version control**

Run `git diff --check`, commit the plan and acceptance report, and create an annotated acceptance tag only if every in-scope product area is either verified or explicitly classified with a reproducible blocker.
