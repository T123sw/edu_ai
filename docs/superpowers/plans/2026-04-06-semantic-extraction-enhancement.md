# Semantic Extraction Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing LLM enhancement path so it can semantically enrich topics, user goals, and constraints without polluting protected fact/state fields.

**Architecture:** Reuse the existing `LLMEnhancementProvider -> LLMEnhancementRouter -> ExtractionGuard` pipeline. Expand the provider’s allowed JSON schema to `current_topics`, `user_goals`, and `constraints`, then add lightweight sanitization in the provider/guard so low-signal phrases are filtered before merge.

**Tech Stack:** Python, pytest, FastAPI chat orchestration layer

---

### Task 1: Lock semantic enrichment behavior with failing tests

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_llm_enhancement_provider.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_extraction_guard.py`

- [ ] **Step 1: Add a failing provider test for semantic topic/goal/constraint extraction**

```python
def test_llm_enhancement_provider_builds_semantic_candidates_for_topics_goals_and_constraints():
    gateway = DummyGateway(
        """
        {
          "current_topics": ["课堂前10分钟学生参与度下降"],
          "user_goals": ["分析问题"],
          "constraints": {"audience": "教研组", "tone": "正式", "extra_constraints": ["突出改进建议"]}
        }
        """
    )
```

- [ ] **Step 2: Run the provider tests and verify RED**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_llm_enhancement_provider.py -v`

Expected: fail because provider currently ignores these fields.

- [ ] **Step 3: Add a failing guard test for low-signal semantic candidates**

```python
def test_extraction_guard_rejects_low_signal_semantic_candidates():
    ...
```

- [ ] **Step 4: Run the guard tests and verify RED**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_extraction_guard.py -v`

Expected: fail because the guard currently accepts generic topic/goal phrases.

### Task 2: Extend provider and guard

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/llm_enhancement_provider.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/extraction_guard.py`

- [ ] **Step 1: Extend provider schema and parser for semantic fields**

```python
_ALLOWED_FIELDS = (
    "summary_text",
    "current_topics",
    "user_goals",
    "constraints",
    "teaching_issues",
    "student_signals",
    "evidence_points",
)
```

- [ ] **Step 2: Normalize and filter low-signal semantic values**

```python
def _normalize_semantic_list(...):
    ...
```

- [ ] **Step 3: Let guard merge sanitized semantic candidates**

```python
if candidate.field in {"current_topics", "user_goals"}:
    ...
```

- [ ] **Step 4: Run provider and guard tests and verify GREEN**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_llm_enhancement_provider.py tests\chat\test_extraction_guard.py -v`

Expected: all tests pass.

### Task 3: Verify router/store integration

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_llm_enhancement_router.py`

- [ ] **Step 1: Add an integration test that semantic candidates land in memory state**

```python
def test_conversation_store_adapter_can_apply_semantic_llm_enhancement_candidates():
    ...
```

- [ ] **Step 2: Run the llm-enhancement integration tests and verify GREEN**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_llm_enhancement_router.py tests\chat\test_route_chat_service.py -v`

Expected: semantic candidates merge into state and existing enhancement trace behavior remains intact.
