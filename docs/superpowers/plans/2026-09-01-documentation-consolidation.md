# Documentation Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Consolidate project documentation under the repository-level `docs/` directory, remove documents for retired subsystems, and leave one accurate deployment/documentation entry point.

**Architecture:** Repository-level `docs/` is the only canonical documentation root. Current specifications, plans, acceptance evidence, deployment facts, architecture contracts, and operations checklists are separated by responsibility; vendored OpenMAIC documentation remains inside `openmaic-sidecar/`. Recently updated 2026-08-31 and 2026-09-01 documents are protected from deletion.

**Tech Stack:** Markdown, Git, PowerShell, repository link validation with ripgrep.

---

### Task 1: Establish the canonical documentation entry point

**Files:**
- Create: `docs/README.md`
- Create: `docs/deployment/README.md`
- Move: `docs/Linux服务器完整部署清单_2026-09-01.md` to `docs/deployment/Linux服务器部署事实与待办.md`
- Modify: `项目总览地图.md`

- [x] **Step 1:** Create `docs/README.md` with links to current specifications, acceptance evidence, deployment, architecture, operations, and implementation history.
- [x] **Step 2:** Create `docs/deployment/README.md` declaring the target runtime versions, ports, directory policy, and supported OpenMAIC-only PPTX path.
- [x] **Step 3:** Move the server scan document into `docs/deployment/` and label it as deployment facts and pending work rather than a ready-to-run installer.
- [x] **Step 4:** Update `项目总览地图.md` so all documentation links resolve through `docs/README.md` and `docs/deployment/README.md`.

### Task 2: Consolidate current acceptance and operational evidence

**Files:**
- Move: `docs/acceptance/legacy-product-evidence/**` to `docs/acceptance/legacy-product-evidence/**`
- Move: `Edu_AI/docs/video-playback-interfaces.md` to `docs/architecture/video-playback-interfaces.md`
- Move: `Edu_AI/docs/database-storage-cutover.md` to `docs/operations/database-storage-cutover.md`
- Move: `Edu_AI/docs/specs/2026-08-10-database-migration-spec.md` to `docs/architecture/database-migration-spec.md`
- Move: `Edu_AI/docs/qa/*.md` to `docs/operations/qa/`
- Modify: `Edu_AI/tests/frontend/profile-kb-courseedit-replacement.test.ts`

- [x] **Step 1:** Move the unique August acceptance records and screenshots under a clearly labelled legacy product-evidence directory without changing their contents.
- [x] **Step 2:** Move the three still-useful architecture/operations documents to their canonical responsibility directories.
- [x] **Step 3:** Update the single frontend source-path assertion for the moved video playback contract.

### Task 3: Remove retired and duplicate documentation

**Files:**
- Delete: remaining `Edu_AI/docs/**`
- Delete: `Edu_AI/api/src/docs/**`
- Delete: Markdown/HTML documentation under `EduAgent/**`
- Delete: Markdown documentation under `automation_spider/**`
- Delete: root plans/specifications dedicated to generic PPT/HTML2PPT workflows
- Delete: obsolete root roadmaps dedicated to P4A, SearXNG, HTML2PPT, or superseded migration comparisons

- [x] **Step 1:** Delete duplicate frontend-local documentation after the current evidence and contracts have been moved.
- [x] **Step 2:** Delete the obsolete backend-local documentation tree, whose paths and architecture predate `Edu_AI/api/src`.
- [x] **Step 3:** Delete documentation owned by the retired EduAgent and crawler subsystems.
- [x] **Step 4:** Delete generic PPT/HTML2PPT plans while preserving OpenMAIC PPTX specifications and acceptance records.

### Task 4: Repair active documentation references

**Files:**
- Modify: root `docs/superpowers/specs/*.md` and `docs/superpowers/plans/*.md` files that reference moved acceptance records
- Modify: `Edu_AI/README.md`
- Modify: `DEPENDENCIES.md`

- [x] **Step 1:** Replace active `docs/acceptance/legacy-product-evidence/...` links with `docs/acceptance/legacy-product-evidence/...` paths.
- [x] **Step 2:** Replace the old nested deployment links in `Edu_AI/README.md` with the canonical deployment index.
- [x] **Step 3:** Rewrite `DEPENDENCIES.md` to remove EduAgent, npm lockfile, venv, old startup scripts, and generic PPT service instructions; record the agreed Conda, Python 3.12, Node 22, pnpm 10.28, and FFmpeg 6+ baseline.

### Task 5: Verify the documentation tree

**Files:**
- Verify: `docs/**`
- Verify: `项目总览地图.md`
- Verify: `Edu_AI/README.md`
- Verify: `DEPENDENCIES.md`

- [x] **Step 1:** Run a repository search for references to `Edu_AI/docs`, `Edu_AI/api/src/docs`, EduAgent, automation_spider, HTML2PPT, ports 8000/46080, and deleted document paths.
- [x] **Step 2:** Confirm OpenMAIC PPTX specification and acceptance documents still exist.
- [x] **Step 3:** Confirm no recently updated 2026-08-31 or 2026-09-01 root specification, plan, or acceptance document was deleted.
- [x] **Step 4:** Inspect `git diff --check` and `git status --short`; do not run or repair the known failing backend test suite in this documentation-only pass.
