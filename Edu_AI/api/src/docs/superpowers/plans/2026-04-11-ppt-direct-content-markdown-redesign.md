# PPT Direct Content Markdown Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PPT slide-plan expansion pipeline with a direct `content_markdown` generator that uses a Chinese prompt plus the raw `content-protocol.md`, then validate and submit the generated markdown to `html2ppt`.

**Architecture:** Remove `PptSlidePlanBuilder` and the assembler/reviewer loop from the PPT runtime. Introduce a focused `PptContentMarkdownGenerator`, simplify runtime generation to a single pass, and upgrade validation/gating to work on final markdown plus outline constraints instead of slide-plan internals.

**Tech Stack:** Python, existing LangChain-style `.invoke(prompt)` LLM integration, pytest, markdown protocol validation, existing PPT workflow runtime.

---

### Task 1: Add The Direct Content Markdown Generator

**Files:**
- Create: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_markdown_generator.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_markdown_generator.py`

- [ ] **Step 1: Write the failing generator prompt/parse tests**

```python
from pathlib import Path

from app.chat.domain.ppt_outline import PptOutline, PptOutlineChapter, PptOutlineSlide
from app.chat.workflows.ppt.content_markdown_generator import PptContentMarkdownGenerator


def _outline() -> PptOutline:
    chapter_slide = PptOutlineSlide(
        slide_index=3,
        role="content",
        title="Skills 与 MCP 的区别",
        goal="帮助学生理解二者分别是什么以及如何配合。",
        key_points=["技能是能力", "MCP 是协议", "二者互补"],
    )
    return PptOutline(
        deck_title="AI Agent 中的 Skills 与 MCP",
        deck_subtitle="计算思维课堂",
        theme_id="heu_academic_elegant",
        chapters=[
            PptOutlineChapter(
                chapter_index=1,
                chapter_title="核心概念",
                chapter_goal="先建立概念框架，再解释关系。",
                slides=[chapter_slide],
            )
        ],
        slides=[
            PptOutlineSlide(slide_index=1, role="cover", title="AI Agent 中的 Skills 与 MCP", goal="开场", key_points=["导入"]),
            PptOutlineSlide(slide_index=2, role="toc", title="目录", goal="结构", key_points=["概念", "区别"]),
            chapter_slide,
            PptOutlineSlide(slide_index=4, role="thanks", title="Q&A", goal="收尾", key_points=["提问"]),
        ],
    )


def test_content_markdown_generator_builds_chinese_prompt_and_injects_protocol(tmp_path):
    protocol_path = tmp_path / "content-protocol.md"
    protocol_path.write_text("# 协议标题\n## 说明\n- Role: content\n", encoding="utf-8")
    prompts = []

    class DummyLLM:
        def invoke(self, prompt: str):
            prompts.append(prompt)
            return "# Deck\n## Slide 1\n- Role: cover\n- Title: 示例\n### Blocks\n- Lead: 开场\n"

    generator = PptContentMarkdownGenerator(llm=DummyLLM(), protocol_path=str(protocol_path))
    markdown, debug = generator.generate(outline=_outline(), preparation=None)

    assert markdown.startswith("# Deck")
    assert debug["protocol_loaded"] is True
    assert "你现在要生成的是完整的 content_markdown" in prompts[0]
    assert "15 页以上" in prompts[0]
    assert "参考协议文档" in prompts[0]
    assert "# 协议标题" in prompts[0]


def test_content_markdown_generator_extracts_markdown_from_fenced_response(tmp_path):
    protocol_path = tmp_path / "content-protocol.md"
    protocol_path.write_text("# 协议\n", encoding="utf-8")

    class DummyLLM:
        def invoke(self, _prompt: str):
            return """```md
# Deck
## Slide 1
- Role: cover
- Title: 示例
### Blocks
- Lead: 开场
```"""

    generator = PptContentMarkdownGenerator(llm=DummyLLM(), protocol_path=str(protocol_path))
    markdown, _debug = generator.generate(outline=_outline(), preparation=None)

    assert markdown.startswith("# Deck")
    assert "```" not in markdown
```

- [ ] **Step 2: Run the new generator tests to verify they fail**

Run: `python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_markdown_generator.py -q`  
Expected: FAIL with `ModuleNotFoundError` or import failure because `content_markdown_generator.py` does not exist yet.

- [ ] **Step 3: Implement the generator**

```python
from __future__ import annotations

from pathlib import Path
import re
from typing import Any


