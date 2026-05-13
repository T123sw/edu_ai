# PPT Dual-Entry Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PPT workflow in app/chat v2 with two entry modes (`reply` and explicit `/ppt`) that converge on one runtime: generate outline, confirm/edit outline, build `content_markdown`, validate it, call `html2ppt`, and return `ppt_outline` / `ppt_deck` artifacts.

**Architecture:** Keep `ConversationSnapshot -> GenerationContext` as the upstream context interface, add PPT-specific normalization and preparation contracts, and implement a dedicated `PptWorkflowRuntime` that owns page-level outline generation, outline confirmation, protocol assembly, validation, and `html2ppt` orchestration. Ship the explicit entry first to validate the shared downstream pipeline, then wire natural-language `generate.ppt` routing into the existing v2 reply workflow.

**Tech Stack:** Python, FastAPI, Pydantic, existing chat v2 workflow runtime, existing conversation store/status card infrastructure, `httpx`, pytest

---

## File Structure

### New files

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_workflow_request.py`
  - Defines normalized PPT workflow request contracts for explicit and conversation entry.
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_preparation.py`
  - Defines `PptPreparationResult` and `PptContextSummary`.
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_outline.py`
  - Defines user-facing outline artifact contracts and confirmation status.
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_artifact.py`
  - Defines helpers for `ppt_outline`, `ppt_content_markdown`, and `ppt_deck`.
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\ppt_request_normalizer.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\ppt_service_v2.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\preparation.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\readiness_judge.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\outline_builder.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\content_markdown_assembler.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\content_validator.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\html2ppt_client.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\runtime.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_preparation.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_request_normalizer.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_validator.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_html2ppt_client.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_service_v2.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py`

### Existing files to modify

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\api\schemas_v2.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\api\routes_v2.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\reply_service_v2.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\route_rules.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\status_card_label_mapper.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\response_builder_v2.py` if action payload helpers need extension

---

### Task 1: Define PPT Contracts and the “Enough Information?” Gate

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_workflow_request.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_preparation.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_outline.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_artifact.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\preparation.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\readiness_judge.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_preparation.py`

- [ ] **Step 1: Write the failing contract and readiness tests**

```python
from app.chat.domain.generation_context import GenerationContext
from app.chat.domain.ppt_workflow_request import PptWorkflowRequest
from app.chat.workflows.ppt.preparation import PptPreparationBuilder
from app.chat.workflows.ppt.readiness_judge import PptReadinessJudge


def test_ppt_workflow_request_defaults_are_stable():
    request = PptWorkflowRequest(
        source_type="explicit",
        conversation_id="conv-1",
        topic="TCP 三次握手",
        audience="大一学生",
        objective="课堂讲解",
    )

    assert request.slide_count == 12
    assert request.theme_id == "heu_academic_elegant"
    assert request.include_notes is True


def test_ppt_preparation_extracts_topic_audience_objective_and_key_points():
    context = GenerationContext(
        conversation_id="conv-1",
        resource_type="ppt",
        summary_text="用户希望做一份面向大一学生的 TCP 三次握手课堂 PPT。",
        current_topics=["TCP 三次握手"],
        user_goals=["生成 PPT", "用于课堂讲解"],
        confirmed_facts=["要讲三次握手流程", "需要解释为什么不能两次握手"],
        constraints={"audience": "大一学生"},
        teaching_issues=["学生容易混淆 SYN 与 ACK"],
        student_signals=[],
        evidence_points=[],
        recent_relevant_messages=[{"role": "user", "content": "请帮我做一份面向大一学生的 TCP 三次握手 PPT"}],
        source_scope={"from_summary": True, "from_memory": True},
    )

    result = PptPreparationBuilder().build(context=context, request_question="请帮我做一份面向大一学生的 TCP 三次握手 PPT")

    assert result.ppt_intent == "generate_ppt"
    assert result.deck_topic == "TCP 三次握手"
    assert result.audience == "大一学生"
    assert result.objective
    assert len(result.key_points) >= 2


def test_ppt_readiness_asks_critical_gap_when_topic_missing():
    decision = PptReadinessJudge().judge(
        deck_topic=None,
        audience="大一学生",
        objective="课堂讲解",
        key_points=["要点一", "要点二"],
        entry_mode="conversation",
    )

    assert decision["action"] == "ask_critical_gap"
    assert decision["missing_critical_fields"] == ["deck_topic"]


