# Lesson Plan Workflow Context-Driven Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a chat v2 `lesson_plan` workflow that reuses the report-style context-driven entry flow, generates a teacher-friendly lesson-plan outline first, waits for user confirmation or edits, then produces a structured standard-prep lesson plan artifact.

**Architecture:** Keep `ConversationSnapshot -> GenerationContext` as the upstream contract, add `LessonPlanPreparationResult` plus `LessonPlanContextOrganizer` and `LessonPlanReadinessJudge`, then let `LessonPlanWorkflowRuntime` manage `soft_confirm -> outlining -> awaiting_outline_confirm -> generating -> completed`. Reuse the existing route/orchestrator framework and persist both conversation workflow state and final course material.

**Tech Stack:** Python, Pydantic, existing chat workflow runtime, existing conversation state persistence, pytest

---

## File Structure

### New files

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\lesson_plan_preparation.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\lesson_plan_context_organizer.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\lesson_plan_readiness_judge.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\lesson_plan\__init__.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\lesson_plan\assembler.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\lesson_plan\runtime.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_context_organizer.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_readiness_judge.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_workflow_runtime.py`

### Existing files to modify

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\slot_definitions.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\route_rules.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\route_chat_service.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_rules.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py`

---

### Task 1: Define Contracts and Slot Schema

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\lesson_plan_preparation.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\slot_definitions.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_context_organizer.py`

- [ ] **Step 1: Write the failing contract test**

```python
from app.chat.domain.lesson_plan_preparation import LessonPlanPreparationResult
from app.chat.slot_definitions import LessonPlanSlots

def test_lesson_plan_preparation_result_defaults_are_stable():
    result = LessonPlanPreparationResult()
    assert result.lesson_plan_intent == "unclear"
    assert result.topic is None
    assert result.knowledge_points == []

def test_lesson_plan_slots_expose_expanded_teacher_fields():
    slots = LessonPlanSlots()
    assert hasattr(slots, "lesson_type")
    assert hasattr(slots, "class_profile")
    assert hasattr(slots, "resource_constraints")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_context_organizer.py -q`

Expected: FAIL with missing model or slot fields.

- [ ] **Step 3: Write minimal contracts and slot schema**

```python
class LessonPlanContextSummary(BaseModel):
    topic_summary: str = ""
    learner_summary: str = ""
    objective_summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    hard_points: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    source_scope: list[str] = Field(default_factory=list)

class LessonPlanPreparationResult(BaseModel):
    lesson_plan_intent: str = "unclear"
    topic: str | None = None
    audience: str | None = None
    objective: str | None = None
    duration: str | None = None
    lesson_type: str | None = None
    lesson_plan_context_summary: LessonPlanContextSummary = Field(default_factory=LessonPlanContextSummary)
    knowledge_points: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    hard_points: list[str] = Field(default_factory=list)
    teaching_methods: list[str] = Field(default_factory=list)
    class_profile: list[str] = Field(default_factory=list)
    resource_constraints: list[str] = Field(default_factory=list)
    style_constraints: list[str] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)
    confidence: str = "low"
    soft_confirm_message: str = ""
```

```python
class LessonPlanSlots(BaseSlots):
    duration: str = ""
    lesson_type: str = ""
    knowledge_points: list[str] = Field(default_factory=list)
    key_points: str = ""
    hard_points: str = ""
    teaching_methods: list[str] = Field(default_factory=list)
    class_profile: str = ""
    assessment_method: str = ""
    homework_preference: str = ""
    resource_constraints: list[str] = Field(default_factory=list)
    style_constraints: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_context_organizer.py -q`

Expected: PASS

---

### Task 2: Implement Assembler, Organizer, and Readiness Judge

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\lesson_plan\assembler.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\lesson_plan_context_organizer.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\lesson_plan_readiness_judge.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_context_organizer.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_readiness_judge.py`

- [ ] **Step 1: Write the failing organizer and judge tests**

