# Quiz Workflow Context-Driven Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a chat-v2-only quiz workflow that inherits conversation context, asks only for critical gaps, soft-confirms the inferred quiz settings, and generates a final quiz artifact directly.

**Architecture:** Reuse the existing report and lesson-plan workflow skeleton: `GenerationContextBuilder` feeds a new quiz assembler, organizer, readiness judge, and workflow runtime. The runtime owns the soft-confirm state machine and delegates final question generation to a small `QuizGenerator` that can optionally enrich prompts with RAG over selected docs before writing a completed `quiz` artifact back through `ReplyServiceV2`.

**Tech Stack:** Python, FastAPI, Pydantic, existing chat v2 orchestrator/workflow framework, pytest

---

## File Map

**Create:**

- `backend/src/app/chat/domain/quiz_preparation.py`
  Defines `QuizContextSummary` and `QuizPreparationResult`.
- `backend/src/app/chat/orchestrator/quiz_context_organizer.py`
  LLM-backed quiz preparation organizer with deterministic fallback.
- `backend/src/app/chat/orchestrator/quiz_readiness_judge.py`
  Quiz-specific “ask gap vs soft confirm” rules.
- `backend/src/app/chat/workflows/quiz/__init__.py`
  Package marker for the new workflow.
- `backend/src/app/chat/workflows/quiz/assembler.py`
  Reduces `GenerationContext` into quiz-oriented slot hints and source summaries.
- `backend/src/app/chat/workflows/quiz/generator.py`
  Builds the quiz prompt, optionally enriches with RAG, parses JSON, and normalizes the final artifact payload.
- `backend/src/app/chat/workflows/quiz/runtime.py`
  Handles quiz soft-confirm, resume, and final generation.
- `backend/src/tests/chat/test_quiz_context_organizer.py`
- `backend/src/tests/chat/test_quiz_readiness_judge.py`
- `backend/src/tests/chat/test_quiz_generator.py`
- `backend/src/tests/chat/test_quiz_workflow_runtime.py`
- `backend/src/tests/chat/test_quiz_route_rules.py`
- `backend/src/tests/chat/test_quiz_reply_service_v2.py`
- `backend/src/tests/chat/test_quiz_routes_v2.py`

**Modify:**

- `backend/src/app/chat/orchestrator/route_rules.py`
  Add explicit quiz routing and quiz follow-up detection.
- `backend/src/app/chat/application/reply_service_v2.py`
  Register the quiz runtime and persist completed quiz artifacts into course storage.
- `backend/src/app/chat/api/routes_v2.py`
  Ensure `/api/chat/v2/reply` error responses use `trace.path = "workflow"` for quiz workflow requests.

No change is required in `schemas_v2.py`, `status_card_label_mapper.py`, or `conversation_store_adapter.py` if the quiz runtime emits `workflow.filled_slots` directly and keeps using the generic `quiz` workflow name already recognized by the status-card label mapper.

### Task 1: Add Quiz Preparation Models, Assembler, Organizer, and Judge

**Files:**
- Create: `backend/src/app/chat/domain/quiz_preparation.py`
- Create: `backend/src/app/chat/workflows/quiz/__init__.py`
- Create: `backend/src/app/chat/workflows/quiz/assembler.py`
- Create: `backend/src/app/chat/orchestrator/quiz_context_organizer.py`
- Create: `backend/src/app/chat/orchestrator/quiz_readiness_judge.py`
- Test: `backend/src/tests/chat/test_quiz_context_organizer.py`
- Test: `backend/src/tests/chat/test_quiz_readiness_judge.py`

- [ ] **Step 1: Write the failing organizer and judge tests**

```python
from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.quiz_context_organizer import QuizContextOrganizer
from app.chat.orchestrator.quiz_readiness_judge import QuizReadinessJudge
from app.chat.domain.quiz_preparation import QuizPreparationResult, QuizContextSummary


def test_quiz_context_organizer_extracts_topic_count_types_and_defaults():
    context = GenerationContext(
        conversation_id="conv-quiz-1",
        resource_type="quiz",
        summary_text="二次函数复习",
        current_topics=["二次函数"],
        user_goals=["围绕易错点生成练习题"],
        confirmed_facts=["顶点式与一般式互化"],
        student_signals=["学生容易混淆开口方向与最值"],
        constraints={"audience": "初三", "difficulty": "medium"},
        source_scope={"from_summary": True, "from_memory": True},
    )

    result = QuizContextOrganizer().organize(
        context=context,
        request_question="围绕二次函数出 8 道填空题，带答案和解析",
        stored_slots={},
    )

    assert result.quiz_intent == "generate_quiz"
    assert result.topic == "二次函数"
    assert result.question_count == 8
    assert result.question_types == ["blank"]
    assert result.include_answers is True
    assert result.include_explanations is True


def test_quiz_context_organizer_reuses_stored_topic_when_adjustment_only_changes_type():
    context = GenerationContext(
        conversation_id="conv-quiz-2",
        resource_type="quiz",
        summary_text="",
    )

    result = QuizContextOrganizer().organize(
        context=context,
        request_question="改成 5 道选择题",
        stored_slots={"topic": "牛顿第二定律", "question_count": "10", "question_types": "blank"},
    )

    assert result.topic == "牛顿第二定律"
    assert result.question_count == 5
    assert result.question_types == ["choice"]


def test_quiz_readiness_judge_asks_for_topic_when_missing():
    judge = QuizReadinessJudge()
    result = QuizPreparationResult(
        quiz_intent="generate_quiz",
        topic=None,
        quiz_context_summary=QuizContextSummary(),
    )

    decision = judge.judge(result, entry_mode="reply")

    assert decision["action"] == "ask_critical_gap"
    assert decision["missing_critical_fields"] == ["topic"]


def test_quiz_readiness_judge_returns_strong_soft_confirm_when_topic_and_basis_exist():
    judge = QuizReadinessJudge()
    result = QuizPreparationResult(
        quiz_intent="generate_quiz",
        topic="二次函数",
        question_count=10,
        question_types=["choice", "blank"],
        difficulty="medium",
        soft_confirm_message="我将围绕二次函数生成 10 道题，可以开始吗？",
        quiz_context_summary=QuizContextSummary(topic_summary="二次函数复习"),
    )

    decision = judge.judge(result, entry_mode="reply")

    assert decision["action"] == "strong_soft_confirm"
    assert "二次函数" in decision["soft_confirm_message"]
```

