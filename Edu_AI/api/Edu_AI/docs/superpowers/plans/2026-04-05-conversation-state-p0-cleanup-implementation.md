# Conversation State P0 Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source-aware report/system pollution filtering to conversation memory extraction so workflow control text no longer contaminates long-lived chat state.

**Architecture:** Keep the current rule-based extractor as the writeback backbone, but add a lightweight source classifier and semantic filtering layer inside `ConversationMemoryExtractor`. Use raw user input only for explicit workflow intent/goals; use filtered semantic text for topics, facts, issues, evidence, and summary so control/meta phrases stop entering long-lived memory.

**Tech Stack:** Python, pytest, existing chat state writeback pipeline

---

### Task 1: Lock P0 Scope With Regression Tests

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_source_filtering.py`
- Reference: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\conversation_memory_extractor_v2.py`

- [ ] **Step 1: Write the failing tests**

Add tests covering these cases:

```python
from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor


def _request(question: str):
    return SimpleNamespace(
        question=question,
        course_id="course-1",
        capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
    )


def test_report_control_turn_does_not_pollute_topics_summary_or_facts():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("请基于当前内容生成一份报告"),
        result={
            "message": {"content": "我将基于“关羽水淹七军战役”，重点围绕“战役全过程分析”，结合当前对话内容先生成一版报告。可以直接开始吗？"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
        },
        existing_state={
            "conversation_summary": {"summary_text": "当前围绕介绍下水淹七军、介绍下关羽的战绩继续对话"},
            "conversation_memory": {
                "current_topics": ["介绍下水淹七军", "介绍下关羽的战绩"],
                "confirmed_facts": ["水淹七军是关羽军事生涯的巅峰战役"],
                "teaching_issues": ["于禁七军陷入混乱"],
                "student_signals": [],
                "evidence_points": [{"type": "observation", "content": "关羽提前准备水军"}],
                "constraints": {"course_id": "course-1", "extra_constraints": []},
                "user_goals": ["继续对话"],
            },
        },
        recent_messages=[],
    )

    memory = patch["conversation_memory"]
    assert memory["current_topics"][:2] == ["介绍下水淹七军", "介绍下关羽的战绩"]
    assert "请基于当前内容生成一份报告" not in memory["current_topics"]
    assert patch["conversation_summary"]["summary_text"] == "当前围绕介绍下水淹七军、介绍下关羽的战绩继续对话"
    assert all("生成一版报告" not in item for item in memory["confirmed_facts"])


def test_outline_control_turn_does_not_generate_new_facts_or_evidence():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("根据已确认的大纲开始生成报告"),
        result={
            "message": {"content": "大纲已生成，请确认或指出要修改的地方：\n- 战役背景\n- 战役过程\n- 战役影响"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "outlining"},
        },
        existing_state={
            "conversation_summary": {"summary_text": "当前围绕介绍下水淹七军继续对话"},
            "conversation_memory": {
                "current_topics": ["介绍下水淹七军"],
                "confirmed_facts": ["关羽利用洪水击败于禁七军"],
                "teaching_issues": [],
                "student_signals": [],
                "evidence_points": [{"type": "observation", "content": "汉水暴涨数丈"}],
                "constraints": {"course_id": "course-1", "extra_constraints": []},
                "user_goals": ["生成报告"],
            },
        },
        recent_messages=[],
    )

    memory = patch["conversation_memory"]
    assert memory["confirmed_facts"] == ["关羽利用洪水击败于禁七军"]
    assert memory["evidence_points"] == [{"type": "observation", "content": "汉水暴涨数丈"}]


def test_assistant_meta_openers_do_not_enter_fact_or_issue_memory():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("skills怎么使用"),
        result={
            "message": {
                "content": "这是一个非常好的问题。使用 AI 的 Skills，本质上就是通过特定方式与模型交互，以激发其能力。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    memory = patch["conversation_memory"]
    assert all("这是一个非常好的问题" not in item for item in memory["confirmed_facts"])
    assert all("这是一个非常好的问题" not in item for item in memory["teaching_issues"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_source_filtering.py -q
```

