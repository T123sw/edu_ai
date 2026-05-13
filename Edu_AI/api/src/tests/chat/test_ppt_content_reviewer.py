from app.chat.domain.ppt_outline import PptOutline
from app.chat.domain.ppt_slide_plan import PptSlidePlan, PptSlidePlanSlide
from app.chat.workflows.ppt.content_reviewer import PptContentReviewer


def _outline() -> PptOutline:
    return PptOutline(
        deck_title="Agent Systems",
        deck_subtitle="course",
        theme_id="heu_academic_elegant",
        slides=[],
        chapters=[],
    )


def test_content_reviewer_prompt_includes_protocol_constraints():
    prompts: list[str] = []

    class DummyLLM:
        def invoke(self, prompt: str):
            prompts.append(prompt)
            return '{"ok": true, "issues": [], "feedback": ""}'

    slide_plan = PptSlidePlan(
        deck_title="Agent Systems",
        deck_subtitle="course",
        theme_id="heu_academic_elegant",
        slides=[
            PptSlidePlanSlide(
                slide_index=3,
                role="content",
                title="Core Loop",
                layout_intent="bullets",
                lead="Use one question to open the concept.",
                bullets=["Point A", "Point B", "Point C"],
                presenter_notes="Keep it concrete.",
            )
        ],
    )
    preparation = type(
        "Preparation",
        (),
        {
            "audience": "General learners",
            "objective": "Classroom teaching",
        },
    )()

    reviewer = PptContentReviewer(llm=DummyLLM())
    result = reviewer.review(
        outline=_outline(),
        slide_plan=slide_plan,
        content_markdown="# Deck\n",
        preparation=preparation,
    )

    assert result["ok"] is True
    assert prompts
    prompt = prompts[0]
    assert "Role + Blocks" in prompt
    assert "cover, toc, section, content, thanks" in prompt
    assert "Do not allow layout_hint" in prompt
    assert "bullets -> Lead/Bullets/Meta" in prompt
    assert "comparison -> Comparison" in prompt
    assert "too sparse" in prompt


def test_content_reviewer_heuristic_flags_layout_hint_and_invalid_role():
    slide_plan = PptSlidePlan(
        deck_title="Agent Systems",
        deck_subtitle="course",
        theme_id="heu_academic_elegant",
        slides=[
            PptSlidePlanSlide(
                slide_index=3,
                role="custom_role",
                title="Core Loop",
                layout_intent="bullets",
                lead="layout_hint: card-layout",
                bullets=["Point A", "Point B"],
                presenter_notes="Keep it concrete.",
            )
        ],
    )

    reviewer = PptContentReviewer(llm=None)
    result = reviewer.review(
        outline=_outline(),
        slide_plan=slide_plan,
        content_markdown="# Deck\n",
        preparation=type("Preparation", (), {"slide_count": 18})(),
    )

    assert result["ok"] is False
    assert any("layout_hint" in issue for issue in result["issues"])
    assert any("invalid role" in issue.lower() for issue in result["issues"])


def test_content_reviewer_heuristic_flags_sparse_content_slide():
    slide_plan = PptSlidePlan(
        deck_title="Agent Systems",
        deck_subtitle="course",
        theme_id="heu_academic_elegant",
        slides=[
            PptSlidePlanSlide(
                slide_index=3,
                role="content",
                title="Core Loop",
                layout_intent="bullets",
                lead="Overview only.",
                bullets=["One point"],
                presenter_notes="Keep it concrete.",
            )
        ],
    )

    reviewer = PptContentReviewer(llm=None)
    result = reviewer.review(
        outline=_outline(),
        slide_plan=slide_plan,
        content_markdown="# Deck\n",
        preparation=type("Preparation", (), {"slide_count": 18})(),
    )

    assert result["ok"] is False
    assert any("too sparse" in issue.lower() for issue in result["issues"])
