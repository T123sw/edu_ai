# Report Preparation Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden report subject and focus extraction so generic report requests do not become the subject, and low-signal LLM outputs are normalized before they reach workflow state.

**Architecture:** Keep `ReportContextOrganizer` as the single entrypoint, but add a rule-based subject extractor for explicit report requests plus a post-processing guardrail that normalizes both fallback and LLM outputs. Recompute missing fields, follow-ups, confidence, and soft-confirm copy from the sanitized result.

**Tech Stack:** Python, pytest, FastAPI chat orchestration layer

---

### Task 1: Lock the weak cases with failing tests

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_report_context_organizer_guardrails.py`

- [ ] **Step 1: Add a failing test for generic report requests**

```python
def test_report_context_organizer_does_not_promote_generic_report_request_to_subject():
    context = GenerationContext(
        conversation_id="conv-generic-report",
        resource_type="report",
        summary_text="",
        current_topics=["继续分析"],
        user_goals=["生成报告"],
        recent_relevant_messages=[{"role": "user", "content": "请基于当前内容生成一份报告"}],
    )

    result = ReportContextOrganizer().organize(
        context=context,
        request_question="请基于当前内容生成一份报告",
    )

    assert result.report_subject is None
    assert result.missing_critical_fields == ["report_subject"]
```

- [ ] **Step 2: Add a failing test for explicit subject extraction from request text**

```python
def test_report_context_organizer_extracts_subject_from_explicit_report_request():
    context = GenerationContext(
        conversation_id="conv-explicit-report",
        resource_type="report",
        summary_text="",
        current_topics=[],
        user_goals=["生成报告"],
    )

    result = ReportContextOrganizer().organize(
        context=context,
        request_question="请围绕课堂前10分钟学生参与度下降生成一份报告",
    )

    assert result.report_subject == "课堂前10分钟学生参与度下降"
```

- [ ] **Step 3: Add a failing test for low-signal LLM outputs**

```python
def test_report_context_organizer_rewrites_low_signal_llm_subject_and_focus():
    class DummyStructured:
        def invoke(self, prompt):
            return ReportPreparationResult(
                report_intent="generate_report",
                report_subject="请基于当前内容生成一份报告",
                report_focus="详细一点",
            )
```

- [ ] **Step 4: Run the organizer guardrail tests and verify RED**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_report_context_organizer_guardrails.py -v`

Expected: the new tests fail because the organizer currently accepts generic request text and low-signal LLM output too easily.

### Task 2: Add subject extraction and result sanitization

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/report_context_organizer.py`

- [ ] **Step 1: Add request-level subject extraction**

```python
def _extract_subject_from_report_request(self, request_question: str) -> str | None:
    ...
```

- [ ] **Step 2: Add result guardrail normalization**

```python
def _sanitize_result(self, *, context, request_question: str, raw_result: ReportPreparationResult) -> ReportPreparationResult:
    ...
```

- [ ] **Step 3: Apply sanitization to both fallback and LLM paths**

```python
result = self._sanitize_result(...)
```

- [ ] **Step 4: Run the guardrail tests and verify GREEN**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_report_context_organizer_guardrails.py -v`

Expected: all guardrail tests pass.

### Task 3: Run related regression coverage

**Files:**
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_report_context_organizer.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_generation_readiness_judge.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_report_runtime_preparation_flow.py`

- [ ] **Step 1: Run the report-preparation regression bundle**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest tests\chat\test_report_context_organizer.py tests\chat\test_report_context_organizer_guardrails.py tests\chat\test_generation_readiness_judge.py tests\chat\test_report_runtime_preparation_flow.py tests\chat\test_report_workflow_runtime_context.py -v`

Expected: all tests pass and sanitized subject/focus still integrate with readiness and runtime flow.
