# Unified OpenMAIC Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `start_api.bat` start and wait for the repository-local OpenMAIC sidecar before starting Edu-AI.

**Architecture:** Keep `openmaic-sidecar/` as a sibling of `Edu_AI/`. Extend the existing
batch orchestrator with dependency checks, safe port reuse, a bounded `/api/health`
readiness loop, and a separate sidecar terminal.

**Tech Stack:** Windows batch, PowerShell health probe, Next.js/pnpm, FastAPI/uvicorn,
pytest static startup tests.

---

### Task 1: Add startup contract tests

**Files:**
- Modify: `backend/src/tests/chat/test_start_api_bat.py`

- [ ] Add tests asserting `start_api.bat` contains `openmaic-sidecar`, port `3000`,
  `pnpm.cmd dev`, `/api/health`, and waits for sidecar health before invoking uvicorn.
- [ ] Run:
  `conda run -n edu-ai python -m pytest tests/chat/test_start_api_bat.py -q`
- [ ] Confirm the new tests fail because sidecar orchestration is absent.

### Task 2: Implement safe sidecar orchestration

**Files:**
- Modify: `backend/src/start_api.bat`

- [ ] Resolve `REPO_ROOT` and `SIDECAR_DIR` from the script location.
- [ ] Extend `--check` with sidecar structure checks.
- [ ] Detect `pnpm.cmd`, with the known `openmaic` conda environment as fallback.
- [ ] Install sidecar dependencies only when `node_modules` is absent.
- [ ] Reuse a healthy process on port 3000.
- [ ] Refuse to kill an unknown unhealthy process on port 3000.
- [ ] Start `pnpm.cmd dev` and wait up to 90 seconds for `/api/health`.
- [ ] Start the Edu-AI frontend and FastAPI only after sidecar is ready.

### Task 3: Verify and commit

**Files:**
- Test: `backend/src/tests/chat/test_start_api_bat.py`
- Test: `backend/src/tests/app/test_legacy_services_retired.py`

- [ ] Run the focused startup tests.
- [ ] Run `start_api.bat --check`.
- [ ] Run `git diff --check`.
- [ ] Confirm OpenMAIC still uses one Next.js process for both UI and API.
- [ ] Commit the implementation and tests.
