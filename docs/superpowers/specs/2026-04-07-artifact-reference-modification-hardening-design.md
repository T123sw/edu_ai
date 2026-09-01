# Artifact Reference Modification Hardening Design

**Goal**

Stabilize the first-stage "modify around a referenced artifact" flow so it behaves predictably for report artifacts, does not mislead users into trying unsupported artifact types, and does not leak conversation-scoped generated files across sessions.

**Scope**

This design intentionally stays inside the first-stage report-editing capability:

- Keep support focused on `report` and `report_outline`
- Do not implement `ask_about_artifact` in this iteration
- Improve the teacher-side UX and state handling around reference-based modification

**Design**

1. Report-only entry point

The right-side "add to chat" affordance should only appear for report artifacts. The backend reference payload already only supports `report` and `report_outline`, so the frontend should stop offering the action on quiz, lesson plan, blog, and other unsupported artifacts.

2. Conversation-scoped generated file hygiene

Generated files created from the active conversation should be tagged as conversation-origin files. Persisted course materials should be tagged separately as course-material files. When the user loads a conversation, the app should replace only conversation-origin generated files while preserving course-material entries. When the user starts a new conversation, conversation-origin files should be cleared and the preview should close.

3. Restore behavior

Conversation detail restore should rebuild report artifacts from persisted workflow state and mark them as conversation-origin files. Loading history should not auto-open the restored preview.

4. Testing approach

Use lightweight frontend tests to verify:

- report-only eligibility for "add to chat"
- store API presence for replacing and clearing conversation-scoped files
- conversation restore keeps preview collapsed
- helper behavior for preserving course-material files while replacing conversation files

**Files**

- `frontend/src/services/teacher/materials.helpers.ts`
- `frontend/src/store/teacher/useStore.ts`
- `frontend/src/components/teacher/ChatPanel.tsx`
- `frontend/src/components/teacher/StudioPanel.tsx`
- `frontend/src/services/teacher/chatV2.helpers.ts`
- `frontend/tests/frontend/*.test.ts`

**Out of Scope**

- Reference-based Q&A over artifacts
- Non-report artifact reference workflows
- Backend route changes for `ask_about_artifact`
