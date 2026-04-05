# Hybrid Extractor Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first-stage foundation for a hybrid extraction system where the existing rule extractor remains the primary path and an LLM enhancement layer can be introduced safely behind merge / guard controls.

**Architecture:** Keep the current rule extractor as the default producer of conversation state. Introduce a layered extraction contract: rule extractor output -> optional LLM enhancement candidate output -> merge / guard decision -> final state patch. In this phase, the focus is on interfaces, trigger plumbing, candidate models, and guard logic, not on fully replacing extraction behavior with LLM calls.

**Tech Stack:** Python, pytest, existing chat persistence/orchestration stack

---

### Task 1: Define shared extractor contracts

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\extraction_candidate.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\extraction_trigger.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_contracts.py`

- [ ] **Step 1: Write the failing contract tests**

Add tests covering:
- candidate patch shape for `summary`, `topics`, `issues`, `signals`, `evidence`
- trigger model shape for `reply_completed`, `workflow_entered`, `artifact_created`

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_contracts.py -q
```

Expected:
- Fails because the new domain models do not yet exist.

- [ ] **Step 3: Implement the minimal contract models**

Create:
- `ExtractionCandidatePatch`
- `ExtractionEvidenceCandidate`
- `ExtractionTrigger`

- [ ] **Step 4: Re-run the focused test to verify GREEN**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_contracts.py -q
```

Expected:
- PASS

### Task 2: Introduce a merge / guard layer for candidate updates

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\extraction_guard.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_guard.py`

- [ ] **Step 1: Write the failing guard tests**

Add tests that verify:
- guard can accept safe topic / issue / signal candidates
- guard rejects direct writes to disallowed fields such as `active_context`
- guard normalizes candidate evidence into merge-safe structures

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_guard.py -q
```

Expected:
- Fails because the guard layer does not yet exist.

- [ ] **Step 3: Implement the minimal guard**

Implement:
- allowed-field filtering
- candidate normalization
- disallowed-field rejection

- [ ] **Step 4: Re-run the focused test to verify GREEN**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_guard.py -q
```

Expected:
- PASS

### Task 3: Add an enhancement orchestration seam without enabling LLM by default

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\llm_enhancement_router.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\persistence\conversation_store_adapter.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_llm_enhancement_router.py`

- [ ] **Step 1: Write the failing router tests**

Add tests that verify:
- default behavior is rule-only
- enhancement router triggers only for configured events
- returned enhancement candidate patches flow through guard before merge

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_llm_enhancement_router.py -q
```

Expected:
- Fails because the router seam is missing.

- [ ] **Step 3: Implement the minimal router seam**

Implement:
- a disabled-by-default enhancement router
- trigger filtering
- handoff to guard before merge

- [ ] **Step 4: Re-run the focused test to verify GREEN**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_llm_enhancement_router.py -q
```

Expected:
- PASS

### Task 4: Validate backward compatibility with the current rule-based path

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2_pipeline.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py`

- [ ] **Step 1: Extend regression tests for rule-only compatibility**

Verify:
- when no enhancement trigger is active, current extraction output is unchanged
- status card / report pipeline still receive the same fields as before

- [ ] **Step 2: Run the focused compatibility suite**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2_pipeline.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_contracts.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_guard.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_llm_enhancement_router.py -q
```

Expected:
- Green run with no regression in the rule-only path.

### Task 5: Broader regression verification

**Files:**
- No additional code changes expected

- [ ] **Step 1: Run broader chat/report regression**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_service_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_compat.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_routes_v2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_chat_service.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_assembler.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2_pipeline.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_contracts.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_extraction_guard.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_llm_enhancement_router.py -q
```

Expected:
- Green regression run with no breakage in report-first context flow.

### Self-Review

- Scope intentionally avoids “full LLM extraction replacement”.
- This plan only lays the foundation: contracts, guard, trigger seam, and compatibility verification.
- The plan is aligned with the boundary spec: rule extractor stays primary, LLM enhancement remains optional and guarded.
