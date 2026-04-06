# Fact Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fact lifecycle so user corrections retract stale facts and prevent them from leaking into status cards and report generation.

**Architecture:** Keep the existing layered memory model, but enrich `user_claims` with correction-aware status transitions. Project `confirmed_facts` only from active user claims or supported external evidence, and teach downstream readers to ignore retracted claims.

**Tech Stack:** Python, pytest, FastAPI chat orchestration layer

---

### Task 1: Lock the expected behavior with failing tests

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_conversation_fact_layering.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_generation_context_builder.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_status_card_builder.py`

- [ ] **Step 1: Write the failing extractor test**

```python
def test_extractor_retracts_previous_user_claim_when_user_corrects_fact():
    extractor = ConversationMemoryExtractor()

    first_patch = extractor.build_state_patch(
        request=_request("前10分钟学生多次走神"),
        result={"message": {"content": "这说明课堂导入阶段吸引力不足。"}, "action": {"name": "chat.reply"}},
        existing_state={},
        recent_messages=[],
    )

    second_patch = extractor.build_state_patch(
        request=_request("不是前10分钟，是后10分钟学生多次走神"),
        result={"message": {"content": "已按更正后的观察继续分析。"}, "action": {"name": "chat.reply"}},
        existing_state=first_patch,
        recent_messages=[],
    )

    memory = second_patch["conversation_memory"]

    assert memory["confirmed_facts"] == ["后10分钟学生多次走神"]
    assert any(item["content"] == "前10分钟学生多次走神" and item["status"] == "retracted" for item in memory["user_claims"])
```

- [ ] **Step 2: Run the extractor test and verify RED**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_conversation_fact_layering.py -k retracts_previous_user_claim -v`

Expected: `FAILED` because the extractor currently keeps both claims active.

- [ ] **Step 3: Write the failing generation-context test**

```python
def test_generation_context_builder_ignores_retracted_user_claims():
    memory = {
        "user_claims": [
            {"content": "前10分钟学生多次走神", "status": "retracted"},
            {"content": "后10分钟学生多次走神", "status": "stated"},
        ],
        "confirmed_facts": ["前10分钟学生多次走神", "后10分钟学生多次走神"],
    }

    assert GenerationContextBuilder._project_confirmed_facts(memory) == ["后10分钟学生多次走神"]
```

- [ ] **Step 4: Run the generation-context test and verify RED**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py -k ignores_retracted_user_claims -v`

Expected: `FAILED` because the projection currently includes all user claims.

- [ ] **Step 5: Write the failing status-card test**

```python
def test_status_card_builder_hides_retracted_claims():
    snapshot = ConversationSnapshot(
        conversation_id="conv-fact-lifecycle",
        summary="",
        conversation_memory={
            "user_claims": [
                {"content": "前10分钟学生多次走神", "status": "retracted"},
                {"content": "后10分钟学生多次走神", "status": "stated"},
            ],
            "confirmed_facts": ["前10分钟学生多次走神", "后10分钟学生多次走神"],
        },
        active_context={},
        capability=CapabilityPolicy(),
    )

    card = StatusCardBuilder().build(snapshot=snapshot, workflow=None, capability=snapshot.capability)

    assert card.confirmed_facts == ["后10分钟学生多次走神"]
```

- [ ] **Step 6: Run the status-card test and verify RED**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_status_card_builder.py -k hides_retracted_claims -v`

Expected: `FAILED` because the status card currently displays all claims.

### Task 2: Implement fact lifecycle in the extractor

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/conversation_memory_extractor_v2.py`

- [ ] **Step 1: Add correction detection helpers**

```python
_CORRECTION_PREFIXES = ("不是", "不对", "更准确地说", "刚才说错了", "应改为", "改成")

def _looks_like_correction(self, text: str) -> bool:
    normalized = self._clean_clause(text)
    return any(normalized.startswith(prefix) for prefix in self._CORRECTION_PREFIXES) or ("不是" in normalized and "是" in normalized)
```

- [ ] **Step 2: Mark stale claims as retracted when a correction arrives**

```python
def _apply_claim_retractions(self, *, question: str, existing_claims: list[dict], new_claims: list[dict]) -> list[dict]:
    if not self._looks_like_correction(question) or not new_claims:
        return list(existing_claims or [])

    updated = []
    new_contents = {str(item.get("content") or "").strip() for item in new_claims}
    for item in list(existing_claims or []):
        content = str((item or {}).get("content") or "").strip()
        if content and content not in new_contents and str((item or {}).get("status") or "").strip() != "retracted":
            updated.append({**item, "status": "retracted"})
        else:
            updated.append(item)
    return updated
```

- [ ] **Step 3: Use only active claims when projecting confirmed facts**

```python
if str((item or {}).get("status") or "").strip() == "retracted":
    continue
```

- [ ] **Step 4: Run extractor tests and verify GREEN**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_conversation_fact_layering.py -v`

Expected: all extractor tests pass.

### Task 3: Update downstream projections

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/generation_context_builder.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/orchestrator/status_card_builder.py`

- [ ] **Step 1: Ignore retracted claims in generation-context projection**

```python
if str((item or {}).get("status") or "").strip() == "retracted":
    continue
```

- [ ] **Step 2: Ignore retracted claims in status-card fact selection**

```python
if isinstance(item, dict) and str(item.get("status") or "").strip() == "retracted":
    continue
```

- [ ] **Step 3: Run focused downstream tests and verify GREEN**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_status_card_builder.py -v`

Expected: both suites pass with the corrected fact projection.

### Task 4: Run regression coverage

**Files:**
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_report_context_handoff_regressions.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_generation_context_relevance.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_report_workflow_runtime_context.py`

- [ ] **Step 1: Run the targeted regression bundle**

Run: `d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_conversation_fact_layering.py d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_status_card_builder.py d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_report_context_handoff_regressions.py d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_relevance.py d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_report_workflow_runtime_context.py -v`

Expected: all tests pass and no retracted fact leaks into report handoff or status-card display.

- [ ] **Step 2: Commit**

```bash
git -C d:\github\edu_ai add \
  d:\github\edu_ai\docs\superpowers\plans\2026-04-06-fact-lifecycle.md \
  d:\github\edu_ai\Edu_AI\api\Edu_AI\app\chat\orchestrator\conversation_memory_extractor_v2.py \
  d:\github\edu_ai\Edu_AI\api\Edu_AI\app\chat\orchestrator\generation_context_builder.py \
  d:\github\edu_ai\Edu_AI\api\Edu_AI\app\chat\orchestrator\status_card_builder.py \
  d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_conversation_fact_layering.py \
  d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_generation_context_builder.py \
  d:\github\edu_ai\Edu_AI\api\Edu_AI\tests\chat\test_status_card_builder.py
git -C d:\github\edu_ai commit -m "feat: add fact lifecycle retraction guards"
```
