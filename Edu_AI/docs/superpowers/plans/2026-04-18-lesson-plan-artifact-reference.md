# Lesson Plan Artifact Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add artifact-reference ask and precise edit support for both `lesson_plan` and `lesson_plan_outline`.

**Architecture:** Reuse the existing artifact-reference routing model from reports and PPTs. Add lesson-plan-specific context loading, structure parsing, intent parsing, and a dedicated edit runtime so only the matched field or step is rewritten while the rest of the structured artifact stays unchanged.

**Tech Stack:** Python, pytest, existing `ReplyServiceV2` artifact-reference flow, course storage generated-material persistence, structured lesson-plan JSON payloads.

---

## File Map

### Modify

- `api/Edu_AI/app/chat/application/artifact_context_loader.py`
  - Load and summarize `lesson_plan` and `lesson_plan_outline` into ask-flow context blocks.
- `api/Edu_AI/app/chat/application/artifact_reference_intent.py`
  - Extend top-level routing to recognize lesson-plan field and step anchors.
- `api/Edu_AI/app/chat/application/reply_service_v2.py`
  - Route lesson-plan artifact asks through context injection and lesson-plan edits through a dedicated runtime in both sync and stream paths.

### Create

- `api/Edu_AI/app/chat/orchestrator/lesson_plan_structure_parser.py`
  - Normalize `lesson_plan` and `lesson_plan_outline` artifacts into addressable structure nodes.
- `api/Edu_AI/app/chat/orchestrator/lesson_plan_edit_intent_parser.py`
  - Parse lesson-plan edit requests into `exact / candidate / unclear` target confidence.
- `api/Edu_AI/app/chat/workflows/lesson_plan/edit_runtime.py`
  - Load the referenced lesson-plan artifact, branch on parsed edit intent, rewrite only one target block, and return revised artifacts.

### Tests

- `api/Edu_AI/tests/chat/test_artifact_reference_intent.py`
  - Extend to cover lesson-plan top-level `ask / edit / unclear`.
- `api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py`
  - Add lesson-plan ask/edit routing tests for sync reply flow.
- `api/Edu_AI/tests/chat/test_reply_service_v2_stream.py`
  - Add lesson-plan ask/edit routing tests for stream reply flow.
- `api/Edu_AI/tests/chat/test_lesson_plan_structure_parser.py`
  - Add parser coverage for `lesson_plan` and `lesson_plan_outline`.
- `api/Edu_AI/tests/chat/test_lesson_plan_edit_intent_parser.py`
  - Add exact, candidate, unclear, and ask-like parsing coverage.
- `api/Edu_AI/tests/chat/test_lesson_plan_edit_runtime.py`
  - Add exact edit, candidate confirmation, unclear clarification, and ask fallback tests.

## Task 1: Add Lesson-Plan Ask Context

**Files:**
- Modify: `api/Edu_AI/app/chat/application/artifact_context_loader.py`
- Test: `api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py`
- Test: `api/Edu_AI/tests/chat/test_reply_service_v2_stream.py`

- [ ] **Step 1: Write the failing sync ask-path test**

```python
def test_reply_service_loads_lesson_plan_artifact_context_for_ask_path():
    captured = {}

    class DummyOrchestrator:
        def dispatch(self, request):
            captured["artifact_context"] = getattr(request, "artifact_context", None)
            return {
                "message": {"role": "assistant", "content": "lesson plan answer"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    course_storage = SimpleNamespace(
        get_generated_material=lambda course_id, material_type, material_id: {
            "material_id": material_id,
            "title": "分数的意义教案.json",
            "plan": {
                "title": "分数的意义",
                "objectives": ["理解分数的意义"],
                "process": [{"step": "导入", "goal": "联系生活经验"}],
            },
        }
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py::test_reply_service_loads_lesson_plan_artifact_context_for_ask_path -v`
Expected: FAIL because `artifact_context_loader.py` returns `None` for `lesson_plan`.

- [ ] **Step 3: Write the failing stream ask-path test**

