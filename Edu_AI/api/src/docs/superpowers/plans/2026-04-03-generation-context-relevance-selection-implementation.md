# Generation Context Relevance Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current “last 6 messages” fallback in `GenerationContextBuilder` with a deterministic relevant-message selector that improves report context quality without requiring model-side semantic retrieval.

**Architecture:** Keep `GenerationContextBuilder` as the only place that chooses `recent_relevant_messages`. Add a focused scoring helper that ranks conversation messages against structured memory signals such as topics, teaching issues, student signals, confirmed facts, and the current user request. Preserve chronological order after selection, and keep the existing last-window behavior as a fallback when nothing scores as relevant.

**Tech Stack:** Python, pytest, existing chat orchestration/report runtime stack

---

### Task 1: Lock relevant-message behavior with failing tests

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_relevance.py`

- [ ] **Step 1: Write failing relevance-selection tests**

Add tests that verify:
- older but relevant messages can outrank newer unrelated messages
- selected messages remain in chronological order
- builder falls back to the recent window when no message matches the relevance signals

- [ ] **Step 2: Run the focused tests to verify RED**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_relevance.py -q
```

Expected:
- At least one test fails because `GenerationContextBuilder` still returns the last 6 raw messages.

### Task 2: Implement deterministic relevance selection

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\generation_context_builder.py`

- [ ] **Step 1: Add scoring helpers for message relevance**

Implement small helpers that:
- collect relevance phrases from memory and request
- score each message by direct phrase overlap
- keep the strongest matches up to a fixed cap

- [ ] **Step 2: Add fallback behavior**

If the score set is empty, preserve the current last-6 behavior so low-state chats do not regress.

- [ ] **Step 3: Re-run the focused tests to verify GREEN**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_relevance.py -q
```

Expected:
- All relevance-selection tests pass.

### Task 3: Verify downstream report handoff still behaves correctly

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py`

- [ ] **Step 1: Add downstream assertions using the selected messages**

Extend report-facing tests so they verify the runtime receives the relevance-selected window rather than an arbitrary trailing window.

- [ ] **Step 2: Run targeted downstream tests**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_relevance.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py -q
```

Expected:
- All focused builder/runtime tests pass.

### Task 4: Full verification for relevance selection

**Files:**
- No additional code changes expected

- [ ] **Step 1: Run a focused suite**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_relevance.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_assembler.py -q
```

Expected:
- Green run with zero failures.

- [ ] **Step 2: Run a broader regression sweep**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_service_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_compat.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_chat_service.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_status_card_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_context_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_relevance.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_assembler.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py -q
```

Expected:
- Green run with no regressions in chat v2, status-card integration, or report-first context flow.

### Self-Review

- Scope is intentionally narrow: this plan improves deterministic relevance selection only.
- Existing report/context architecture stays intact; only the message window selection strategy changes.
- No placeholder steps remain; every task ends with a concrete verification command.