class PptContentMarkdownGenerator:
    def __init__(self, llm=None, protocol_path: str | None = None) -> None:
        self.llm = llm
        default_protocol = Path(__file__).resolve().parents[3] / "html2ppt" / "content-protocol.md"
        self.protocol_path = Path(protocol_path) if protocol_path else default_protocol

    @staticmethod
    def _clean(value: object, default: str = "") -> str:
        text = str(value or "").strip()
        return text or default

    @staticmethod
    def _preview_text(value: object, limit: int = 360) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        return text if len(text) <= limit else f"{text[:limit]}...(+{len(text) - limit} chars)"

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        raw_text = getattr(response, "content", response)
        if isinstance(raw_text, str):
            return raw_text.strip()
        if isinstance(raw_text, list):
            parts: list[str] = []
            for item in raw_text:
                if isinstance(item, dict):
                    text = str(item.get("text") or "").strip()
                else:
                    text = str(item or "").strip()
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()
        return str(raw_text or "").strip()

    @staticmethod
    def _strip_fences(text: str) -> str:
        normalized = str(text or "").strip()
        normalized = re.sub(r"^```(?:markdown|md)?\s*", "", normalized, flags=re.I)
        normalized = re.sub(r"\s*```$", "", normalized)
        return normalized.strip()

    def _build_prompt(self, *, outline, preparation, protocol_text: str) -> str:
        audience = self._clean(getattr(preparation, "audience", None), "中文教学场景的学习者")
        objective = self._clean(getattr(preparation, "objective", None), "生成一套可以直接讲授的课件")
        key_points = [str(item).strip() for item in list(getattr(preparation, "key_points", []) or []) if str(item).strip()]
        source_excerpts = [str(item).strip() for item in list(getattr(preparation, "source_excerpts", []) or []) if str(item).strip()]
        outline_payload = outline.model_dump(exclude_none=True) if hasattr(outline, "model_dump") else outline
        return (
            "你是一名中文教学课件内容设计助手。\n"
            "你现在要生成的是完整的 content_markdown，而不是 JSON，也不是 slide plan。\n"
            "请严格依据已确认大纲生成完整课件，覆盖封面、目录、内容页和结束页。\n"
            "你必须严格遵守下方给出的参考协议文档，但不要复述规则，不要解释。\n"
            "可以为了课堂讲解效果主动拆页、扩页、加入过渡页、举例页、总结页或对比页。\n"
            "15 页以上是推荐目标，不是硬性指标；不要为了凑页数机械重复。\n"
            "内容要适合中文 PPT 阅读与课堂讲授。\n"
            "输出只能是最终的 content_markdown，不要使用代码块围栏。\n\n"
            f"受众：{audience}\n"
            f"目标：{objective}\n"
            f"关键点：{' | '.join(key_points) if key_points else '未提供'}\n"
            f"参考摘录：{' | '.join(source_excerpts) if source_excerpts else '未提供'}\n\n"
            "已确认大纲：\n"
            f"{outline_payload}\n\n"
            "参考协议文档：\n"
            f"{protocol_text}\n"
        )

    def generate(self, *, outline, preparation) -> tuple[str, dict]:
        if self.llm is None:
            raise RuntimeError("ppt content markdown generator requires an llm")
        protocol_text = self.protocol_path.read_text(encoding="utf-8")
        prompt = self._build_prompt(outline=outline, preparation=preparation, protocol_text=protocol_text)
        response = self.llm.invoke(prompt)
        markdown = self._strip_fences(self._extract_response_text(response))
        return markdown, {
            "prompt_preview": self._preview_text(prompt),
            "response_preview": self._preview_text(response),
            "protocol_path": str(self.protocol_path),
            "protocol_loaded": True,
            "generation_mode": "direct_content_markdown",
        }
```

- [ ] **Step 4: Run the generator tests to verify they pass**

Run: `python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_markdown_generator.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_markdown_generator.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_markdown_generator.py
git commit -m "feat: add PPT direct content markdown generator"
```

### Task 2: Refactor The PPT Runtime And Default Wiring

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/runtime.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime_debug.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py`

- [ ] **Step 1: Write failing runtime and wiring tests for the new generator path**

