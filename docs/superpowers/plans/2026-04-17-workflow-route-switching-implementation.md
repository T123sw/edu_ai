# Workflow Route Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make explicit user requests switch immediately from an existing workflow to fast chat or another workflow.

**Architecture:** Add deterministic pre-resume switch detection in the existing route-rule module. Keep workflow runtime code unchanged so the behavior remains centralized in routing.

**Tech Stack:** Python, pytest, existing `ChatRequestV2`, `WorkflowState`, and `RouteDecision` domain models.

---

### Task 1: Route Tests

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_route_rules.py`

- [ ] **Step 1: Write the failing tests**

Add tests for switching from running and completed report workflows back to fast chat or into PPT generation.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/chat/test_route_rules.py -q` from `Edu_AI/api/Edu_AI`.

Expected: the new tests fail because current routing resumes the existing report workflow.

### Task 2: Route Rule Implementation

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/route_rules.py`

- [ ] **Step 1: Add explicit chat-exit markers**

Add `_CHAT_EXIT_MARKERS` with high-confidence phrases such as "回到普通对话", "退出工作流", and "先聊天".

- [ ] **Step 2: Add `_is_explicit_chat_exit()`**

Normalize the user question and match the chat-exit markers.

- [ ] **Step 3: Add pre-resume switch handling**

Inside `decide_route()`, before existing interrupt and resume handling, route explicit chat exits to fast chat and explicit artifact-generation requests to their target workflow.

- [ ] **Step 4: Run route tests**

Run: `python -m pytest tests/chat/test_route_rules.py -q` from `Edu_AI/api/Edu_AI`.

Expected: all route-rule tests pass.

### Task 3: Focused Regression Verification

**Files:**
- Test only

- [ ] **Step 1: Run related route suites**

Run: `python -m pytest tests/chat/test_route_rules.py tests/chat/test_route_rules_ppt.py tests/chat/test_quiz_route_rules.py -q` from `Edu_AI/api/Edu_AI`.

Expected: all selected route tests pass.

- [ ] **Step 2: Inspect changed files**

Run: `git diff -- Edu_AI/api/Edu_AI/app/chat/orchestrator/route_rules.py Edu_AI/api/Edu_AI/tests/chat/test_route_rules.py`.

Expected: diff only contains route switching tests and route switching logic.
