# Report Workflow Context-Driven Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current slot-first report entry flow with a context-organize-first flow that produces a `ReportPreparationResult`, judges whether a report is already generatable, asks only for critical gaps, and only then hands off to report generation.

**Architecture:** Keep `ConversationSnapshot -> GenerationContext` as the upstream interface, add a new `ReportContextOrganizer` plus `GenerationReadinessJudge` in the report workflow entry path, and let `ReportWorkflowRuntime` decide between strong soft confirm, weak soft confirm, critical-gap follow-up, or direct generation. Preserve the existing report engine for outline/content generation, but stop letting the old `focus_assessor` act as the main gate for report entry.

**Tech Stack:** Python, Pydantic, existing chat workflow runtime, existing report engine, pytest

---

## File Structure

### New files

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\report_preparation.py`
  - Defines `ReportContextSummary`, `ReportPreparationResult`, readiness enums/constants, and normalization helpers.

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\report_context_organizer.py`
  - Converts `GenerationContext` plus request metadata into a `ReportPreparationResult`.
  - First version may use deterministic scaffolding plus optional LLM assistance, but must return a stable structured result.

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\generation_readiness_judge.py`
  - Applies the new “can we write a report skeleton?” rules.
  - Returns `direct_generate`, `weak_soft_confirm`, `strong_soft_confirm`, or `ask_critical_gap`.

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_context_organizer.py`
  - Tests organizer output schema and field derivation.

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_readiness_judge.py`
  - Tests “enough to generate” decision rules.

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_runtime_preparation_flow.py`
  - Tests runtime orchestration across strong confirm / weak confirm / direct generate / ask critical gap.

### Existing files to modify

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\report\runtime.py`
  - Insert organizer and judge into the report runtime entry flow.
  - Emit `report_preparation_result` and `readiness_decision` traces.

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\report\assembler.py`
  - Keep compatibility with current gathered context, but add mapping from `ReportPreparationResult` to legacy engine state if required.

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\agents\universal_report_engine.py`
  - Reduce entry dependence on old `core_topic/focus_area` gating when runtime has already decided “generate-ready”.
  - Preserve generator/outliner logic.

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\report\__init__.py` or relevant export modules if needed
  - Export new orchestrator components if the package pattern expects it.

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_universal_report_engine_context_slots.py`
  - Update expectations to match the redesigned entry flow.

---

### Task 1: Define Report Preparation Contracts

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\report_preparation.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_context_organizer.py`

- [ ] **Step 1: Write the failing contract test**

```python
from app.chat.domain.report_preparation import ReportPreparationResult


def test_report_preparation_result_defaults_are_stable():
    result = ReportPreparationResult()

    assert result.report_intent == "unclear"
    assert result.report_subject is None
    assert result.report_focus is None
    assert result.key_points == []
    assert result.evidence_points == []
    assert result.missing_critical_fields == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_context_organizer.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing model.

- [ ] **Step 3: Write minimal contract definitions**

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class ReportContextSummary(BaseModel):
    subject_summary: str = ""
    focus_summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    evidence_points: list[dict] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    source_scope: list[str] = Field(default_factory=list)


class ReportPreparationResult(BaseModel):
    report_intent: str = "unclear"
    report_subject: str | None = None
    report_focus: str | None = None
    report_context_summary: ReportContextSummary = Field(default_factory=ReportContextSummary)
    key_points: list[str] = Field(default_factory=list)
    evidence_points: list[dict] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    source_scope: dict = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)
    confidence: str = "low"
    soft_confirm_message: str = ""
    followup_candidates: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_context_organizer.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/domain/report_preparation.py tests/chat/test_report_context_organizer.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add report preparation contracts"
```

---

### Task 2: Implement ReportContextOrganizer

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\report_context_organizer.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_context_organizer.py`

- [ ] **Step 1: Write the failing organizer behavior tests**

```python
from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer


def test_organizer_creates_subject_focus_and_summary_from_generation_context():
    context = GenerationContext(
        conversation_id="conv-1",
        resource_type="report",
        summary_text="当前围绕关羽北伐失败原因展开分析，重点涉及军资供应与内部失和。",
        current_topics=["关羽北伐失败原因"],
        user_goals=["生成报告"],
        confirmed_facts=["军资问题与内部失和相互影响"],
        constraints={"audience": "教研组"},
        teaching_issues=["军资供应如何引发内部失和"],
        student_signals=[],
        evidence_points=[{"type": "observation", "content": "军资短缺导致军心波动"}],
        recent_relevant_messages=[{"role": "user", "content": "请基于前面的分析生成一份报告"}],
        source_scope={"from_summary": True, "from_memory": True},
    )

    result = ReportContextOrganizer().organize(context=context, request_question="请基于当前内容生成一份报告")

    assert result.report_intent == "generate_report"
    assert result.report_subject == "关羽北伐失败原因"
    assert result.report_focus == "军资供应如何引发内部失和"
    assert result.key_points
    assert result.report_context_summary.subject_summary
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_context_organizer.py -q
```

Expected: FAIL with missing organizer or incorrect fields.

- [ ] **Step 3: Write minimal organizer implementation**

```python
from __future__ import annotations