```python
from types import SimpleNamespace

from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.workflow_state import WorkflowState
from app.chat.workflows.ppt.runtime import PptWorkflowRuntime


class StubContentMarkdownGenerator:
    def __init__(self, markdown: str):
        self.markdown = markdown
        self.calls = []

    def generate(self, *, outline, preparation):
        self.calls.append({"outline": outline.deck_title, "preparation": getattr(preparation, "topic", "")})
        return self.markdown, {
            "generation_mode": "direct_content_markdown",
            "prompt_preview": "生成完整 content_markdown",
            "response_preview": self.markdown[:40],
            "protocol_path": "content-protocol.md",
            "protocol_loaded": True,
        }


def test_ppt_runtime_uses_direct_content_markdown_generator_after_outline_confirmation():
    generator = StubContentMarkdownGenerator(
        "# Deck\n## Slide 1\n- Role: cover\n- Title: TCP\n### Blocks\n- Lead: 开场\n"
    )
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_generation_context()),
        content_markdown_generator=generator,
        html2ppt_client=StubHtml2PptClient(),
    )

    result = runtime.run(
        request=ChatRequestV2(question="开始", action_hint="generate.ppt", conversation_id="conv-ppt"),
        snapshot=_awaiting_outline_snapshot(),
        decision=None,
    )

    assert generator.calls
    assert result["workflow"]["status"] == "completed"
    assert "ppt_content_generation_debug" in result["trace"]


def test_build_default_reply_service_v2_wires_content_markdown_generator(monkeypatch):
    seen = {}

    class DummyPptRuntime:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr("app.chat.application.reply_service_v2.PptWorkflowRuntime", DummyPptRuntime)
    monkeypatch.setattr("app.chat.application.reply_service_v2.get_fallback_llm", lambda: object())

    build_default_reply_service_v2()

    assert seen["content_markdown_generator"] is not None
    assert "slide_plan_builder" not in seen
    assert "content_markdown_assembler" not in seen
```

- [ ] **Step 2: Run the targeted runtime and wiring tests to verify they fail**

Run: `python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime_debug.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q`  
Expected: FAIL because `PptWorkflowRuntime` still expects `slide_plan_builder` and `reply_service_v2` still wires the old components.

- [ ] **Step 3: Refactor runtime and dependency injection to the single-pass generator**

```python
from .content_markdown_generator import PptContentMarkdownGenerator
from .content_gate import PptContentGate
from .content_validator import PptContentValidator


class PptWorkflowRuntime:
    def __init__(
        self,
        *,
        generation_context_builder: GenerationContextBuilder | None = None,
        ppt_context_organizer: PptContextOrganizer | None = None,
        readiness_judge: PptReadinessJudge | None = None,
        outline_builder: PptOutlineBuilder | None = None,
        content_markdown_generator: PptContentMarkdownGenerator | None = None,
        content_gate: PptContentGate | None = None,
        content_validator: PptContentValidator | None = None,
        html2ppt_client: Html2PptClient | None = None,
        html2ppt_client_factory=None,
        poll_interval_seconds: float = 2.0,
        max_poll_attempts: int = 600,
        max_poll_seconds: float = 1200.0,
        phase_poll_timeout_seconds: dict[str, float] | None = None,
    ) -> None:
        self.generation_context_builder = generation_context_builder or GenerationContextBuilder()
        self.ppt_context_organizer = ppt_context_organizer or PptContextOrganizer()
        self.readiness_judge = readiness_judge or PptReadinessJudge()
        self.outline_builder = outline_builder or PptOutlineBuilder()
        self.content_markdown_generator = content_markdown_generator or PptContentMarkdownGenerator()
        self.content_validator = content_validator or PptContentValidator()
        self.content_gate = content_gate or PptContentGate(content_validator=self.content_validator)
        self._html2ppt_client = html2ppt_client
        self._html2ppt_client_factory = html2ppt_client_factory
        ...

    def _submit_outline(self, *, request, outline: PptOutline, preparation, followup_rounds: int) -> dict[str, Any]:
        outline = _normalize_outline_theme(outline)
        content_markdown, generation_debug = self.content_markdown_generator.generate(
            outline=outline,
            preparation=preparation,
        )
        validation = self.content_gate.apply(content_markdown=content_markdown, outline=outline)
        content_markdown = str(validation.get("final_markdown") or content_markdown)
        artifacts = [
            _build_outline_artifact(conversation_id=request.conversation_id or "", outline=outline),
            _build_markdown_artifact(
                conversation_id=request.conversation_id or "",
                outline=outline,
                content_markdown=content_markdown,
            ),
        ]
        if not bool(validation.get("ok")):
            return self._response(
                request=request,
                message="当前内容协议稿未通过结构校验，暂时不提交到 PPT 引擎。",
                workflow={
                    "type": "ppt",
                    "status": "failed",
                    "phase": "validating_content_markdown",
                    "filled_slots": _build_filled_slots(preparation=preparation, followup_rounds=followup_rounds),
                },
                artifacts=artifacts,
                trace={
                    "path": "workflow",
                    "workflow_name": "ppt",
                    "ppt_preparation_result": preparation.model_dump(exclude_none=True),
                    "ppt_outline_summary": self._summarize_outline(outline),
                    "ppt_content_generation_debug": generation_debug,
                    "ppt_validation": validation,
                    "ppt_content_markdown": content_markdown,
                },
            )
        ...
```

