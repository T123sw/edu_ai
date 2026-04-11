from app.chat.domain.ppt_slide_plan import (
    PptSlidePlan,
    PptSlidePlanCard,
    PptSlidePlanChapter,
    PptSlidePlanComparison,
    PptSlidePlanComparisonColumn,
    PptSlidePlanSlide,
)
from app.chat.workflows.ppt.content_markdown_assembler import PptContentMarkdownAssembler


def _slide_plan() -> PptSlidePlan:
    slides = [
        PptSlidePlanSlide(
            slide_index=1,
            role="cover",
            title="TCP 三次握手",
            layout_intent="lead",
            lead="理解 TCP 连接建立的基本过程。",
            bullets=["课程主题：TCP 三次握手", "对象：大一计算机专业学生"],
        ),
        PptSlidePlanSlide(
            slide_index=2,
            role="toc",
            title="目录",
            layout_intent="bullets",
            bullets=["为什么需要连接建立", "三次握手步骤", "常见误区"],
        ),
        PptSlidePlanSlide(
            slide_index=3,
            role="content",
            title="为什么需要连接建立",
            layout_intent="comparison",
            lead="从通信可靠性与状态同步两个角度理解。",
            comparison=PptSlidePlanComparison(
                left=PptSlidePlanComparisonColumn(title="没有握手", items=["无法确认对端是否在线", "初始序列号不同步"]),
                right=PptSlidePlanComparisonColumn(title="有握手", items=["确认双方可达", "同步后续传输状态"]),
            ),
            presenter_notes="先讲问题，再讲握手的必要性。",
        ),
        PptSlidePlanSlide(
            slide_index=4,
            role="content",
            title="三次握手流程",
            layout_intent="cards",
            lead="每一步都承担不同的确认职责。",
            cards=[
                PptSlidePlanCard(title="第一次", text="客户端发送 SYN，请求建立连接。"),
                PptSlidePlanCard(title="第二次", text="服务端回复 SYN + ACK。"),
                PptSlidePlanCard(title="第三次", text="客户端回复 ACK，连接建立。"),
            ],
        ),
        PptSlidePlanSlide(
            slide_index=5,
            role="thanks",
            title="Q&A",
            layout_intent="lead",
            lead="谢谢聆听，欢迎提问。",
        ),
    ]
    return PptSlidePlan(
        deck_title="TCP 三次握手",
        deck_subtitle="面向大一计算机专业学生",
        theme_id="heu_academic_elegant",
        chapters=[
            PptSlidePlanChapter(
                chapter_index=1,
                chapter_title="连接建立",
                chapter_goal="理解连接建立逻辑",
                slides=slides[2:4],
            )
        ],
        slides=slides,
    )


def test_content_markdown_assembler_emits_rich_blocks_from_slide_plan():
    markdown = PptContentMarkdownAssembler().assemble(slide_plan=_slide_plan())

    assert "# Deck" in markdown
    assert "## Slide 3" in markdown
    assert "- Comparison:" in markdown
    assert "- Cards:" in markdown
    assert "### Notes" in markdown
    assert "- Toc:" in markdown


def test_content_markdown_assembler_keeps_slide_plan_slide_order():
    markdown = PptContentMarkdownAssembler().assemble(slide_plan=_slide_plan())

    assert markdown.index("## Slide 1") < markdown.index("## Slide 2") < markdown.index("## Slide 3") < markdown.index("## Slide 4")
def test_content_markdown_assembler_matches_html2ppt_content_style_with_slide_separators():
    markdown = PptContentMarkdownAssembler().assemble(slide_plan=_slide_plan())

    assert "\n---\n\n## Slide 1" in markdown
    assert "\n---\n\n## Slide 2" in markdown
    assert "\n---\n\n## Slide 3" in markdown


def test_content_markdown_assembler_uses_chapter_titles_for_toc_instead_of_content_slide_titles():
    slides = [
        PptSlidePlanSlide(
            slide_index=1,
            role="cover",
            title="Agent",
            layout_intent="lead",
            lead="overview",
            bullets=["audience", "goal"],
        ),
        PptSlidePlanSlide(
            slide_index=2,
            role="toc",
            title="目录",
            layout_intent="bullets",
            bullets=["should", "not", "be", "used"],
        ),
        PptSlidePlanSlide(
            slide_index=3,
            role="content",
            title="核心工作循环：核心概念",
            layout_intent="bullets",
            lead="lead",
            bullets=["a", "b"],
        ),
        PptSlidePlanSlide(
            slide_index=4,
            role="content",
            title="核心工作循环：工作机制",
            layout_intent="bullets",
            lead="lead",
            bullets=["a", "b"],
        ),
        PptSlidePlanSlide(
            slide_index=5,
            role="content",
            title="工具调用：核心概念",
            layout_intent="bullets",
            lead="lead",
            bullets=["a", "b"],
        ),
        PptSlidePlanSlide(
            slide_index=6,
            role="thanks",
            title="Q&A",
            layout_intent="lead",
            lead="thanks",
        ),
    ]
    slide_plan = PptSlidePlan(
        deck_title="Agent",
        deck_subtitle="course",
        theme_id="heu_academic_elegant",
        chapters=[
            PptSlidePlanChapter(
                chapter_index=1,
                chapter_title="核心工作循环",
                chapter_goal="explain loop",
                slides=slides[2:4],
            ),
            PptSlidePlanChapter(
                chapter_index=2,
                chapter_title="工具调用",
                chapter_goal="explain tools",
                slides=[slides[4]],
            ),
        ],
        slides=slides,
    )

    markdown = PptContentMarkdownAssembler().assemble(slide_plan=slide_plan)
    toc_block = markdown.split("## Slide 2", 1)[1].split("---", 1)[0]

    assert "核心工作循环" in toc_block
    assert "工具调用" in toc_block
    assert "核心工作循环：核心概念" not in toc_block
    assert "核心工作循环：工作机制" not in toc_block
    assert "工具调用：核心概念" not in toc_block