- [ ] **Step 2: Run the new preparation tests to verify they fail**

Run: `python -m pytest backend/src/tests/chat/test_quiz_context_organizer.py backend/src/tests/chat/test_quiz_readiness_judge.py -q`

Expected: `4 passed` does not appear yet; imports should fail because the quiz preparation modules do not exist.

- [ ] **Step 3: Implement the quiz preparation models, assembler, organizer, and judge**

```python
# backend/src/app/chat/domain/quiz_preparation.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QuizContextSummary(BaseModel):
    topic_summary: str = ""
    learner_summary: str = ""
    focus_summary: str = ""
    knowledge_points: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    source_scope: list[str] = Field(default_factory=list)


class QuizPreparationResult(BaseModel):
    quiz_intent: str = "unclear"
    topic: str | None = None
    audience: str | None = None
    objective: str | None = None
    difficulty: str | None = None
    question_count: int | None = None
    question_types: list[str] = Field(default_factory=list)
    include_answers: bool = True
    include_explanations: bool = True
    knowledge_points: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    style_constraints: list[str] = Field(default_factory=list)
    preparation_source: str = "fallback"
    preparation_model: str = ""
    quiz_context_summary: QuizContextSummary = Field(default_factory=QuizContextSummary)
    source_scope: dict[str, bool] = Field(default_factory=dict)
    missing_critical_fields: list[str] = Field(default_factory=list)
    confidence: str = "low"
    soft_confirm_message: str = ""
    followup_candidates: list[str] = Field(default_factory=list)
```

```python
# backend/src/app/chat/workflows/quiz/assembler.py
from __future__ import annotations

import re
from typing import Any

from app.chat.domain.generation_context import GenerationContext

_COUNT_PATTERN = re.compile(r"(?P<count>\d{1,3})\s*(道|题)")
_TYPE_MARKERS = {
    "choice": ("选择题", "单选题", "单选"),
    "blank": ("填空题", "填空"),
    "short": ("简答题", "简答"),
}


class QuizAssembler:
    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _extract_question_count(self, text: str) -> int | None:
        match = _COUNT_PATTERN.search(self._clean(text))
        if not match:
            return None
        return int(match.group("count"))

    def _extract_question_types(self, text: str) -> list[str]:
        normalized = self._clean(text)
        result: list[str] = []
        for kind, markers in _TYPE_MARKERS.items():
            if any(marker in normalized for marker in markers):
                result.append(kind)
        return result

    def from_generation_context(self, context: GenerationContext) -> dict[str, Any]:
        latest_user = ""
        for message in reversed(list(context.recent_relevant_messages or [])):
            if self._clean((message or {}).get("role")) == "user":
                latest_user = self._clean((message or {}).get("content"))
                break

        constraints = dict(context.constraints or {})
        topic = next((item for item in list(context.current_topics or []) if self._clean(item)), "") or self._clean(context.summary_text)
        question_types = self._extract_question_types(latest_user)
        question_count = self._extract_question_count(latest_user)

        return {
            "summary": context.summary_text,
            "current_topics": list(context.current_topics or []),
            "user_goals": list(context.user_goals or []),
            "confirmed_facts": list(context.confirmed_facts or []),
            "constraints": constraints,
            "teaching_issues": list(context.teaching_issues or []),
            "student_signals": list(context.student_signals or []),
            "evidence_points": list(context.evidence_points or []),
            "recent_messages": list(context.recent_relevant_messages or []),
            "source_scope": dict(context.source_scope or {}),
            "slot_hints": {
                "topic": topic,
                "audience": self._clean(constraints.get("audience") or constraints.get("target_audience")),
                "objective": self._clean(constraints.get("objective")),
                "difficulty": self._clean(constraints.get("difficulty")),
                "question_count": question_count,
                "question_types": question_types,
            },
        }
```

