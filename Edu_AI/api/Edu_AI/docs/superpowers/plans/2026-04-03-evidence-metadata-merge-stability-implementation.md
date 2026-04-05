# Evidence Metadata And Merge Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `conversation_memory.evidence_points` richer and more stable by attaching source metadata and by merging repeated evidence across turns instead of rewriting shallow content-only items.

**Architecture:** Add stable message identifiers at the storage layer so new evidence items can reference concrete messages. Upgrade the extractor to emit richer evidence entries with `source_type`, `source_message_ids`, and `confidence`, then merge by semantic content while upgrading confidence and preserving source links. Keep `GenerationContextBuilder`, `ReportAssembler`, and `ReportWorkflowRuntime` consuming the richer evidence structure without changing their public shape.

**Tech Stack:** Python, pytest, JSON conversation storage, existing chat v2 orchestration/report runtime stack

---

### Task 1: Lock the new behavior with failing tests

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_merge.py`

- [ ] **Step 1: Write failing tests for evidence metadata**

Add tests that verify:
- stored messages carry `message_id`
- extracted evidence points include `source_type`, `source_message_ids`, and `confidence`
- repeated evidence merges into a single item while accumulating source message ids and upgrading confidence

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_merge.py -q
```

Expected:
- At least one assertion fails because messages currently lack ids or evidence is still content-only.

### Task 2: Implement message ids and richer evidence extraction

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\core\conversation_storage.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\conversation_memory_extractor_v2.py`

- [ ] **Step 1: Add stable message ids in storage**

Ensure both newly appended messages and older loaded messages expose `message_id`.

- [ ] **Step 2: Upgrade evidence extraction**

Extend evidence items to include:
- `type`
- `content`
- `source_type`
- `source_message_ids`
- `confidence`

Use the latest assistant/user messages from the recent window as evidence sources when applicable.

- [ ] **Step 3: Implement merge stability**

When the same evidence content reappears:
- keep one evidence item
- merge `source_message_ids`
- upgrade `confidence`

- [ ] **Step 4: Re-run focused tests to verify GREEN**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_merge.py -q
```

Expected:
- All evidence metadata tests pass.

### Task 3: Verify persistence and report handoff still work with richer evidence

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_pipeline.py`

- [ ] **Step 1: Add pipeline tests**

Verify:
- `ConversationStoreAdapter.write_v2_result()` persists richer evidence points
- `GenerationContextBuilder` preserves the richer evidence objects
- `ReportAssembler` and `ReportWorkflowRuntime` pass them through unchanged

- [ ] **Step 2: Run focused pipeline tests**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_merge.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_pipeline.py -q
```

Expected:
- Green run confirming persistence and report pipeline continuity.

### Task 4: Full verification for evidence metadata and merge stability

**Files:**
- No additional code changes expected

- [ ] **Step 1: Run focused verification**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_merge.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_pipeline.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2_pipeline.py -q
```

Expected:
- Green run with no failures in phase-2 conversation-memory behavior.

- [ ] **Step 2: Run broader chat/report regression**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_service_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_compat.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_chat_service.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_assembler.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_merge.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_evidence_metadata_pipeline.py -q
```

Expected:
- Green regression run with richer evidence support in the chat and report paths.

### Self-Review

- Scope stays narrow: richer evidence metadata plus merge stability only.
- Existing report/context contracts stay structurally compatible because `evidence_points` already flows as `list[dict]`.
- Every task ends in a concrete verification command and avoids placeholders.
