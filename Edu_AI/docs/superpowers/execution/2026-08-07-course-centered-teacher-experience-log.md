# Course-Centered Teacher Experience Execution Log

**Spec:** `docs/superpowers/specs/2026-08-06-course-centered-teacher-experience-design.md`
**Plans:** `docs/superpowers/plans/README.md`
**Started:** 2026-08-07 (Asia/Shanghai)
**Execution mode:** Superpowers `executing-plans`, inline execution, test-driven development

## Recording Rules

Each entry records a decision made without pausing for confirmation, the recommended choice taken, its reason, affected scope, verification evidence, and commit when available. Data-destructive choices are not auto-approved.

## Decisions

### D001 — Isolate implementation from the dirty main checkout

- **Context:** The main checkout contains unrelated modified Agent/RAG source files, tests, course data, runtime data, and frontend chat files.
- **Choice:** Commit only the approved Spec/plan/log documents, then create `feat/course-centered-teacher-ux` in an isolated worktree for implementation.
- **Reason:** This prevents unrelated user changes from entering phase commits and satisfies the Superpowers worktree requirement without discarding any current work.
- **Impact:** Implementation commands and commits run in the isolated worktree. The original checkout remains available with its unrelated changes untouched.
- **Evidence:** Plan/Spec commit `1e1e6b8`; linked worktree `D:\github\edu_ai\.worktrees\course-centered-teacher-ux`; branch `feat/course-centered-teacher-ux`; original dirty checkout remains separate.
- **Status:** Applied.

### D002 — Build ignored local OpenMAIC packages in the isolated workspace

- **Context:** A clean dependency install links `mathml2omml`, `pptxgenjs`, `@openmaic/dsl`, and `@openmaic/renderer` from source. Their ignored `dist/` directories are absent in a fresh worktree, so tests/build cannot resolve package exports. The sidecar postinstall also uses Unix `rm`, which fails in Windows PowerShell/cmd.
- **Choice:** Restore the locked sidecar workspace, build the two vendored packages, then build DSL and renderer with their underlying cross-platform TypeScript/Rollup commands. Keep all generated `dist/` and nested dependency folders ignored and outside commits.
- **Reason:** This restores the repository’s intended local-package runtime without altering product source or inventing a different dependency graph.
- **Impact:** Frontend tests and build can run in the isolated worktree. No generated package output is staged.
- **Status:** Applied.

## Phase Evidence

### Baseline — 2026-08-07

- Frontend unit/contract tests: **137 passed, 0 failed** after local-package build.
- Frontend production build: **passed**; existing chunk-size warnings remain (largest application chunk approximately 3.19 MB).
- Frontend lint: **0 errors, 82 warnings**. Warnings are recorded as the pre-change baseline and must not increase; stage 6 will address in-scope warnings.
- Focused backend baseline: **25 passed, 1 failed**. The failure is `test_get_course_materials_returns_paginated_aggregate_scope` (`total` expected 25, got 0), caused by the current creator/owner visibility filter. This is an explicit Plan 1 Task 5 target, not an environmental failure.
- Worktree source status after dependency setup: clean before the log update.