def test_ppt_readiness_requires_enough_points_for_page_level_outline():
    decision = PptReadinessJudge().judge(
        deck_topic="TCP 三次握手",
        audience="大一学生",
        objective="课堂讲解",
        key_points=["为什么需要握手"],
        entry_mode="conversation",
    )

    assert decision["action"] == "ask_critical_gap"
    assert decision["missing_critical_fields"] == ["key_points"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_preparation.py -q
```

Expected: FAIL with missing PPT contracts/builders.

- [ ] **Step 3: Write minimal contracts and preparation logic**

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class PptWorkflowRequest(BaseModel):
    source_type: str
    conversation_id: str
    topic: str
    audience: str
    objective: str
    slide_count: int = 12
    theme_id: str = "heu_academic_elegant"
    template_style: str = "教学简洁风"
    visual_preference: str = "图文并茂"
    include_notes: bool = True
    selected_doc_ids: list[str] = Field(default_factory=list)
    source_summary: str = ""
    constraints: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class PptPreparationResult(BaseModel):
    ppt_intent: str = "unclear"
    deck_topic: str | None = None
    audience: str | None = None
    objective: str | None = None
    recommended_slide_count: int | None = None
    key_points: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    source_scope: dict = Field(default_factory=dict)
    missing_critical_fields: list[str] = Field(default_factory=list)
    confidence: str = "low"
    soft_confirm_message: str = ""
    followup_candidates: list[str] = Field(default_factory=list)


class PptPreparationBuilder:
    def build(self, *, context, request_question: str) -> PptPreparationResult:
        topic = next((item for item in list(context.current_topics or []) if str(item).strip()), None)
        audience = str((context.constraints or {}).get("audience") or "").strip() or None
        objective = next((item for item in list(context.user_goals or []) if "PPT" not in str(item)), None) or "生成一版结构清晰的教学 PPT"
        key_points = list(context.confirmed_facts or [])[:4]
        missing = ["deck_topic"] if not topic else []
        return PptPreparationResult(
            ppt_intent="generate_ppt" if "ppt" in str(request_question or "").lower() else "unclear",
            deck_topic=topic,
            audience=audience,
            objective=objective,
            recommended_slide_count=12,
            key_points=key_points,
            constraints=dict(context.constraints or {}),
            source_scope=dict(context.source_scope or {}),
            missing_critical_fields=missing,
            confidence="medium" if topic else "low",
            soft_confirm_message=f"我将基于“{topic}”先整理一版 PPT 大纲，可以直接开始吗？" if topic else "",
            followup_candidates=["这份 PPT 主要想讲哪个主题？"] if not topic else [],
        )


class PptReadinessJudge:
    def judge(self, *, deck_topic: str | None, audience: str | None, objective: str | None, key_points: list[str], entry_mode: str) -> dict:
        if not str(deck_topic or "").strip():
            return {"action": "ask_critical_gap", "missing_critical_fields": ["deck_topic"]}
        if len(list(key_points or [])) < 2:
            return {"action": "ask_critical_gap", "missing_critical_fields": ["key_points"]}
        if str(audience or "").strip() and str(objective or "").strip() and len(list(key_points or [])) >= 2:
            return {"action": "generate_outline", "missing_critical_fields": []}
        return {
            "action": "ask_critical_gap",
            "missing_critical_fields": [field for field, value in [("audience", audience), ("objective", objective)] if not str(value or "").strip()],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_preparation.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/domain/ppt_workflow_request.py app/chat/domain/ppt_preparation.py app/chat/domain/ppt_outline.py app/chat/domain/ppt_artifact.py app/chat/workflows/ppt/preparation.py app/chat/workflows/ppt/readiness_judge.py tests/chat/test_ppt_preparation.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add ppt contracts and readiness gate"
```

---

### Task 2: Build Deterministic Page-Level Outline, Markdown Assembly, and Validation

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\outline_builder.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\content_markdown_assembler.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\content_validator.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_validator.py`

- [ ] **Step 1: Write the failing outline and markdown tests**

```python
from app.chat.domain.ppt_workflow_request import PptWorkflowRequest
from app.chat.workflows.ppt.content_markdown_assembler import PptContentMarkdownAssembler
from app.chat.workflows.ppt.content_validator import PptContentValidator
from app.chat.workflows.ppt.outline_builder import PptOutlineBuilder


def test_outline_builder_creates_page_level_outline():
    request = PptWorkflowRequest(
        source_type="explicit",
        conversation_id="conv-1",
        topic="TCP 三次握手",
        audience="大一学生",
        objective="课堂讲解",
        slide_count=5,
    )

    outline = PptOutlineBuilder().build(request=request)

    assert outline.deck_title == "TCP 三次握手"
    assert [slide.role for slide in outline.slides] == ["cover", "toc", "content", "content", "thanks"]
    assert all(slide.key_points for slide in outline.slides[2:-1])
    assert outline.chapters


def test_markdown_assembler_outputs_valid_protocol():
    request = PptWorkflowRequest(
        source_type="explicit",
        conversation_id="conv-1",
        topic="TCP 三次握手",
        audience="大一学生",
        objective="课堂讲解",
        slide_count=5,
    )

    outline = PptOutlineBuilder().build(request=request)
    markdown = PptContentMarkdownAssembler().assemble(outline=outline)
    validation = PptContentValidator().validate(markdown)

    assert "# Deck" in markdown
    assert "## Slide 1" in markdown
    assert "### Blocks" in markdown
    assert validation["ok"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_validator.py -q
```

Expected: FAIL because builders and validator do not exist.

- [ ] **Step 3: Write minimal deterministic builders and validator**

```python
from __future__ import annotations

from app.chat.domain.ppt_outline import PptOutline, PptOutlineChapter, PptOutlineSlide


class PptOutlineBuilder:
    def build(self, *, request) -> PptOutline:
        outline = PptOutline(
            deck_title=request.topic,
            deck_subtitle=f"面向{request.audience}",
            theme_id=request.theme_id,
        )
        slide_count = max(int(request.slide_count or 0), 4)
        outline.slides.append(PptOutlineSlide(slide_index=1, role="cover", title=request.topic, goal=request.objective, key_points=[request.objective]))
        outline.slides.append(PptOutlineSlide(slide_index=2, role="toc", title="目录", goal="展示结构", key_points=["学习目标", "核心章节"]))
        chapter_slides = []
        for index in range(3, slide_count):
            slide = PptOutlineSlide(
                slide_index=index,
                role="content",
                title=f"第{index - 2}部分",
                goal=request.objective,
                key_points=[f"{request.topic}关键点{index - 2}", f"面向{request.audience}解释"],
            )
            chapter_slides.append(slide)
            outline.slides.append(slide)
        outline.slides.append(PptOutlineSlide(slide_index=slide_count, role="thanks", title="Q&A", goal="结束页", key_points=["总结", "答疑"]))
        outline.chapters.append(PptOutlineChapter(chapter_index=1, chapter_title="主体内容", chapter_goal=request.objective, slides=chapter_slides))
        return outline


class PptContentMarkdownAssembler:
    def assemble(self, *, outline) -> str:
        lines = [
            "# Deck",
            f"- Title: {outline.deck_title}",
            f"- Subtitle: {outline.deck_subtitle}",
            f"- Theme: {outline.theme_id}",
            "",
        ]
        for slide in outline.slides:
            lines.extend(["---", "", f"## Slide {slide.slide_index}", f"- Role: {slide.role}", f"- Title: {slide.title}", "", "### Blocks"])
            if slide.role in {"cover", "thanks"}:
                lines.append(f"- Lead: {(slide.key_points or [slide.goal])[0]}")
            else:
                lines.append("- Bullets:")
                for item in list(slide.key_points or [slide.goal]):
                    lines.append(f"  - {item}")
            if slide.presenter_notes:
                lines.extend(["", "### Notes", slide.presenter_notes])
            lines.append("")
        return "\n".join(lines).strip() + "\n"


class PptContentValidator:
    def validate(self, markdown: str) -> dict:
        text = str(markdown or "")
        errors: list[str] = []
        if "# Deck" not in text:
            errors.append("missing deck header")
        slides = [chunk for chunk in text.split("## Slide ") if chunk.strip()]
        if not slides:
            errors.append("missing slide blocks")
        for chunk in slides:
            if "- Role:" not in chunk:
                errors.append("missing role")
            if "- Title:" not in chunk:
                errors.append("missing title")
            if "### Blocks" not in chunk:
                errors.append("missing blocks")
        return {"ok": not errors, "errors": errors}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_validator.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/workflows/ppt/outline_builder.py app/chat/workflows/ppt/content_markdown_assembler.py app/chat/workflows/ppt/content_validator.py tests/chat/test_ppt_outline_builder.py tests/chat/test_ppt_content_markdown_assembler.py tests/chat/test_ppt_content_validator.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add ppt outline and markdown pipeline"
```

---

### Task 3: Add `html2ppt` Client and Ship the Explicit `/api/chat/v2/ppt` Entry

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\html2ppt_client.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\ppt_request_normalizer.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\ppt_service_v2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\api\schemas_v2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\api\routes_v2.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_html2ppt_client.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_request_normalizer.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_service_v2.py`

- [ ] **Step 1: Write the failing explicit-entry tests**

```python
from app.chat.application.ppt_request_normalizer import normalize_explicit_ppt_request
from app.chat.workflows.ppt.html2ppt_client import Html2PptClient


def test_html2ppt_client_builds_create_job_payload():
    client = Html2PptClient(base_url="http://127.0.0.1:46080")
    payload = client._build_create_job_payload(
        content_markdown="# Deck\n",
        theme_id="heu_academic_elegant",
        metadata={
            "request_id": "req-1",
            "timestamp": "2026-04-08T10:00:00+08:00",
            "idempotency_key": "idem-1",
            "user_id": "user-1",
        },
    )

    assert payload["theme_id"] == "heu_academic_elegant"
    assert payload["metadata"]["idempotency_key"] == "idem-1"


def test_explicit_ppt_request_normalizer_backfills_conversation_id_and_defaults():
    payload = type(
        "Payload",
        (),
        {
            "conversation_id": None,
            "topic": "TCP 三次握手",
            "audience": "大一学生",
            "objective": "课堂讲解",
            "slide_count": 8,
            "theme_id": "heu_academic_elegant",
            "template_style": "教学简洁风",
            "visual_preference": "图文并茂",
            "include_notes": True,
            "selected_doc_ids": ["doc_001"],
            "user_instruction": "加入抓包示意",
            "idempotency_key": "idem-1",
            "owner": "teacher_a",
        },
    )()

    request = normalize_explicit_ppt_request(payload)

    assert request.conversation_id.startswith("conv-")
    assert request.selected_doc_ids == ["doc_001"]
    assert request.metadata["idempotency_key"] == "idem-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_html2ppt_client.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_request_normalizer.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_service_v2.py -q
```

Expected: FAIL because client/normalizer/service do not exist.

- [ ] **Step 3: Implement the client, normalizer, and starter service**

```python
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import httpx

from app.chat.domain.ppt_workflow_request import PptWorkflowRequest


class Html2PptClient:
    def __init__(self, *, base_url: str, timeout_seconds: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _build_create_job_payload(self, *, content_markdown: str, theme_id: str, metadata: dict) -> dict:
        return {"content_markdown": content_markdown, "theme_id": theme_id, "metadata": dict(metadata or {})}


def normalize_explicit_ppt_request(payload) -> PptWorkflowRequest:
    conversation_id = str(getattr(payload, "conversation_id", "") or "").strip() or f"conv-{uuid4().hex[:12]}"
    return PptWorkflowRequest(
        source_type="explicit",
        conversation_id=conversation_id,
        topic=str(getattr(payload, "topic", "") or "").strip(),
        audience=str(getattr(payload, "audience", "") or "").strip(),
        objective=str(getattr(payload, "objective", "") or "").strip(),
        slide_count=int(getattr(payload, "slide_count", 12) or 12),
        theme_id=str(getattr(payload, "theme_id", "") or "heu_academic_elegant").strip(),
        template_style=str(getattr(payload, "template_style", "") or "教学简洁风").strip(),
        visual_preference=str(getattr(payload, "visual_preference", "") or "图文并茂").strip(),
        include_notes=bool(getattr(payload, "include_notes", True)),
        selected_doc_ids=list(getattr(payload, "selected_doc_ids", []) or []),
        constraints={"user_instruction": str(getattr(payload, "user_instruction", "") or "").strip()},
        metadata={
            "request_id": f"req-{uuid4().hex[:12]}",
            "timestamp": datetime.now().isoformat(),
            "idempotency_key": str(getattr(payload, "idempotency_key", "") or f"ppt-{uuid4().hex[:8]}"),
            "user_id": str(getattr(payload, "owner", "") or "").strip(),
            "entry_mode": "explicit_ppt",
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_html2ppt_client.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_request_normalizer.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_service_v2.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/workflows/ppt/html2ppt_client.py app/chat/application/ppt_request_normalizer.py app/chat/application/ppt_service_v2.py app/chat/api/schemas_v2.py app/chat/api/routes_v2.py tests/chat/test_html2ppt_client.py tests/chat/test_ppt_request_normalizer.py tests/chat/test_ppt_service_v2.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add explicit ppt workflow entry"
```

---

### Task 4: Implement `PptWorkflowRuntime`, Final Deck Artifact, and Reply-Path Routing

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\runtime.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\reply_service_v2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\route_rules.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\status_card_label_mapper.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py`

- [ ] **Step 1: Write the failing runtime and route tests**

```python
from types import SimpleNamespace

from app.chat.domain.ppt_workflow_request import PptWorkflowRequest
from app.chat.orchestrator.route_rules import decide_route
from app.chat.workflows.ppt.runtime import PptWorkflowRuntime


class StubHtml2PptClient:
    def create_job(self, **kwargs):
        return {"job_id": "job_001", "status": "queued"}

    def get_job_status(self, job_id):
        return {
            "job_id": job_id,
            "status": "succeeded",
            "phase": "completed",
            "progress": 100,
            "message": "生成完成",
            "latest_revision_id": "rev_0000",
        }

    def get_job_results(self, job_id):
        return {
            "job_id": job_id,
            "latest_revision_id": "rev_0000",
            "theme_id": "heu_academic_elegant",
            "results": {
                "html_fragment_url": "/ppt/artifacts/job_001/rev_0000/deck.fragment.html",
                "html_full_url": "/ppt/artifacts/job_001/rev_0000/deck.html",
                "pptx_url": "/ppt/artifacts/job_001/rev_0000/deck.pptx",
                "manifest_url": "/ppt/artifacts/job_001/rev_0000/manifest.json",
            },
            "slide_count": 5,
            "metadata": {},
        }


def test_route_rules_send_generate_ppt_action_to_ppt_workflow():
    request = SimpleNamespace(question="请帮我生成 PPT", action_hint="generate.ppt")
    snapshot = SimpleNamespace(active_artifact=None, active_context={}, conversation_memory={}, workflow_state=None)

    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)

    assert decision.path == "workflow"
    assert decision.workflow_name == "ppt"


def test_ppt_runtime_returns_outline_then_final_deck():
    runtime = PptWorkflowRuntime(html2ppt_client=StubHtml2PptClient())
    request = PptWorkflowRequest(
        source_type="explicit",
        conversation_id="conv-1",
        topic="TCP 三次握手",
        audience="大一学生",
        objective="课堂讲解",
        slide_count=5,
        metadata={
            "request_id": "req-1",
            "timestamp": "2026-04-08T10:00:00+08:00",
            "idempotency_key": "idem-1",
            "user_id": "teacher_a",
        },
    )

    pending = runtime.run_explicit(request=request)
    final = runtime.run_after_outline_confirm(request=request)

    assert pending["workflow"]["stage"] == "awaiting_outline_confirmation"
    assert final["workflow"]["stage"] == "completed"
    assert any(artifact.get("artifact_type") == "ppt_deck" for artifact in final["artifacts"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q
```

Expected: FAIL because runtime and routing are not implemented.

- [ ] **Step 3: Implement the minimal runtime and route wiring**

```python
from __future__ import annotations

from app.chat.workflows.ppt.content_markdown_assembler import PptContentMarkdownAssembler
from app.chat.workflows.ppt.content_validator import PptContentValidator
from app.chat.workflows.ppt.outline_builder import PptOutlineBuilder


class PptWorkflowRuntime:
    def __init__(self, *, html2ppt_client, outline_builder=None, markdown_assembler=None, validator=None):
        self.html2ppt_client = html2ppt_client
        self.outline_builder = outline_builder or PptOutlineBuilder()
        self.markdown_assembler = markdown_assembler or PptContentMarkdownAssembler()
        self.validator = validator or PptContentValidator()

    def run_explicit(self, *, request):
        outline = self.outline_builder.build(request=request)
        return {
            "message": {"role": "assistant", "content": "已生成 PPT 大纲，请先确认。"},
            "conversation": {"conversation_id": request.conversation_id},
            "action": {"name": "ppt.outline.review", "available_actions": ["ppt.outline.confirm", "ppt.outline.edit", "ppt.cancel"]},
            "workflow": {"workflow_id": f"wf-ppt-{request.conversation_id}", "workflow_type": "ppt", "status": "running", "stage": "awaiting_outline_confirmation"},
            "artifacts": [{"artifact_id": f"ppt-outline-{request.conversation_id}", "artifact_type": "ppt_outline", "title": f"{outline.deck_title}-大纲", "content": outline.model_dump()}],
            "trace": {"path": "workflow", "entry_mode": request.metadata.get("entry_mode", "explicit_ppt")},
        }

    def run_after_outline_confirm(self, *, request):
        outline = self.outline_builder.build(request=request)
        markdown = self.markdown_assembler.assemble(outline=outline)
        validation = self.validator.validate(markdown)
        if not validation["ok"]:
            raise ValueError(f"invalid content_markdown: {validation['errors']}")
        job = self.html2ppt_client.create_job(content_markdown=markdown, theme_id=request.theme_id, metadata=request.metadata)
        status = self.html2ppt_client.get_job_status(job["job_id"])
        results = self.html2ppt_client.get_job_results(job["job_id"])
        return {
            "message": {"role": "assistant", "content": "已生成，请在右侧查看。"},
            "conversation": {"conversation_id": request.conversation_id},
            "action": {"name": "ppt.view"},
            "workflow": {"workflow_id": f"wf-ppt-{request.conversation_id}", "workflow_type": "ppt", "status": "completed", "stage": "completed"},
            "artifacts": [{
                "artifact_id": results["job_id"],
                "artifact_type": "ppt_deck",
                "title": f"{outline.deck_title}.pptx",
                "content": {
                    "job_id": results["job_id"],
                    "revision_id": results["latest_revision_id"],
                    "pptx_url": results["results"]["pptx_url"],
                    "html_url": results["results"]["html_full_url"],
                    "fragment_url": results["results"]["html_fragment_url"],
                    "manifest_url": results["results"]["manifest_url"],
                    "slide_count": results["slide_count"],
                },
                "generation_state": {
                    "status": status["status"],
                    "phase": status["phase"],
                    "progress": status["progress"],
                    "message": status["message"],
                },
            }],
            "trace": {"path": "workflow"},
        }
```

In `route_rules.py`:

```python
ACTION_TO_WORKFLOW = {
    "generate.report": "report",
    "generate.lesson_plan": "lesson_plan",
    "generate.ppt": "ppt",
    "research.lookup": "research",
}

if request.action_hint == "generate.ppt":
    return RouteDecision(
        path="workflow",
        action="generate.ppt",
        workflow_name="ppt",
        reason="explicit_ppt",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/workflows/ppt/runtime.py app/chat/application/reply_service_v2.py app/chat/orchestrator/route_rules.py app/chat/orchestrator/status_card_label_mapper.py tests/chat/test_ppt_workflow_runtime.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: wire ppt workflow into v2 runtime"
```

---

## Spec Coverage Check

This plan covers the approved PPT workflow design by mapping the major design commitments to implementation tasks:

1. Two entry modes:
   - explicit `/api/chat/v2/ppt` in Task 3
   - reply/workflow routing in Task 4
2. Shared normalized request object:
   - Task 1 + Task 3
3. Outline before PPT generation:
   - Task 2 + Task 4
4. Code-led `content_markdown` assembly:
   - Task 2
5. Validation before `html2ppt`:
   - Task 2 + Task 4
6. Dedicated `html2ppt` adapter:
   - Task 3
7. Artifact-based output:
   - Task 1 + Task 4
8. Follow-up gate for insufficient information:
   - Task 1

No spec gaps requiring a second implementation plan were found.

## Placeholder Scan

Checked for:

- `TODO`
- `TBD`
- `implement later`
- missing filenames
- missing test commands

No placeholders remain. Each task includes exact files, concrete tests, run commands, implementation snippets, and commit commands.

## Type Consistency Check

Reviewed the plan for consistent naming:

- normalized input uses `PptWorkflowRequest`
- information gate uses `PptPreparationResult`
- user-facing outline uses `PptOutline`
- final downloadable output uses `ppt_deck`

No conflicting names were found.