```python
# backend/src/app/chat/orchestrator/quiz_context_organizer.py
from __future__ import annotations

import re
from typing import Any

from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.quiz_preparation import QuizContextSummary, QuizPreparationResult
from app.chat.workflows.quiz.assembler import QuizAssembler


class QuizContextOrganizer:
    _LOW_SIGNAL = {"", "习题", "练习题", "出题", "quiz", "生成题目"}
    _COUNT_PATTERN = re.compile(r"(?P<count>\d{1,3})\s*(道|题)")

    def __init__(self, *, llm: Any | None = None, assembler: QuizAssembler | None = None):
        self.llm = llm
        self.assembler = assembler or QuizAssembler()

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _extract_question_types(self, text: str) -> list[str]:
        normalized = self._clean(text)
        result: list[str] = []
        if any(token in normalized for token in ("选择题", "单选题", "单选")):
            result.append("choice")
        if any(token in normalized for token in ("填空题", "填空")):
            result.append("blank")
        if any(token in normalized for token in ("简答题", "简答")):
            result.append("short")
        return result

    def _extract_question_count(self, text: str) -> int | None:
        match = self._COUNT_PATTERN.search(self._clean(text))
        return int(match.group("count")) if match else None

    def _fallback_prepare(self, *, context: GenerationContext, request_question: str, stored_slots: dict[str, str]) -> QuizPreparationResult:
        assembled = self.assembler.from_generation_context(context)
        slot_hints = dict(assembled.get("slot_hints") or {})
        topic = self._clean(slot_hints.get("topic") or stored_slots.get("topic"))
        if not topic:
            question = self._clean(request_question)
            if question.lower() not in self._LOW_SIGNAL:
                topic = question

        question_types = self._extract_question_types(request_question) or [
            item for item in self._clean(stored_slots.get("question_types")).split("|") if item
        ] or list(slot_hints.get("question_types") or []) or ["choice"]
        question_count = (
            self._extract_question_count(request_question)
            or int(self._clean(stored_slots.get("question_count") or 0) or 0)
            or slot_hints.get("question_count")
            or 10
        )

        normalized_question = self._clean(request_question)
        difficulty = self._clean(slot_hints.get("difficulty") or stored_slots.get("difficulty")) or "medium"
        if "基础" in normalized_question or "简单" in normalized_question:
            difficulty = "low"
        elif "提高" in normalized_question or "较难" in normalized_question:
            difficulty = "high"

        include_answers = "不要答案" not in normalized_question
        include_explanations = "不要解析" not in normalized_question
        weak_points = [self._clean(item) for item in list(context.student_signals or []) if self._clean(item)]
        knowledge_points = [self._clean(item) for item in list(context.confirmed_facts or []) if self._clean(item)]
        source_scope = {
            "from_conversation": bool((context.source_scope or {}).get("from_memory") or (context.source_scope or {}).get("from_recent_messages")),
            "from_docs": bool((context.source_scope or {}).get("from_docs")),
            "from_course": bool(context.current_course_id),
            "from_artifacts": bool((context.source_scope or {}).get("from_artifacts")),
        }
        summary = QuizContextSummary(
            topic_summary=self._clean(context.summary_text or topic),
            learner_summary=self._clean(slot_hints.get("audience") or stored_slots.get("audience")),
            focus_summary="、".join(weak_points[:2] or knowledge_points[:2]),
            knowledge_points=knowledge_points[:4],
            weak_points=weak_points[:4],
            constraints=dict(context.constraints or {}),
            source_scope=[key for key, enabled in source_scope.items() if enabled],
        )
        soft_confirm_message = (
            f"我将基于当前对话内容，围绕{topic}，按{difficulty}难度生成 {question_count} 道"
            f"{'、'.join(question_types)}练习，并附答案与解析，可以直接开始吗？"
            if topic
            else ""
        )
        return QuizPreparationResult(
            quiz_intent="generate_quiz" if any(token in normalized_question for token in ("习题", "练习题", "测验", "出题", "quiz")) or "练习" in " ".join(context.user_goals or []) else "unclear",
            topic=topic or None,
            audience=self._clean(slot_hints.get("audience") or stored_slots.get("audience")) or None,
            objective=self._clean(slot_hints.get("objective") or stored_slots.get("objective")) or None,
            difficulty=difficulty,
            question_count=question_count,
            question_types=question_types,
            include_answers=include_answers,
            include_explanations=include_explanations,
            knowledge_points=knowledge_points[:6],
            weak_points=weak_points[:6],
            preparation_source="fallback",
            preparation_model="",
            quiz_context_summary=summary,
            source_scope=source_scope,
            missing_critical_fields=[] if topic else ["topic"],
            confidence="high" if topic and (knowledge_points or weak_points) else "medium" if topic else "low",
            soft_confirm_message=soft_confirm_message,
            followup_candidates=["你希望围绕哪个知识点出题？"] if not topic else [],
        )

    def organize(self, *, context: GenerationContext, request_question: str, stored_slots: dict[str, str]) -> QuizPreparationResult:
        return self._fallback_prepare(
            context=context,
            request_question=request_question,
            stored_slots=stored_slots,
        )
```

```python
# backend/src/app/chat/orchestrator/quiz_readiness_judge.py
from __future__ import annotations

from app.chat.domain.quiz_preparation import QuizPreparationResult


class QuizReadinessJudge:
    def _has_generation_basis(self, result: QuizPreparationResult) -> bool:
        if result.difficulty:
            return True
        if len(list(result.question_types or [])) >= 1:
            return True
        if result.question_count:
            return True
        if len(list(result.knowledge_points or [])) >= 1:
            return True
        if len(list(result.weak_points or [])) >= 1:
            return True
        if str(result.quiz_context_summary.topic_summary or "").strip():
            return True
        return False

    def judge(self, result: QuizPreparationResult, *, entry_mode: str) -> dict:
        if not str(result.topic or "").strip():
            return {
                "action": "ask_critical_gap",
                "question": "你希望围绕哪个知识点或主题出题？",
                "missing_critical_fields": ["topic"],
            }

        if self._has_generation_basis(result):
            action = "weak_soft_confirm" if str(entry_mode or "").strip().lower() == "button" else "strong_soft_confirm"
            return {
                "action": action,
                "question": "",
                "missing_critical_fields": [],
                "soft_confirm_message": str(result.soft_confirm_message or "").strip(),
            }

        return {
            "action": "ask_critical_gap",
            "question": "你更希望我先确定题型、题量还是难度？",
            "missing_critical_fields": ["generation_basis"],
        }
```

- [ ] **Step 4: Run the preparation tests to verify they pass**

Run: `python -m pytest backend/src/tests/chat/test_quiz_context_organizer.py backend/src/tests/chat/test_quiz_readiness_judge.py -q`

Expected: `4 passed`

- [ ] **Step 5: Commit the preparation layer**

```bash
git add backend/src/app/chat/domain/quiz_preparation.py backend/src/app/chat/workflows/quiz/__init__.py backend/src/app/chat/workflows/quiz/assembler.py backend/src/app/chat/orchestrator/quiz_context_organizer.py backend/src/app/chat/orchestrator/quiz_readiness_judge.py backend/src/tests/chat/test_quiz_context_organizer.py backend/src/tests/chat/test_quiz_readiness_judge.py
git commit -m "feat: add quiz preparation layer"
```

### Task 2: Implement Quiz Generator and Workflow Runtime

