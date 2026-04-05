# Message Kind Layering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tag persisted conversation messages with a stable `message_kind` (`user_content`, `assistant_content`, `assistant_meta`, `workflow_control`, `workflow_result`) and make relevance selection skip non-semantic control/meta messages.

**Architecture:** Add lightweight message-kind tagging at persistence time, using the existing conversation-memory extractor’s source heuristics as the classifier. Keep message storage backward-compatible by defaulting untagged historical messages to role-based content kinds. Update generation-context relevance selection to exclude `workflow_control` and `assistant_meta` from scoring and fallback windows.

**Tech Stack:** Python, pytest, JSON conversation storage, conversation store adapter, generation context builder.

---

### Task 1: Add failing tests for message kind persistence and relevance filtering

**Files:**
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_message_kind_layering.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_generation_context_relevance.py`

- [ ] **Step 1: Write persistence tagging tests**

```python
def test_write_v2_result_tags_workflow_control_messages():
    adapter.write_v2_result(...)
    messages = storage.get_messages("conv-1")
    assert messages[0]["message_kind"] == "workflow_control"
    assert messages[1]["message_kind"] == "workflow_control"


def test_write_v2_result_tags_normal_chat_messages_as_content():
    adapter.write_v2_result(...)
    messages = storage.get_messages("conv-2")
    assert messages[0]["message_kind"] == "user_content"
    assert messages[1]["message_kind"] == "assistant_content"
```

- [ ] **Step 2: Write relevance-filtering tests**

```python
def test_generation_context_builder_skips_workflow_control_and_assistant_meta_messages():
    context = GenerationContextBuilder().build_for_resource(...)
    assert [item["content"] for item in context.recent_relevant_messages] == [
        "先看课堂参与度的问题",
        "后排学生走神比较明显",
    ]
```

- [ ] **Step 3: Run focused tests to verify failure**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_message_kind_layering.py Edu_AI/api/Edu_AI/tests/chat/test_generation_context_relevance.py -q`

Expected: FAIL because current persistence does not write `message_kind`, and relevance selection still includes control/meta messages.

### Task 2: Implement message kind tagging in storage and adapter

**Files:**
- Modify: `Edu_AI/api/Edu_AI/core/conversation_storage.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/persistence/conversation_store_adapter.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/conversation_memory_extractor_v2.py`

- [ ] **Step 1: Add public message-kind classification helpers**

```python
def classify_message_kind(self, *, role: str, text: str, workflow_type: str = "", action_name: str = "", artifacts: list[dict] | None = None) -> str:
    ...
```

- [ ] **Step 2: Extend storage append/normalize to preserve `message_kind`**

```python
def append_message(..., message_kind: Optional[str] = None):
    message = {..., "message_kind": message_kind or default_kind}
```

- [ ] **Step 3: Update adapter write path to classify both user and assistant messages**

```python
self.append_message(..., message_kind=user_kind)
self.append_message(..., message_kind=assistant_kind)
```

- [ ] **Step 4: Run focused persistence tests**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_message_kind_layering.py -q`

Expected: PASS

### Task 3: Use message kinds in relevance selection

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/generation_context_builder.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_generation_context_relevance.py`

- [ ] **Step 1: Filter non-semantic messages before scoring and fallback**

```python
def _is_semantic_message(self, message: dict) -> bool:
    return str(message.get("message_kind") or "") not in {"workflow_control", "assistant_meta"}
```

- [ ] **Step 2: Apply the filter both to scored candidates and fallback recent windows**

```python
messages = [msg for msg in raw_messages if self._is_semantic_message(msg)]
```

- [ ] **Step 3: Run focused relevance tests**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_generation_context_relevance.py -q`

Expected: PASS

### Task 4: Run full chat regression

**Files:**
- Modify: `Edu_AI/api/Edu_AI/docs/superpowers/plans/2026-04-05-message-kind-layering-implementation.md`

- [ ] **Step 1: Run the focused layering suite**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat/test_message_kind_layering.py Edu_AI/api/Edu_AI/tests/chat/test_generation_context_relevance.py -q`

Expected: PASS

- [ ] **Step 2: Run the full chat suite**

Run: `pytest Edu_AI/api/Edu_AI/tests/chat -q`

Expected: PASS

- [ ] **Step 3: Record verification results in handoff notes**

```markdown
- Focused message-kind suite: `X passed`
- Full `tests/chat`: `Y passed`
- Residual warnings: existing `jieba/pkg_resources` and `.pytest_cache` warnings only
```