```python
"ppt": PptWorkflowRuntime(
    generation_context_builder=GenerationContextBuilder(),
    ppt_context_organizer=PptContextOrganizer(llm=get_fallback_llm()),
    readiness_judge=PptReadinessJudge(),
    outline_builder=PptOutlineBuilder(llm=get_fallback_llm()),
    content_markdown_generator=PptContentMarkdownGenerator(llm=get_fallback_llm()),
    content_validator=PptContentValidator(),
    html2ppt_client_factory=lambda: Html2PptClient(
        base_url=os.getenv("HTML2PPT_BASE_URL", "http://127.0.0.1:46080")
    ),
)
```

- [ ] **Step 4: Run the targeted runtime and wiring tests to verify they pass**

Run: `python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime_debug.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/workflows/ppt/runtime.py Edu_AI/api/Edu_AI/app/chat/application/reply_service_v2.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime_debug.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py
git commit -m "refactor: switch PPT runtime to direct content markdown generation"
```

### Task 3: Upgrade Validation And Gate To Work On Final Markdown

**Files:**
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_validator.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_gate.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_validator.py`
- Test: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_gate.py`

- [ ] **Step 1: Write failing validator and gate tests for full protocol blocks**

```python
from app.chat.domain.ppt_outline import PptOutline
from app.chat.workflows.ppt.content_gate import PptContentGate
from app.chat.workflows.ppt.content_validator import PptContentValidator


def test_content_validator_accepts_full_protocol_blocks():
    markdown = """# Deck
- Title: AI Agent 中的 Skills 与 MCP
- Subtitle: 计算思维课堂
- Theme: heu_academic_elegant

---

## Slide 1
- Role: cover
- Title: AI Agent 中的 Skills 与 MCP

### Blocks
- Lead: 先建立概念框架，再讲区别与应用
- Meta:
  - 对象：计算思维课程学生
  - 场景：课堂讲解

---

## Slide 2
- Role: content
- Title: Skills 与 MCP 的关系

### Blocks
- Comparison:
  - Left-Title: Skills
    Left-Items:
      - 表示能力本身
      - 关注“会做什么”
  - Right-Title: MCP
    Right-Items:
      - 表示能力接入协议
      - 关注“如何接入与调用”
"""

    validation = PptContentValidator().validate(markdown)

    assert validation["ok"] is True
    assert validation["errors"] == []


def test_content_gate_can_validate_markdown_without_slide_plan():
    markdown = """# Deck
## Slide 1
- Role: cover
- Title: 示例
### Blocks
- Lead: 开场
"""
    outline = PptOutline(deck_title="示例", deck_subtitle="课堂", theme_id="heu_academic_elegant", slides=[], chapters=[])

    result = PptContentGate().apply(content_markdown=markdown, outline=outline)

    assert result["ok"] is True
    assert result["final_markdown"] == markdown
```

- [ ] **Step 2: Run the validator and gate tests to verify they fail**

Run: `python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_validator.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_gate.py -q`  
Expected: FAIL because the validator still enforces phase-1-only blocks and the gate still requires `slide_plan`.

- [ ] **Step 3: Implement protocol-oriented validation and outline-only gating**

```python
from __future__ import annotations

import re


class PptContentValidator:
    _ROLE_VALUES = {"cover", "toc", "section", "content", "thanks"}
    _BLOCK_VALUES = {"Lead", "Bullets", "Meta", "Toc", "Cards", "Comparison", "Process", "Media"}

    def validate(self, markdown: str) -> dict:
        text = str(markdown or "")
        errors: list[str] = []

        if not text.strip().startswith("# Deck"):
            errors.append("missing deck header")

        slide_matches = list(
            re.finditer(r"(?ms)^## Slide\\s+(\\d+)\\s*$.*?(?=^## Slide\\s+\\d+\\s*$|\\Z)", text)
        )
        if not slide_matches:
            errors.append("missing slide blocks")
            return {"ok": False, "errors": errors}

        for match in slide_matches:
            slide_index = match.group(1)
            slide_text = match.group(0)
            role_match = re.search(r"(?m)^- Role:\\s*(.+?)\\s*$", slide_text)
            if not role_match:
                errors.append(f"slide {slide_index} missing role")
            elif role_match.group(1).strip() not in self._ROLE_VALUES:
                errors.append(f"slide {slide_index} has invalid role")
            if not re.search(r"(?m)^- Title:\\s*.+$", slide_text):
                errors.append(f"slide {slide_index} missing title")
            if "### Blocks" not in slide_text:
                errors.append(f"slide {slide_index} missing blocks")
            block_names = re.findall(r"(?m)^- (Lead|Bullets|Meta|Toc|Cards|Comparison|Process|Media):", slide_text)
            if not block_names:
                errors.append(f"slide {slide_index} missing supported block type")

        return {"ok": not errors, "errors": errors}
```