from app.chat.domain.report_preparation import ReportContextSummary, ReportPreparationResult


class ReportContextOrganizer:
    def organize(self, *, context, request_question: str) -> ReportPreparationResult:
        report_intent = "generate_report" if "报告" in str(request_question or "") or "生成报告" in "".join(context.user_goals) else "unclear"
        report_subject = next((item for item in context.current_topics if str(item or "").strip()), None)
        report_focus = next((item for item in context.teaching_issues if str(item or "").strip()), None)
        if not report_focus and report_subject:
            report_focus = f"综合分析{report_subject}下的主要问题与结论"
        key_points = list(context.confirmed_facts[:3]) or [str(item.get('content') or '').strip() for item in context.evidence_points[:3] if str(item.get('content') or '').strip()]
        evidence_points = list(context.evidence_points[:3])
        summary = ReportContextSummary(
            subject_summary=context.summary_text or str(report_subject or ""),
            focus_summary=str(report_focus or ""),
            key_points=key_points,
            evidence_points=evidence_points,
            constraints=dict(context.constraints or {}),
            source_scope=[name for name, enabled in dict(context.source_scope or {}).items() if enabled],
        )
        missing = []
        if report_intent != "generate_report":
            missing.append("report_intent")
        if not report_subject:
            missing.append("report_subject")
        return ReportPreparationResult(
            report_intent=report_intent,
            report_subject=report_subject,
            report_focus=report_focus,
            report_context_summary=summary,
            key_points=key_points,
            evidence_points=evidence_points,
            constraints=dict(context.constraints or {}),
            source_scope={
                "from_conversation": bool(context.source_scope.get("from_recent_messages") or context.source_scope.get("from_summary") or context.source_scope.get("from_memory")),
                "from_docs": bool(context.source_scope.get("from_docs")),
                "from_course": bool(context.current_course_id),
                "from_artifacts": bool(context.source_scope.get("from_artifacts")),
            },
            missing_critical_fields=missing,
            confidence="medium" if report_subject else "low",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_context_organizer.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/orchestrator/report_context_organizer.py tests/chat/test_report_context_organizer.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add report context organizer"
```

---

### Task 3: Implement GenerationReadinessJudge

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\generation_readiness_judge.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_readiness_judge.py`

- [ ] **Step 1: Write the failing judge tests**

```python
from app.chat.domain.report_preparation import ReportPreparationResult
from app.chat.orchestrator.generation_readiness_judge import GenerationReadinessJudge


def test_judge_returns_strong_soft_confirm_when_subject_and_focus_exist():
    result = ReportPreparationResult(
        report_intent="generate_report",
        report_subject="关羽北伐失败原因",
        report_focus="军资供应如何引发内部失和",
        key_points=["军资短缺导致内部失和", "军心受挫"],
    )

    decision = GenerationReadinessJudge().judge(result, entry_mode="reply")

    assert decision["action"] == "strong_soft_confirm"


def test_judge_returns_ask_critical_gap_when_subject_missing():
    result = ReportPreparationResult(report_intent="generate_report")

    decision = GenerationReadinessJudge().judge(result, entry_mode="reply")

    assert decision["action"] == "ask_critical_gap"
    assert decision["missing_critical_fields"] == ["report_subject"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_readiness_judge.py -q
```

Expected: FAIL

- [ ] **Step 3: Write minimal readiness judge**

```python
from __future__ import annotations


class GenerationReadinessJudge:
    def judge(self, result, *, entry_mode: str) -> dict:
        if "report_intent" in result.missing_critical_fields or result.report_intent != "generate_report":
            return {"action": "ask_critical_gap", "missing_critical_fields": ["report_intent"]}
        if "report_subject" in result.missing_critical_fields or not result.report_subject:
            return {"action": "ask_critical_gap", "missing_critical_fields": ["report_subject"]}

        has_focus = bool(result.report_focus)
        has_points = len(result.key_points) >= 2
        has_evidence = len(result.evidence_points) >= 2
        has_summary = bool(result.report_context_summary.subject_summary)

        if has_focus or has_points or has_evidence or has_summary:
            if entry_mode == "button":
                return {"action": "weak_soft_confirm"}
            return {"action": "strong_soft_confirm"}

        return {"action": "ask_critical_gap", "missing_critical_fields": ["report_focus"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_readiness_judge.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/orchestrator/generation_readiness_judge.py tests/chat/test_generation_readiness_judge.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add report readiness judge"
```

---

### Task 4: Integrate Organizer and Judge into ReportWorkflowRuntime

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\report\runtime.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_runtime_preparation_flow.py`

- [ ] **Step 1: Write the failing runtime orchestration tests**

```python
from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.report_preparation import ReportPreparationResult
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


def test_runtime_returns_soft_confirm_without_calling_engine_when_context_is_ready():
    called = {"engine": False}

    class DummyEngine:
        def invoke(self, state):
            called["engine"] = True
            return {"reply": "should-not-run", "status": "running"}

    class DummyOrganizer:
        def organize(self, *, context, request_question):
            return ReportPreparationResult(
                report_intent="generate_report",
                report_subject="关羽北伐失败原因",
                report_focus="军资供应如何引发内部失和",
                key_points=["a", "b"],
                soft_confirm_message="我将基于关羽北伐失败原因生成报告，可以开始吗？",
            )

    class DummyJudge:
        def judge(self, result, *, entry_mode):
            return {"action": "strong_soft_confirm"}

    runtime = ReportWorkflowRuntime(
        engine=DummyEngine(),
        report_context_organizer=DummyOrganizer(),
        generation_readiness_judge=DummyJudge(),
    )

    result = runtime.run(
        request=ChatRequestV2(question="请基于当前内容生成一份报告", conversation_id="conv-1"),
        snapshot=ConversationSnapshot(conversation_id="conv-1"),
        decision=None,
    )

    assert called["engine"] is False
    assert result["workflow"]["status"] == "awaiting_confirm"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_runtime_preparation_flow.py -q
```

Expected: FAIL

- [ ] **Step 3: Modify runtime to branch before engine invocation**

```python
self.report_context_organizer = report_context_organizer or ReportContextOrganizer()
self.generation_readiness_judge = generation_readiness_judge or GenerationReadinessJudge()

preparation_result = self.report_context_organizer.organize(
    context=generation_context,
    request_question=request.question,
)
readiness = self.generation_readiness_judge.judge(
    preparation_result,
    entry_mode="button" if getattr(request, "action_hint", "") == "generate.report" else "reply",
)

if readiness["action"] == "strong_soft_confirm":
    return {
        "message": {"role": "assistant", "content": preparation_result.soft_confirm_message or "..."},
        "conversation": {"conversation_id": request.conversation_id or ""},
        "action": {"name": "generate.report"},
        "artifacts": [],
        "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
        "sources": [],
        "trace": {"path": "workflow", "workflow_name": "report", "readiness_action": "strong_soft_confirm"},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_runtime_preparation_flow.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/workflows/report/runtime.py tests/chat/test_report_runtime_preparation_flow.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add report preparation entry flow"
```

---

### Task 5: Lower Legacy Engine Gate and Keep Compatibility

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\agents\universal_report_engine.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\report\assembler.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_universal_report_engine_context_slots.py`

- [ ] **Step 1: Write the failing compatibility test**

```python
from app.chat.agents.universal_report_engine import evaluator_node


def test_evaluator_skips_focus_assessor_when_runtime_marks_generation_ready():
    decision = evaluator_node(
        {
            "phase": "evaluating",
            "report_slots": {"core_topic": "Skills 与 MCP 的差异"},
            "generation_ready": True,
            "soft_confirmed": True,
            "outline_confirmed": False,
            "user_input": "生成报告",
            "human_feedback": "",
        }
    )

    assert decision["phase"] == "outlining"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_universal_report_engine_context_slots.py -q
```

Expected: FAIL

- [ ] **Step 3: Implement compatibility bridge**

```python
if state.get("generation_ready"):
    if not state.get("outline_confirmed"):
        return {"phase": "outlining"}
    return {"phase": "generating"}
```

Also add assembler mapping so `ReportPreparationResult` can still produce legacy `core_topic/focus_area` hints when the existing engine needs them.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_universal_report_engine_context_slots.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/agents/universal_report_engine.py app/chat/workflows/report/assembler.py tests/chat/test_universal_report_engine_context_slots.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: relax legacy report gate for prepared context"
```

---

### Task 6: Verification and Regression

**Files:**
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_context_organizer.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_readiness_judge.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_runtime_preparation_flow.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_universal_report_engine_context_slots.py`

- [ ] **Step 1: Run focused report entry suite**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_context_organizer.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_readiness_judge.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_runtime_preparation_flow.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_universal_report_engine_context_slots.py -q
```

Expected: all PASS

- [ ] **Step 2: Run full chat regression**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat -q
```

Expected: all PASS

- [ ] **Step 3: Commit final integration**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/domain/report_preparation.py app/chat/orchestrator/report_context_organizer.py app/chat/orchestrator/generation_readiness_judge.py app/chat/workflows/report/runtime.py app/chat/workflows/report/assembler.py app/chat/agents/universal_report_engine.py tests/chat/test_report_context_organizer.py tests/chat/test_generation_readiness_judge.py tests/chat/test_report_runtime_preparation_flow.py tests/chat/test_universal_report_engine_context_slots.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: redesign report workflow around prepared context"
```

---

## Self-Review

### Spec coverage

- 新的入口链路：Task 2, 3, 4
- `ReportContextOrganizer` 契约：Task 1, 2
- “可生成”判定规则：Task 3
- 强弱软确认与关键缺口追问：Task 4
- 降级旧 `focus_assessor` 门禁：Task 5
- 全链路验证：Task 6

### Placeholder scan

- No `TODO`, `TBD`, or “implement later”
- Every code-changing task includes concrete code
- Every verification step includes a runnable command

### Type consistency

- Main runtime data type is `ReportPreparationResult`
- Organizer returns `ReportPreparationResult`
- Judge consumes `ReportPreparationResult`
- Runtime branches on `readiness["action"]`

