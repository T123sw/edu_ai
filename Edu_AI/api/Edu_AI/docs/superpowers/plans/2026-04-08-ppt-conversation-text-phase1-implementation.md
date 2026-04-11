# PPT Conversation Text Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a conversation-driven, text-only PPT workflow in `app/chat v2` that reuses existing conversation state, asks only a few high-value follow-up questions when information is insufficient, confirms a page-level outline with the user, then assembles `content_markdown`, calls `html2ppt`, and returns a `ppt_deck` artifact.

**Architecture:** Reuse `ReplyServiceV2 -> MainOrchestrator -> workflow runtime` as the only phase-1 entry path. Add a PPT-specific organizer, readiness judge, outline builder, markdown assembler, validator, and `html2ppt` client; keep the first phase limited to text-only blocks (`Lead` / `Toc` / `Bullets`) and defer explicit `/ppt` entry plus all media/image capability.

**Tech Stack:** Python, Pydantic, existing chat v2 orchestration stack, LangChain `ChatOpenAI`, `httpx`, pytest

---

## File Structure

### New files

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_workflow_request.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_preparation.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_outline.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_artifact.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\ppt_context_organizer.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\readiness_judge.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\outline_builder.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\content_markdown_assembler.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\content_validator.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\html2ppt_client.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\runtime.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_context_organizer.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_readiness_judge.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_validator.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_html2ppt_client.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py`

### Existing files to modify

- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\reply_service_v2.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\route_rules.py`
- `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\status_card_label_mapper.py`

---

### Task 1: Add PPT Soft-Slot Preparation and Readiness

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_workflow_request.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_preparation.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\ppt_context_organizer.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\readiness_judge.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_context_organizer.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_readiness_judge.py`

- [ ] **Step 1: Write the failing tests**

```python
from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.ppt_context_organizer import PptContextOrganizer
from app.chat.workflows.ppt.readiness_judge import PptReadinessJudge


def test_ppt_context_organizer_extracts_topic_audience_objective_and_key_points():
    context = GenerationContext(
        conversation_id="conv-1",
        resource_type="ppt",
        summary_text="用户希望做一份面向大一学生的 TCP 三次握手课堂 PPT。",
        current_topics=["TCP 三次握手"],
        user_goals=["生成 PPT", "课堂讲解"],
        confirmed_facts=["三次握手流程", "为什么不是两次握手"],
        constraints={"audience": "大一学生"},
        teaching_issues=[],
        student_signals=[],
        evidence_points=[],
        recent_relevant_messages=[],
        source_scope={"from_summary": True},
    )
    result = PptContextOrganizer().organize(context=context, request_question="请帮我做一份 TCP 三次握手 PPT")
    assert result.deck_topic == "TCP 三次握手"
    assert result.audience == "大一学生"
    assert result.objective == "课堂讲解"
    assert len(result.key_points) >= 2


def test_ppt_readiness_asks_only_one_question_for_topic_gap():
    preparation = PptContextOrganizer().organize(
        context=GenerationContext(
            conversation_id="conv-2",
            resource_type="ppt",
            summary_text="请帮我做成 PPT。",
            current_topics=[],
            user_goals=["生成 PPT"],
            confirmed_facts=["重点讲两次握手和三次握手区别", "说明 ACK 的作用"],
            constraints={},
            teaching_issues=[],
            student_signals=[],
            evidence_points=[],
            recent_relevant_messages=[],
            source_scope={},
        ),
        request_question="请帮我做成 PPT",
    )
    decision = PptReadinessJudge().judge(preparation=preparation, followup_count=0)
    assert decision.required_slots == ["deck_topic"]
    assert decision.followup_question == "这份 PPT 主要想讲哪个主题？"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_context_organizer.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_readiness_judge.py -q
```

Expected: FAIL with missing PPT preparation modules.

- [ ] **Step 3: Write minimal implementation**

```python
class PptPreparationResult(BaseModel):
    ppt_intent: str = "unclear"
    deck_topic: str | None = None
    audience: str | None = None
    objective: str | None = None
    key_points: list[str] = Field(default_factory=list)
    source_basis: list[str] = Field(default_factory=list)
    slide_count: int | None = None
    template_style: str | None = None
    visual_preference: str | None = None
    include_notes: bool = True
    assumptions: list[str] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)


