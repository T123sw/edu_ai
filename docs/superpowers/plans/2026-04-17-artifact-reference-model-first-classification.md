# Artifact Reference Model-First Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current keyword-based artifact reference routing with a model-first classifier that decides whether a referenced artifact turn is discussion, edit, exit, or switch before the existing chat and edit runtimes execute.

**Architecture:** Add a compact `artifact_intent_classifier` module that uses the existing chat model interface to return strict JSON with `action`, `confidence`, and optional `target_hint`. `ReplyServiceV2` will call this classifier before the current artifact edit branch, treat low-confidence or malformed responses as discussion, and keep using the existing report and PPT edit runtimes as the execution layer. Existing frontend state sync remains in place and does not need new behavior for this phase.

**Tech Stack:** Python, pytest, existing chat model gateway / fallback LLM, current `ReplyServiceV2`, existing report and PPT edit runtimes

---

## File Structure

### New files

- `Edu_AI/api/Edu_AI/app/chat/orchestrator/artifact_intent_classifier.py`
  Responsibility: build compact artifact context, call the model, parse strict JSON, validate action/confidence, and return a normalized classifier result with safe fallback metadata.

- `Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py`
  Responsibility: unit-test the classifier in isolation, including valid JSON, fenced JSON, invalid JSON, model exception, and low-confidence fallback cases.

### Modified files

- `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
  Responsibility: replace `resolve_artifact_context(...)` usage with the classifier, preserve state-clearing behavior for `exit_artifact_context`, and keep report/PPT runtime dispatch unchanged after classification.

- `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py`
  Responsibility: update service-level tests so discussion, edit, exit, and malformed-classifier fallback behavior are asserted through the reply service.

- `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py`
  Responsibility: verify PPT references still route into `PptEditRuntime` when the classifier returns `edit_current_artifact`, and do not route there when the classifier returns `discuss_current_artifact`.

### No code changes expected in this phase

- `Edu_AI/src/components/teacher/ChatPanel.tsx`
- `Edu_AI/src/services/teacher/chatV2.ts`

Reason: frontend state sync was already implemented in the previous iteration, and the response contract for persisted `state` does not change in this phase.

## Task 1: Add the failing classifier tests

**Files:**
- Create: `Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py`

- [ ] **Step 1: Write the failing unit tests for strict JSON parsing and fallback**

```python
from types import SimpleNamespace

from app.chat.orchestrator.artifact_intent_classifier import classify_artifact_intent


class DummyModel:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(content=self.response)


