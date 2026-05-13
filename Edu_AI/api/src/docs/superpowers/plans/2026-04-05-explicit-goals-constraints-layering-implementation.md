# Explicit Goals and Constraints Layering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `conversation_memory.user_goals` and `conversation_memory.constraints` into explicit user-declared fields and derived workflow fields while preserving compatibility for current report/status-card consumers.

**Architecture:** Keep the rule-based extractor as the write path, but add explicit/derived subfields so long-lived conversation state can distinguish user-stated intent/requirements from workflow-inferred intent/constraints. Continue exposing compatible `user_goals` and `constraints` projections to downstream consumers until all readers migrate.

**Tech Stack:** Python, pytest, chat orchestrator state patching, existing generation/status-card/report consumers.

---

### Task 1: Add failing tests for explicit vs derived layering

**Files:**
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_goal_constraint_layering.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py`

- [ ] **Step 1: Write the failing extractor tests**

```python
def test_extractor_separates_explicit_user_goal_from_derived_workflow_goal():
    patch = extractor.build_state_patch(...)
    memory = patch["conversation_memory"]
    assert memory["explicit_user_goals"] == ["分析问题"]
    assert memory["derived_workflow_goal"] == "生成报告"
    assert memory["user_goals"][0] == "生成报告"
    assert "分析问题" in memory["user_goals"]


def test_extractor_separates_explicit_constraints_from_derived_constraints():
    patch = extractor.build_state_patch(...)
    memory = patch["conversation_memory"]
    assert memory["explicit_user_constraints"]["audience"] == "教研组"
    assert memory["explicit_user_constraints"]["tone"] == "正式"
    assert memory["derived_workflow_constraints"]["course_id"] == "course-1"
    assert memory["constraints"]["course_id"] == "course-1"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_goal_constraint_layering.py -q`

Expected: FAIL with missing `explicit_user_goals` / `explicit_user_constraints` / `derived_workflow_goal` / `derived_workflow_constraints`.

- [ ] **Step 3: Add consumer compatibility tests**

```python
def test_generation_context_builder_prefers_explicit_goals_but_keeps_compat_projection():
    context = GenerationContextBuilder().build_for_resource(...)
    assert context.user_goals == ["生成报告", "分析问题"]
    assert context.constraints["audience"] == "教研组"
    assert context.constraints["course_id"] == "course-1"


def test_status_card_builder_prefers_explicit_goal_for_user_facing_goal_label():
    card = StatusCardBuilder().build(...)
    assert card.goal == "分析问题"
```

- [ ] **Step 4: Run focused consumer tests to verify failure**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py -q`

Expected: FAIL because current readers do not know about the new layered fields.

- [ ] **Step 5: Commit red tests**

```bash
git add Edu_AI/api/Edu_AI/tests/chat/test_goal_constraint_layering.py Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py
git commit -m "test: cover explicit vs derived goal and constraint layering"
```

### Task 2: Implement layered state patching in the extractor

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/conversation_memory_extractor_v2.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_goal_constraint_layering.py`

- [ ] **Step 1: Add explicit/derived helper methods**

```python
def _extract_explicit_user_goal(self, question: str) -> str | None:
    ...


def _extract_derived_workflow_goal(self, *, question: str, action_name: str, workflow_type: str) -> str | None:
    ...


def _split_constraints(self, *, question: str, existing_memory: dict, request) -> tuple[dict, dict, dict]:
    ...
```

- [ ] **Step 2: Run the new extractor tests and confirm they still fail for the expected missing behavior**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_goal_constraint_layering.py -q`

Expected: FAIL on assertions about merged/projection behavior.

- [ ] **Step 3: Update `build_state_patch()` to persist layered fields and keep compatibility projections**

```python
explicit_goal = self._extract_explicit_user_goal(semantic_question)
derived_goal = self._extract_derived_workflow_goal(...)
explicit_constraints, derived_constraints, merged_constraints = self._split_constraints(...)

merged_memory.update(
    {
        "explicit_user_goals": explicit_goals,
        "derived_workflow_goal": derived_goal,
        "user_goals": projected_goals,
        "explicit_user_constraints": explicit_constraints,
        "derived_workflow_constraints": derived_constraints,
        "constraints": merged_constraints,
    }
)
```

- [ ] **Step 4: Run extractor tests and confirm green**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_goal_constraint_layering.py -q`

Expected: PASS

- [ ] **Step 5: Commit extractor implementation**

```bash
git add Edu_AI/api/Edu_AI/app/chat/orchestrator/conversation_memory_extractor_v2.py Edu_AI/api/Edu_AI/tests/chat/test_goal_constraint_layering.py
git commit -m "feat: layer explicit and derived conversation goals and constraints"
```

### Task 3: Update consumers to read layered state safely

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/generation_context_builder.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/status_card_builder.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py`

- [ ] **Step 1: Update `GenerationContextBuilder` to read layered goals/constraints through compatibility projections**

```python
explicit_goals = list(memory.get("explicit_user_goals") or [])
projected_goals = list(memory.get("user_goals") or [])
context_goals = projected_goals or explicit_goals
constraints = dict(memory.get("constraints") or {})
```

- [ ] **Step 2: Update `StatusCardBuilder` to prefer user-explicit goal for card goal text**

```python
goal = next(iter(memory.get("explicit_user_goals") or []), None) \
    or next(iter(memory.get("user_goals") or []), None) \
    or workflow_goal
```

- [ ] **Step 3: Run focused consumer tests**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py -q`

Expected: PASS

- [ ] **Step 4: Commit consumer compatibility updates**

```bash
git add Edu_AI/api/Edu_AI/app/chat/orchestrator/generation_context_builder.py Edu_AI/api/Edu_AI/app/chat/orchestrator/status_card_builder.py Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py
git commit -m "feat: consume layered goals and constraints safely"
```

### Task 4: Run regression verification

**Files:**
- Modify: `Edu_AI/api/Edu_AI/docs/superpowers/plans/2026-04-05-explicit-goals-constraints-layering-implementation.md`

- [ ] **Step 1: Run the focused state-layering test suite**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_goal_constraint_layering.py Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py -q`

Expected: PASS

- [ ] **Step 2: Run the full chat regression suite**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat -q`

Expected: PASS

- [ ] **Step 3: Record verification results in handoff notes**

```markdown
- Focused layering suite: `X passed`
- Full `tests/chat`: `Y passed`
- Residual warnings: existing `jieba/pkg_resources` and `.pytest_cache` warnings only
```

- [ ] **Step 4: Commit verification-only updates if needed**

```bash
git add Edu_AI/api/Edu_AI/docs/superpowers/plans/2026-04-05-explicit-goals-constraints-layering-implementation.md
git commit -m "docs: record explicit goal and constraint layering verification"
```
