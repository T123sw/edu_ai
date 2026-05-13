# Status Card Expanded Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the status card so users can expand it to inspect richer conversation state, including confirmed facts, student signals, evidence points, and extra generation constraints.

**Architecture:** Keep `StatusCardBuilder` as the single backend place that derives card-facing state from conversation memory. Expand the `StatusCardViewModel` with detail fields that remain optional, then update the frontend `StatusCard` component to render a compact default state with a local expand/collapse detail panel. Preserve the existing default card behavior for low-state chats.

**Tech Stack:** Python, TypeScript, React, Ant Design, pytest, Vite build

---

### Task 1: Lock backend detail-field behavior with failing tests

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_details.py`

- [ ] **Step 1: Write failing tests for detail fields**

Add tests that verify `StatusCardBuilder` exposes:
- `student_signals`
- `evidence_points`
- `extra_constraints`

Also verify low-state chat still falls back cleanly with empty detail lists.

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_details.py -q
```

Expected:
- At least one assertion fails because the view model does not yet include the new detail fields.

### Task 2: Implement backend status-card detail mapping

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\status_card.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\status_card_builder.py`

- [ ] **Step 1: Extend the view model**

Add optional list fields for:
- `student_signals`
- `evidence_points`
- `extra_constraints`

- [ ] **Step 2: Map conversation memory into those fields**

Populate the lists from:
- `conversation_memory.student_signals`
- `conversation_memory.evidence_points[*].content`
- `conversation_memory.constraints.extra_constraints`

- [ ] **Step 3: Re-run focused backend tests to verify GREEN**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_details.py -q
```

Expected:
- All backend detail-field tests pass.

### Task 3: Implement expandable frontend card details

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\src\services\teacher\chatV2.ts`
- Modify: `d:\Edu_AI_1\Edu_AI\src\components\teacher\StatusCard.tsx`
- Modify: `d:\Edu_AI_1\Edu_AI\src\components\teacher\StatusCard.css`

- [ ] **Step 1: Extend the frontend status-card type**

Add the same optional detail fields to `StatusCardV2`.

- [ ] **Step 2: Add an expand/collapse detail section**

Update the component so it:
- stays compact by default
- shows a small toggle when detail data exists
- reveals confirmed facts, student signals, evidence points, and extra constraints in a structured detail area

- [ ] **Step 3: Style the detail panel**

Add card-consistent styling for:
- the toggle row
- detail groups
- compact evidence/fact lists

### Task 4: Verify end-to-end compatibility

**Files:**
- No additional code changes expected

- [ ] **Step 1: Run backend focused verification**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_details.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_service_v2.py -q
```

Expected:
- Green backend run with no status-card regressions.

- [ ] **Step 2: Run frontend production build**

Run:

```powershell
npm run build
```

Expected:
- Successful Vite production build with the expanded status-card UI.

### Self-Review

- Scope stays narrow: no new routes, no new persistence behavior, no extra workflow changes.
- Backend remains the source of truth for card state; frontend only controls local expand/collapse presentation.
- Every task ends in an executable verification command and avoids placeholders.