```python
def test_reply_service_stream_loads_lesson_plan_artifact_context_for_ask_path():
    captured = {}

    class ArtifactStreamOrchestrator:
        def dispatch_stream(self, request):
            captured["artifact_context"] = getattr(request, "artifact_context", None)
            yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id, "sources": []}}
            yield {
                "type": "result",
                "payload": {
                    "message": {"role": "assistant", "content": "lesson plan answer"},
                    "conversation": {"conversation_id": request.conversation_id},
                    "action": {"name": "chat.reply"},
                    "workflow": None,
                    "artifacts": [],
                    "sources": [],
                    "trace": {"path": "fast"},
                },
            }
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest api/Edu_AI/tests/chat/test_reply_service_v2_stream.py::test_reply_service_stream_loads_lesson_plan_artifact_context_for_ask_path -v`
Expected: FAIL because `artifact_context` is missing.

- [ ] **Step 5: Implement minimal lesson-plan context loading**

```python
def _build_lesson_plan_context(*, artifact_type: str, source_artifact: dict[str, Any], title: str) -> str:
    if artifact_type == "lesson_plan":
        plan = dict(source_artifact.get("plan") or source_artifact.get("content") or {})
        process = list(plan.get("process") or [])
        lines = [
            f"标题：{plan.get('title') or title}",
            *[f"目标：{item}" for item in list(plan.get("objectives") or []) if str(item or "").strip()],
            *[
                f"环节 {index}：{step.get('step')} - {step.get('goal')}"
                for index, step in enumerate(process, start=1)
                if isinstance(step, dict)
            ],
        ]
        return "\n".join(line for line in lines if str(line or "").strip()).strip()

    outline = dict(source_artifact.get("outline") or source_artifact.get("content") or {})
    lesson_flow = list(outline.get("lesson_flow") or [])
    lines = [
        f"主题：{((outline.get('basic_info') or {}).get('topic') or title)}",
        *[
            f"环节 {index}：{item.get('step')} - {item.get('goal')}"
            for index, item in enumerate(lesson_flow, start=1)
            if isinstance(item, dict)
        ],
    ]
    return "\n".join(line for line in lines if str(line or "").strip()).strip()
```

- [ ] **Step 6: Wire lesson-plan material lookup in `_load_source_artifact`**

```python
if course_storage_manager is not None and hasattr(course_storage_manager, "get_generated_material") and course_id and artifact_id:
    if artifact_type.startswith("ppt_"):
        material_type = "ppt"
    elif artifact_type.startswith("lesson_plan"):
        material_type = "lesson_plan"
    else:
        material_type = "report"
```

- [ ] **Step 7: Run the focused ask-path tests**

Run: `pytest api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py::test_reply_service_loads_lesson_plan_artifact_context_for_ask_path api/Edu_AI/tests/chat/test_reply_service_v2_stream.py::test_reply_service_stream_loads_lesson_plan_artifact_context_for_ask_path -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add api/Edu_AI/app/chat/application/artifact_context_loader.py api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py api/Edu_AI/tests/chat/test_reply_service_v2_stream.py
git commit -m "Add lesson plan artifact ask context"
```

## Task 2: Add Lesson-Plan Structure Parsing

**Files:**
- Create: `api/Edu_AI/app/chat/orchestrator/lesson_plan_structure_parser.py`
- Test: `api/Edu_AI/tests/chat/test_lesson_plan_structure_parser.py`

- [ ] **Step 1: Write the failing `lesson_plan` parser test**

```python
def test_parse_lesson_plan_nodes_emits_field_and_process_nodes():
    nodes = parse_lesson_plan_nodes(
        artifact_id="lesson-plan-1",
        artifact_type="lesson_plan",
        content={
            "title": "分数的意义",
            "objectives": ["理解分数的意义"],
            "process": [{"step": "导入", "goal": "联系生活经验", "duration": "5分钟"}],
        },
    )

    assert nodes[0]["node_type"] == "field"
    assert any(node["node_label"] == "教学目标" for node in nodes)
    assert any(node["node_label"] == "导入" for node in nodes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest api/Edu_AI/tests/chat/test_lesson_plan_structure_parser.py::test_parse_lesson_plan_nodes_emits_field_and_process_nodes -v`