class PptReadinessDecision(BaseModel):
    action: str
    required_slots: list[str] = Field(default_factory=list)
    followup_question: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class PptContextOrganizer:
    def organize(self, *, context, request_question: str) -> PptPreparationResult:
        topic = next((str(item).strip() for item in list(getattr(context, "current_topics", []) or []) if str(item).strip()), None)
        audience = str((getattr(context, "constraints", {}) or {}).get("audience") or "").strip() or None
        goals = [str(item).strip() for item in list(getattr(context, "user_goals", []) or []) if str(item).strip()]
        objective = next((item for item in goals if item not in {"生成 PPT", "PPT"}), None) or None
        key_points = [str(item).strip() for item in list(getattr(context, "confirmed_facts", []) or []) if str(item).strip()][:4]
        source_basis = ["conversation_summary"] if bool((getattr(context, "source_scope", {}) or {}).get("from_summary")) else []
        return PptPreparationResult(
            ppt_intent="generate_ppt" if "ppt" in str(request_question or "").lower() or "PPT" in str(request_question or "") else "unclear",
            deck_topic=topic,
            audience=audience,
            objective=objective,
            key_points=key_points,
            source_basis=source_basis,
            include_notes=True,
        )


class PptReadinessJudge:
    def judge(self, *, preparation, followup_count: int) -> PptReadinessDecision:
        if not str(preparation.deck_topic or "").strip():
            return PptReadinessDecision(action="ask_followup", required_slots=["deck_topic"], followup_question="这份 PPT 主要想讲哪个主题？")
        if followup_count >= 2:
            assumptions = list(preparation.assumptions or [])
            if not str(preparation.audience or "").strip():
                assumptions.append("默认面向通用教学场景")
            if not str(preparation.objective or "").strip():
                assumptions.append("默认用于课堂讲解")
            return PptReadinessDecision(action="generate_outline", assumptions=assumptions)
        if not str(preparation.audience or "").strip():
            return PptReadinessDecision(action="ask_followup", required_slots=["audience"], followup_question="这份 PPT 主要面向哪类学生或听众？")
        if not str(preparation.objective or "").strip():
            return PptReadinessDecision(action="ask_followup", required_slots=["objective"], followup_question="你希望这份 PPT 更偏课堂讲解、汇报展示，还是复习总结？")
        if len(list(preparation.key_points or [])) < 2:
            return PptReadinessDecision(action="ask_followup", required_slots=["key_points"], followup_question="你最希望这份 PPT 重点覆盖哪 2 到 4 个部分？")
        return PptReadinessDecision(action="generate_outline")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_context_organizer.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_readiness_judge.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/domain/ppt_workflow_request.py app/chat/domain/ppt_preparation.py app/chat/orchestrator/ppt_context_organizer.py app/chat/workflows/ppt/readiness_judge.py tests/chat/test_ppt_context_organizer.py tests/chat/test_ppt_readiness_judge.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add ppt preparation and readiness gate"
```

---

### Task 2: Build a Page-Level Text-Only Outline and Markdown Pipeline

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_outline.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\domain\ppt_artifact.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\outline_builder.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\content_markdown_assembler.py`
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\content_validator.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_validator.py`

- [ ] **Step 1: Write the failing tests**

```python
from app.chat.domain.ppt_preparation import PptPreparationResult
from app.chat.workflows.ppt.content_markdown_assembler import PptContentMarkdownAssembler
from app.chat.workflows.ppt.content_validator import PptContentValidator
from app.chat.workflows.ppt.outline_builder import PptOutlineBuilder


def test_outline_builder_creates_cover_toc_content_and_thanks_without_media():
    preparation = PptPreparationResult(
        deck_topic="TCP 三次握手",
        audience="大一学生",
        objective="课堂讲解",
        key_points=["三次握手流程", "为什么不是两次握手"],
    )
    outline = PptOutlineBuilder(llm=None).build(preparation=preparation)
    assert [slide.role for slide in outline.slides] == ["cover", "toc", "content", "content", "thanks"]