```python
from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.lesson_plan_context_organizer import LessonPlanContextOrganizer
from app.chat.orchestrator.lesson_plan_readiness_judge import LessonPlanReadinessJudge
from app.chat.workflows.lesson_plan.assembler import LessonPlanAssembler

def test_lesson_plan_assembler_builds_teacher_facing_slot_hints():
    context = GenerationContext(
        conversation_id="conv-lesson-1",
        resource_type="lesson_plan",
        summary_text="当前围绕二次函数第一课时展开，面向高一，课时45分钟。",
        current_topics=["二次函数第一课时"],
        user_goals=["整理教案"],
        confirmed_facts=["面向高一学生", "重点是图像与性质"],
        constraints={"audience": "高一", "length": "45分钟"},
        teaching_issues=["学生对图像与解析式联系不稳"],
        student_signals=["基础概念会混淆"],
        evidence_points=[],
        recent_relevant_messages=[{"role": "user", "content": "帮我整理一节高一二次函数教案"}],
        source_scope={"from_summary": True, "from_memory": True},
    )
    gathered = LessonPlanAssembler().from_generation_context(context)
    assert gathered["slot_hints"]["topic"] == "二次函数第一课时"
    assert gathered["slot_hints"]["audience"] == "高一"
    assert gathered["slot_hints"]["duration"] == "45分钟"

def test_judge_requires_topic_as_critical_gap():
    result = LessonPlanPreparationResult(lesson_plan_intent="generate_lesson_plan")
    decision = LessonPlanReadinessJudge().judge(result, entry_mode="reply")
    assert decision["action"] == "ask_critical_gap"
    assert decision["missing_critical_fields"] == ["topic"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_context_organizer.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_readiness_judge.py -q`

Expected: FAIL with missing modules or wrong derived fields.

- [ ] **Step 3: Write minimal assembler, organizer, and judge**

```python
class LessonPlanAssembler:
    def from_generation_context(self, context):
        constraints = dict(context.constraints or {})
        return {
            "summary": context.summary_text,
            "current_topics": list(context.current_topics),
            "user_goals": list(context.user_goals),
            "confirmed_facts": list(context.confirmed_facts),
            "constraints": constraints,
            "teaching_issues": list(context.teaching_issues),
            "student_signals": list(context.student_signals),
            "slot_hints": {
                "topic": next((item for item in context.current_topics if str(item or "").strip()), ""),
                "audience": str(constraints.get("audience") or "").strip(),
                "duration": str(constraints.get("length") or "").strip(),
            },
        }
```

```python
class LessonPlanContextOrganizer:
    def organize(self, *, context, request_question: str):
        constraints = dict(context.constraints or {})
        topic = next((item for item in context.current_topics if str(item or "").strip()), None)
        audience = str(constraints.get("audience") or "").strip() or None
        duration = str(constraints.get("length") or "").strip() or None
        key_points = [str(item or "").strip() for item in list(context.confirmed_facts or []) if str(item or "").strip()][:3]
        hard_points = [str(item or "").strip() for item in list(context.teaching_issues or []) if str(item or "").strip()][:2]
        class_profile = [str(item or "").strip() for item in list(context.student_signals or []) if str(item or "").strip()][:3]
        return LessonPlanPreparationResult(
            lesson_plan_intent="generate_lesson_plan" if "教案" in str(request_question or "") or any("教案" in str(goal or "") for goal in list(context.user_goals or [])) else "unclear",
            topic=str(topic or "").strip() or None,
            audience=audience,
            duration=duration,
            lesson_type="新授课",
            knowledge_points=key_points,
            key_points=key_points,
            hard_points=hard_points,
            class_profile=class_profile,
            soft_confirm_message=f"我将基于“{topic}”先整理一版标准备课型教案大纲，请先确认方向是否合适。",
        )

class LessonPlanReadinessJudge:
    def judge(self, result, *, entry_mode: str) -> dict:
        if not str(result.topic or "").strip():
            return {"action": "ask_critical_gap", "missing_critical_fields": ["topic"]}
        has_outline_basis = any([
            bool(str(result.objective or "").strip()),
            bool(str(result.audience or "").strip() and str(result.duration or "").strip()),
            len(list(result.knowledge_points or [])) >= 2,
            bool(list(result.key_points or []) or list(result.hard_points or [])),
            bool(str(result.lesson_plan_context_summary.topic_summary or "").strip()),
        ])
        if has_outline_basis:
            action = "weak_soft_confirm" if str(entry_mode or "").strip().lower() == "button" else "strong_soft_confirm"
            return {"action": action, "missing_critical_fields": []}
        return {"action": "ask_critical_gap", "missing_critical_fields": ["objective_or_outline_basis"]}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_context_organizer.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_readiness_judge.py -q`