Expected: FAIL because the parser file does not exist.

- [ ] **Step 3: Write the failing `lesson_plan_outline` parser test**

```python
def test_parse_lesson_plan_outline_nodes_emits_basic_fields_and_flow_nodes():
    nodes = parse_lesson_plan_nodes(
        artifact_id="outline-1",
        artifact_type="lesson_plan_outline",
        content={
            "basic_info": {"topic": "分数的意义", "duration": "40分钟"},
            "lesson_flow": [{"step": "导入", "goal": "进入主题"}],
        },
    )

    assert any(node["node_label"] == "topic" for node in nodes)
    assert any(node["node_label"] == "导入" for node in nodes)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest api/Edu_AI/tests/chat/test_lesson_plan_structure_parser.py::test_parse_lesson_plan_outline_nodes_emits_basic_fields_and_flow_nodes -v`
Expected: FAIL because the parser file does not exist.

- [ ] **Step 5: Implement the minimal structure parser**

```python
def parse_lesson_plan_nodes(*, artifact_id: str, artifact_type: str, content: Any) -> list[dict[str, Any]]:
    if artifact_type == "lesson_plan":
        return _parse_lesson_plan_content(artifact_id=artifact_id, content=dict(content or {}))
    if artifact_type == "lesson_plan_outline":
        return _parse_lesson_plan_outline(artifact_id=artifact_id, content=dict(content or {}))
    return []
```

```python
def _field_node(*, artifact_id: str, key: str, label: str, value: Any, order_index: int) -> dict[str, Any]:
    return {
        "node_id": f"{artifact_id}:{key}",
        "node_type": "field",
        "node_key": key,
        "node_label": label,
        "order_index": order_index,
        "content": value,
    }
```

- [ ] **Step 6: Include stable field labels and step labels**

```python
_LESSON_PLAN_FIELD_LABELS = {
    "objectives": "教学目标",
    "keyPoints": "教学重点",
    "hardPoints": "教学难点",
    "teachingAids": "教学准备",
    "boardPlan": "板书设计",
    "homework": "作业",
    "reflectionTips": "反思提示",
}
```

- [ ] **Step 7: Run the parser test file**

Run: `pytest api/Edu_AI/tests/chat/test_lesson_plan_structure_parser.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add api/Edu_AI/app/chat/orchestrator/lesson_plan_structure_parser.py api/Edu_AI/tests/chat/test_lesson_plan_structure_parser.py
git commit -m "Add lesson plan structure parser"
```

## Task 3: Add Lesson-Plan Edit Intent Parsing

**Files:**
- Create: `api/Edu_AI/app/chat/orchestrator/lesson_plan_edit_intent_parser.py`
- Modify: `api/Edu_AI/app/chat/application/artifact_reference_intent.py`
- Test: `api/Edu_AI/tests/chat/test_artifact_reference_intent.py`
- Test: `api/Edu_AI/tests/chat/test_lesson_plan_edit_intent_parser.py`

- [ ] **Step 1: Write the failing top-level intent test**

```python
def test_classify_lesson_plan_edit_with_field_anchor_as_edit():
    result = classify_artifact_reference_intent(
        "重写教学目标",
        artifact_type="lesson_plan",
    )

    assert result["intent_class"] == "edit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest api/Edu_AI/tests/chat/test_artifact_reference_intent.py::test_classify_lesson_plan_edit_with_field_anchor_as_edit -v`
Expected: FAIL because lesson-plan anchors are not recognized.

- [ ] **Step 3: Write the failing lesson-plan edit-intent parser tests**

```python
def test_parse_lesson_plan_edit_intent_matches_named_field_exactly():
    request = parse_lesson_plan_edit_intent(
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan"},
        question="重写教学目标",
        structure_nodes=[
            {"node_id": "lp-1:objectives", "node_type": "field", "node_key": "objectives", "node_label": "教学目标", "content": ["理解分数"]},
        ],
    )

    assert request["target_confidence"] == "exact"
    assert request["target_node_id"] == "lp-1:objectives"
```