Expected:

- FAIL because workflow control text currently enters `current_topics`, `confirmed_facts`, `summary`, or `evidence_points`

---

### Task 2: Add Source-Aware Semantic Filtering To The Extractor

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\conversation_memory_extractor_v2.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_source_filtering.py`

- [ ] **Step 1: Add source classification helpers**

Introduce lightweight helpers inside `ConversationMemoryExtractor`:

```python
def _classify_user_text(self, text: str) -> str:
    ...

def _classify_assistant_text(self, text: str) -> str:
    ...

def _semantic_user_text(self, text: str) -> str:
    ...

def _semantic_assistant_text(self, text: str) -> str:
    ...
```

Target categories:

- `user_content`
- `workflow_control`
- `assistant_content`
- `assistant_meta`
- `workflow_result`

Patterns to filter should cover:

- `请基于当前内容生成一份报告`
- `根据已确认的大纲开始生成报告`
- `确认并继续`
- `请确认或指出要修改的地方`
- `大纲已生成`
- `我将基于……先生成一版报告`
- `已识别用户请求生成……`
- `这是一个非常好的问题`
- `这是一个非常实际的问题`

- [ ] **Step 2: Route only semantic text into memory fields**

In `build_state_patch(...)`, keep:

- raw `question` for `_extract_goal`

But use filtered semantic text for:

- `_extract_topics`
- `_extract_constraints`
- `_extract_issues`
- `_extract_student_signals`
- `_extract_evidence_points`
- `_extract_confirmed_facts`
- `_build_summary`

Pseudo-shape:

```python
semantic_question = self._semantic_user_text(question)
semantic_answer = self._semantic_assistant_text(answer)
```

Behavior goals:

- workflow control text should not create new topics
- assistant meta/control text should not enter facts/issues/evidence
- if a turn contains no semantic user/assistant text, preserve existing summary instead of regenerating from control text

- [ ] **Step 3: Keep user goal extraction intact**

Do not break report intent capture:

```python
goal = self._extract_goal(raw_question, ...)
```

This means:

- report request still updates `user_goals`
- but does not pollute semantic memory fields

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_source_filtering.py -q
```

Expected:

- PASS

---

### Task 3: Protect Existing Conversation-Memory Behavior With Regression Coverage

**Files:**
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2_pipeline.py`

- [ ] **Step 1: Add one regression asserting report control turns still update goals**

Example:

```python
def test_report_control_turn_still_updates_user_goal_without_polluting_topics():
    ...
    assert patch["conversation_memory"]["user_goals"][0] == "生成报告"
    assert "请基于当前内容生成一份报告" not in patch["conversation_memory"]["current_topics"]
```

- [ ] **Step 2: Add one pipeline regression asserting persisted state keeps semantic topic but not control phrase**

Example:

```python
def test_pipeline_does_not_persist_report_control_phrase_as_topic():
    ...
    assert "请基于当前内容生成一份报告" not in state["conversation_memory"]["current_topics"]
```

- [ ] **Step 3: Run focused regression suite**

Run:

```bash
pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_source_filtering.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_conversation_memory_phase2_pipeline.py -q
```

Expected:

- PASS

---

### Task 4: Run Broader Chat Verification

**Files:**
- Verify only

- [ ] **Step 1: Run broader chat test suite**

Run:

```bash
pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat -q
```

Expected:

- PASS
- Existing warnings allowed only if unrelated and pre-existing

- [ ] **Step 2: Summarize behavioral impact**

Confirm these outcomes in the final handoff:

- report/system phrases no longer become topics/facts/evidence
- `user_goals` still correctly captures report intent
- old workflows continue to run
- summary no longer gets rewritten by pure control turns