**Files:**
- Create: `backend/src/app/chat/workflows/quiz/generator.py`
- Create: `backend/src/app/chat/workflows/quiz/runtime.py`
- Test: `backend/src/tests/chat/test_quiz_generator.py`
- Test: `backend/src/tests/chat/test_quiz_workflow_runtime.py`

- [ ] **Step 1: Write the failing generator and runtime tests**

```python
from types import SimpleNamespace

from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.contracts import ChatRequestV2
from app.chat.workflows.quiz.generator import QuizGenerator
from app.chat.workflows.quiz.runtime import QuizWorkflowRuntime


def test_quiz_generator_normalizes_llm_json_into_artifact_shape():
    class DummyLLM:
        def invoke(self, messages):
            return """
            {
              "questions": [
                {
                  "id": 1,
                  "type": "选择题",
                  "difficulty": "中",
                  "content": "二次函数 y=x^2 的顶点坐标是（ ）。",
                  "options": ["A. (0,0)", "B. (1,0)", "C. (0,1)", "D. (1,1)"],
                  "answer": "A",
                  "analysis": "顶点式可直接读出顶点。"
                }
              ]
            }
            """

    generator = QuizGenerator(llm=DummyLLM(), rag_fetcher=lambda **kwargs: {"ok": True, "payload": {"answer": ""}})
    artifact = generator.generate(
        preparation={
            "topic": "二次函数",
            "difficulty": "medium",
            "question_count": 1,
            "question_types": ["choice"],
            "include_answers": True,
            "include_explanations": True,
            "knowledge_points": ["图像与性质"],
            "weak_points": ["顶点坐标"],
        },
        context_summary="二次函数复习",
        conversation_id="conv-quiz-1",
        owner="teacher-a",
        allow_rag=False,
        selected_doc_ids=[],
    )

    assert artifact["artifact_type"] == "quiz"
    assert artifact["content"]["questions"][0]["type"] == "choice"
    assert artifact["content"]["questions"][0]["stem"].startswith("二次函数")


def test_quiz_workflow_runtime_returns_soft_confirm_before_generation():
    class StubOrganizer:
        def organize(self, *, context, request_question, stored_slots):
            return SimpleNamespace(
                model_dump=lambda exclude_none=True: {
                    "quiz_intent": "generate_quiz",
                    "topic": "二次函数",
                    "difficulty": "medium",
                    "question_count": 8,
                    "question_types": ["choice", "blank"],
                    "include_answers": True,
                    "include_explanations": True,
                    "knowledge_points": ["图像与性质"],
                    "weak_points": ["最值"],
                    "soft_confirm_message": "我将围绕二次函数生成 8 道题，可以开始吗？",
                },
                topic="二次函数",
                difficulty="medium",
                question_count=8,
                question_types=["choice", "blank"],
                include_answers=True,
                include_explanations=True,
                knowledge_points=["图像与性质"],
                weak_points=["最值"],
                soft_confirm_message="我将围绕二次函数生成 8 道题，可以开始吗？",
            )

    class StubJudge:
        def judge(self, result, *, entry_mode):
            return {"action": "strong_soft_confirm", "soft_confirm_message": result.soft_confirm_message, "missing_critical_fields": []}

    class StubGenerator:
        def generate(self, **kwargs):
            raise AssertionError("generator should not run before soft confirm resume")

    runtime = QuizWorkflowRuntime(
        quiz_context_organizer=StubOrganizer(),
        quiz_readiness_judge=StubJudge(),
        quiz_generator=StubGenerator(),
    )

    result = runtime.run(
        request=ChatRequestV2(question="根据以上内容生成练习题", conversation_id="conv-quiz-2"),
        snapshot=ConversationSnapshot(conversation_id="conv-quiz-2"),
        decision=None,
    )

    assert result["workflow"]["status"] == "awaiting_confirm"
    assert result["workflow"]["stage"] == "soft_confirm"
    assert result["message"]["content"].startswith("我将围绕二次函数")


def test_quiz_workflow_runtime_resumes_generation_after_soft_confirm():
    class StubGenerator:
        def generate(self, **kwargs):
            return {
                "artifact_id": "conv-quiz-3:quiz",
                "artifact_type": "quiz",
                "title": "二次函数-练习.json",
                "content": {
                    "title": "二次函数练习",
                    "difficulty": "medium",
                    "question_type": "mixed",
                    "questions": [{"id": "1", "type": "choice", "stem": "题目", "options": ["A", "B", "C", "D"], "answer": "A", "explanation": "解析"}],
                },
                "generation_state": {"status": "completed", "generation_mode": "initial", "source_scope": {"from_conversation": True}},
            }

    runtime = QuizWorkflowRuntime(quiz_generator=StubGenerator())
    snapshot = ConversationSnapshot(
        conversation_id="conv-quiz-3",
        workflow_state={
            "workflow_id": "conv-quiz-3",
            "workflow_type": "quiz",
            "status": "awaiting_confirm",
            "stage": "soft_confirm",
            "filled_slots": {
                "topic": "二次函数",
                "difficulty": "medium",
                "question_count": "8",
                "question_types": "choice|blank",
                "include_answers": "true",
                "include_explanations": "true",
            },
        },
        active_context={"active_workflow_type": "quiz", "active_workflow_status": "awaiting_confirm"},
    )

    result = runtime.run(
        request=ChatRequestV2(question="可以", conversation_id="conv-quiz-3"),
        snapshot=snapshot,
        decision=None,
    )

    assert result["workflow"]["status"] == "completed"
    assert result["artifacts"][0]["artifact_type"] == "quiz"
    assert result["message"]["content"] == "已生成，请在右侧查看。"
```

- [ ] **Step 2: Run the runtime tests to verify they fail**

Run: `python -m pytest backend/src/tests/chat/test_quiz_generator.py backend/src/tests/chat/test_quiz_workflow_runtime.py -q`

Expected: `3 passed` does not appear yet; imports should fail because the quiz generator and runtime do not exist.

