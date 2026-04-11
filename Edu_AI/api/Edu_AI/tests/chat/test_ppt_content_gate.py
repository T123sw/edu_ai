from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.chat.domain.ppt_outline import PptOutline, PptOutlineSlide
from app.chat.workflows.ppt.content_gate import PptContentGate


def _outline() -> PptOutline:
    return PptOutline(
        deck_title="Agent Systems",
        deck_subtitle="course",
        theme_id="heu_academic_elegant",
        slides=[
            PptOutlineSlide(slide_index=1, role="cover", title="Agent Systems", goal="Open", key_points=["intro"]),
            PptOutlineSlide(slide_index=2, role="content", title="Core Loop", goal="Explain", key_points=["loop"]),
        ],
    )


def test_content_gate_accepts_direct_content_markdown_with_rich_protocol_blocks():
    markdown = """# Deck
- Title: Agent Systems
- Subtitle: 课程讲解
- Theme: heu_academic_elegant

---

## Slide 1
- Role: cover
- Title: Agent Systems

### Blocks
- Lead: 课程聚焦 Agent 系统的核心能力。
- Meta:
  - Audience: 计算思维课程学生
  - Objective: 课堂讲解

---

## Slide 2
- Role: content
- Title: Core Loop

### Blocks
- Cards:
  - Title: Planning
    Text: 先判断目标与当前状态之间的差距。
  - Title: Acting
    Text: 再调用工具或执行动作推动任务前进。
- Process:
  - Step-Title: Observe
    Step-Text: 收集环境与上下文信号。
  - Step-Title: Decide
    Step-Text: 形成下一步动作方案。
- Comparison:
  - Left-Title: Without Memory
    Left-Items:
      - 容易重复犯错
    Right-Title: With Memory
    Right-Items:
      - 可以复用经验
- Media:
  - Kind: image
  - URL: https://example.com/loop.png
  - Alt: Agent loop diagram
"""

    result = PptContentGate().apply(content_markdown=markdown, outline=_outline())

    assert result["ok"] is True
    assert result["errors"] == []
    assert result["transformations"] == []
    assert result["final_markdown"] == markdown


def test_content_gate_surfaces_validator_errors_without_slide_plan_dependency():
    markdown = """## Slide 1
- Role: invalid-role
- Title: Broken Slide

### Blocks
- Lead: missing deck header and invalid role
"""

    result = PptContentGate().apply(content_markdown=markdown, outline=_outline())

    assert result["ok"] is False
    assert result["issues"]
    assert result["issues"][0]["code"] == "content.structure.invalid"
    assert "invalid role" in " ".join(result["errors"])
