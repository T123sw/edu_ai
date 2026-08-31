# Agent Conversation and Resource Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the unified ReAct Agent entry for every conversation while preventing ordinary QA from seeing resource-mutation tools or producing unverified task-submission claims.

**Architecture:** Every streaming message without an explicit page action remains inside `ReActAgent`. A deterministic `TeachingTaskContract` is extracted before graph execution and stored in graph state; the Executor uses that contract plus the current compiled plan to enforce a server-side tool allowlist. Prompt instructions distinguish QA from resource work, while confirmation parsing uses exact short-reply matching so an active outline can safely resume generation.

**Tech Stack:** Python 3.12, FastAPI application services, LangGraph ReAct runtime, Pydantic task contracts, pytest.

---

## File Structure

- Modify `Edu_AI/api/src/app/chat/runtime/react_agent.py`: remove the normal FastChat bypass, extract the task contract once, and seed it into graph state for every turn.
- Modify `Edu_AI/api/src/app/chat/runtime/planning/task_contract_extractor.py`: recognize exact short outline confirmations without matching confirmation words inside knowledge questions.
- Modify `Edu_AI/api/src/app/chat/runtime/nodes/executor.py`: hide state-mutating tools for unplanned QA and inject mode-specific execution instructions.
- Modify `Edu_AI/api/src/app/chat/runtime/nodes/prompts.py`: replace mixed global instructions with explicit role, intent, tool, and truthfulness boundaries.
- Modify `Edu_AI/api/src/tests/chat/runtime/test_react_agent.py`: verify every ordinary conversation stays inside ReAct Agent and generation still emits real task events.
- Modify `Edu_AI/api/src/tests/chat/runtime/test_teaching_task_contract.py`: cover exact confirmation and false-positive boundaries.
- Modify `Edu_AI/api/src/tests/chat/runtime/test_plan_compiler.py`: verify a bare `开始` after an active report outline compiles a `generate_report` step.
- Modify `Edu_AI/api/src/tests/chat/runtime/test_phase5_strict.py`: verify QA cannot see mutating tools even when no plan was compiled.
- Modify `Edu_AI/api/src/tests/chat/runtime/test_agent_prompt_boundaries.py`: lock down the redesigned prompt and truthful-submission rules.

### Task 1: Restore the Unified ReAct Agent Entry

**Files:**
- Modify: `Edu_AI/api/src/tests/chat/runtime/test_react_agent.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/react_agent.py:27-155`

- [ ] **Step 1: Replace the FastChat-delegation regression test with an Agent-entry test**

Update `test_react_agent.py` so ordinary QA must be processed by the Agent gateway and must not call `FakeFastRuntime`:

```python
def test_react_agent_keeps_ordinary_question_inside_agent_runtime():
    request, snapshot = _request_snapshot()
    request.question = "链表如何实现"
    fast_runtime = FakeFastRuntime()
    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        fast_runtime=fast_runtime,
        max_steps=4,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert events[0]["type"] == "status"
    assert events[-1]["payload"]["trace"]["path"] == "agent"
    assert events[-1]["payload"]["message"]["content"] == "你好，可以。"
    assert fast_runtime.calls == []
```

- [ ] **Step 2: Run the test and verify it fails for the FastChat bypass**

Run:

```powershell
$env:PYTHONPATH='D:\Edu_AI_1\Edu_AI\api\src'
python -m pytest src/tests/chat/runtime/test_react_agent.py::test_react_agent_keeps_ordinary_question_inside_agent_runtime -q
```

Expected: FAIL because the current implementation returns FastChat events and records `reason=ordinary_question`.

- [ ] **Step 3: Remove the early FastChat return but keep one contract extraction**

In `react_agent.py`, remove the `RouteDecision` import, `_AGENT_FOLLOWUP_MARKERS`, `_ACTIVE_TASK_INTENTS`, and the `yield from self.fast_runtime.run_stream(... ordinary_question ...)` branch. Keep `extract_task_contract` and compute it immediately after restoring checkpoint state:

```python
contract = extract_task_contract(
    request,
    capability,
    checkpoint_state,
    snapshot=snapshot,
)

yield {
    "type": "status",
    "payload": {"stage": "thinking", "label": "正在分析请求..."},
}
needs_planning = should_plan(request, snapshot, checkpoint_state)
```

Seed the real contract instead of an empty mapping in `initial_input`:

```python
initial_input = {
    "messages": messages,
    "tool_exchange": [],
    "retrieval_sources": [],
    "fallback_reason": "",
    "needs_planning": needs_planning,
    "task_contract": contract.model_dump(mode="json"),
    # keep the remaining existing fields unchanged
}
```

