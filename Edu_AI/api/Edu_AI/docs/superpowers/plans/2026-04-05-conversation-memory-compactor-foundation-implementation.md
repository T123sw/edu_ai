# Conversation Memory Compactor Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first production compactor/refiner foundation so conversation memory can periodically converge instead of only appending.

**Architecture:** Introduce a focused `ConversationMemoryCompactor` that runs after the extractor assembles the next memory patch. The compactor should keep the current schema stable, add lightweight `conversation_memory_meta`, and apply a small first batch of cleanup rules: trigger-based compaction, topic cleanup, and stale goal cleanup during workflow-oriented turns.

**Tech Stack:** Python, pytest, existing chat orchestrator/storage modules

---

### Task 1: Add failing tests for compactor triggers and cleanup

**Files:**
- Create: `d:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_conversation_memory_compactor.py`

- [ ] **Step 1: Write the failing tests**

```python
from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor


def _request(question: str):
    return SimpleNamespace(
        question=question,
        course_id="course-1",
        capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
    )


def test_compactor_runs_on_fourth_turn_and_cleans_workflow_residue():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("继续分析水淹七军的战术过程"),
        result={"message": {"content": "关羽提前准备水军并利用洪水时机。"}, "action": {"name": "chat.reply"}},
        existing_state={
            "conversation_summary": {"summary_text": "当前围绕水淹七军继续对话"},
            "conversation_memory": {
                "current_topics": ["请基于当前内容生成一份报告", "确认并继续", "介绍下水淹七军"],
                "user_goals": ["生成报告", "继续对话"],
            },
            "conversation_memory_meta": {
                "turn_count": 3,
                "last_compacted_turn": 0,
                "compaction_count": 0,
            },
        },
        recent_messages=[],
    )

    assert patch["conversation_memory_meta"]["turn_count"] == 4
    assert patch["conversation_memory_meta"]["compaction_count"] == 1
    assert patch["conversation_memory_meta"]["last_compacted_turn"] == 4
    assert "请基于当前内容生成一份报告" not in patch["conversation_memory"]["current_topics"]
    assert "确认并继续" not in patch["conversation_memory"]["current_topics"]


def test_compactor_drops_stale_continue_chat_goal_on_report_turn():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("请基于当前内容生成一份报告"),
        result={
            "message": {"content": "我将基于当前内容先生成一版报告。"},
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
        },
        existing_state={
            "conversation_memory": {
                "current_topics": ["介绍下水淹七军"],
                "user_goals": ["继续对话"],
            },
            "conversation_memory_meta": {
                "turn_count": 1,
                "last_compacted_turn": 0,
                "compaction_count": 0,
            },
        },
        recent_messages=[],
    )

    assert patch["conversation_memory_meta"]["compaction_count"] == 1
    assert patch["conversation_memory"]["user_goals"][0] == "生成报告"
    assert "继续对话" not in patch["conversation_memory"]["user_goals"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
pytest d:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_conversation_memory_compactor.py -q
```

Expected: FAIL because `conversation_memory_meta` and compactor cleanup do not exist yet.

### Task 2: Implement compactor foundation and integrate it into extractor

**Files:**
- Create: `d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/orchestrator/conversation_memory_compactor.py`
- Modify: `d:/Edu_AI_1/Edu_AI/api/Edu_AI/app/chat/orchestrator/conversation_memory_extractor_v2.py`

- [ ] **Step 1: Add minimal compactor implementation**

Implement a new compactor that:
- tracks `turn_count`
- decides compaction on every 4th turn or workflow/generate turns
- cleans workflow residue from `current_topics`
- drops stale `继续对话` when current derived goal is resource generation
- returns cleaned memory plus `conversation_memory_meta`

- [ ] **Step 2: Wire extractor to run compactor after assembling merged memory**

Run compactor at the end of `build_state_patch(...)` and include:
- `conversation_memory`
- `conversation_memory_meta`

- [ ] **Step 3: Re-run focused tests**

Run:
```bash
pytest d:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_conversation_memory_compactor.py -q
```

Expected: PASS

### Task 3: Run regression verification

**Files:**
- Test: `d:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat`

- [ ] **Step 1: Run focused memory-related regression**

Run:
```bash
pytest d:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_conversation_memory_phase2.py d:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_message_kind_layering.py d:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat/test_generation_context_relevance.py -q
```

Expected: PASS

- [ ] **Step 2: Run full chat regression**

Run:
```bash
pytest d:/Edu_AI_1/Edu_AI/api/Edu_AI/tests/chat -q
```

Expected: PASS

