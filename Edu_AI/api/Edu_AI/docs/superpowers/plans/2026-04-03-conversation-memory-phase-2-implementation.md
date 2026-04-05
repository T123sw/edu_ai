# Conversation Memory Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `conversation_memory` beyond the first MVP so normal chat can maintain richer structured state, and make the merge behavior stable enough for status-card display and report handoff.

**Architecture:** Keep the existing `ConversationStoreAdapter -> ConversationMemoryExtractor -> ContextBuilder -> GenerationContextBuilder -> ReportAssembler` chain. Add the next minimal set of automatically maintained fields in the extractor, codify merge behavior in deterministic helper methods, and verify both persistence and downstream report consumption with focused tests before broader regression.

**Tech Stack:** Python, pytest, existing chat v2 orchestration/persistence stack

---

### Task 1: Lock the new behavior with failing extractor tests

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_extractor.py`

- [ ] **Step 1: Write failing tests for new fields and merge behavior**

Add tests that verify:
- `student_signals` are extracted from participation/attention/discipline style language
- `evidence_points` are extracted from stronger observation-style clauses
- `constraints.extra_constraints` can absorb additional formatting requirements instead of being lost
- newer goals move to the front while keeping prior goals in the history window

- [ ] **Step 2: Run focused extractor tests to verify RED**

Run:

```powershell
pytest tests/chat/test_conversation_memory_extractor.py -q
```

Expected:
- At least one new assertion fails because the current extractor does not yet populate the new memory fields or richer merge behavior.

### Task 2: Implement extractor phase-2 memory maintenance

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\conversation_memory_extractor.py`

- [ ] **Step 1: Add deterministic merge helpers**

Implement focused helpers for:
- stable list dedupe with limits
- merging goals with newest-active-first behavior
- merging constraints with slot override plus `extra_constraints` accumulation
- extracting `student_signals`
- extracting `evidence_points`

- [ ] **Step 2: Extend `build_state_patch` to write the new fields**

Update the returned `conversation_memory` payload so it now maintains:
- `student_signals`
- `evidence_points`
- stronger `constraints.extra_constraints`
- stable `user_goals` ordering

- [ ] **Step 3: Re-run focused extractor tests to verify GREEN**

Run:

```powershell
pytest tests/chat/test_conversation_memory_extractor.py -q
```

Expected:
- All extractor tests pass.

### Task 3: Verify persistence and downstream report handoff

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_persistence_and_compat.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_new_path_persistence.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_assembler.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py`

- [ ] **Step 1: Add persistence assertions for the new memory fields**

Extend persistence tests so normal reply persistence checks for:
- `student_signals`
- `evidence_points`
- retained constraints shape

- [ ] **Step 2: Extend downstream context tests**

Verify that once those fields exist in conversation memory:
- `GenerationContextBuilder` carries them
- `ReportAssembler` includes them in `gathered_context`
- `ReportWorkflowRuntime` delivers them to the report engine state

- [ ] **Step 3: Run targeted downstream tests**

Run:

```powershell
pytest tests/chat/test_persistence_and_compat.py tests/chat/test_new_path_persistence.py tests/chat/test_generation_context_builder.py tests/chat/test_report_assembler.py tests/chat/test_report_workflow_runtime_context.py -q
```

Expected:
- All targeted persistence and report-context tests pass.

### Task 4: Full verification for conversation-memory phase 2

**Files:**
- No additional code changes expected

- [ ] **Step 1: Run the focused phase-2 suite**

Run:

```powershell
pytest tests/chat/test_conversation_memory_extractor.py tests/chat/test_persistence_and_compat.py tests/chat/test_new_path_persistence.py tests/chat/test_generation_context_builder.py tests/chat/test_report_assembler.py tests/chat/test_report_workflow_runtime_context.py -q
```

Expected:
- Green run with zero failures.

- [ ] **Step 2: Run a broader chat regression sweep**

Run:

```powershell
pytest tests/chat/test_reply_service_v2.py tests/chat/test_report_service_v2.py tests/chat/test_routes_compat.py tests/chat/test_routes_v2.py tests/chat/test_route_chat_service.py tests/chat/test_status_card_builder.py tests/chat/test_context_builder.py tests/chat/test_generation_context_builder.py tests/chat/test_conversation_memory_extractor.py tests/chat/test_persistence_and_compat.py tests/chat/test_new_path_persistence.py tests/chat/test_report_assembler.py tests/chat/test_report_workflow_runtime_context.py -q
```

Expected:
- Green run with no regressions in chat v2, status-card, and report-first context integration.

### Self-Review

- Scope is intentionally limited to extractor/persistence/report-handoff continuity; it does not attempt to redesign all memory fields in one pass.
- All planned changes map back to the phase-2 goal: richer `conversation_memory`, deterministic merge behavior, and downstream report reuse.
- No placeholder implementation steps remain; every task ends in an executable verification command.