```python
def test_parse_lesson_plan_edit_intent_returns_candidate_for_repeated_activity_steps():
    request = parse_lesson_plan_edit_intent(
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan"},
        question="把活动部分改一下",
        structure_nodes=[
            {"node_id": "lp-1:process:1", "node_type": "step", "node_label": "小组活动"},
            {"node_id": "lp-1:process:2", "node_type": "step", "node_label": "活动总结"},
        ],
    )

    assert request["target_confidence"] == "candidate"
    assert request["candidate_labels"] == ["小组活动", "活动总结"]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest api/Edu_AI/tests/chat/test_lesson_plan_edit_intent_parser.py -v`
Expected: FAIL because the parser file does not exist.

- [ ] **Step 5: Extend top-level artifact intent for lesson-plan anchors**

```python
_LESSON_PLAN_ANCHORS = (
    "教学目标",
    "教学重点",
    "教学难点",
    "教学准备",
    "板书设计",
    "作业",
    "反思提示",
    "导入",
    "练习",
    "总结",
    "第1个环节",
    "第2个环节",
)
```

```python
if kind in {"lesson_plan", "lesson_plan_outline"}:
    if not _contains_edit_keyword(text):
        return {"intent_class": "ask", "reason": "no_explicit_edit_verb", "requires_confirmation": False}
    if any(anchor in text for anchor in _LESSON_PLAN_ANCHORS) or _extract_freeform_anchor(text):
        return {"intent_class": "edit", "reason": "explicit_edit_with_lesson_plan_anchor", "requires_confirmation": False}
    return {"intent_class": "unclear", "reason": "lesson_plan_edit_without_safe_target", "requires_confirmation": True}
```

- [ ] **Step 6: Implement minimal lesson-plan edit-intent parsing**

```python
def parse_lesson_plan_edit_intent(*, artifact_reference: dict[str, Any], question: str, structure_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    if _looks_like_question(question):
        return _build_request(intent_type="ask_about_artifact", target_confidence="unclear", action_type="ask_about_artifact")

    exact_node = _find_exact_field_or_step_match(structure_nodes, question)
    if exact_node is not None:
        return _build_exact_request(exact_node, question=question, artifact_reference=artifact_reference)

    candidate_nodes = _find_candidate_matches(structure_nodes, question)
    if len(candidate_nodes) > 1:
        return _build_candidate_request(candidate_nodes, question=question, artifact_reference=artifact_reference)

    return _build_request(intent_type="edit_artifact", target_confidence="unclear", action_type="rewrite", instruction=question)
```

- [ ] **Step 7: Run the focused intent tests**

Run: `pytest api/Edu_AI/tests/chat/test_artifact_reference_intent.py api/Edu_AI/tests/chat/test_lesson_plan_edit_intent_parser.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add api/Edu_AI/app/chat/application/artifact_reference_intent.py api/Edu_AI/app/chat/orchestrator/lesson_plan_edit_intent_parser.py api/Edu_AI/tests/chat/test_artifact_reference_intent.py api/Edu_AI/tests/chat/test_lesson_plan_edit_intent_parser.py
git commit -m "Add lesson plan edit intent parsing"
```

## Task 4: Add Lesson-Plan Edit Runtime

**Files:**
- Create: `api/Edu_AI/app/chat/workflows/lesson_plan/edit_runtime.py`
- Test: `api/Edu_AI/tests/chat/test_lesson_plan_edit_runtime.py`

- [ ] **Step 1: Write the failing exact-edit runtime test**

```python
def test_lesson_plan_edit_runtime_rewrites_only_the_target_field():
    runtime = LessonPlanEditRuntime(llm=FakeLLM('["能说出分数的意义"]'))
    result = runtime.run(
        question="重写教学目标",
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan", "version_id": "v1"},
        source_artifact={
            "artifact_id": "lp-1",
            "artifact_type": "lesson_plan",
            "title": "分数的意义教案.json",
            "content": {
                "title": "分数的意义",
                "objectives": ["理解分数的意义"],
                "process": [{"step": "导入", "goal": "联系生活经验"}],
            },
        },
    )

    lesson_plan_artifact = result["artifacts"][0]
    assert lesson_plan_artifact["content"]["objectives"] == ["能说出分数的意义"]
    assert lesson_plan_artifact["content"]["process"][0]["goal"] == "联系生活经验"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest api/Edu_AI/tests/chat/test_lesson_plan_edit_runtime.py::test_lesson_plan_edit_runtime_rewrites_only_the_target_field -v`