Also expose the classification in trace:

```python
ctx.trace["intent"] = contract.intent
ctx.trace["contract_hash"] = contract.contract_hash
```

- [ ] **Step 4: Run the focused Agent tests**

Run:

```powershell
python -m pytest src/tests/chat/runtime/test_react_agent.py -q
```

Expected: all tests pass; ordinary QA ends with `trace.path == "agent"`.

- [ ] **Step 5: Commit the unified entry change**

```powershell
git add Edu_AI/api/src/app/chat/runtime/react_agent.py Edu_AI/api/src/tests/chat/runtime/test_react_agent.py
git commit -m "fix: restore unified react agent entry"
```

### Task 2: Enforce QA Tool Boundaries Without a Compiled Plan

**Files:**
- Modify: `Edu_AI/api/src/tests/chat/runtime/test_phase5_strict.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/nodes/executor.py:31-45,879-948`

- [ ] **Step 1: Add a failing test for unplanned QA mutation filtering**

Add to `test_phase5_strict.py`:

```python
def test_executor_hides_mutating_tools_for_unplanned_qa_contract():
    from app.chat.runtime.nodes.executor import _filter_tool_schemas_for_step

    schemas = [
        SCHEMA_RAG_SEARCH,
        SCHEMA_IMAGE_SEARCH,
        SCHEMA_DRAFT_OUTLINE,
        SCHEMA_GENERATE_REPORT,
    ]
    state = {
        "task_contract": {"intent": "qa"},
        "plan_mode": "",
        "current_plan": {},
    }

    filtered = _filter_tool_schemas_for_step(schemas, state)

    assert [item["function"]["name"] for item in filtered] == [
        "rag_search",
        "image_search",
    ]
```

- [ ] **Step 2: Run the test and verify mutating tools are currently visible**

Run:

```powershell
python -m pytest src/tests/chat/runtime/test_phase5_strict.py::test_executor_hides_mutating_tools_for_unplanned_qa_contract -q
```

Expected: FAIL because `_filter_tool_schemas_for_step` currently returns every schema when `plan_mode` is empty.

- [ ] **Step 3: Filter mutation tools from every QA turn before plan-mode handling**

Import tool metadata in `executor.py`:

```python
from app.chat.runtime.agent_tools.tool_meta import get_tool_meta
```

At the start of `_filter_tool_schemas_for_step`, add:

```python
contract = dict(state.get("task_contract") or {})
if str(contract.get("intent") or "") == "qa":
    tool_schemas = [
        schema
        for schema in tool_schemas
        if not get_tool_meta(
            str((schema.get("function") or {}).get("name") or "")
        ).mutates_state
    ]
```

Then retain the existing strict/guided step filtering. This leaves RAG, Web, and image search available while removing `draft_outline` and every registered `generate_*` tool.

- [ ] **Step 4: Add a test proving generation contracts retain their planned tool**

```python
def test_executor_keeps_expected_generation_tool_for_generation_contract():
    from app.chat.runtime.nodes.executor import _filter_tool_schemas_for_step

    state = {
        "task_contract": {"intent": "confirm"},
        "plan_mode": "guided",
        "plan_step_index": 0,
        "current_plan": {
            "steps": [{"expected_tools": ["generate_report"]}],
        },
    }

    filtered = _filter_tool_schemas_for_step(
        [SCHEMA_RAG_SEARCH, SCHEMA_GENERATE_REPORT], state
    )

    assert [item["function"]["name"] for item in filtered] == [
        "rag_search",
        "generate_report",
    ]
```

- [ ] **Step 5: Run strict-mode tests**

Run:

```powershell
python -m pytest src/tests/chat/runtime/test_phase5_strict.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit the tool-boundary change**

```powershell
git add Edu_AI/api/src/app/chat/runtime/nodes/executor.py Edu_AI/api/src/tests/chat/runtime/test_phase5_strict.py
git commit -m "fix: close resource tools during ordinary qa"
```

### Task 3: Make Active-Outline Confirmation Exact and Consistent

**Files:**
- Modify: `Edu_AI/api/src/tests/chat/runtime/test_teaching_task_contract.py`
- Modify: `Edu_AI/api/src/tests/chat/runtime/test_plan_compiler.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/planning/task_contract_extractor.py:45-54,260-279`

- [ ] **Step 1: Add failing contract tests for bare confirmation and knowledge questions**

Add to `test_teaching_task_contract.py`:

```python
def test_active_outline_accepts_exact_short_confirmation_replies():
    state = {
        "active_draft_outline": {
            "subject": "链表实现",
            "resource_type": "report",
        }
    }

    for text in ("开始", "好的", "可以", "确认", "没问题"):
        contract = extract_task_contract(request(text), capability(), state)
        assert contract.intent == "confirm"