def test_markdown_assembler_emits_text_only_protocol():
    preparation = PptPreparationResult(
        deck_topic="TCP 三次握手",
        audience="大一学生",
        objective="课堂讲解",
        key_points=["三次握手流程", "为什么不是两次握手"],
    )
    outline = PptOutlineBuilder(llm=None).build(preparation=preparation)
    markdown = PptContentMarkdownAssembler().assemble(outline=outline)
    assert "# Deck" in markdown
    assert "- Media:" not in markdown


def test_content_validator_rejects_media_blocks_in_phase1():
    validation = PptContentValidator().validate("# Deck\n## Slide 1\n- Role: content\n- Title: t\n### Blocks\n- Media:\n")
    assert validation["ok"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_validator.py -q
```

Expected: FAIL with missing outline/assembler/validator.

- [ ] **Step 3: Write minimal implementation**

```python
import json
import re


class PptOutlineSlide(BaseModel):
    slide_index: int
    role: str
    title: str
    goal: str
    key_points: list[str] = Field(default_factory=list)


class PptOutlineChapter(BaseModel):
    chapter_index: int
    chapter_title: str
    chapter_goal: str
    slides: list[PptOutlineSlide] = Field(default_factory=list)


class PptOutline(BaseModel):
    deck_title: str
    deck_subtitle: str | None = None
    theme_id: str = "heu_academic_elegant"
    confirmation_status: str = "pending"
    chapters: list[PptOutlineChapter] = Field(default_factory=list)
    slides: list[PptOutlineSlide] = Field(default_factory=list)


class PptOutlineBuilder:
    def build(self, *, preparation) -> PptOutline:
        if self.llm is not None:
            prompt = (
                "请生成章节级+逐页级 PPT 大纲，输出 JSON。"
                f"\n主题：{preparation.deck_topic}"
                f"\n受众：{preparation.audience}"
                f"\n目标：{preparation.objective}"
                f"\n关键点：{'；'.join(list(preparation.key_points or []))}"
            )
            response = self.llm.invoke(
                [
                    {"role": "system", "content": "你是资深教学型 PPT 设计助手。输出必须是 JSON。"},
                    {"role": "user", "content": prompt},
                ]
            )
            text = str(getattr(response, "content", response) or "")
            match = re.search(r"\{.*\}", text, re.S)
            if match:
                return PptOutline.model_validate(json.loads(match.group(0)))
        slides = [
            PptOutlineSlide(slide_index=1, role="cover", title=str(preparation.deck_topic or "课堂 PPT"), goal=str(preparation.objective or "导入主题"), key_points=[str(preparation.objective or "导入主题")]),
            PptOutlineSlide(slide_index=2, role="toc", title="目录", goal="展示结构", key_points=list(preparation.key_points or [])),
        ]
        for index, point in enumerate(list(preparation.key_points or []), start=3):
            slides.append(PptOutlineSlide(slide_index=index, role="content", title=point, goal=f"讲清楚{point}", key_points=[point, f"结合{preparation.deck_topic}解释"]))
        slides.append(PptOutlineSlide(slide_index=len(slides) + 1, role="thanks", title="Q&A", goal="总结并答疑", key_points=["回顾重点", "欢迎提问"]))
        return PptOutline(deck_title=str(preparation.deck_topic or "课堂 PPT"), deck_subtitle=f"面向{preparation.audience or '通用学习者'}", slides=slides)


class PptContentMarkdownAssembler:
    def assemble(self, *, outline) -> str:
        lines = ["# Deck", f"- Title: {outline.deck_title}", f"- Subtitle: {outline.deck_subtitle or ''}", f"- Theme: {outline.theme_id}", ""]
        toc_items = [slide.title for slide in outline.slides if slide.role == "content"]
        for slide in outline.slides:
            lines.extend(["---", "", f"## Slide {slide.slide_index}", f"- Role: {slide.role}", f"- Title: {slide.title}", "", "### Blocks"])
            if slide.role in {"cover", "thanks"}:
                lines.append(f"- Lead: {(slide.key_points or [slide.goal])[0]}")
            elif slide.role == "toc":
                lines.append("- Toc:")
                for item in toc_items:
                    lines.append(f"  - {item}")
            else:
                lines.append("- Bullets:")
                for item in list(slide.key_points or [slide.goal]):
                    lines.append(f"  - {item}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"


class PptContentValidator:
    def validate(self, markdown: str) -> dict:
        text = str(markdown or "")
        errors: list[str] = []
        if "# Deck" not in text:
            errors.append("missing deck header")
        if "### Blocks" not in text:
            errors.append("missing blocks")
        if "- Media:" in text:
            errors.append("media not supported in phase1")
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
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/domain/ppt_outline.py app/chat/domain/ppt_artifact.py app/chat/workflows/ppt/outline_builder.py app/chat/workflows/ppt/content_markdown_assembler.py app/chat/workflows/ppt/content_validator.py tests/chat/test_ppt_outline_builder.py tests/chat/test_ppt_content_markdown_assembler.py tests/chat/test_ppt_content_validator.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add text-only ppt outline pipeline"
```

---

### Task 3: Add the `html2ppt` Client

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\html2ppt_client.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_html2ppt_client.py`

- [ ] **Step 1: Write the failing test**

```python
import httpx

from app.chat.workflows.ppt.html2ppt_client import Html2PptClient


def test_html2ppt_client_create_job_and_fetch_results():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/ppt/jobs":
            return httpx.Response(200, json={"job_id": "job_001", "status": "queued"})
        if request.method == "GET" and request.url.path == "/ppt/jobs/job_001":
            return httpx.Response(200, json={"job_id": "job_001", "status": "succeeded"})
        if request.method == "GET" and request.url.path == "/ppt/jobs/job_001/results":
            return httpx.Response(200, json={"job_id": "job_001", "results": {"pptx_url": "/ppt/artifacts/job_001/rev_0000/deck.pptx"}})
        return httpx.Response(404)

    client = Html2PptClient(
        base_url="http://testserver",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver"),
    )
    assert client.create_job(content_markdown="# Deck\n", theme_id="heu_academic_elegant", metadata={"request_id": "req", "timestamp": "2026-04-08T10:00:00+08:00", "idempotency_key": "idem", "user_id": "teacher"})["job_id"] == "job_001"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_html2ppt_client.py -q
```

Expected: FAIL with missing client.

- [ ] **Step 3: Write minimal implementation**

```python
import httpx


class Html2PptClient:
    def __init__(self, *, base_url: str, http_client: httpx.Client | None = None):
        self.base_url = str(base_url).rstrip("/")
        self.http_client = http_client or httpx.Client(base_url=self.base_url, timeout=30.0)

    def create_job(self, *, content_markdown: str, theme_id: str, metadata: dict) -> dict:
        response = self.http_client.post("/ppt/jobs", json={"content_markdown": content_markdown, "theme_id": theme_id, "metadata": metadata})
        response.raise_for_status()
        return response.json()

    def get_job_status(self, job_id: str) -> dict:
        response = self.http_client.get(f"/ppt/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    def get_job_results(self, job_id: str) -> dict:
        response = self.http_client.get(f"/ppt/jobs/{job_id}/results")
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_html2ppt_client.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/workflows/ppt/html2ppt_client.py tests/chat/test_html2ppt_client.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: add html2ppt client"
```

---

### Task 4: Wire the Conversation Runtime into `reply_service_v2`

**Files:**
- Create: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt\runtime.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application\reply_service_v2.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\route_rules.py`
- Modify: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\orchestrator\status_card_label_mapper.py`
- Test: `d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py`

- [ ] **Step 1: Write the failing tests**

```python
from types import SimpleNamespace

from app.chat.domain.generation_context import GenerationContext
from app.chat.orchestrator.route_rules import decide_route
from app.chat.workflows.ppt.runtime import PptWorkflowRuntime


class StubHtml2PptClient:
    def create_job(self, **kwargs):
        return {"job_id": "job_001", "status": "queued"}

    def get_job_status(self, job_id):
        return {"job_id": job_id, "status": "succeeded", "phase": "completed", "progress": 100, "message": "done"}

    def get_job_results(self, job_id):
        return {"job_id": job_id, "latest_revision_id": "rev_0000", "results": {"pptx_url": "/ppt/artifacts/job_001/rev_0000/deck.pptx"}, "slide_count": 5}


def test_route_rules_send_generate_ppt_to_ppt_workflow():
    request = SimpleNamespace(question="请帮我生成 PPT", action_hint="generate.ppt")
    snapshot = SimpleNamespace(active_artifact=None, active_context={}, conversation_memory={}, workflow_state=None)
    decision = decide_route(request=request, snapshot=snapshot, workflow_state=None)
    assert decision.workflow_name == "ppt"


def test_ppt_runtime_returns_followup_when_topic_missing():
    runtime = PptWorkflowRuntime(html2ppt_client=StubHtml2PptClient())
    context = GenerationContext(conversation_id="conv-1", resource_type="ppt", summary_text="", current_topics=[], user_goals=["生成 PPT"], confirmed_facts=["要点一", "要点二"], constraints={}, teaching_issues=[], student_signals=[], evidence_points=[], recent_relevant_messages=[], source_scope={})
    result = runtime.run(request=SimpleNamespace(question="帮我做成 PPT", conversation_id="conv-1"), snapshot=None, decision=SimpleNamespace(action="generate.ppt"), generation_context=context, workflow_state=None)
    assert result["workflow"]["required_slots"] == ["deck_topic"]


def test_ppt_runtime_returns_outline_then_deck():
    runtime = PptWorkflowRuntime(html2ppt_client=StubHtml2PptClient())
    context = GenerationContext(conversation_id="conv-2", resource_type="ppt", summary_text="面向大一学生讲解 TCP 三次握手。", current_topics=["TCP 三次握手"], user_goals=["生成 PPT", "课堂讲解"], confirmed_facts=["三次握手流程", "为什么不是两次握手"], constraints={"audience": "大一学生"}, teaching_issues=[], student_signals=[], evidence_points=[], recent_relevant_messages=[], source_scope={"from_summary": True})
    first = runtime.run(request=SimpleNamespace(question="请帮我做一份 TCP 三次握手 PPT", conversation_id="conv-2"), snapshot=None, decision=SimpleNamespace(action="generate.ppt"), generation_context=context, workflow_state=None)
    second = runtime.run(request=SimpleNamespace(question="确认并继续", conversation_id="conv-2"), snapshot=None, decision=SimpleNamespace(action="generate.ppt"), generation_context=context, workflow_state=SimpleNamespace(status="awaiting_confirm", artifacts=first["artifacts"], metadata={"followup_count": 0}))
    assert first["workflow"]["stage"] == "awaiting_outline_confirmation"
    assert second["workflow"]["stage"] == "completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q
```

Expected: FAIL with missing runtime wiring.

- [ ] **Step 3: Write minimal implementation**

```python
class PptWorkflowRuntime:
    def __init__(self, *, html2ppt_client, context_organizer=None, readiness_judge=None, outline_builder=None, markdown_assembler=None, validator=None):
        self.html2ppt_client = html2ppt_client
        self.context_organizer = context_organizer or PptContextOrganizer()
        self.readiness_judge = readiness_judge or PptReadinessJudge()
        self.outline_builder = outline_builder or PptOutlineBuilder(llm=get_fallback_llm())
        self.markdown_assembler = markdown_assembler or PptContentMarkdownAssembler()
        self.validator = validator or PptContentValidator()

    def run(self, *, request, snapshot, decision, generation_context, workflow_state):
        if workflow_state and getattr(workflow_state, "status", "") == "awaiting_confirm":
            outline_content = next((item.get("content") for item in list(getattr(workflow_state, "artifacts", []) or []) if item.get("artifact_type") == "ppt_outline"), None)
            markdown = self.markdown_assembler.assemble(outline=outline_content)
            validation = self.validator.validate(markdown)
            if not validation["ok"]:
                raise ValueError(f"invalid content_markdown: {validation['errors']}")
            job = self.html2ppt_client.create_job(content_markdown=markdown, theme_id="heu_academic_elegant", metadata={"request_id": f"ppt-{request.conversation_id}", "timestamp": "2026-04-08T10:00:00+08:00", "idempotency_key": f"ppt-{request.conversation_id}", "user_id": "conversation-user"})
            status = self.html2ppt_client.get_job_status(job["job_id"])
            results = self.html2ppt_client.get_job_results(job["job_id"])
            return {"workflow": {"workflow_type": "ppt", "stage": "completed", "status": "completed"}, "artifacts": [{"artifact_type": "ppt_deck", "content": results, "generation_state": status}]}

        preparation = self.context_organizer.organize(context=generation_context, request_question=request.question)
        decision_payload = self.readiness_judge.judge(preparation=preparation, followup_count=int((getattr(workflow_state, "metadata", {}) or {}).get("followup_count", 0)) if workflow_state else 0)
        if decision_payload.action == "ask_followup":
            return {"message": {"role": "assistant", "content": decision_payload.followup_question}, "workflow": {"workflow_type": "ppt", "stage": "collecting_inputs", "required_slots": decision_payload.required_slots}, "artifacts": []}
        outline = self.outline_builder.build(preparation=preparation)
        return {"message": {"role": "assistant", "content": "已整理出 PPT 大纲，请先确认。"}, "workflow": {"workflow_type": "ppt", "stage": "awaiting_outline_confirmation", "status": "awaiting_confirm"}, "artifacts": [{"artifact_type": "ppt_outline", "content": outline.model_dump()}]}
```

In `route_rules.py` add:

```python
ACTION_TO_WORKFLOW["generate.ppt"] = "ppt"
```

And route to PPT when:

```python
request.action_hint == "generate.ppt" or "PPT" in request.question or "ppt" in request.question.lower()
```

In `reply_service_v2.py` workflow registry add:

```python
"ppt": PptWorkflowRuntime(
    html2ppt_client=Html2PptClient(base_url="http://127.0.0.1:3100"),
)
```

In `status_card_label_mapper.py` add:

```python
_WORKFLOW_LABELS["ppt"] = "PPT"
_WORKFLOW_LABELS["ppt_outline"] = "PPT 提纲"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH='d:\Edu_AI_1\Edu_AI\api\Edu_AI'; pytest d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_context_organizer.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_readiness_judge.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_outline_builder.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_markdown_assembler.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_content_validator.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_html2ppt_client.py d:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat\test_ppt_workflow_runtime.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI add app/chat/workflows/ppt/runtime.py app/chat/application/reply_service_v2.py app/chat/orchestrator/route_rules.py app/chat/orchestrator/status_card_label_mapper.py tests/chat/test_ppt_workflow_runtime.py
git -C d:\Edu_AI_1\Edu_AI\api\Edu_AI commit -m "feat: wire conversation ppt workflow"
```

---

## Scope Guardrails

This phase intentionally excludes:

1. Explicit `POST /api/chat/v2/ppt` entry
2. Image/media blocks
3. Online image search, RAG image retrieval, or media asset selection
4. Multi-page revision
5. Exposing `content_markdown` to ordinary users

## Spec Coverage Check

This plan covers the phase-1 requirements:

1. Conversation entry only:
   - Task 4
2. Soft-slot extraction from conversation state:
   - Task 1
3. Ask only when missing information blocks page-level outline generation:
   - Task 1
4. Page-level outline before PPT generation:
   - Task 2 + Task 4
5. Code-led `content_markdown` assembly:
   - Task 2
6. Validation before calling `html2ppt`:
   - Task 2 + Task 4
7. `html2ppt` adapter:
   - Task 3
8. Text-only first phase, no media:
   - Task 2 + Scope Guardrails

No phase-1 spec gaps were found.

## Placeholder Scan

Checked for:

- `TODO`
- `TBD`
- `implement later`
- missing file paths
- missing test commands

No placeholders remain.

## Type Consistency Check

Reviewed the plan for naming consistency:

- normalized request uses `PptWorkflowRequest`
- conversation summary output uses `PptPreparationResult`
- readiness output uses `PptReadinessDecision`
- user confirmation object uses `PptOutline`
- final downloadable artifact uses `ppt_deck`

No conflicting names were found.
