# Persist Generated Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the generated artifacts list visible in the right-side studio after refresh by restoring it from persisted conversation state, and merge a report outline into its final report item once the report body is generated.

**Architecture:** Expose persisted artifact state from the conversation detail API, rebuild the right-side generated file list from that state when loading a conversation, and update report artifact mapping so `report_outline + report` becomes a single report entry carrying an embedded outline. The studio preview will switch between body and outline inside one report item instead of showing two separate list entries.

**Tech Stack:** FastAPI, JSON conversation storage, React, Zustand, TypeScript, Ant Design

---

### Task 1: Define failing frontend expectations for merged report artifacts

**Files:**
- Modify: `d:\github\edu_ai\Edu_AI\tests\frontend\chatV2.helpers.test.ts`

- [ ] **Step 1: Write the failing test**

Add assertions that:
- outline-only responses still produce one outline report item
- outline + final report responses produce one final report item
- the merged final report item carries embedded outline content in `meta.outlineContent`

- [ ] **Step 2: Run test to verify it fails**

Run: `node Edu_AI/tests/frontend/chatV2.helpers.test.ts`
Expected: FAIL because helper still returns separate outline and report items.

- [ ] **Step 3: Write minimal implementation**

Update the helper so it merges outline data into the final report artifact when both are present.

- [ ] **Step 4: Run test to verify it passes**

Run: `node Edu_AI/tests/frontend/chatV2.helpers.test.ts`
Expected: PASS

### Task 2: Define failing expectations for restoring generated files from conversation detail

**Files:**
- Create: `d:\github\edu_ai\Edu_AI\tests\frontend\generatedFiles.restore.test.ts`
- Modify: `d:\github\edu_ai\Edu_AI\src\services\teacher\chatV2.helpers.ts`

- [ ] **Step 1: Write the failing test**

Add tests for a helper that rebuilds generated files from persisted conversation detail state:
- report-only artifact restores one report item
- outline + report artifact state restores one merged report item
- restored files retain conversation id in metadata

- [ ] **Step 2: Run test to verify it fails**

Run: `node Edu_AI/tests/frontend/generatedFiles.restore.test.ts`
Expected: FAIL because restore helper does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add a helper that reads `state.workflow_state.artifacts` from conversation detail and maps them through the same merge logic used for immediate response artifacts.

- [ ] **Step 4: Run test to verify it passes**

Run: `node Edu_AI/tests/frontend/generatedFiles.restore.test.ts`
Expected: PASS

### Task 3: Expose persisted artifact state from conversation detail API

**Files:**
- Modify: `d:\github\edu_ai\Edu_AI\api\Edu_AI\core\conversation_storage.py`
- Modify: `d:\github\edu_ai\Edu_AI\src\services\teacher\api.ts`

- [ ] **Step 1: Write the failing test**

Prefer a lightweight backend test if one already exists near conversation storage; otherwise rely on the new frontend restore test by requiring `detail.state` shape in the typed response.

- [ ] **Step 2: Run test to verify it fails**

Run the restore test after adding typed expectations.
Expected: FAIL because conversation detail does not expose persisted state.

- [ ] **Step 3: Write minimal implementation**

Return `state` from `ConversationStorage.get_conversation(...)` and reflect that field in `ConversationDetailResponse`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node Edu_AI/tests/frontend/generatedFiles.restore.test.ts`
Expected: PASS

### Task 4: Restore and maintain generated files in the frontend store

**Files:**
- Modify: `d:\github\edu_ai\Edu_AI\src\store\teacher\useStore.ts`
- Modify: `d:\github\edu_ai\Edu_AI\src\components\teacher\ChatPanel.tsx`
- Modify: `d:\github\edu_ai\Edu_AI\src\components\teacher\StudioPanel.tsx`

- [ ] **Step 1: Write the failing test**

If component tests are unavailable, cover the critical mapping logic in helper tests and keep implementation minimal:
- store needs `setGeneratedFiles`
- loading a conversation should replace right-side generated files with restored items from that conversation
- starting a new conversation should clear the current generated file list and preview

- [ ] **Step 2: Run test to verify it fails**

Run the helper tests and, if available, the targeted frontend build/test command.
Expected: FAIL because load path does not restore files and store cannot replace the list.

- [ ] **Step 3: Write minimal implementation**

Add `meta` and `setGeneratedFiles` to the store, call the restore helper inside `loadConversation`, and clear list/preview on new conversation or deleting the active conversation with no fallback.

- [ ] **Step 4: Run test to verify it passes**

Run the targeted frontend tests and build.
Expected: PASS

### Task 5: Add inline outline/body switching for report preview

**Files:**
- Modify: `d:\github\edu_ai\Edu_AI\src\components\teacher\StudioPanel.tsx`

- [ ] **Step 1: Write the failing test**

If no component test harness exists, encode the behavior through helper metadata tests first, then manually verify the UI by build/runtime checks:
- only one report entry appears when final report already exists
- preview shows a switch button when embedded outline content exists
- preview defaults to body and can switch to outline

- [ ] **Step 2: Run test to verify it fails**

Run the helper tests or component tests if present.
Expected: FAIL because the preview does not know about embedded outline metadata.

- [ ] **Step 3: Write minimal implementation**

Use report file metadata such as `meta.outlineContent` and local preview mode state to render `正文` / `大纲` toggle buttons inside the report preview.

- [ ] **Step 4: Run test to verify it passes**

Run targeted frontend tests and build.
Expected: PASS

### Task 6: Verify end-to-end behavior

**Files:**
- No code changes required unless verification reveals a defect.

- [ ] **Step 1: Run targeted tests**

Run:
- `node Edu_AI/tests/frontend/chatV2.helpers.test.ts`
- `node Edu_AI/tests/frontend/generatedFiles.restore.test.ts`

Expected: PASS

- [ ] **Step 2: Run frontend build**

Run: `cd d:\github\edu_ai\Edu_AI && npm.cmd run build`
Expected: PASS

- [ ] **Step 3: Sanity-check backend import path if touched**

Run a lightweight import or existing targeted test if needed for the conversation detail API.

