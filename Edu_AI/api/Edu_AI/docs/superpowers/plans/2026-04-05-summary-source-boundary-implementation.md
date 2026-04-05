# Summary Source Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce `conversation_summary.summary_text` as a consumer-only view that never backfills long-lived fact buckets such as `user_stated_facts` or `confirmed_facts`.

**Architecture:** Keep summary generation intact, but harden projections and consumers so facts only come from stateful fact layers (`user_stated_facts`, legacy `confirmed_facts`) and never from summary text. Add regression tests around extractor, guard, generation context, and status-card consumption.

**Tech Stack:** Python, pytest, chat orchestrator, status-card builder, extraction guard.

---

### Task 1: Add failing regression tests for the summary boundary

**Files:**
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_summary_source_boundary.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_extraction_guard.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py`

- [ ] **Step 1: Write extractor boundary tests**

```python
def test_control_turn_does_not_backfill_facts_from_existing_summary():
    patch = extractor.build_state_patch(...)
    memory = patch["conversation_memory"]
    assert memory["user_stated_facts"] == []
    assert memory["confirmed_facts"] == []
```

- [ ] **Step 2: Write consumer/guard boundary tests**

```python
def test_generation_context_builder_never_backfills_confirmed_facts_from_summary():
    context = GenerationContextBuilder().build_for_resource(...)
    assert context.confirmed_facts == []


def test_status_card_builder_prefers_user_stated_facts_over_legacy_confirmed_bucket():
    card = StatusCardBuilder().build(...)
    assert card.confirmed_facts == ["前10分钟学生多次走神"]


def test_extraction_guard_summary_candidate_does_not_mutate_fact_buckets():
    merged = guard.merge(...)
    assert merged["conversation_memory"]["confirmed_facts"] == ["前10分钟学生多次走神"]
```

- [ ] **Step 3: Run tests to verify at least the status-card projection fails**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_summary_source_boundary.py Edu_AI/api/Edu_AI/tests/chat/test_extraction_guard.py Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py -q`

Expected: FAIL because `StatusCardBuilder` still reads legacy `confirmed_facts` first.

### Task 2: Harden fact projection helpers and status-card consumption

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/conversation_memory_extractor_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/generation_context_builder.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/status_card_builder.py`

- [ ] **Step 1: Add an explicit confirmed-fact projection helper in the extractor**

```python
@staticmethod
def _project_confirmed_facts(*, user_stated_facts: list[str], existing_memory: dict) -> list[str]:
    if user_stated_facts:
        return list(user_stated_facts)
    return list(existing_memory.get("confirmed_facts") or [])
```

- [ ] **Step 2: Update extractor and generation-context consumers to use the explicit projection**

```python
confirmed_facts = self._project_confirmed_facts(...)
```

- [ ] **Step 3: Update status-card consumption to prefer `user_stated_facts`**

```python
confirmed_facts = list(
    memory.get("user_stated_facts")
    or memory.get("confirmed_facts")
    or []
)[:3]
```

- [ ] **Step 4: Run focused regression tests**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_summary_source_boundary.py Edu_AI/api/Edu_AI/tests/chat/test_extraction_guard.py Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py -q`

Expected: PASS

### Task 3: Run full chat regression

**Files:**
- Modify: `Edu_AI/api/Edu_AI/docs/superpowers/plans/2026-04-05-summary-source-boundary-implementation.md`

- [ ] **Step 1: Run the full chat suite**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat -q`

Expected: PASS

- [ ] **Step 2: Record verification in handoff notes**

```markdown
- Focused summary-boundary suite: `X passed`
- Full `tests/chat`: `Y passed`
- Residual warnings: existing `jieba/pkg_resources` and `.pytest_cache` warnings only
```