def test_confirmation_words_inside_knowledge_questions_do_not_confirm_outline():
    state = {
        "active_draft_outline": {
            "subject": "链表实现",
            "resource_type": "report",
        }
    }

    for text in ("开始节点是什么", "可以解释一下链表吗", "好的教案有哪些特点"):
        contract = extract_task_contract(request(text), capability(), state)
        assert contract.intent == "qa"
```

- [ ] **Step 2: Add a failing plan test for the screenshot reproduction**

Add to `test_plan_compiler.py`:

```python
def test_bare_start_after_report_outline_compiles_real_report_generation():
    state = {
        "active_draft_outline": {
            "resource_type": "report",
            "subject": "链表实现报告大纲",
            "outline_markdown": "# 链表实现报告大纲",
        }
    }
    contract = extract_task_contract(request("开始"), capability(), state)
    plan = compile_plan(contract, state)

    assert contract.intent == "confirm"
    assert actions(plan) == ["generate_resource", "verify", "report_result"]
    assert tools(plan)[0] == ["generate_report"]
```

- [ ] **Step 3: Run the new tests and verify `开始` is currently `qa`**

Run:

```powershell
python -m pytest src/tests/chat/runtime/test_teaching_task_contract.py::test_active_outline_accepts_exact_short_confirmation_replies src/tests/chat/runtime/test_plan_compiler.py::test_bare_start_after_report_outline_compiles_real_report_generation -q
```

Expected: FAIL with `intent == "qa"` for `开始`.

- [ ] **Step 4: Implement normalized exact confirmation matching**

Replace the mixed confirmation tuple with explicit exact and phrase sets:

```python
_CONFIRM_EXACT_REPLIES = {
    "开始",
    "好的",
    "可以",
    "确认",
    "没问题",
    "ok",
}
_CONFIRM_PHRASES = (
    "按这个",
    "就按",
    "开始生成",
    "继续生成",
    "可以生成",
)


def _is_outline_confirmation(question: str) -> bool:
    normalized = re.sub(r"[\s，,。.!！?？]+", "", str(question or "").lower())
    return normalized in _CONFIRM_EXACT_REPLIES or any(
        phrase in normalized for phrase in _CONFIRM_PHRASES
    )
```

Use it only when an active outline exists:

```python
if active_outline and _is_outline_confirmation(question):
    return "confirm"
```

Update `_topic` to use `_is_outline_confirmation(question)` rather than iterating the removed tuple.

- [ ] **Step 5: Run contract and compiler tests**

Run:

```powershell
python -m pytest src/tests/chat/runtime/test_teaching_task_contract.py src/tests/chat/runtime/test_plan_compiler.py -q
```

Expected: all tests pass, including the three false-positive knowledge questions.

- [ ] **Step 6: Commit the confirmation fix**

```powershell
git add Edu_AI/api/src/app/chat/runtime/planning/task_contract_extractor.py Edu_AI/api/src/tests/chat/runtime/test_teaching_task_contract.py Edu_AI/api/src/tests/chat/runtime/test_plan_compiler.py
git commit -m "fix: align outline confirmation intent"
```

### Task 4: Redesign the Agent Prompt Around Explicit Modes

**Files:**
- Modify: `Edu_AI/api/src/tests/chat/runtime/test_agent_prompt_boundaries.py`
- Modify: `Edu_AI/api/src/app/chat/runtime/nodes/prompts.py:5-74`
- Modify: `Edu_AI/api/src/app/chat/runtime/nodes/executor.py:1064-1088`

- [ ] **Step 1: Add failing assertions for the four prompt boundaries**

Replace the current single prompt test with:

```python
def test_agent_prompt_defines_qa_resource_tool_and_truth_boundaries():
    prompt = build_system_content(None, actor_role="teacher")

    assert "【普通问答模式】" in prompt
    assert "RAG 或 Web 结果只是回答依据，不代表用户要求生成资源" in prompt
    assert "不得评价回答是否缺少图片、图表或教学环节" in prompt
    assert "【资源任务模式】" in prompt
    assert "只有当前轮 generate_* 工具成功返回非空 task_id" in prompt
    assert "不得声称任务已提交、已启动或正在后台生成" in prompt