```python
class PptContentGate:
    def apply(self, *, content_markdown: str, outline) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        warnings: list[str] = []

        validation = self.content_validator.validate(content_markdown)
        for error in list(validation.get("errors") or []):
            issues.append(
                self._issue(
                    code="content.structure.invalid",
                    severity="error",
                    slide_index=None,
                    field_path="content_markdown",
                    message=str(error),
                    suggested_action="fix_content_structure",
                )
            )

        errors = [issue["message"] for issue in issues if issue.get("severity") == "error"]
        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "issues": issues,
            "transformations": [],
            "final_markdown": content_markdown,
        }
```

- [ ] **Step 4: Run the validator and gate tests to verify they pass**

Run: `python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_validator.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_gate.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_validator.py Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_gate.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_validator.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_gate.py
git commit -m "feat: validate direct PPT content markdown against full protocol"
```

### Task 4: Remove Obsolete Components And Align The Test Suite

**Files:**
- Delete: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/slide_plan_builder.py`
- Delete: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_slide_plan_builder.py`
- Delete: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_slide_plan_builder_debug.py`
- Delete: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_markdown_assembler.py`
- Delete: `Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_reviewer.py`
- Modify: `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/__init__.py` if needed

- [ ] **Step 1: Write the cleanup expectation into the test suite**

```python
import importlib
import pytest


def test_slide_plan_builder_module_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.chat.workflows.ppt.slide_plan_builder")
```

- [ ] **Step 2: Run the cleanup test to verify it fails**

Run: `python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_markdown_generator.py -q`  
Expected: FAIL or remain incomplete until old modules are removed and tests are aligned.

- [ ] **Step 3: Delete the obsolete implementation and tests**

```text
Delete the slide-plan builder module and the tests that only verify the removed slide-plan / assembler / reviewer flow:

- Edu_AI/api/Edu_AI/app/chat/workflows/ppt/slide_plan_builder.py
- Edu_AI/api/Edu_AI/tests/chat/test_ppt_slide_plan_builder.py
- Edu_AI/api/Edu_AI/tests/chat/test_ppt_slide_plan_builder_debug.py
- Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_markdown_assembler.py
- Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_reviewer.py
```

- [ ] **Step 4: Run the focused regression suite**

Run: `python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_markdown_generator.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_validator.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_content_gate.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime.py Edu_AI/api/Edu_AI/tests/chat/test_ppt_workflow_runtime_debug.py Edu_AI/api/Edu_AI/tests/chat/test_reply_service_v2.py -q`  
Expected: PASS

- [ ] **Step 5: Run a final project-level PPT regression slice**

Run: `python -m pytest Edu_AI/api/Edu_AI/tests/chat/test_ppt_* -q`  
Expected: PASS with the new direct-content pipeline only.

- [ ] **Step 6: Commit**

```bash
git add Edu_AI/api/Edu_AI/app/chat/workflows/ppt Edu_AI/api/Edu_AI/tests/chat
git commit -m "refactor: remove PPT slide-plan pipeline"
```

## Self-Review

### Spec coverage

- Direct generator replaces `slide_plan_builder`: covered by Task 1 and Task 2.
- Chinese prompt plus raw `content-protocol.md`: covered by Task 1 tests and implementation.
- Reviewer disabled for now: covered by Task 2 runtime/wiring refactor.
- Validator upgraded to full protocol: covered by Task 3.
- Delete old builder and related tests: covered by Task 4.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Each task names exact files and commands.
- Every code-changing step includes concrete code blocks or explicit delete actions.

### Type consistency

- New runtime dependency is consistently named `content_markdown_generator`.
- New debug field is consistently named `ppt_content_generation_debug`.
- Validation and gate steps consistently operate on `content_markdown` and `outline`, not `slide_plan`.