Expected: PASS

---

### Task 3: Implement LessonPlanWorkflowRuntime and Route Wiring

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\lesson_plan\__init__.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\lesson_plan\runtime.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\route_chat_service.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\route_rules.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_workflow_runtime.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_rules.py`

- [ ] **Step 1: Write the failing runtime and resume-routing tests**

```python
from types import SimpleNamespace

from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.route_rules import decide_route
from app.chat.workflows.lesson_plan.runtime import LessonPlanWorkflowRuntime

def test_runtime_wraps_outline_result_as_workflow_artifact():
    class DummyEngine:
        def invoke(self, state):
            return {
                "final_response": "请确认这版教案大纲是否合适。",
                "status": "awaiting_human",
                "phase": "outlining",
                "lesson_plan_outline": {"basic_info": {"topic": "二次函数第一课时"}},
            }

    snapshot = ConversationSnapshot(
        conversation_id="conv-lesson-runtime",
        recent_messages=[{"role": "user", "content": "帮我生成教案"}],
        summary="当前围绕高一二次函数第一课时展开。",
        conversation_memory={"current_topics": ["二次函数第一课时"], "user_goals": ["整理教案"], "constraints": {"audience": "高一", "length": "45分钟"}},
        active_context={},
        referenced_artifact_ids=[],
    )
    result = LessonPlanWorkflowRuntime(engine=DummyEngine()).run(request=ChatRequestV2(question="生成教案", action_hint="generate.lesson_plan"), snapshot=snapshot, decision=None)
    assert result["workflow"]["type"] == "lesson_plan"
    assert result["artifacts"][0]["artifact_type"] == "lesson_plan_outline"

def test_lesson_plan_followup_from_active_context_uses_workflow():
    snapshot = SimpleNamespace(
        active_artifact=None,
        active_context={"active_workflow_type": "lesson_plan", "active_workflow_status": "awaiting_confirm", "active_artifact_type": "lesson_plan_outline"},
        conversation_memory={"user_goals": ["整理教案"], "derived_workflow_goal": "整理教案"},
    )
    decision = decide_route(request=ChatRequestV2(question="确认并继续"), snapshot=snapshot, workflow_state=None)
    assert decision.path == "workflow"
    assert decision.workflow_name == "lesson_plan"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_workflow_runtime.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_rules.py -q`

Expected: FAIL because runtime and lesson-plan resume logic are not implemented.

- [ ] **Step 3: Implement runtime, workflow registration, and follow-up detection**

```python
class LessonPlanWorkflowRuntime:
    def __init__(self, *, engine=None, generation_context_builder=None, lesson_plan_assembler=None, lesson_plan_context_organizer=None, lesson_plan_readiness_judge=None):
        self.engine = engine
        self.generation_context_builder = generation_context_builder or GenerationContextBuilder()
        self.lesson_plan_assembler = lesson_plan_assembler or LessonPlanAssembler()
        self.lesson_plan_context_organizer = lesson_plan_context_organizer or LessonPlanContextOrganizer()
        self.lesson_plan_readiness_judge = lesson_plan_readiness_judge or LessonPlanReadinessJudge()

    def run(self, *, request, snapshot, decision):
        context = self.generation_context_builder.build(snapshot=snapshot, request=request, resource_type="lesson_plan")
        gathered = self.lesson_plan_assembler.from_generation_context(context)
        preparation = self.lesson_plan_context_organizer.organize(context=context, request_question=request.question)
        readiness = self.lesson_plan_readiness_judge.judge(preparation, entry_mode="button" if request.action_hint == "generate.lesson_plan" else "reply")
        raw = self.engine.invoke({"gathered_context": gathered, "lesson_plan_preparation_result": preparation.model_dump(), "readiness_decision": readiness, "user_input": request.question})
        return {
            "message": {"content": raw.get("final_response") or raw.get("reply") or ""},
            "action": {"name": "generate.lesson_plan"},
            "workflow": {"type": "lesson_plan", "status": "awaiting_confirm" if raw.get("status") == "awaiting_human" else raw.get("status") or "running", "phase": raw.get("phase") or "outlining"},
            "artifacts": [{"artifact_id": "lesson-plan-outline-1", "artifact_type": "lesson_plan_outline", "title": "教案大纲.md", "content": raw.get("lesson_plan_outline")}],
            "trace": {"lesson_plan_preparation_result": preparation.model_dump(), "readiness_decision": readiness},
            "sources": [],
        }