Expected: FAIL because the runtime file does not exist.

- [ ] **Step 3: Write the failing candidate and unclear tests**

```python
def test_lesson_plan_edit_runtime_returns_candidate_confirmation_before_edit():
    result = runtime.run(question="把活动部分改一下", ...)
    assert result["workflow"]["status"] == "awaiting_input"
    assert "我还没有开始修改" in result["message"]["content"]
```

```python
def test_lesson_plan_edit_runtime_returns_clarification_for_unclear_target():
    result = runtime.run(question="优化一下这个教案", ...)
    assert result["workflow"]["status"] == "awaiting_input"
    assert "请告诉我你想修改哪一部分" in result["message"]["content"]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest api/Edu_AI/tests/chat/test_lesson_plan_edit_runtime.py -v`
Expected: FAIL because the runtime file does not exist.

- [ ] **Step 5: Implement minimal runtime branching**

```python
class LessonPlanEditRuntime:
    def run(self, *, question: str, artifact_reference: dict, source_artifact: dict) -> dict:
        nodes = parse_lesson_plan_nodes(
            artifact_id=str(source_artifact.get("artifact_id") or artifact_reference.get("artifact_id") or ""),
            artifact_type=str(source_artifact.get("artifact_type") or artifact_reference.get("artifact_type") or ""),
            content=source_artifact.get("content"),
        )
        edit_request = parse_lesson_plan_edit_intent(
            artifact_reference=artifact_reference,
            question=question,
            structure_nodes=nodes,
        )
```

```python
        if edit_request.get("intent_type") == "ask_about_artifact":
            return self._awaiting_input("当前引用的是教案内容。如需编辑，请明确字段、环节名或引用原文。", edit_request)
        if edit_request.get("target_confidence") == "candidate":
            hint = " / ".join(edit_request.get("candidate_labels") or [])
            return self._awaiting_input(f"我还没有开始修改。你要改的是：{hint}？确认后我再修改。", edit_request)
        if edit_request.get("target_confidence") == "unclear":
            return self._awaiting_input("请告诉我你想修改哪一部分，可以直接说字段名、环节名、引用一句原文，或说第几个环节。", edit_request)
```

- [ ] **Step 6: Implement minimal structured rewrite helper**

```python
def _rewrite_lesson_plan_content(self, *, source_content: dict[str, Any], edit_request: dict[str, Any]) -> dict[str, Any]:
    next_content = deepcopy(dict(source_content or {}))
    if edit_request.get("target_node_id", "").endswith(":objectives"):
        next_content["objectives"] = self._invoke_json_or_text_list(prompt, fallback=next_content.get("objectives") or [])
    elif ":process:" in str(edit_request.get("target_node_id") or ""):
        step_index = int(str(edit_request["target_node_id"]).rsplit(":", 1)[-1]) - 1
        next_content["process"][step_index] = self._invoke_json_or_text_dict(prompt, fallback=next_content["process"][step_index])
    return next_content
```

- [ ] **Step 7: Run the runtime test file**

Run: `pytest api/Edu_AI/tests/chat/test_lesson_plan_edit_runtime.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add api/Edu_AI/app/chat/workflows/lesson_plan/edit_runtime.py api/Edu_AI/tests/chat/test_lesson_plan_edit_runtime.py
git commit -m "Add lesson plan edit runtime"
```

## Task 5: Wire ReplyService Routing and Run Regression

**Files:**
- Modify: `api/Edu_AI/app/chat/application/reply_service_v2.py`
- Modify: `api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py`
- Modify: `api/Edu_AI/tests/chat/test_reply_service_v2_stream.py`

- [ ] **Step 1: Write the failing sync edit-routing test**