- [ ] **Step 3: Implement the generator and runtime**

```python
# backend/src/app/chat/workflows/quiz/generator.py
from __future__ import annotations

import json
from typing import Any, Callable

from app.chat.tools.agent_tools import rag_search_tool


class QuizGenerator:
    def __init__(self, *, llm: Any | None = None, rag_fetcher: Callable[..., dict] | None = None):
        self.llm = llm
        self.rag_fetcher = rag_fetcher or rag_search_tool

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _normalize_type(self, value: str) -> str:
        normalized = self._clean(value)
        if "选择" in normalized or normalized.lower() == "choice":
            return "choice"
        if "填空" in normalized or normalized.lower() == "blank":
            return "blank"
        if "简答" in normalized or normalized.lower() == "short":
            return "short"
        return "choice"

    def _parse_questions(self, raw: Any) -> list[dict[str, Any]]:
        text = getattr(raw, "content", raw)
        text = self._clean(text)
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("{") and candidate.endswith("}"):
                    text = candidate
                    break
        start = text.find("{")
        end = text.rfind("}")
        payload = json.loads(text[start : end + 1] if start >= 0 and end > start else text)
        questions = list(payload.get("questions") or [])
        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate(questions, start=1):
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": str(item.get("id") or idx),
                    "type": self._normalize_type(str(item.get("type") or "")),
                    "stem": self._clean(item.get("content") or item.get("stem")),
                    "options": item.get("options") or None,
                    "answer": self._clean(item.get("answer")),
                    "explanation": self._clean(item.get("analysis") or item.get("explanation")),
                }
            )
        return [item for item in normalized if item["stem"]]

    def generate(self, *, preparation: dict[str, Any], context_summary: str, conversation_id: str, owner: str | None, allow_rag: bool, selected_doc_ids: list[str]) -> dict[str, Any]:
        topic = self._clean(preparation.get("topic")) or "练习"
        rag_summary = ""
        if allow_rag and selected_doc_ids:
            rag_result = self.rag_fetcher(
                query=f"围绕{topic}整理出题所需的关键知识点、易错点和题面素材",
                top_k=6,
                selected_doc_ids=selected_doc_ids,
                owner=owner,
            )
            rag_summary = self._clean(((rag_result.get("payload") or {}).get("answer")))

        if self.llm is None:
            raise RuntimeError("quiz_generator_llm_unavailable")

        prompt = f"""
你是一名资深教学测评专家。请围绕 {topic} 生成 {int(preparation.get("question_count") or 10)} 道题。
题型：{",".join(list(preparation.get("question_types") or ['choice']))}
难度：{self._clean(preparation.get("difficulty") or 'medium')}
知识点：{",".join(list(preparation.get("knowledge_points") or []))}
薄弱点：{",".join(list(preparation.get("weak_points") or []))}
上下文摘要：{context_summary}
资料补充：{rag_summary}
只输出一个 JSON 对象：
{{
  "questions": [
    {{
      "id": 1,
      "type": "选择题|填空题|简答题",
      "difficulty": "低|中|高",
      "content": "题干",
      "options": ["A. 0", "B. 1", "C. -1", "D. 2"],
      "answer": "答案",
      "analysis": "解析"
    }}
  ]
}}
"""
        raw = self.llm.invoke(prompt)
        questions = self._parse_questions(raw)
        question_type = "mixed" if len({item["type"] for item in questions}) > 1 else (questions[0]["type"] if questions else "choice")
        return {
            "artifact_id": f"{conversation_id}:quiz",
            "artifact_type": "quiz",
            "title": f"{topic}-练习.json",
            "content": {
                "title": f"{topic}练习",
                "difficulty": self._clean(preparation.get("difficulty") or "medium"),
                "question_type": question_type,
                "questions": questions,
            },
            "generation_state": {
                "status": "completed",
                "generation_mode": "initial",
                "source_scope": dict(preparation.get("source_scope") or {}),
            },
        }
```

