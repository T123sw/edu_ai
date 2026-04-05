# Report First Context Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the report workflow consume a structured report-first `GenerationContext` built from conversation summary, memory, active context, and recent relevant messages, while keeping the current report engine state machine intact.

**Architecture:** Extend the conversation snapshot so it can carry report-relevant structured state already stored in conversation persistence, then add a dedicated `GenerationContextBuilder` plus `ReportAssembler` to convert snapshot data into richer `gathered_context` for `ReportWorkflowRuntime`. Keep the current `universal_report_engine` entry contract stable by upgrading the contents of `gathered_context` rather than rewriting the engine internals in this pass.

**Tech Stack:** Python 3.12, Pydantic models, pytest, existing chat v2 backend under `app/chat`

**Execution note:** `D:\Edu_AI_1\Edu_AI\api\Edu_AI` is not currently inside a git repository in this environment, so this plan uses file-level verification and pytest-based acceptance instead of per-task commit steps.

---

## File Structure

### New files

- `app/chat/domain/generation_context.py`
  Defines typed models for report-first generation context and nested report context payloads.
- `app/chat/orchestrator/generation_context_builder.py`
  Builds a `GenerationContext` for a requested resource type from snapshot + request capability.
- `app/chat/workflows/report/assembler.py`
  Adapts `GenerationContext` into the richer `gathered_context` structure expected by the report runtime.
- `tests/chat/test_generation_context_builder.py`
  Covers report-first context assembly from snapshot state.
- `tests/chat/test_report_assembler.py`
  Covers transformation from `GenerationContext` to report gathered context.

### Modified files

- `app/chat/domain/conversation_snapshot.py`
  Extend snapshot with structured state fields needed by the builder.
- `app/chat/orchestrator/context_builder.py`
  Read summary, memory, active context, course context, and referenced artifacts from persistence-backed state.
- `app/chat/persistence/conversation_store_adapter.py`
  Persist and expose the new state fields needed by report-first context.
- `app/chat/workflows/report/runtime.py`
  Replace ad hoc `gathered_context` assembly with builder + assembler driven input.
- `app/chat/application/reply_service_v2.py`
  Wire the new builder for report transitions from `/reply`.
- `app/chat/application/report_service_v2.py`
  Wire the new builder for direct `/report`.
- `tests/chat/test_context_builder.py`
  Extend snapshot assertions for structured state.
- `tests/chat/test_new_path_persistence.py`
  Cover active context and referenced artifact persistence.
- `tests/chat/test_report_workflow_runtime_context.py`
  Assert the runtime now passes richer structured gathered context.
- `tests/chat/test_report_service_v2.py`
  Keep service-level report behavior stable while using the new builder path.

---

### Task 1: Extend Snapshot And Persistence State

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\conversation_snapshot.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\context_builder.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\persistence\conversation_store_adapter.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_context_builder.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_new_path_persistence.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_context_builder_exposes_structured_report_context_fields():
    storage.update_state(
        "conv-ctx",
        {
            "conversation_summary": {"summary_text": "课堂问题集中在参与度"},
            "conversation_memory": {
                "current_topics": ["课堂参与度"],
                "confirmed_facts": ["前10分钟学生分心明显"],
                "constraints": {"audience": "教研组", "style_notes": []},
                "teaching_issues": ["开场吸引力不足"],
                "evidence_points": [{"type": "observation", "content": "前10分钟学生分心明显"}],
                "referenced_artifact_ids": ["artifact-1"],
            },
            "active_context": {
                "current_course_id": "course-1",
                "active_artifact_id": "artifact-2",
                "active_artifact_type": "report_outline",
                "pinned_doc_ids": ["doc-1"],
            },
        },
    )

    snapshot = builder.build(ChatRequestV2(question="生成报告", conversation_id="conv-ctx", owner="teacher-a"))

    assert snapshot.summary == "课堂问题集中在参与度"
    assert snapshot.conversation_memory["current_topics"] == ["课堂参与度"]
    assert snapshot.active_context["current_course_id"] == "course-1"
    assert snapshot.referenced_artifact_ids == ["artifact-1"]


