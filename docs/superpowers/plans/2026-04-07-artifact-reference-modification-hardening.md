# Artifact Reference Modification Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the first-stage referenced-report modification flow so only supported report artifacts enter it and conversation-scoped generated files stay isolated from course-material files.

**Architecture:** Add lightweight generated-file origin metadata, expose store actions for replacing and clearing conversation-scoped files, and gate the teacher-side "add to chat" action behind report-artifact eligibility. Keep backend editing behavior unchanged; only tighten the frontend entry points and state model around it.

**Tech Stack:** React, TypeScript, Zustand, Ant Design, lightweight Node-based frontend tests

---

### Task 1: Lock helper behavior

**Files:**
- Modify: `frontend/tests/frontend/materials.helpers.test.ts`
- Modify: `frontend/src/services/teacher/materials.helpers.ts`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run `node --experimental-strip-types frontend/tests/frontend/materials.helpers.test.ts` and verify it fails**
- [ ] **Step 3: Add `isArtifactReferenceEligible`, `replaceConversationGeneratedFiles`, `clearConversationGeneratedFiles`, and `origin: 'course_material'` metadata**
- [ ] **Step 4: Re-run the helper test and verify it passes**

### Task 2: Tighten store and chat restore flow

**Files:**
- Modify: `frontend/tests/frontend/chatPanel.artifact-reference.test.ts`
- Modify: `frontend/tests/frontend/chatPanel.restore-preview.test.ts`
- Modify: `frontend/src/store/teacher/useStore.ts`
- Modify: `frontend/src/components/teacher/ChatPanel.tsx`
- Modify: `frontend/src/services/teacher/chatV2.helpers.ts`

- [ ] **Step 1: Write failing tests for store methods and restore behavior**
- [ ] **Step 2: Run the two frontend tests and verify they fail**
- [ ] **Step 3: Add store methods for replacing and clearing conversation-scoped generated files**
- [ ] **Step 4: Update chat restore/new-conversation paths to use those methods**
- [ ] **Step 5: Mark restored/generated conversation artifacts with `origin: 'conversation'`**
- [ ] **Step 6: Re-run the two frontend tests and verify they pass**

### Task 3: Restrict add-to-chat to report artifacts

**Files:**
- Modify: `frontend/tests/frontend/studioPanel.add-to-chat.test.ts`
- Modify: `frontend/src/components/teacher/StudioPanel.tsx`

- [ ] **Step 1: Write the failing test for report-only add-to-chat eligibility**
- [ ] **Step 2: Run `node --experimental-strip-types frontend/tests/frontend/studioPanel.add-to-chat.test.ts` and verify it fails**
- [ ] **Step 3: Update `StudioPanel` to hide unsupported add-to-chat entries**
- [ ] **Step 4: Re-run the test and verify it passes**

### Task 4: Verify the targeted surface

**Files:**
- No additional code changes required unless verification fails

- [ ] **Step 1: Run the targeted frontend tests**
- [ ] **Step 2: Run `cmd /c npm run build` in `Edu_AI/`**
- [ ] **Step 3: Re-run backend artifact-reference tests in `backend/src/` to confirm no regression**