```python
# backend/src/app/chat/workflows/quiz/runtime.py
from __future__ import annotations

from typing import Any

from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.orchestrator.quiz_context_organizer import QuizContextOrganizer
from app.chat.orchestrator.quiz_readiness_judge import QuizReadinessJudge
from app.chat.workflows.quiz.assembler import QuizAssembler
from app.chat.workflows.quiz.generator import QuizGenerator


class QuizWorkflowRuntime:
    def __init__(
        self,
        *,
        generation_context_builder=None,
        quiz_assembler=None,
        quiz_context_organizer=None,
        quiz_readiness_judge=None,
        quiz_generator=None,
    ):
        self.generation_context_builder = generation_context_builder or GenerationContextBuilder()
        self.quiz_assembler = quiz_assembler or QuizAssembler()
        self.quiz_context_organizer = quiz_context_organizer or QuizContextOrganizer()
        self.quiz_readiness_judge = quiz_readiness_judge or QuizReadinessJudge()
        self.quiz_generator = quiz_generator or QuizGenerator()

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _stored_slots(self, snapshot) -> dict[str, str]:
        workflow_state = getattr(snapshot, "workflow_state", None) if snapshot is not None else None
        if hasattr(workflow_state, "model_dump"):
            workflow_state = workflow_state.model_dump()
        return {
            str(key): str(value)
            for key, value in dict((workflow_state or {}).get("filled_slots") or {}).items()
            if value not in (None, "")
        }

    def _is_affirmative(self, text: str) -> bool:
        normalized = self._clean(text).lower().strip("。！？,，；;: ")
        return normalized in {"可以", "继续", "确认", "确认并继续", "开始", "ok", "yes"}

    def _filled_slots(self, preparation: dict[str, Any]) -> dict[str, str]:
        return {
            "topic": self._clean(preparation.get("topic")),
            "audience": self._clean(preparation.get("audience")),
            "objective": self._clean(preparation.get("objective")),
            "difficulty": self._clean(preparation.get("difficulty") or "medium"),
            "question_count": str(preparation.get("question_count") or 10),
            "question_types": "|".join(list(preparation.get("question_types") or ["choice"])),
            "include_answers": str(bool(preparation.get("include_answers", True))).lower(),
            "include_explanations": str(bool(preparation.get("include_explanations", True))).lower(),
        }

    def run(self, *, request, snapshot, decision):
        capability = getattr(request, "capability", None)
        generation_context = GenerationContext(
            conversation_id=self._clean(getattr(request, "conversation_id", "")),
            resource_type="quiz",
        )
        if snapshot is not None:
            generation_context = self.generation_context_builder.build_for_resource(
                request=request,
                snapshot=snapshot,
                resource_type="quiz",
            )

        stored_slots = self._stored_slots(snapshot)
        preparation = self.quiz_context_organizer.organize(
            context=generation_context,
            request_question=request.question,
            stored_slots=stored_slots,
        )
        readiness = self.quiz_readiness_judge.judge(preparation, entry_mode="reply")
        workflow_state = getattr(snapshot, "workflow_state", None) if snapshot is not None else None
        workflow_dict = workflow_state.model_dump() if hasattr(workflow_state, "model_dump") else dict(workflow_state or {})
        stage = self._clean(workflow_dict.get("stage"))
        should_generate = stage == "soft_confirm" and self._is_affirmative(request.question)

        if readiness["action"] == "ask_critical_gap":
            return {
                "message": {"role": "assistant", "content": readiness["question"]},
                "conversation": {"conversation_id": self._clean(getattr(request, "conversation_id", ""))},
                "action": {"name": "generate.quiz"},
                "artifacts": [],
                "workflow": {
                    "type": "quiz",
                    "status": "awaiting_confirm",
                    "stage": "critical_gap",
                    "required_slots": readiness["missing_critical_fields"],
                    "filled_slots": self._filled_slots(preparation.model_dump(exclude_none=True)),
                },
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "quiz", "quiz_preparation_result": preparation.model_dump(exclude_none=True), "readiness_decision": readiness},
            }

        if not should_generate:
            return {
                "message": {"role": "assistant", "content": readiness["soft_confirm_message"]},
                "conversation": {"conversation_id": self._clean(getattr(request, "conversation_id", ""))},
                "action": {"name": "generate.quiz"},
                "artifacts": [],
                "workflow": {
                    "type": "quiz",
                    "status": "awaiting_confirm",
                    "stage": "soft_confirm",
                    "required_slots": [],
                    "filled_slots": self._filled_slots(preparation.model_dump(exclude_none=True)),
                },
                "sources": [],
                "trace": {"path": "workflow", "workflow_name": "quiz", "quiz_preparation_result": preparation.model_dump(exclude_none=True), "readiness_decision": readiness},
            }

        artifact = self.quiz_generator.generate(
            preparation=preparation.model_dump(exclude_none=True),
            context_summary=generation_context.summary_text,
            conversation_id=self._clean(getattr(request, "conversation_id", "")),
            owner=getattr(request, "owner", None),
            allow_rag=bool(getattr(capability, "allow_rag", False)),
            selected_doc_ids=list(getattr(capability, "selected_doc_ids", []) or []),
        )
        return {
            "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
            "conversation": {"conversation_id": self._clean(getattr(request, "conversation_id", ""))},
            "action": {"name": "generate.quiz"},
            "artifacts": [artifact],
            "workflow": {
                "type": "quiz",
                "status": "completed",
                "stage": "generating",
                "required_slots": [],
                "filled_slots": self._filled_slots(preparation.model_dump(exclude_none=True)),
            },
            "sources": [],
            "trace": {"path": "workflow", "workflow_name": "quiz", "quiz_preparation_result": preparation.model_dump(exclude_none=True), "readiness_decision": readiness},
        }
```

- [ ] **Step 4: Run the generator and runtime tests to verify they pass**

Run: `python -m pytest backend/src/tests/chat/test_quiz_generator.py backend/src/tests/chat/test_quiz_workflow_runtime.py -q`

Expected: `3 passed`

- [ ] **Step 5: Commit the quiz runtime**

```bash
git add backend/src/app/chat/workflows/quiz/generator.py backend/src/app/chat/workflows/quiz/runtime.py backend/src/tests/chat/test_quiz_generator.py backend/src/tests/chat/test_quiz_workflow_runtime.py
git commit -m "feat: add quiz workflow runtime"
```

### Task 3: Wire Quiz Routing, Reply Service Registration, Persistence, and API Error Tracing

**Files:**
- Modify: `backend/src/app/chat/orchestrator/route_rules.py`
- Modify: `backend/src/app/chat/application/reply_service_v2.py`
- Modify: `backend/src/app/chat/api/routes_v2.py`
- Test: `backend/src/tests/chat/test_quiz_route_rules.py`
- Test: `backend/src/tests/chat/test_quiz_reply_service_v2.py`
- Test: `backend/src/tests/chat/test_quiz_routes_v2.py`

- [ ] **Step 1: Write the failing routing, registration, and API tests**

```python
# backend/src/tests/chat/test_quiz_route_rules.py
from types import SimpleNamespace

from app.chat.orchestrator.route_rules import decide_route


def test_decide_route_prefers_explicit_quiz_workflow():
    decision = decide_route(
        request=SimpleNamespace(
            question="根据上面的内容生成习题",
            action_hint="generate.quiz",
            conversation_id="conv-quiz-route-1",
        ),
        snapshot=None,
        workflow_state=None,
    )

    assert decision.path == "workflow"
    assert decision.workflow_name == "quiz"
    assert decision.action == "generate.quiz"


def test_decide_route_detects_quiz_followup_from_active_context():
    snapshot = SimpleNamespace(
        active_context={
            "active_workflow_type": "quiz",
            "active_workflow_status": "awaiting_confirm",
            "active_artifact_type": "quiz",
        },
        conversation_memory={
            "user_goals": ["生成二次函数练习题"],
            "explicit_user_goals": [],
            "derived_workflow_goal": "quiz",
        },
        active_artifact=None,
    )

    decision = decide_route(
        request=SimpleNamespace(
            question="可以，直接开始",
            action_hint="",
            conversation_id="conv-quiz-route-2",
        ),
        snapshot=snapshot,
        workflow_state=None,
    )

    assert decision.path == "workflow"
    assert decision.workflow_name == "quiz"
    assert decision.reason in {"resume_active_quiz_context", "quiz_followup_from_context"}
```