```

Add a step-hint test to `test_phase5_strict.py` or a focused executor prompt test:

```python
def test_qa_step_hint_explicitly_forbids_resource_submission_claims():
    from app.chat.runtime.nodes.executor import _inject_plan_step_hint

    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "开始节点是什么"},
    ]
    state = {
        "plan_mode": "guided",
        "plan_step_index": 0,
        "task_contract": {"intent": "qa"},
        "current_plan": {
            "steps": [{
                "user_title": "回答问题",
                "internal_action": "answer_question",
                "expected_tools": [],
            }]
        },
    }

    rendered = _inject_plan_step_hint(messages, state)
    hint = next(item["content"] for item in rendered if "当前执行步骤" in item["content"])
    assert "本轮是普通问答" in hint
    assert "不得声称已创建或提交后台任务" in hint
```

- [ ] **Step 2: Run prompt tests and verify the new mode labels are absent**

Run:

```powershell
python -m pytest src/tests/chat/runtime/test_agent_prompt_boundaries.py src/tests/chat/runtime/test_phase5_strict.py::test_qa_step_hint_explicitly_forbids_resource_submission_claims -q
```

Expected: FAIL because the current prompt mixes QA and resource instructions and has no truthful-submission rule.

- [ ] **Step 3: Replace `COMMON_AGENT_INSTRUCTIONS` with explicit mode sections**

Use the following content structure in `prompts.py`:

```python
COMMON_AGENT_INSTRUCTIONS = """

【执行依据】
系统会提供当前任务契约、编译计划、执行步骤和允许工具。它们是本轮唯一执行权限。
只能使用当前步骤授权的工具，不得跳步、扩大任务或用文本模拟工具调用。

【普通问答模式】
当前契约为 qa 或当前步骤为 answer_question 时，只回答用户当前问题。
RAG 或 Web 结果只是回答依据，不代表用户要求生成资源。
不得把检索结果改写成教案、报告、PPT 或资源评审；不得评价回答是否缺少图片、图表或教学环节；
不得主动建议生成资源，也不得调用大纲、资源生成、修改或取消工具。

【资源任务模式】
只有契约为 generate_single、prepare_bundle、modify 或 confirm 时才执行资源步骤。
报告、PPT、教案必须遵守检索、大纲、确认、生成边界；其他资源按编译计划执行。
配图完整性检查只适用于明确的 fetch_visuals 或 generate_resource 步骤。

【任务真实性】
只有当前轮 generate_* 工具成功返回非空 task_id，才能说任务已提交、已启动或正在后台生成。
没有成功工具结果时，不得声称任务已提交、已启动或正在后台生成；提交失败时直接说明失败原因。

【追问与表达】
仅在一个会显著改变结果的关键信息缺失时追问一次。表达自然简洁，不展示内部推理。
"""
```

Keep actor-specific capability lists and active-outline memory, but change the active-outline suffix so it does not ask the model to override the compiled contract:

```python
base += (
    "\n\n【当前会话工作记忆】\n"
    f"本会话中已向用户展示了 {rtype} 大纲（主题：{subject}），内容如下：\n"
    f"{md}\n\n"
    "该大纲仅供当前契约与计划使用。只有当前步骤明确授权对应 generate_* 工具时，"
    "才可将大纲作为 confirmed_outline 传入。"
)
```

- [ ] **Step 4: Add intent-specific text to `_inject_plan_step_hint`**

Before composing `hint`, derive the current contract and action:

```python
intent = str((state.get("task_contract") or {}).get("intent") or "")
action = str(step.get("internal_action") or "")
mode_boundary = ""
if intent == "qa" or action == "answer_question":
    mode_boundary = (
        "本轮是普通问答：只回答当前问题；不得调用资源工具，"
        "不得声称已创建或提交后台任务。\n"
    )
elif action == "generate_resource":
    mode_boundary = (
        "本轮是资源生成步骤：只有生成工具成功返回 task_id 后，"
        "才能向用户报告任务已提交。\n"
    )
```

Insert `mode_boundary` before `请专注完成此步骤`.

- [ ] **Step 5: Run prompt and executor tests**

Run:

```powershell
python -m pytest src/tests/chat/runtime/test_agent_prompt_boundaries.py src/tests/chat/runtime/test_phase5_strict.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit the Prompt redesign**

```powershell
git add Edu_AI/api/src/app/chat/runtime/nodes/prompts.py Edu_AI/api/src/app/chat/runtime/nodes/executor.py Edu_AI/api/src/tests/chat/runtime/test_agent_prompt_boundaries.py Edu_AI/api/src/tests/chat/runtime/test_phase5_strict.py
git commit -m "fix: isolate qa and resource agent prompts"
```