```

```python
_LESSON_PLAN_CONTINUE_MARKERS = {"继续", "开始", "确认", "确认并继续", "按这个大纲生成", "开始生成教案"}

def _is_lesson_plan_followup(question: str, snapshot) -> bool:
    normalized = _normalized_text(question)
    active_context = _snapshot_active_context(snapshot)
    memory = _snapshot_memory(snapshot)
    return normalized in _LESSON_PLAN_CONTINUE_MARKERS and (
        str(active_context.get("active_workflow_type") or "").strip() == "lesson_plan"
        or any("教案" in str(item or "") for item in list(memory.get("user_goals") or []) + [memory.get("derived_workflow_goal")])
    )
```

```python
workflow_registry["lesson_plan"] = LessonPlanWorkflowRuntime(engine=self.report_engine)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_workflow_runtime.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_rules.py -q`

Expected: PASS

---

### Task 4: Persist Final Lesson Plan Artifacts and Run Regression Suite

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\route_chat_service.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py`

- [ ] **Step 1: Write the failing persistence test**

```python
def test_route_chat_service_persists_completed_lesson_plan_course_material():
    saved = []

    class StorageManagerStub:
        def save_generated_material(self, *, course_id, material_type, material_id, material_data, file_data=None):
            saved.append((course_id, material_type, material_id, material_data))
            return True

    service.course_storage_manager = StorageManagerStub()
    payload = SimpleNamespace(question="开始生成教案", conversation_id="conv-save-lesson", course_id="course-1", allow_rag=False, use_rag=False, allow_web=False, selected_doc_ids=[])
    result = {
        "conversation": {"conversation_id": "conv-save-lesson"},
        "message": {"content": "教案已生成"},
        "workflow": {"type": "lesson_plan", "status": "completed", "phase": "completed"},
        "artifacts": [{"artifact_id": "lesson-plan-1", "artifact_type": "lesson_plan", "title": "二次函数教案.md", "content": {"title": "二次函数第一课时"}}],
    }
    service._persist_new_result(payload, result)
    assert saved[0][1] == "lesson_plan"
    assert saved[0][3]["plan"]["title"] == "二次函数第一课时"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py -q`

Expected: FAIL because lesson-plan course material persistence is not implemented.

- [ ] **Step 3: Implement lesson-plan persistence helper and call it from `_persist_new_result`**

```python
def _persist_lesson_plan_course_material(self, *, payload, result: dict) -> None:
    course_id = str(getattr(payload, "course_id", "") or "").strip()
    workflow = dict(result.get("workflow") or {})
    if not course_id or str(workflow.get("type") or "").strip() != "lesson_plan" or str(workflow.get("status") or "").strip() != "completed":
        return
    artifact = next((item for item in list(result.get("artifacts") or []) if isinstance(item, dict) and str(item.get("artifact_type") or "").strip() == "lesson_plan"), None)
    if not artifact or not getattr(self, "course_storage_manager", None):
        return
    self.course_storage_manager.save_generated_material(
        course_id=course_id,
        material_type="lesson_plan",
        material_id=str(artifact.get("artifact_id") or "").strip(),
        material_data={"title": str(artifact.get("title") or "教案").strip(), "material_type": "lesson_plan", "plan": artifact.get("content")},
    )
```

- [ ] **Step 4: Run focused and broader verification**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_context_organizer.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_readiness_judge.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_lesson_plan_workflow_runtime.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_rules.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py `
  d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_route_chat_service.py -q
```

Expected: PASS with no lesson-plan workflow regressions.

---

## Self-Review

- Spec coverage: preparation contracts, readiness rules, outline-first runtime, resume routing, and final persistence are all mapped to tasks.
- Placeholder scan: no `TBD`, `TODO`, or “implement later” markers remain.
- Type consistency: `LessonPlanPreparationResult`, `lesson_plan`, `lesson_plan_outline`, and `lesson_plan` artifact names are used consistently.
