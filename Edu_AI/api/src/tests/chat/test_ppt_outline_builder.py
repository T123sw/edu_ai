from types import SimpleNamespace

from app.chat.workflows.ppt.outline_builder import PptOutlineBuilder


def _make_preparation(**overrides):
    payload = {
        "deck_topic": "Agent Systems",
        "audience": "General learners",
        "objective": "Classroom teaching",
        "key_points": [
            "Agent definition",
            "Tool calling architecture",
            "Skills system design",
            "Real-world examples",
        ],
        "slide_count": 8,
        "theme_id": "heu_academic_elegant",
        "source_basis": ["conversation_summary", "artifact_context"],
        "source_excerpts": [
            "Agent systems combine reasoning, tool use, and observation.",
            "Students often confuse the historical concept with product packaging claims.",
        ],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_outline_builder_creates_chapter_and_page_level_structure_without_duplicate_content_titles():
    outline = PptOutlineBuilder(llm=None).build(preparation=_make_preparation())

    assert outline.deck_title == "Agent Systems"
    assert outline.confirmation_status == "pending"
    assert outline.slides[0].role == "cover"
    assert outline.slides[1].role == "toc"
    assert outline.slides[-1].role == "thanks"
    content_titles = [slide.title for slide in outline.slides if slide.role == "content"]
    assert len(content_titles) == len(set(content_titles))
    assert len(outline.chapters) >= 2


def test_outline_builder_prompt_requests_instructional_expansion_and_substantial_deck():
    class DummyLLM:
        def __init__(self):
            self.prompts: list[str] = []

        def invoke(self, prompt, *_args, **_kwargs):
            self.prompts.append(prompt)
            return ""

    llm = DummyLLM()
    builder = PptOutlineBuilder(llm=llm)
    builder.build(preparation=_make_preparation(slide_count=None))

    prompt = llm.prompts[0]
    assert "instructional designer" in prompt
    assert "You may extend the provided context" in prompt
    assert "15-20+ slides overall" in prompt
    assert "not a short summary" in prompt
    assert "Grounded source excerpts" in prompt
    assert "Seed key points" in prompt


def test_outline_builder_sanitizes_duplicate_llm_outline_into_unique_content_slides():
    class DummyLLM:
        def invoke(self, *_args, **_kwargs):
            return """
            {
              "deck_title": "Agent Systems",
              "deck_subtitle": "General learners",
              "theme_id": "heu_academic_elegant",
              "confirmation_status": "pending",
              "chapters": [
                {
                  "chapter_index": 1,
                  "chapter_title": "Agent Systems",
                  "chapter_goal": "Explain the core concept",
                  "slides": [
                    {
                      "slide_index": 3,
                      "role": "content",
                      "title": "Agent Systems",
                      "goal": "Explain the core concept",
                      "key_points": ["definition", "traits"]
                    },
                    {
                      "slide_index": 4,
                      "role": "content",
                      "title": "Agent Systems",
                      "goal": "Explain the architecture",
                      "key_points": ["tools", "execution"]
                    }
                  ]
                }
              ],
              "slides": [
                {
                  "slide_index": 1,
                  "role": "cover",
                  "title": "Agent Systems",
                  "goal": "Classroom teaching",
                  "key_points": ["teaching"]
                },
                {
                  "slide_index": 2,
                  "role": "toc",
                  "title": "Agenda",
                  "goal": "Show the structure",
                  "key_points": ["concept", "architecture", "examples"]
                },
                {
                  "slide_index": 3,
                  "role": "content",
                  "title": "Agent Systems",
                  "goal": "Explain the core concept",
                  "key_points": ["definition", "traits"]
                },
                {
                  "slide_index": 4,
                  "role": "content",
                  "title": "Agent Systems",
                  "goal": "Explain the architecture",
                  "key_points": ["tools", "execution"]
                },
                {
                  "slide_index": 5,
                  "role": "thanks",
                  "title": "Q&A",
                  "goal": "Wrap up",
                  "key_points": ["questions"]
                }
              ]
            }
            """

    outline = PptOutlineBuilder(llm=DummyLLM()).build(preparation=_make_preparation())

    content_titles = [slide.title for slide in outline.slides if slide.role == "content"]
    chapter_titles = [chapter.chapter_title for chapter in outline.chapters]

    assert len(content_titles) >= 3
    assert len(content_titles) == len(set(content_titles))
    assert len(chapter_titles) == len(set(chapter_titles))
    assert "Tool calling architecture" in content_titles


def test_outline_builder_normalizes_freeform_theme_names_to_supported_theme_id():
    outline = PptOutlineBuilder(llm=None).build(
        preparation=_make_preparation(theme_id="custom theme")
    )

    assert outline.theme_id == "heu_academic_elegant"


def test_outline_builder_fallback_splits_rich_key_points_into_multiple_chapters():
    outline = PptOutlineBuilder(llm=None).build(
        preparation=_make_preparation(
            deck_topic="History Of Guan Yu",
            audience="High school history class",
            objective="Explain how a historical figure became a cultural image",
            key_points=["era background", "image formation", "religious meaning", "literary shaping", "real impact"],
            slide_count=9,
        )
    )

    assert len(outline.chapters) >= 2
    assert all(chapter.chapter_title for chapter in outline.chapters)
    assert all(chapter.chapter_goal for chapter in outline.chapters)
    content_titles = [slide.title for slide in outline.slides if slide.role == "content"]
    assert len(content_titles) == len(set(content_titles))


def test_outline_builder_allows_rich_input_to_reach_fifteen_pages_when_slide_count_is_missing():
    outline = PptOutlineBuilder(llm=None).build(
        preparation=_make_preparation(
            slide_count=None,
            key_points=[
                "Agent definition",
                "Core components",
                "Reasoning and planning",
                "Tool calling",
                "Memory",
                "Workflow orchestration",
                "MCP",
                "Typical applications",
                "Classroom examples",
                "Common pitfalls",
                "Safety and limits",
                "Summary",
            ],
        )
    )

    assert len(outline.slides) == 15


def test_outline_builder_defaults_to_compact_fallback_when_slide_count_is_missing():
    outline = PptOutlineBuilder(llm=None).build(
        preparation=_make_preparation(
            slide_count=None,
            key_points=["Agent definition", "Core components", "Tool calling"],
        )
    )

    assert len(outline.slides) == 6


def test_outline_builder_does_not_force_fifteen_pages_in_rule_fallback():
    outline = PptOutlineBuilder(llm=None).build(
        preparation=_make_preparation(
            slide_count=15,
            key_points=[
                "Core loop",
                "Tool calling details",
                "Skills design and applications",
            ],
        )
    )

    content_titles = [slide.title for slide in outline.slides if slide.role == "content"]

    assert len(outline.slides) == 6
    assert len(content_titles) == 3
    assert len(content_titles) == len(set(content_titles))


def test_outline_builder_keeps_sparse_llm_outline_without_rule_based_forced_expansion():
    class DummyLLM:
        def invoke(self, *_args, **_kwargs):
            return """
            {
              "deck_title": "Agent Workflow",
              "deck_subtitle": "General learners",
              "theme_id": "heu_academic_elegant",
              "confirmation_status": "pending",
              "chapters": [
                {
                  "chapter_index": 1,
                  "chapter_title": "Core traits",
                  "chapter_goal": "Explain the core traits",
                  "slides": [
                    {
                      "slide_index": 3,
                      "role": "content",
                      "title": "Core loop",
                      "goal": "Explain the core loop",
                      "key_points": ["observe", "plan", "act"]
                    },
                    {
                      "slide_index": 4,
                      "role": "content",
                      "title": "Tool calling details",
                      "goal": "Explain tool calling details",
                      "key_points": ["interface", "arguments", "results"]
                    },
                    {
                      "slide_index": 5,
                      "role": "content",
                      "title": "Skills design and applications",
                      "goal": "Explain skills design and applications",
                      "key_points": ["modularity", "reuse", "composition"]
                    }
                  ]
                }
              ],
              "slides": [
                {
                  "slide_index": 1,
                  "role": "cover",
                  "title": "Agent Workflow",
                  "goal": "Classroom teaching",
                  "key_points": ["teaching", "general learners"]
                },
                {
                  "slide_index": 2,
                  "role": "toc",
                  "title": "Agenda",
                  "goal": "Show the structure",
                  "key_points": ["traits", "tools", "skills"]
                },
                {
                  "slide_index": 3,
                  "role": "content",
                  "title": "Core loop",
                  "goal": "Explain the core loop",
                  "key_points": ["observe", "plan", "act"]
                },
                {
                  "slide_index": 4,
                  "role": "content",
                  "title": "Tool calling details",
                  "goal": "Explain tool calling details",
                  "key_points": ["interface", "arguments", "results"]
                },
                {
                  "slide_index": 5,
                  "role": "content",
                  "title": "Skills design and applications",
                  "goal": "Explain skills design and applications",
                  "key_points": ["modularity", "reuse", "composition"]
                },
                {
                  "slide_index": 6,
                  "role": "thanks",
                  "title": "Q&A",
                  "goal": "Wrap up",
                  "key_points": ["questions"]
                }
              ]
            }
            """

    outline = PptOutlineBuilder(llm=DummyLLM()).build(
        preparation=_make_preparation(
            slide_count=15,
            key_points=["Core loop", "Tool calling details", "Skills design and applications"],
        )
    )

    content_titles = [slide.title for slide in outline.slides if slide.role == "content"]

    assert len(outline.slides) == 6
    assert len(content_titles) == 3
    assert len(content_titles) == len(set(content_titles))


def test_outline_builder_falls_back_when_llm_invoke_raises():
    class DummyLLM:
        def invoke(self, *_args, **_kwargs):
            raise RuntimeError("llm unavailable")

    outline = PptOutlineBuilder(llm=DummyLLM()).build(
        preparation=_make_preparation(
            deck_topic="Skills In Agent Systems",
            audience="General learners",
            objective="Classroom teaching",
            key_points=["concept", "workflow", "applications"],
            slide_count=6,
        )
    )

    assert outline.deck_title == "Skills In Agent Systems"
    assert len(outline.slides) == 6
    assert outline.slides[0].role == "cover"
    assert outline.slides[-1].role == "thanks"