```python
# backend/src/tests/chat/test_quiz_reply_service_v2.py
from types import SimpleNamespace

from app.chat.application.reply_service_v2 import ReplyServiceV2


class DummyConversationStore:
    def write_v2_result(self, conversation_id, request, result):
        self.last_write = (conversation_id, request, result)


class DummyStatusCardBuilder:
    def build(self, snapshot, workflow, capability):
        return {"title": "quiz"}


class DummyContextBuilder:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def build(self, request):
        return self.snapshot


class DummyCourseStorageManager:
    def __init__(self):
        self.saved = []

    def save_generated_material(self, **kwargs):
        self.saved.append(kwargs)
        return {"material_id": "quiz-material-1"}


def test_reply_service_persists_completed_quiz_artifact():
    storage = DummyCourseStorageManager()
    snapshot = SimpleNamespace(active_context={}, workflow_state=None)
    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(
            dispatch=lambda request: {
                "message": {"role": "assistant", "content": "done"},
                "conversation": {"conversation_id": "conv-quiz-reply-1"},
                "action": {"name": "generate.quiz"},
                "workflow": {"type": "quiz", "status": "completed", "stage": "generating"},
                "artifacts": [
                    {
                        "artifact_id": "conv-quiz-reply-1:quiz",
                        "artifact_type": "quiz",
                        "title": "二次函数练习.json",
                        "content": {"title": "二次函数练习", "questions": [{"id": "1", "stem": "题目"}]},
                    }
                ],
            }
        ),
        conversation_store=DummyConversationStore(),
        context_builder=DummyContextBuilder(snapshot),
        status_card_builder=DummyStatusCardBuilder(),
        course_storage_manager=storage,
    )

    payload = SimpleNamespace(
        question="生成一套二次函数习题",
        conversation_id="conv-quiz-reply-1",
        capability=SimpleNamespace(selected_course_id="course-1"),
        owner="teacher-a",
        artifact_reference=None,
    )
    result = service.reply(payload)

    assert result["artifacts"][0]["artifact_type"] == "quiz"
    assert storage.saved[0]["material_type"] == "quiz"
```

```python
# backend/src/tests/chat/test_quiz_routes_v2.py
from fastapi.testclient import TestClient

from app.main import app


def test_chat_reply_quiz_failure_returns_workflow_trace(monkeypatch):
    class FailingReplyService:
        def reply(self, payload):
            raise RuntimeError("quiz boom")

    monkeypatch.setattr(
        "app.chat.api.routes_v2._get_reply_service",
        lambda: FailingReplyService(),
    )
    monkeypatch.setattr(
        "app.chat.api.routes_v2.get_current_user",
        lambda: {"username": "teacher-a"},
    )

    client = TestClient(app)
    response = client.post(
        "/api/chat/v2/reply",
        json={
            "question": "根据当前对话生成习题",
            "action_hint": "generate.quiz",
            "conversation_id": "conv-quiz-route-api-1",
        },
    )

    assert response.status_code == 500
    assert response.json()["trace"]["path"] == "workflow"
```

- [ ] **Step 2: Run the new wiring tests to verify they fail**

Run: `python -m pytest backend/src/tests/chat/test_quiz_route_rules.py backend/src/tests/chat/test_quiz_reply_service_v2.py backend/src/tests/chat/test_quiz_routes_v2.py -q`

Expected: at least one assertion fails because quiz routing, reply-service registration, or quiz workflow error tracing is not wired yet.

- [ ] **Step 3: Implement route detection, workflow registration, quiz persistence, and quiz workflow trace-path handling**

```python
# backend/src/app/chat/orchestrator/route_rules.py
ACTION_TO_WORKFLOW = {
    "generate.report": "report",
    "generate.ppt": "ppt",
    "generate.lesson_plan": "lesson_plan",
    "generate.quiz": "quiz",
    "research.lookup": "research",
}

_QUIZ_REQUEST_MARKERS = {
    "习题",
    "练习题",
    "测试题",
    "出题",
    "quiz",
}

_QUIZ_CONTINUE_MARKERS = {
    "继续",
    "开始",
    "确认",
    "确认并继续",
    "确认并生成",
    "可以",
    "开始生成",
}


def _is_explicit_quiz_request(question: str) -> bool:
    normalized = _normalized_text(question)
    if not normalized:
        return False
    return any(marker in normalized for marker in _QUIZ_REQUEST_MARKERS)


def _is_quiz_followup(question: str, snapshot) -> bool:
    normalized = _normalized_text(question)
    if not normalized:
        return False

    active_context = _snapshot_active_context(snapshot)
    active_artifact_type = _snapshot_active_artifact_type(snapshot)
    memory = _snapshot_memory(snapshot)

    quiz_goal = any(
        any(marker in str(item or "").lower() for marker in ("习题", "练习题", "测试题", "quiz"))
        for item in list(memory.get("user_goals") or [])
        + list(memory.get("explicit_user_goals") or [])
        + [memory.get("derived_workflow_goal")]
    )
    quiz_context_active = (
        str(active_context.get("active_workflow_type") or "").strip() == "quiz"
        and str(active_context.get("active_workflow_status") or "").strip() in {"running", "awaiting_confirm"}
    )
    quiz_artifact_active = active_artifact_type == "quiz"

    if not (quiz_goal or quiz_context_active or quiz_artifact_active):
        return False

    if normalized in _QUIZ_CONTINUE_MARKERS:
        return True
    if any(token in normalized for token in ("生成习题", "生成练习题", "开始出题", "直接出题")):
        return True
    if quiz_artifact_active and any(token in normalized for token in ("继续", "确认", "开始", "生成")):
        return True
    return False

# Insert these branches into decide_route() after the active report/ppt resume checks
# and before the generic report/ppt/lesson-plan explicit routing.
if (
        not workflow_state
        and not request.action_hint
        and str(active_context.get("active_workflow_type") or "").strip() == "quiz"
        and str(active_context.get("active_workflow_status") or "").strip() in {"running", "awaiting_confirm"}
        and _is_quiz_followup(request.question, snapshot)
    ):
        return RouteDecision(
            path="workflow",
            action="generate.quiz",
            workflow_name="quiz",
            reason="resume_active_quiz_context",
        )

    if request.action_hint == "generate.quiz" or _is_explicit_quiz_request(request.question):
        return RouteDecision(
            path="workflow",
            action="generate.quiz",
            workflow_name="quiz",
            reason="explicit_quiz",
        )

    if _is_quiz_followup(request.question, snapshot):
        return RouteDecision(
            path="workflow",
            action="generate.quiz",
            workflow_name="quiz",
            reason="quiz_followup_from_context",
        )
```

