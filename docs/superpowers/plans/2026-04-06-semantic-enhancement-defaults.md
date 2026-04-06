# Semantic Enhancement Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make semantic extraction enhancement production-usable by rejecting low-confidence semantic candidates and enabling the enhancement path by default.

**Architecture:** Keep the current enhancement pipeline, but parse optional field-level confidence for semantic candidates in `LLMEnhancementProvider` and let `ExtractionGuard` reject low-confidence semantic writes. Separately, flip the feature-flag default so the route service uses LLM enhancement unless explicitly disabled.

**Tech Stack:** Python, pytest, FastAPI chat orchestration layer

---

### Task 1: Lock confidence behavior with failing tests

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_llm_enhancement_provider.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_extraction_guard.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_route_feature_flags.py`

- [ ] **Step 1: Add a failing provider test for low-confidence semantic metadata**

```python
def test_llm_enhancement_provider_parses_semantic_field_confidence():
    ...
```

- [ ] **Step 2: Add a failing guard test that low-confidence semantic candidates are rejected**

```python
def test_extraction_guard_rejects_low_confidence_semantic_candidates():
    ...
```

- [ ] **Step 3: Add a failing flag test for default enablement**

```python
def test_load_route_feature_flags_enables_llm_enhancement_by_default(monkeypatch):
    ...
```

- [ ] **Step 4: Run targeted tests and verify RED**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_llm_enhancement_provider.py tests\chat\test_extraction_guard.py tests\chat\test_route_feature_flags.py -v`

Expected: fail because semantic confidence is not parsed/gated and the feature flag still defaults to disabled.

### Task 2: Implement confidence gating and default enablement

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/llm_enhancement_provider.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/extraction_guard.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/route_feature_flags.py`

- [ ] **Step 1: Parse optional `*_confidence` fields for semantic candidates**
- [ ] **Step 2: Reject low-confidence semantic candidates in guard**
- [ ] **Step 3: Flip `CHAT_USE_LLM_ENHANCEMENT` default from `0` to `1`**
- [ ] **Step 4: Run targeted tests and verify GREEN**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_llm_enhancement_provider.py tests\chat\test_extraction_guard.py tests\chat\test_route_feature_flags.py -v`

Expected: all tests pass.

### Task 3: Verify integration after defaults change

**Files:**
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_llm_enhancement_router.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_route_service_factory.py`

- [ ] **Step 1: Run integration tests**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_llm_enhancement_router.py tests\chat\test_route_service_factory.py -v`

Expected: semantic enhancement integration still works and the service factory can still disable enhancement when env explicitly sets `CHAT_USE_LLM_ENHANCEMENT=0`.
