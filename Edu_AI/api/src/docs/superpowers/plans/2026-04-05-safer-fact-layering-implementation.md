# Safer Fact Layering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the broad `confirmed_facts` bucket into safer subfields while keeping report/status-card consumers compatible.

**Architecture:** Extend conversation memory with layered fact fields so user-declared facts and assistant-derived fact candidates are tracked separately. Preserve the legacy `confirmed_facts` field as a compatibility projection, and update generation-context building to prefer the safer user-backed fact layer first.

**Tech Stack:** Python, pytest, existing chat state writeback and generation-context pipeline

---

### Task 1: Add Failing Tests For Fact Layering

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_fact_layering.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py`

- [ ] **Step 1: Write failing extractor tests**

Add tests covering:

```python
def test_extractor_separates_user_stated_facts_from_assistant_fact_candidates():
    ...
    assert memory["user_stated_facts"] == ["前10分钟学生多次走神"]
    assert any("开场吸引力不足" in item for item in memory["assistant_fact_candidates"])
    assert memory["confirmed_facts"] == ["前10分钟学生多次走神"]


def test_report_control_turn_does_not_add_assistant_fact_candidates_to_confirmed_facts():
    ...
    assert memory["assistant_fact_candidates"] == []
    assert memory["confirmed_facts"] == existing_confirmed
```

- [ ] **Step 2: Write failing generation-context compatibility test**

Add one test verifying:

```python
assert context.confirmed_facts == ["前10分钟学生多次走神"]
```

when memory contains:

- `user_stated_facts=["前10分钟学生多次走神"]`
- `assistant_fact_candidates=["教师开场吸引力不足"]`
- `confirmed_facts=["旧兼容事实"]`

Expected:

- generation context prefers the safer user-backed fact layer first

- [ ] **Step 3: Run focused tests to verify they fail**

Run:

```bash
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_fact_layering.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py -q
```

Expected:

- FAIL because new fields do not exist yet and generation context still reads only legacy `confirmed_facts`

---

### Task 2: Implement Layered Fact Extraction With Compatibility

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\conversation_memory_extractor_v2.py`

- [ ] **Step 1: Add user-side fact extraction**

Introduce a helper for extracting declarative user facts from semantic user text:

```python
def _extract_user_stated_facts(self, question: str, existing_facts: list[str]) -> list[str]:
    ...
```

Rules:

- ignore workflow control turns
- ignore interrogatives
- ignore short fragments
- keep declarative, reusable observations

- [ ] **Step 2: Re-label current assistant fact extraction as candidates**

Introduce:

```python
def _extract_assistant_fact_candidates(self, answer: str, existing_candidates: list[str]) -> list[str]:
    ...
```

Use the current assistant fact extraction heuristics here, not in legacy `confirmed_facts`.

- [ ] **Step 3: Build compatibility projection**

In `build_state_patch(...)`, write:

```python
user_stated_facts = ...
assistant_fact_candidates = ...
confirmed_facts = user_stated_facts or list(existing_memory.get("confirmed_facts") or [])
```

Behavior goals:

- new assistant statements no longer expand the long-lived compatibility facts bucket
- user-stated facts populate both the new field and compatibility field
- existing conversations keep legacy `confirmed_facts` if no safer user-backed facts exist yet

- [ ] **Step 4: Persist the new fields alongside existing memory**

Ensure `conversation_memory` now includes:

- `user_stated_facts`
- `assistant_fact_candidates`
- legacy `confirmed_facts`

- [ ] **Step 5: Run focused tests**

Run:

```bash
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_fact_layering.py -q
```

Expected:

- PASS

---

### Task 3: Teach GenerationContext To Prefer The Safer Fact Layer

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\generation_context_builder.py`
- Optional Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\generation_context.py`

- [ ] **Step 1: Add compatibility preference order**

Use this order when building `context.confirmed_facts`:

1. `user_stated_facts`
2. `user_confirmed_interpretations` (if introduced later, not required in this step)
3. legacy `confirmed_facts`

Minimal implementation for this step:

```python
confirmed_facts = list(memory.get("user_stated_facts") or []) or list(memory.get("confirmed_facts") or [])
```

- [ ] **Step 2: Keep existing consumers unchanged**

Do not rename the downstream `GenerationContext.confirmed_facts` field yet.

- [ ] **Step 3: Run focused compatibility tests**

Run:

```bash
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_fact_layering.py -q
```

Expected:

- PASS

---

### Task 4: Run Broader Chat Regression

**Files:**
- Verify only

- [ ] **Step 1: Run broader chat regression**

Run:

```bash
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat -q
```

Expected:

- PASS

- [ ] **Step 2: Summarize safety impact**

Confirm in final handoff:

- user-backed facts are now separated from assistant-derived candidates
- legacy `confirmed_facts` remains compatible for existing consumers
- report/status-card/generation-context still run without schema breakage
