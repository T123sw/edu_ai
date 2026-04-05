# Status Card Evidence Metadata Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose richer evidence metadata in the expanded status card so users can see not just evidence text, but also where it came from and how strong it is.

**Architecture:** Keep `StatusCardBuilder` as the backend projection layer for all card-facing state. Add a small nested evidence-detail structure to `StatusCardViewModel`, map richer `conversation_memory.evidence_points` into it, and update the frontend expanded detail area to render evidence rows with metadata badges while preserving the existing compact default layout.

**Tech Stack:** Python, TypeScript, React, Ant Design, pytest, Vite build

---

### Task 1: Lock backend evidence-detail behavior with failing tests

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_evidence_metadata.py`

- [ ] **Step 1: Write failing tests**

Add tests that verify:
- `StatusCardBuilder` exposes rich evidence details with `content`, `source_type`, `confidence`, and a derived source-count
- low-state chats still expose an empty evidence-detail list

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_evidence_metadata.py -q
```

Expected:
- At least one assertion fails because the card view model does not yet include rich evidence details.

### Task 2: Implement backend evidence-detail mapping

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\status_card.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\status_card_builder.py`

- [ ] **Step 1: Add a nested evidence-detail model**

Include:
- `content`
- `source_type`
- `confidence`
- `source_message_count`

- [ ] **Step 2: Map conversation evidence into card details**

Project `conversation_memory.evidence_points` into the new detail model while keeping the existing plain `evidence_points` list for backwards compatibility in the card.

- [ ] **Step 3: Re-run focused backend tests to verify GREEN**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_evidence_metadata.py -q
```

Expected:
- All backend evidence-detail tests pass.

### Task 3: Render richer evidence details in the frontend card

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\src\services\teacher\chatV2.ts`
- Modify: `d:\Edu_AI_1\Edu_AI\src\components\teacher\StatusCardV2.tsx`
- Modify: `d:\Edu_AI_1\Edu_AI\src\components\teacher\StatusCard.css`

- [ ] **Step 1: Extend the frontend type**

Add an optional `evidence_details` list matching the backend shape.

- [ ] **Step 2: Update expanded detail rendering**

Show each evidence item with:
- evidence content
- a source-type badge
- a confidence badge
- a compact source-count label

- [ ] **Step 3: Style the evidence metadata rows**

Add compact badge styles that fit the existing card visual language.

### Task 4: Verify compatibility

**Files:**
- No additional code changes expected

- [ ] **Step 1: Run backend focused verification**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_details.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_evidence_metadata.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_service_v2.py -q
```

Expected:
- Green backend run with no status-card regressions.

- [ ] **Step 2: Run frontend production build**

Run:

```powershell
npm run build
```

Expected:
- Successful Vite production build with richer evidence metadata rendering.

### Self-Review

- Scope remains narrow: display richer evidence metadata only.
- Backend still owns the state projection; frontend only changes presentation.
- Every task ends with a concrete verification command and avoids placeholders.
