from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.chat.domain.ppt_outline import PptOutline, PptOutlineSlide
from app.chat.domain.ppt_preparation import PptPreparationResult
from app.chat.workflows.ppt.content_markdown_generator import PptContentMarkdownGenerator


def _outline() -> PptOutline:
    return PptOutline(
        deck_title="Agent Systems",
        deck_subtitle="course",
        theme_id="heu_academic_elegant",
        slides=[
            PptOutlineSlide(
                slide_index=1,
                role="cover",
                title="Agent Systems",
                goal="Open the deck",
                key_points=["Audience", "Objective"],
            ),
            PptOutlineSlide(
                slide_index=3,
                role="content",
                title="Core Loop",
                goal="Explain the loop",
                key_points=["Observe", "Reason", "Act"],
            ),
        ],
    )


def _preparation() -> PptPreparationResult:
    return PptPreparationResult(
        audience="大学生",
        objective="讲清核心流程",
        key_points=["先理解定义", "再看流程"],
        source_basis=["课堂笔记"],
        source_excerpts=["原始摘录 A"],
        page_count=18,
    )


def test_content_markdown_generator_prompt_includes_direct_content_instructions_soft_constraint_and_protocol_text():
    prompts: list[str] = []

    class DummyLLM:
        def invoke(self, prompt: str) -> str:
            prompts.append(prompt)
            return "# Deck\n"

    protocol_path = Path(__file__).resolve().parents[2] / "html2ppt" / "content-protocol.md"
    protocol_text = protocol_path.read_text(encoding="utf-8")

    generator = PptContentMarkdownGenerator(llm=DummyLLM())
    content_markdown, debug = generator.generate(outline=_outline(), preparation=_preparation())

    assert content_markdown == "# Deck"
    assert debug["generation_mode"] == "direct_content_markdown"
    assert debug["protocol_loaded"] is True
    assert Path(debug["protocol_path"]).resolve() == protocol_path.resolve()
    assert prompts

    prompt = prompts[0]
    assert "直接生成完整的最终 content_markdown" in prompt
    assert "15+" in prompt
    assert protocol_text in prompt
    assert "Agent Systems" in prompt
    assert "大学生" in prompt
    assert "讲清核心流程" in prompt
    assert "不要使用 *、** 这类 Markdown 强调或列表符号" in prompt
    assert "模板里如果已经有 01/02/03 或 1/2/3 这类视觉序号" in prompt
    assert "不要输出字面量 \\n" in prompt
    assert "结束页（thanks）不要写成回顾总结页" in prompt
    assert "general learners" not in prompt
    assert "classroom teaching" not in prompt


def test_content_markdown_generator_raises_when_protocol_missing():
    missing_protocol_path = Path(__file__).resolve().parents[2] / "html2ppt" / "missing-content-protocol.md"
    generator = PptContentMarkdownGenerator(protocol_path=missing_protocol_path)

    try:
        generator.generate(outline=_outline(), preparation=_preparation())
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError as exc:
        assert str(missing_protocol_path) in str(exc)


def test_content_markdown_generator_strips_fenced_markdown_response_from_list_content():
    class DummyLLM:
        def invoke(self, prompt: str):
            return type(
                "Response",
                (),
                {
                    "content": [
                        {"text": "```md\n# Deck"},
                        {"text": "- Title: Agent Systems\n```"},
                    ]
                },
            )()

    generator = PptContentMarkdownGenerator(llm=DummyLLM())
    content_markdown, debug = generator.generate(outline=_outline(), preparation=_preparation())

    assert content_markdown == "# Deck\n- Title: Agent Systems"
    assert "```" not in content_markdown
    assert debug["response_preview"].startswith("```md")
