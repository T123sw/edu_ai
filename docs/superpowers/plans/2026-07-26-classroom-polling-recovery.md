# Classroom Polling Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resume an interrupted AI-classroom browser poll without resubmitting or losing the existing job.

**Architecture:** Persist the latest per-course `EduJob` in localStorage through a small
testable module. Reuse the existing polling helper from both new submissions and mount-time
recovery, clearing storage only on terminal completion/failure.

**Tech Stack:** React, TypeScript, browser localStorage, Node test runner.

---

### Task 1: Persistent pending-job store

**Files:**
- Create: `Edu_AI/src/openmaic/classroomGenerationRecovery.ts`
- Create: `Edu_AI/src/openmaic/classroomGenerationRecovery.test.ts`

- [ ] Write tests for save/read, per-course isolation, replacement, guarded clearing, and malformed data.
- [ ] Run the new test and confirm it fails because the module is missing.
- [ ] Implement the minimal storage module.
- [ ] Run the new test and confirm it passes.
- [ ] Commit the storage substage.

### Task 2: Resume polling in the workbench entry

**Files:**
- Modify: `Edu_AI/src/components/teacher/ClassroomGenerationEntry.tsx`
- Modify: `Edu_AI/src/openmaic/classroomGenerationFlow.test.ts`

- [ ] Add a failing source-contract test for recovery integration.
- [ ] Refactor submission and recovery through one polling function.
- [ ] Persist immediately after POST and on every progress update.
- [ ] Recover once per stored job on mount/course change.
- [ ] Clear only the matching record on success or explicit terminal failure.
- [ ] Run the focused and complete frontend tests.
- [ ] Commit the UI recovery substage.

### Task 3: Verify the live task and final behavior

**Files:**
- No production changes expected.

- [ ] Confirm the current OpenMAIC job reaches a terminal status.
- [ ] Confirm the matching Edu-AI job is persisted as succeeded/failed.
- [ ] Run frontend lint and production build.
- [ ] Run `git diff --check` and confirm a clean worktree.