### Task 5: Verify Real Report Submission and Full Regression

**Files:**
- Modify: `Edu_AI/api/src/tests/chat/runtime/test_react_agent.py`
- Test: `Edu_AI/api/src/tests/chat/runtime/test_agent_report_grounding.py`
- Test: `Edu_AI/api/src/tests/chat/runtime/test_plan_compiler.py`
- Test: `Edu_AI/api/src/tests/chat/runtime/test_teaching_task_contract.py`

- [ ] **Step 1: Add an end-to-end Agent confirmation test**

Add a focused test using a temporary Agent state store and a patched generation command service. Add `AgentRunStore` to the imports, then seed an active report outline, send `开始`, and assert the command configuration plus the real task event:

```python
from app.chat.persistence.agent_run_store import AgentRunStore


def test_react_agent_bare_start_submits_confirmed_report(monkeypatch, tmp_path):
    submitted_commands = []

    class CommandService:
        def submit(self, command):
            submitted_commands.append(command)
            return SimpleNamespace(edu_job_id="job-report-start-1")

    monkeypatch.setattr(
        "app.chat.runtime.agent_tools.handlers.report.generation_command_service",
        CommandService(),
    )
    run_store = AgentRunStore(tmp_path / "agent_runs.db")
    request, snapshot = _request_snapshot()
    request.conversation_id = "conv-report-start-1"
    request.question = "开始"
    run_store.save(
        request.conversation_id,
        request.owner,
        request.course_id,
        {
            "active_draft_outline": {
                "resource_type": "report",
                "subject": "链表实现报告大纲",
                "outline_markdown": "# 链表实现报告大纲",
            }
        },
    )
    agent = ReActAgent(
        agent_gateway=FakeTextGateway(),
        fast_runtime=FakeFastRuntime(),
        agent_run_store=run_store,
        max_steps=6,
        timeout_seconds=5,
    )

    events = list(agent.run_stream(request=request, snapshot=snapshot))

    assert len(submitted_commands) == 1
    assert submitted_commands[0].resource_type == "report"
    assert (
        submitted_commands[0].config["confirmed_outline"]
        == "# 链表实现报告大纲"
    )
    submitted = next(event for event in events if event["type"] == "task_submitted")
    assert submitted["payload"]["task_id"] == "job-report-start-1"
    assert submitted["payload"]["workflow_type"] == "report"
    assert any(
        step.get("tool") == "generate_report" and step.get("ok")
        for step in events[-1]["payload"]["trace"]["agent_steps"]
    )
    run_store.close()
```

This uses the existing public durable-state seam; do not add a production-only state mutation API.

- [ ] **Step 2: Run the integration test and verify it passes**

Run:

```powershell
python -m pytest src/tests/chat/runtime/test_react_agent.py::test_react_agent_bare_start_submits_confirmed_report -q
```

Expected: PASS with one `task_submitted` event and task ID `job-report-start-1`.

- [ ] **Step 3: Run the complete Agent runtime suite**

Run:

```powershell
python -m pytest src/tests/chat/runtime -q
```

Expected: all runtime tests pass.

- [ ] **Step 4: Run adjacent chat routing and FastChat fallback tests**

Run:

```powershell
python -m pytest src/tests/chat/test_fast_chat_runtime.py src/tests/chat/test_route_rules.py src/tests/chat/test_reply_service_v2.py -q
```

Expected: all selected tests pass. FastChat remains available only as fallback or explicit non-Agent path.

- [ ] **Step 5: Check formatting and compilation**

Run:

```powershell
git diff --check -- Edu_AI/api/src/app/chat/runtime Edu_AI/api/src/tests/chat/runtime
python -m compileall -q Edu_AI/api/src/app/chat/runtime
```

Expected: exit code 0; no whitespace errors or Python compilation failures.

- [ ] **Step 6: Commit the integration regression coverage**

```powershell
git add Edu_AI/api/src/tests/chat/runtime/test_react_agent.py
git commit -m "test: verify confirmed report task submission"
```

- [ ] **Step 7: Review the final diff against the design**

Verify all of the following from the final diff and test output:

```text
Every ordinary stream enters ReActAgent.
QA can use RAG/Web but cannot see mutating resource tools.
Resource-name questions remain qa.
Bare 开始 confirms only an active outline.
Knowledge questions containing 开始/可以 remain qa.
Resource submission success requires a real generate_* tool result with task_id.
FastChat is not the normal QA router.
```

Expected: every statement is directly supported by production code and at least one automated test.