```python
# backend/src/app/chat/application/reply_service_v2.py
from app.chat.orchestrator.quiz_context_organizer import QuizContextOrganizer
from app.chat.orchestrator.quiz_readiness_judge import QuizReadinessJudge
from app.chat.workflows.quiz.assembler import QuizAssembler
from app.chat.workflows.quiz.generator import QuizGenerator
from app.chat.workflows.quiz.runtime import QuizWorkflowRuntime


def _persist_quiz_course_material(*, payload, result, course_storage_manager):
    if course_storage_manager is None:
        return

    capability = getattr(payload, "capability", None)
    course_id = str(getattr(capability, "selected_course_id", "") or "").strip()
    owner = str(getattr(payload, "owner", "") or "").strip()
    if not course_id or not owner:
        return

    for artifact in list(result.get("artifacts") or []):
        if str(artifact.get("artifact_type") or "").strip() != "quiz":
            continue
        course_storage_manager.save_generated_material(
            course_id=course_id,
            owner=owner,
            material_type="quiz",
            title=str(artifact.get("title") or "quiz"),
            content=artifact.get("content") or {},
            metadata={
                "artifact_id": artifact.get("artifact_id"),
                "conversation_id": ((result.get("conversation") or {}).get("conversation_id")) or getattr(payload, "conversation_id", ""),
                "workflow_type": "quiz",
            },
        )


# In ReplyServiceV2.reply(), call the helper immediately after finalize_report_result().
finalize_report_result(
    payload=payload,
    result=result,
    course_storage_manager=self.course_storage_manager,
    compact_message=True,
)
_persist_quiz_course_material(
    payload=payload,
    result=result,
    course_storage_manager=self.course_storage_manager,
)

# In build_default_reply_service_v2(), add this entry to workflow_registry.
"quiz": QuizWorkflowRuntime(
    generation_context_builder=GenerationContextBuilder(),
    quiz_assembler=QuizAssembler(),
    quiz_context_organizer=QuizContextOrganizer(llm=get_fallback_llm()),
    quiz_readiness_judge=QuizReadinessJudge(),
    quiz_generator=QuizGenerator(
        llm=get_fallback_llm(),
        rag_fetcher=rag_search_tool,
    ),
),
```

```python
# backend/src/app/chat/api/routes_v2.py
def _is_workflow_intent_from_reply(payload: ChatReplyRequestV2) -> bool:
    question = str(payload.question or "")
    if payload.action_hint in {"generate.report", "generate.ppt", "generate.lesson_plan", "generate.quiz"}:
        return True
    return any(token in question.lower() for token in ("ppt", "quiz")) or any(
        token in question for token in ("报告", "课件", "教案", "习题", "练习题", "测试题")
    )


@router.post("/reply", response_model=ChatResponseV2)
async def reply(payload: ChatReplyRequestV2, current_user: dict = Depends(get_current_user)):
    try:
        return _get_reply_service().reply(_with_owner(payload, current_user))
    except Exception as exc:
        body = build_v2_error_response(
            code="workflow_failed",
            message=str(exc),
            conversation_id=payload.conversation_id or "",
            trace_path="workflow" if _is_workflow_intent_from_reply(payload) else "fast",
            retryable=False,
        )
        return JSONResponse(status_code=500, content=body)
```

- [ ] **Step 4: Run the targeted quiz wiring tests and then the full quiz workflow test set**

Run:

`python -m pytest backend/src/tests/chat/test_quiz_route_rules.py backend/src/tests/chat/test_quiz_reply_service_v2.py backend/src/tests/chat/test_quiz_routes_v2.py -q`

Then run:

`python -m pytest backend/src/tests/chat/test_quiz_context_organizer.py backend/src/tests/chat/test_quiz_readiness_judge.py backend/src/tests/chat/test_quiz_generator.py backend/src/tests/chat/test_quiz_workflow_runtime.py backend/src/tests/chat/test_quiz_route_rules.py backend/src/tests/chat/test_quiz_reply_service_v2.py backend/src/tests/chat/test_quiz_routes_v2.py -q`

Expected: all seven quiz-specific tests pass.

- [ ] **Step 5: Commit the quiz workflow wiring**

```bash
git add backend/src/app/chat/orchestrator/route_rules.py backend/src/app/chat/application/reply_service_v2.py backend/src/app/chat/api/routes_v2.py backend/src/tests/chat/test_quiz_route_rules.py backend/src/tests/chat/test_quiz_reply_service_v2.py backend/src/tests/chat/test_quiz_routes_v2.py
git commit -m "feat: wire quiz workflow into chat v2"
```