def test_new_report_path_persists_active_context_and_referenced_artifacts():
    data = service.chat(
        question="帮我整理成报告",
        conversation_id="conv-report",
        model_id=None,
        use_rag=False,
        selected_doc_ids=["doc-1"],
        owner="teacher-a",
        course_id="course-1",
        allow_web=False,
        action_hint="generate.report",
        artifact_id=None,
    )

    state = storage.get_state("conv-report")

    assert state["active_context"]["active_workflow_type"] == "report"
    assert state["active_context"]["active_artifact_type"] == "report_outline"
    assert state["active_context"]["current_course_id"] == "course-1"
    assert state["active_context"]["pinned_doc_ids"] == ["doc-1"]
    assert state["referenced_artifact_ids"] == ["conv-report:outline"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/chat/test_context_builder.py tests/chat/test_new_path_persistence.py -q
```

Expected:

- FAIL because `ConversationSnapshot` does not expose `conversation_memory` / `active_context` / `referenced_artifact_ids`
- FAIL because persistence does not yet write `active_context` / `referenced_artifact_ids`

- [ ] **Step 3: Implement the minimal snapshot and persistence changes**

```python
# app/chat/domain/conversation_snapshot.py
class ConversationSnapshot(BaseModel):
    conversation_id: str = ""
    recent_messages: list[dict] = Field(default_factory=list)
    summary: str = ""
    conversation_memory: dict = Field(default_factory=dict)
    active_context: dict = Field(default_factory=dict)
    referenced_artifact_ids: list[str] = Field(default_factory=list)
    active_task: str | None = None
    active_artifact: ArtifactRef | None = None
    workflow_state: WorkflowState | None = None
    capability: CapabilityPolicy = Field(default_factory=CapabilityPolicy)


# app/chat/orchestrator/context_builder.py
summary = str(((state.get("conversation_summary") or {}).get("summary_text")) or summary or "")
conversation_memory = dict(state.get("conversation_memory") or {})
active_context = dict(state.get("active_context") or {})
referenced_artifact_ids = list(state.get("referenced_artifact_ids") or conversation_memory.get("referenced_artifact_ids") or [])

return ConversationSnapshot(
    conversation_id=request.conversation_id or "",
    recent_messages=list(raw_snapshot.get("messages") or []),
    summary=summary,
    conversation_memory=conversation_memory,
    active_context=active_context,
    referenced_artifact_ids=referenced_artifact_ids,
    active_task=state.get("active_task"),
    active_artifact=active_artifact,
    workflow_state=workflow_state,
    capability=request.capability,
)


# app/chat/persistence/conversation_store_adapter.py
state_patch["referenced_artifact_ids"] = [artifact.get("artifact_id") for artifact in artifacts if artifact.get("artifact_id")]
state_patch["active_context"] = {
    "active_workflow_type": (workflow or {}).get("type") or "",
    "active_workflow_status": workflow_status or ((workflow or {}).get("status") or ""),
    "active_artifact_id": first.get("artifact_id") if artifacts else "",
    "active_artifact_type": first.get("artifact_type") if artifacts else "",
    "current_course_id": getattr(request, "course_id", None),
    "pinned_doc_ids": list(getattr(getattr(request, "capability", None), "selected_doc_ids", []) or []),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
pytest tests/chat/test_context_builder.py tests/chat/test_new_path_persistence.py -q
```

Expected:

- PASS for the new structured snapshot assertions
- PASS for the report persistence assertions

- [ ] **Step 5: Run a quick file-scope verification**

Run:

```powershell
pytest tests/chat/test_persistence_and_compat.py -q
```

Expected:

- PASS to confirm the new state writes do not break existing persistence behavior

### Task 2: Add Report-First GenerationContext Builder

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\generation_context.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\generation_context_builder.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_generation_context_builder_builds_report_context_from_snapshot():
    snapshot = ConversationSnapshot(
        conversation_id="conv-1",
        recent_messages=[
            {"role": "user", "content": "课堂前10分钟学生容易分心"},
            {"role": "assistant", "content": "我先整理课堂问题"},
        ],
        summary="课堂问题集中在参与度和开场控制",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "confirmed_facts": ["前10分钟学生分心明显"],
            "constraints": {"audience": "教研组", "style_notes": []},
            "teaching_issues": ["开场吸引力不足"],
            "student_signals": ["前10分钟注意力分散"],
            "evidence_points": [{"type": "observation", "content": "前10分钟学生分心明显"}],
        },
        active_context={
            "current_course_id": "course-1",
            "active_artifact_id": "artifact-2",
            "active_artifact_type": "report_outline",
            "pinned_doc_ids": ["doc-1"],
        },
        referenced_artifact_ids=["artifact-1"],
    )

    context = GenerationContextBuilder().build_for_resource(
        request=request,
        snapshot=snapshot,
        resource_type="report",
    )

    assert context.resource_type == "report"
    assert context.summary_text == "课堂问题集中在参与度和开场控制"
    assert context.confirmed_facts == ["前10分钟学生分心明显"]
    assert context.selected_doc_ids == ["doc-1"]
    assert context.current_course_id == "course-1"
    assert context.referenced_artifact_ids == ["artifact-1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/chat/test_generation_context_builder.py -q
```

Expected:

- FAIL because `generation_context.py` and `generation_context_builder.py` do not exist yet

- [ ] **Step 3: Implement the minimal builder**

```python
# app/chat/domain/generation_context.py
class GenerationContext(BaseModel):
    conversation_id: str
    resource_type: str
    summary_text: str = ""
    current_topics: list[str] = Field(default_factory=list)
    user_goals: list[str] = Field(default_factory=list)
    confirmed_facts: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    teaching_issues: list[str] = Field(default_factory=list)
    student_signals: list[str] = Field(default_factory=list)
    evidence_points: list[dict] = Field(default_factory=list)
    selected_doc_ids: list[str] = Field(default_factory=list)
    referenced_artifact_ids: list[str] = Field(default_factory=list)
    current_course_id: str | None = None
    active_artifact_id: str | None = None
    active_artifact_type: str | None = None
    recent_relevant_messages: list[dict] = Field(default_factory=list)
    source_scope: dict = Field(default_factory=dict)


# app/chat/orchestrator/generation_context_builder.py
class GenerationContextBuilder:
    def build_for_resource(self, *, request, snapshot, resource_type: str) -> GenerationContext:
        memory = dict(getattr(snapshot, "conversation_memory", {}) or {})
        active_context = dict(getattr(snapshot, "active_context", {}) or {})
        selected_doc_ids = list(active_context.get("pinned_doc_ids") or getattr(getattr(request, "capability", None), "selected_doc_ids", []) or [])
        recent_relevant_messages = list(getattr(snapshot, "recent_messages", []) or [])[-6:]
        return GenerationContext(
            conversation_id=getattr(snapshot, "conversation_id", "") or getattr(request, "conversation_id", "") or "",
            resource_type=resource_type,
            summary_text=getattr(snapshot, "summary", "") or "",
            current_topics=list(memory.get("current_topics") or []),
            user_goals=list(memory.get("user_goals") or []),
            confirmed_facts=list(memory.get("confirmed_facts") or []),
            constraints=dict(memory.get("constraints") or {}),
            teaching_issues=list(memory.get("teaching_issues") or []),
            student_signals=list(memory.get("student_signals") or []),
            evidence_points=list(memory.get("evidence_points") or []),
            selected_doc_ids=selected_doc_ids,
            referenced_artifact_ids=list(getattr(snapshot, "referenced_artifact_ids", []) or []),
            current_course_id=active_context.get("current_course_id"),
            active_artifact_id=active_context.get("active_artifact_id"),
            active_artifact_type=active_context.get("active_artifact_type"),
            recent_relevant_messages=recent_relevant_messages,
            source_scope={
                "from_summary": bool(getattr(snapshot, "summary", "")),
                "from_memory": bool(memory),
                "from_recent_messages": bool(recent_relevant_messages),
                "from_docs": bool(selected_doc_ids),
                "from_artifacts": bool(getattr(snapshot, "referenced_artifact_ids", [])),
            },
        )
```

- [ ] **Step 4: Run the new builder test**

Run:

```powershell
pytest tests/chat/test_generation_context_builder.py -q
```

Expected:

- PASS with a typed report-first `GenerationContext`

- [ ] **Step 5: Run adjacent regression tests**

Run:

```powershell
pytest tests/chat/test_context_builder.py tests/chat/test_report_service_v2.py -q
```

Expected:

- PASS, proving the new builder layer does not disturb snapshot/service behavior

### Task 3: Add ReportAssembler And Upgrade Runtime Gathered Context

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\report\assembler.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\report\runtime.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_assembler.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_report_assembler_builds_rich_gathered_context():
    context = GenerationContext(
        conversation_id="conv-1",
        resource_type="report",
        summary_text="课堂问题集中在参与度和开场控制",
        current_topics=["课堂参与度"],
        user_goals=["生成报告"],
        confirmed_facts=["前10分钟学生分心明显"],
        constraints={"audience": "教研组", "style_notes": []},
        teaching_issues=["开场吸引力不足"],
        student_signals=["前10分钟注意力分散"],
        evidence_points=[{"type": "observation", "content": "前10分钟学生分心明显"}],
        selected_doc_ids=["doc-1"],
        referenced_artifact_ids=["artifact-1"],
        current_course_id="course-1",
        active_artifact_id="artifact-2",
        active_artifact_type="report_outline",
        recent_relevant_messages=[{"role": "user", "content": "课堂前10分钟学生容易分心"}],
        source_scope={"from_summary": True, "from_memory": True, "from_recent_messages": True, "from_docs": True, "from_artifacts": True},
    )

    gathered = ReportAssembler().from_generation_context(context)

    assert gathered["summary"] == "课堂问题集中在参与度和开场控制"
    assert gathered["confirmed_facts"] == ["前10分钟学生分心明显"]
    assert gathered["constraints"]["audience"] == "教研组"
    assert gathered["current_course_id"] == "course-1"
    assert gathered["active_artifact"]["artifact_id"] == "artifact-2"


def test_report_runtime_passes_rich_gathered_context_to_engine():
    assert seen["gathered_context"]["confirmed_facts"] == ["前10分钟学生分心明显"]
    assert seen["gathered_context"]["teaching_issues"] == ["开场吸引力不足"]
    assert seen["gathered_context"]["source_scope"]["from_memory"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/chat/test_report_assembler.py tests/chat/test_report_workflow_runtime_context.py -q
```

Expected:

- FAIL because `ReportAssembler` does not exist
- FAIL because runtime still only passes summary/recent_messages/active_task/active_artifact

- [ ] **Step 3: Implement the assembler and runtime wiring**

```python
# app/chat/workflows/report/assembler.py
class ReportAssembler:
    def from_generation_context(self, context: GenerationContext) -> dict:
        return {
            "summary": context.summary_text,
            "current_topics": list(context.current_topics),
            "user_goals": list(context.user_goals),
            "confirmed_facts": list(context.confirmed_facts),
            "constraints": dict(context.constraints),
            "teaching_issues": list(context.teaching_issues),
            "student_signals": list(context.student_signals),
            "evidence_points": list(context.evidence_points),
            "recent_messages": list(context.recent_relevant_messages),
            "active_artifact": {
                "artifact_id": context.active_artifact_id,
                "artifact_type": context.active_artifact_type,
            } if context.active_artifact_id else None,
            "current_course_id": context.current_course_id,
            "referenced_artifact_ids": list(context.referenced_artifact_ids),
            "source_scope": dict(context.source_scope),
        }


# app/chat/workflows/report/runtime.py
generation_context = self.generation_context_builder.build_for_resource(
    request=request,
    snapshot=snapshot,
    resource_type="report",
)
gathered_context = self.report_assembler.from_generation_context(generation_context)
state = {
    "user_input": request.question,
    "report_state": getattr(snapshot, "workflow_state", None) if snapshot is not None else None,
    "conversation_id": request.conversation_id or "",
    "owner": getattr(request, "owner", None),
    "allow_rag": bool(getattr(capability, "allow_rag", False)),
    "allow_web": bool(getattr(capability, "allow_web", False)),
    "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
    "gathered_context": gathered_context,
}
```

- [ ] **Step 4: Run the focused report tests**

Run:

```powershell
pytest tests/chat/test_report_assembler.py tests/chat/test_report_workflow_runtime_context.py tests/chat/test_report_workflow_runtime.py tests/chat/test_report_workflow_runtime_status.py -q
```

Expected:

- PASS with richer gathered context while keeping report status normalization and artifact behavior intact

- [ ] **Step 5: Run report service regression tests**

Run:

```powershell
pytest tests/chat/test_report_service_v2.py tests/chat/test_reply_service_v2.py -q
```

Expected:

- PASS, confirming both direct `/report` and report transitions from `/reply` still work

### Task 4: Wire The New Builder Path Into Services And Run End-To-End Verification

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\report_service_v2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\reply_service_v2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_report_service_v2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_reply_service_v2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_new_path_persistence.py`

- [ ] **Step 1: Write or extend failing service-level tests**

```python
def test_build_default_report_service_v2_uses_generation_context_builder(monkeypatch):
    seen = {}

    class DummyGenerationContextBuilder:
        def build_for_resource(self, *, request, snapshot, resource_type):
            seen["resource_type"] = resource_type
            return fake_context

    monkeypatch.setattr(
        "app.chat.application.report_service_v2.GenerationContextBuilder",
        lambda: DummyGenerationContextBuilder(),
    )

    service = build_default_report_service_v2()
    service.report(payload)

    assert seen["resource_type"] == "report"
```

- [ ] **Step 2: Run service-level tests to verify they fail**

Run:

```powershell
pytest tests/chat/test_report_service_v2.py tests/chat/test_reply_service_v2.py -q
```

Expected:

- FAIL because the default services do not yet construct runtimes with the new builder dependency

- [ ] **Step 3: Wire the default services**

```python
# app/chat/application/report_service_v2.py
runtime = ReportWorkflowRuntime(
    engine_resolver=...,
    generation_context_builder=GenerationContextBuilder(),
    report_assembler=ReportAssembler(),
)


# app/chat/application/reply_service_v2.py
workflow_registry={
    "report": ReportWorkflowRuntime(
        engine_resolver=...,
        generation_context_builder=GenerationContextBuilder(),
        report_assembler=ReportAssembler(),
    )
}
```

- [ ] **Step 4: Run the end-to-end focused suite**

Run:

```powershell
pytest tests/chat/test_context_builder.py tests/chat/test_generation_context_builder.py tests/chat/test_report_assembler.py tests/chat/test_report_workflow_runtime_context.py tests/chat/test_report_service_v2.py tests/chat/test_reply_service_v2.py tests/chat/test_new_path_persistence.py -q
```

Expected:

- PASS, proving the report-first context path is wired end to end

- [ ] **Step 5: Run a broader chat v2 regression sweep**

Run:

```powershell
pytest tests/chat/test_report_workflow_runtime.py tests/chat/test_report_workflow_runtime_status.py tests/chat/test_route_chat_service.py tests/chat/test_route_rules.py -q
```

Expected:

- PASS, showing the new report-first context integration did not break routing or workflow envelope behavior
