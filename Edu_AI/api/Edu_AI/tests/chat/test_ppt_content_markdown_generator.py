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


def test_content_markdown_generator_prompt_includes_new_teaching_constraints_and_protocol_text():
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
    assert "请直接生成完整的最终 content_markdown" in prompt
    assert "整体建议不少于 18 页" in prompt
    assert "每一页都要写出真实内容，不要只重复标题" in prompt
    assert "大多数内容页应尽量同时包含以下要素中的至少 3 种" in prompt
    assert "不要只回答“是什么”" in prompt
    assert "如果是方法型内容，不要只给流程，要补充适用条件、关键步骤、优缺点和常见错误" in prompt
    assert "请根据大纲自动补全合理的教学链路" in prompt
    assert "整套内容必须像认真备课后的教学型 PPT 文稿" in prompt
    assert "大多数内容页都应形成“一个明确小主题 + 一段展开解释 + 必要例子/比较/结论”的结构" in prompt
    assert "不要输出“下面开始生成”“以下是最终结果”“第 X 页”等额外提示语" in prompt
    assert "如果协议允许使用 summary、quote、case、columns 等 block，请优先用于承载真实教学内容" in prompt
    assert "结束页只保留简洁收尾信息，不再展开知识点，不写大段总结" in prompt
    assert protocol_text in prompt
    assert "Agent Systems" in prompt
    assert "大学生" in prompt
    assert "讲清核心流程" in prompt
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