```python
def test_reply_service_routes_explicit_lesson_plan_edit_to_lesson_plan_edit_runtime():
    calls = {"lesson_plan_edit": [], "dispatch": []}

    class DummyLessonPlanEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            calls["lesson_plan_edit"].append(request.question)
            return {
                "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "lesson_plan.edit"},
                "workflow": {"type": "lesson_plan", "status": "completed"},
                "artifacts": [],
                "sources": [],
                "trace": {"path": "workflow"},
            }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py::test_reply_service_routes_explicit_lesson_plan_edit_to_lesson_plan_edit_runtime -v`
Expected: FAIL because `ReplyServiceV2` has no lesson-plan edit runtime branch.

- [ ] **Step 3: Write the failing stream edit-routing test**

```python
def test_reply_service_stream_routes_explicit_lesson_plan_edit_to_lesson_plan_edit_runtime():
    events = list(service.reply_stream(payload))
    assert [event["type"] for event in events] == ["result", "done"]
    assert events[0]["payload"]["action"]["name"] == "lesson_plan.edit"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest api/Edu_AI/tests/chat/test_reply_service_v2_stream.py::test_reply_service_stream_routes_explicit_lesson_plan_edit_to_lesson_plan_edit_runtime -v`
Expected: FAIL because stream routing does not know about lesson-plan edit runtime.

- [ ] **Step 5: Add `lesson_plan_edit_runtime` to the service constructor and builder**

```python
class ReplyServiceV2:
    def __init__(..., lesson_plan_edit_runtime=None, ...):
        self.lesson_plan_edit_runtime = lesson_plan_edit_runtime
```

```python
return ReplyServiceV2(
    ...,
    lesson_plan_edit_runtime=LessonPlanEditRuntime(llm=get_fallback_llm()),
)
```

- [ ] **Step 6: Route lesson-plan artifact edits before fallback report runtime**

```python
def _run_artifact_edit(self, *, request, snapshot, artifact_type: str):
    if artifact_type in {"lesson_plan", "lesson_plan_outline"} and self.lesson_plan_edit_runtime is not None:
        return self.lesson_plan_edit_runtime.run_from_request(
            request=request,
            snapshot=snapshot,
            course_storage_manager=self.course_storage_manager,
        )
```

- [ ] **Step 7: Run the focused reply-service tests**

Run: `pytest api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py api/Edu_AI/tests/chat/test_reply_service_v2_stream.py -v`
Expected: PASS

- [ ] **Step 8: Run the focused lesson-plan artifact regression suite**

Run: `pytest api/Edu_AI/tests/chat/test_artifact_reference_intent.py api/Edu_AI/tests/chat/test_lesson_plan_structure_parser.py api/Edu_AI/tests/chat/test_lesson_plan_edit_intent_parser.py api/Edu_AI/tests/chat/test_lesson_plan_edit_runtime.py api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py api/Edu_AI/tests/chat/test_reply_service_v2_stream.py api/Edu_AI/tests/chat/test_fast_chat_runtime.py -q`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add api/Edu_AI/app/chat/application/reply_service_v2.py api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py api/Edu_AI/tests/chat/test_reply_service_v2_stream.py
git commit -m "Wire lesson plan artifact reference flow"
```

## Self-Review

### Spec Coverage

- ask flow for `lesson_plan`: covered by Task 1
- ask flow for `lesson_plan_outline`: covered by Task 1
- top-level `ask / edit / unclear`: covered by Task 3
- structure-aware targeting: covered by Task 2 and Task 3
- dedicated lesson-plan edit runtime: covered by Task 4
- sync and stream routing: covered by Task 5

### Placeholder Scan

- No `TODO`, `TBD`, or "implement later" markers remain.
- Every testing step includes an exact command.
- Every code-changing step includes a concrete code block.

### Type Consistency

- New parser entry point stays `parse_lesson_plan_nodes(...)`
- New intent parser entry point stays `parse_lesson_plan_edit_intent(...)`
- New runtime stays `LessonPlanEditRuntime`
- Reply service constructor and builder use the same `lesson_plan_edit_runtime` name