def _snapshot():
    return SimpleNamespace(
        active_artifact={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        recent_messages=[
            {"role": "user", "content": "把这份报告加到对话"},
            {"role": "assistant", "content": "已加入当前对话上下文"},
        ],
    )


def test_classifier_returns_edit_action_from_valid_json():
    model = DummyModel(response='{"action":"edit_current_artifact","confidence":"high","reason":"user asks for rewrite"}')

    result = classify_artifact_intent(
        question="把第三部分扩写一下",
        request_reference={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        snapshot=_snapshot(),
        llm=model,
    )

    assert result.action == "edit_current_artifact"
    assert result.confidence == "high"
    assert result.source == "llm_json"


def test_classifier_treats_low_confidence_as_discussion():
    model = DummyModel(response='{"action":"edit_current_artifact","confidence":"low","reason":"uncertain"}')

    result = classify_artifact_intent(
        question="再展开一点",
        request_reference={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        snapshot=_snapshot(),
        llm=model,
    )

    assert result.action == "discuss_current_artifact"
    assert result.confidence == "low"
    assert result.source == "llm_low_confidence"


def test_classifier_treats_invalid_json_as_discussion():
    model = DummyModel(response="not-json")

    result = classify_artifact_intent(
        question="把第三部分扩写一下",
        request_reference={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        snapshot=_snapshot(),
        llm=model,
    )

    assert result.action == "discuss_current_artifact"
    assert result.source == "fallback_invalid_json"


def test_classifier_rejects_switch_without_new_request_reference():
    model = DummyModel(response='{"action":"switch_artifact","confidence":"high","reason":"switch"}')

    result = classify_artifact_intent(
        question="改这个新的",
        request_reference={"artifact_id": "report-1", "artifact_type": "report", "title": "李白性格分析"},
        snapshot=_snapshot(),
        llm=model,
        has_new_reference=False,
    )

    assert result.action == "discuss_current_artifact"
    assert result.source == "fallback_invalid_switch"
```

- [ ] **Step 2: Run the new test file and verify it fails because the classifier module does not exist yet**

Run:

```powershell
d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `classify_artifact_intent`

- [ ] **Step 3: Commit the failing test skeleton**

```powershell
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 add Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 commit -m "test: add artifact intent classifier coverage"
```

## Task 2: Implement the model-first classifier

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/orchestrator/artifact_intent_classifier.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py`

- [ ] **Step 1: Write the minimal classifier implementation**

```python
from __future__ import annotations

import json
from dataclasses import dataclass


ALLOWED_ACTIONS = {
    "discuss_current_artifact",
    "edit_current_artifact",
    "switch_artifact",
    "exit_artifact_context",
}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


@dataclass(slots=True)
class ArtifactIntentDecision:
    action: str
    confidence: str
    reason: str = ""
    source: str = "fallback"
    clear_reference: bool = False
    target_hint: dict | None = None


def classify_artifact_intent(*, question, request_reference, snapshot, llm, has_new_reference=False):
    if request_reference is None and not getattr(snapshot, "active_artifact", None):
        return ArtifactIntentDecision(action="no_artifact", confidence="low", source="no_artifact")

    if llm is None:
        return ArtifactIntentDecision(action="discuss_current_artifact", confidence="low", source="fallback_no_llm")

    prompt = _build_prompt(question=question, request_reference=request_reference, snapshot=snapshot)
    try:
        raw = llm.invoke(prompt)
    except Exception as exc:
        return ArtifactIntentDecision(
            action="discuss_current_artifact",
            confidence="low",
            reason=str(exc),
            source="fallback_model_error",
        )

    payload = _parse_payload(getattr(raw, "content", raw))
    if payload is None:
        return ArtifactIntentDecision(action="discuss_current_artifact", confidence="low", source="fallback_invalid_json")

    action = str(payload.get("action") or "").strip()
    confidence = str(payload.get("confidence") or "").strip().lower()
    if action not in ALLOWED_ACTIONS or confidence not in ALLOWED_CONFIDENCE:
        return ArtifactIntentDecision(action="discuss_current_artifact", confidence="low", source="fallback_invalid_payload")
    if action == "switch_artifact" and not has_new_reference:
        return ArtifactIntentDecision(action="discuss_current_artifact", confidence="low", source="fallback_invalid_switch")
    if confidence != "high":
        return ArtifactIntentDecision(
            action="discuss_current_artifact",
            confidence=confidence,
            reason=str(payload.get("reason") or ""),
            source="llm_low_confidence",
        )

    return ArtifactIntentDecision(
        action=action,
        confidence=confidence,
        reason=str(payload.get("reason") or ""),
        source="llm_json",
        clear_reference=(action == "exit_artifact_context"),
        target_hint=payload.get("target_hint") if isinstance(payload.get("target_hint"), dict) else None,
    )
```

- [ ] **Step 2: Run classifier tests and verify they pass**

Run:

```powershell
d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py -q
```

Expected: PASS

- [ ] **Step 3: Commit the classifier implementation**

```powershell
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 add Edu_AI/api/Edu_AI/app/chat/orchestrator/artifact_intent_classifier.py Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 commit -m "feat: add model-first artifact intent classifier"
```

## Task 3: Integrate the classifier into `ReplyServiceV2`

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py`

- [ ] **Step 1: Update the service tests to inject a classifier and assert routing**

```python
def test_reply_service_uses_classifier_discussion_result_for_referenced_report_questions():
    orchestrator_calls = []
    report_calls = []

    class DummyClassifier:
        def classify(self, **kwargs):
            return SimpleNamespace(action="discuss_current_artifact", confidence="high", clear_reference=False)

    class DummyOrchestrator:
        def dispatch(self, request):
            orchestrator_calls.append(request.question)
            return {
                "message": {"role": "assistant", "content": "这是讨论"},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "chat.reply"},
                "workflow": None,
                "artifacts": [],
                "sources": [],
                "trace": {"path": "fast"},
            }

    class DummyReportEditRuntime:
        def run_from_request(self, *, request, snapshot, course_storage_manager):
            report_calls.append(request.question)
            return {}

    service = ReplyServiceV2(
        orchestrator=DummyOrchestrator(),
        report_edit_runtime=DummyReportEditRuntime(),
        artifact_intent_classifier=DummyClassifier(),
        conversation_store=SimpleNamespace(write_v2_result=lambda conversation_id, request, result: None),
        context_builder=SimpleNamespace(build=lambda request: SimpleNamespace(active_artifact={"artifact_id": "report-1"}, recent_messages=[])),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "chat"}),
        course_storage_manager=SimpleNamespace(),
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "chat.reply"
    assert orchestrator_calls == ["这份报告的核心观点是什么"]
    assert report_calls == []
```

- [ ] **Step 2: Run the focused service tests and verify they fail before integration**

Run:

```powershell
d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py -q
```

Expected: FAIL because `ReplyServiceV2` does not accept or use the classifier dependency yet

- [ ] **Step 3: Implement the reply-service integration**

```python
from app.chat.orchestrator.artifact_intent_classifier import classify_artifact_intent


class ReplyServiceV2:
    def __init__(
        self,
        *,
        orchestrator=None,
        orchestrator_factory=None,
        conversation_store=None,
        context_builder=None,
        status_card_builder=None,
        course_storage_manager=None,
        report_edit_runtime=None,
        ppt_edit_runtime=None,
        artifact_intent_classifier=None,
    ):
        self.artifact_intent_classifier = artifact_intent_classifier

    def _classify_artifact_intent(self, *, request, snapshot):
        request_reference = getattr(request, "artifact_reference", None)
        classifier = self.artifact_intent_classifier
        if classifier is not None and hasattr(classifier, "classify"):
            return classifier.classify(
                question=getattr(request, "question", ""),
                request_reference=request_reference,
                snapshot=snapshot,
                has_new_reference=_has_new_reference(request_reference, snapshot),
            )
        return classify_artifact_intent(
            question=getattr(request, "question", ""),
            request_reference=request_reference,
            snapshot=snapshot,
            llm=get_fallback_llm(),
            has_new_reference=_has_new_reference(request_reference, snapshot),
        )
```

Key routing behavior to preserve:

- `edit_current_artifact` still routes report references into `ReportEditRuntime`
- `edit_current_artifact` still routes PPT references into `PptEditRuntime`
- `discuss_current_artifact` stays on `orchestrator.dispatch`
- `exit_artifact_context` clears `request.artifact_reference` and writes the existing clear-state patch
- malformed / low-confidence classifier output never routes into an edit runtime

- [ ] **Step 4: Run the focused service tests and verify they pass**

Run:

```powershell
d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py -q
```

Expected: PASS

- [ ] **Step 5: Commit the reply-service integration**

```powershell
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 add Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 commit -m "feat: route artifact references with model-first classification"
```

## Task 4: Preserve state and regression coverage

**Files:**
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py`
- Modify: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py` if trace or state metadata needs to be exposed for assertions

- [ ] **Step 1: Add regression tests for exit-state clearing and invalid classifier fallback**

```python
def test_reply_service_clears_reference_when_classifier_returns_exit():
    service = ReplyServiceV2(
        orchestrator=DummyOrchestrator(),
        artifact_intent_classifier=SimpleNamespace(
            classify=lambda **kwargs: SimpleNamespace(
                action="exit_artifact_context",
                confidence="high",
                clear_reference=True,
            )
        ),
        conversation_store=adapter,
        context_builder=SimpleNamespace(build=lambda request: exit_snapshot),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "chat"}),
        course_storage_manager=SimpleNamespace(),
    )

    result = service.reply(payload)

    assert result["state"]["artifact_reference"] == {}
    assert result["state"]["active_artifact"] == {}


def test_reply_service_invalid_classifier_fallback_stays_on_chat_path():
    service = ReplyServiceV2(
        orchestrator=DummyOrchestrator(),
        report_edit_runtime=DummyReportEditRuntime(),
        artifact_intent_classifier=SimpleNamespace(
            classify=lambda **kwargs: SimpleNamespace(
                action="discuss_current_artifact",
                confidence="low",
                clear_reference=False,
            )
        ),
        conversation_store=SimpleNamespace(write_v2_result=lambda conversation_id, request, result: None),
        context_builder=SimpleNamespace(build=lambda request: chat_snapshot),
        status_card_builder=SimpleNamespace(build=lambda **kwargs: {"mode": "chat"}),
        course_storage_manager=SimpleNamespace(),
    )

    result = service.reply(payload)

    assert result["action"]["name"] == "chat.reply"
    assert report_calls == []
```

- [ ] **Step 2: Run the expanded backend regression suite**

Run:

```powershell
d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py Edu_AI/api/Edu_AI/tests/core/test_conversation_storage_artifact_reference.py -q
```

Expected: PASS

- [ ] **Step 3: Commit the regression coverage**

```powershell
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 add Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 commit -m "test: cover artifact classifier fallbacks and exit state"
```

## Task 5: Final verification

**Files:**
- Verify only; no planned code changes

- [ ] **Step 1: Run the final backend verification command**

```powershell
d:\github\edu_ai\Edu_AI\api\Edu_AI\.venv\Scripts\python.exe -m pytest Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py Edu_AI/api/Edu_AI/tests/core/test_conversation_storage_artifact_reference.py -q
```

Expected: all targeted backend tests pass

- [ ] **Step 2: Inspect the worktree diff**

Run:

```powershell
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 status --short
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 diff -- Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py Edu_AI/api/Edu_AI/app/chat/orchestrator/artifact_intent_classifier.py Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py
```

Expected: only the planned backend files changed for this phase

- [ ] **Step 3: Create the implementation summary commit**

```powershell
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 add Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py Edu_AI/api/Edu_AI/app/chat/orchestrator/artifact_intent_classifier.py Edu_AI/api/Edu_AI/tests/chat/test_artifact_intent_classifier.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_artifact_reference.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2_ppt_edit.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py
git -C d:\github\edu_ai\.worktrees\feature-new-feature-20260417 commit -m "feat: add model-first artifact reference routing"
```
