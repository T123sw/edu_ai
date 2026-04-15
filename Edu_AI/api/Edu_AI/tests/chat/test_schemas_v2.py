from app.chat.api.schemas_v2 import (
    ChatDirectPptGenerateResponseV2,
    ChatDirectPptOutlineResponseV2,
    ChatDirectReportResponseV2,
    ChatLessonPlanCardsRequestV2,
    ChatLessonPlanCardsResponseV2,
    ChatPptCardsRequestV2,
    ChatPptCardsResponseV2,
    ChatReportCardsRequestV2,
    ChatReportCardsResponseV2,
    ChatReportRequestV2,
    ChatResponseV2,
    DirectPptConfigV2,
    KnowledgeBaseDirectPptGenerateRequestV2,
    KnowledgeBaseDirectPptOutlineRequestV2,
    KnowledgeBaseDirectReportRequestV2,
    PptEntryCardSelectionV2,
    PptEntryPrefillConfigV2,
    ReportEntryCardSelectionV2,
)
from app.chat.schemas import ChatRequest


def test_chat_request_supports_allow_rag_and_allow_web():
    payload = ChatRequest(question="hello")

    assert payload.allow_rag is False
    assert payload.allow_web is False
    assert payload.selected_doc_ids == []


def test_chat_response_v2_supports_new_top_level_shape():
    payload = ChatResponseV2(
        message={"role": "assistant", "content": "ok"},
        conversation={"conversation_id": "conv-1"},
        action={"name": "chat.reply"},
        artifacts=[],
        workflow=None,
        sources=[],
        trace={"path": "fast"},
    )

    assert payload.message["content"] == "ok"
    assert payload.trace.path == "fast"


def test_chat_report_cards_request_supports_selected_docs():
    payload = ChatReportCardsRequestV2(
        course_id="course-1",
        selected_doc_ids=["doc-1", "doc-2"],
    )

    assert payload.course_id == "course-1"
    assert payload.selected_doc_ids == ["doc-1", "doc-2"]


def test_chat_ppt_cards_request_supports_selected_docs():
    payload = ChatPptCardsRequestV2(
        course_id="course-1",
        selected_doc_ids=["doc-1", "doc-2"],
    )

    assert payload.course_id == "course-1"
    assert payload.selected_doc_ids == ["doc-1", "doc-2"]


def test_chat_lesson_plan_cards_request_supports_selected_docs():
    payload = ChatLessonPlanCardsRequestV2(
        course_id="course-1",
        selected_doc_ids=["doc-1", "doc-2"],
    )

    assert payload.course_id == "course-1"
    assert payload.selected_doc_ids == ["doc-1", "doc-2"]


def test_chat_report_request_supports_knowledge_base_entry_fields():
    payload = ChatReportRequestV2(
        question="generate a report",
        entry_mode="knowledge_base_report",
        selected_doc_ids=["doc-1"],
        prompt_draft="draft",
        final_user_prompt="final prompt",
        selected_card=ReportEntryCardSelectionV2(
            card_id="preset-brief",
            card_type="preset",
            preset_key="brief",
        ),
    )

    assert payload.entry_mode == "knowledge_base_report"
    assert payload.prompt_draft == "draft"
    assert payload.final_user_prompt == "final prompt"
    assert payload.selected_card.card_id == "preset-brief"


def test_chat_report_cards_response_supports_unified_card_model():
    payload = ChatReportCardsResponseV2(
        entry_mode="knowledge_base_report",
        cards=[
            {
                "card_id": "preset-brief",
                "card_type": "preset",
                "title": "Brief report",
                "description": "Summarize the key ideas.",
                "prompt_draft": "Generate a brief report.",
                "preset_key": "brief",
            },
            {
                "card_id": "rec-summary",
                "card_type": "recommended",
                "title": "Core summary",
                "description": "Summarize the core content.",
                "prompt_draft": "Summarize the selected documents.",
                "recommendation_type": "summary",
                "recommendation_source": "doc_summaries",
                "fit_score": "high",
            },
        ],
        trace={"cache_hit": False, "selected_doc_count": 2},
    )

    assert payload.entry_mode == "knowledge_base_report"
    assert payload.cards[0].preset_key == "brief"
    assert payload.cards[1].recommendation_type == "summary"
    assert payload.cards[1].fit_score == "high"


def test_chat_lesson_plan_cards_response_supports_unified_card_model():
    payload = ChatLessonPlanCardsResponseV2(
        entry_mode="knowledge_base_lesson_plan",
        default_selected_card_id="preset-new-lesson",
        cards=[
            {
                "card_id": "preset-new-lesson",
                "card_type": "preset",
                "title": "新授课教案",
                "description": "适合围绕核心概念和关键材料组织单课时教学。",
                "prompt_draft": "请基于已选文档生成一份新授课教案。",
                "preset_key": "new_lesson",
                "prefill_config": {
                    "topic": "关羽的战绩与历史评价",
                    "audience": "初中历史",
                    "duration": "45分钟",
                    "lesson_type": "新授课",
                    "objective": "梳理主要战绩并辩证评价人物形象",
                    "style_hint": "贴近真实课堂，突出问题链和史料分析",
                },
            },
            {
                "card_id": "rec-historical-inquiry",
                "card_type": "recommended",
                "title": "史料探究教案",
                "description": "适合围绕史料辨析、观点比较与课堂讨论组织教学。",
                "prompt_draft": "请基于已选文档生成一份史料探究课教案。",
                "recommendation_type": "historical_inquiry",
                "recommendation_source": "doc_summaries",
                "fit_score": "high",
                "prefill_config": {
                    "topic": "关羽的战绩与历史评价",
                    "audience": "初中历史",
                    "duration": "45分钟",
                    "lesson_type": "探究课",
                    "objective": "通过史料辨析形成历史评价",
                },
            },
        ],
        trace={"selected_doc_count": 2},
    )

    assert payload.entry_mode == "knowledge_base_lesson_plan"
    assert payload.default_selected_card_id == "preset-new-lesson"
    assert payload.cards[0].preset_key == "new_lesson"
    assert payload.cards[1].recommendation_type == "historical_inquiry"
    assert payload.cards[1].prefill_config.topic == "关羽的战绩与历史评价"


def test_knowledge_base_direct_report_request_supports_selected_docs_and_prompt_fields():
    payload = KnowledgeBaseDirectReportRequestV2(
        question="generate report",
        course_id="course-1",
        selected_doc_ids=["doc-1"],
        prompt_draft="draft",
        final_user_prompt="final prompt",
        selected_card=ReportEntryCardSelectionV2(
            card_id="preset-brief",
            card_type="preset",
            preset_key="brief",
        ),
        report_config={"source_scope": "selected_documents_only"},
    )

    assert payload.question == "generate report"
    assert payload.selected_doc_ids == ["doc-1"]
    assert payload.final_user_prompt == "final prompt"
    assert payload.selected_card.card_id == "preset-brief"


def test_chat_direct_report_response_supports_artifact_only_shape():
    payload = ChatDirectReportResponseV2(
        action={"name": "generate.report.direct"},
        artifacts=[
            {
                "artifact_id": "report-1",
                "artifact_type": "report",
                "title": "report.md",
                "content": "# report",
            }
        ],
        trace={"path": "direct", "selected_doc_count": 1},
    )

    assert payload.action["name"] == "generate.report.direct"
    assert payload.trace.path == "direct"
    assert payload.artifacts[0]["artifact_type"] == "report"


def test_direct_ppt_outline_request_supports_selected_docs_and_config():
    payload = KnowledgeBaseDirectPptOutlineRequestV2(
        course_id="course-1",
        selected_doc_ids=["doc-1"],
        ppt_config=DirectPptConfigV2(
            deck_title="Agent Basics",
            audience="Undergraduate students",
            objective="Classroom presentation",
            theme_id="heu_academic_elegant",
            length_option="medium",
            target_slide_count=16,
            key_points=["Definition", "Workflow"],
            general_requirements="Audience is high school students.",
            selected_card=PptEntryCardSelectionV2(
                card_id="preset-knowledge-lecture",
                card_type="preset",
                preset_key="knowledge_lecture",
            ),
        ),
    )

    assert payload.course_id == "course-1"
    assert payload.selected_doc_ids == ["doc-1"]
    assert payload.ppt_config.target_slide_count == 16
    assert payload.ppt_config.length_option == "medium"


def test_direct_ppt_generate_request_uses_draft_id():
    payload = KnowledgeBaseDirectPptGenerateRequestV2(
        draft_id="ppt-draft-1",
        confirm=True,
        outline={"deck_title": "Agent Basics", "slides": []},
    )

    assert payload.draft_id == "ppt-draft-1"
    assert payload.confirm is True
    assert payload.outline["deck_title"] == "Agent Basics"


def test_direct_ppt_outline_response_supports_draft_payload():
    payload = ChatDirectPptOutlineResponseV2(
        action={"name": "generate.ppt.outline.direct"},
        draft={"draft_id": "ppt-draft-1", "status": "outline_ready"},
        artifacts=[],
        trace={"path": "direct", "draft_id": "ppt-draft-1"},
    )

    assert payload.action["name"] == "generate.ppt.outline.direct"
    assert payload.draft["draft_id"] == "ppt-draft-1"


def test_chat_ppt_cards_response_supports_ppt_card_model():
    payload = ChatPptCardsResponseV2(
        entry_mode="knowledge_base_ppt",
        default_selected_card_id="preset-knowledge-lecture",
        cards=[
            {
                "card_id": "preset-knowledge-lecture",
                "card_type": "preset",
                "title": "Knowledge lecture",
                "description": "Lecture-oriented PPT entry.",
                "objective_hint": "课堂讲解",
                "length_option": "medium",
                "preset_key": "knowledge_lecture",
                "prefill_config": {
                    "deck_title": "System skills",
                    "audience": "本科生",
                    "objective": "课堂讲解",
                    "theme_id": "heu_academic_basic",
                    "length_option": "medium",
                    "target_slide_count": 16,
                    "key_points": ["定义", "流程"],
                },
            }
        ],
        trace={"selected_doc_count": 1},
    )

    assert payload.entry_mode == "knowledge_base_ppt"
    assert payload.default_selected_card_id == "preset-knowledge-lecture"
    assert payload.cards[0].preset_key == "knowledge_lecture"
    assert payload.cards[0].prefill_config.theme_id == "heu_academic_basic"


def test_ppt_entry_prefill_config_supports_allowed_themes():
    payload = PptEntryPrefillConfigV2(
        deck_title="System skills",
        audience="本科生",
        objective="课堂讲解",
        theme_id="heu_academic_basic",
        length_option="short",
        target_slide_count=10,
        key_points=["定义"],
    )

    assert payload.theme_id == "heu_academic_basic"
    assert payload.length_option == "short"


def test_direct_ppt_generate_response_supports_run_payload():
    payload = ChatDirectPptGenerateResponseV2(
        action={"name": "generate.ppt.direct"},
        run={"run_id": "ppt-run-1", "status": "running"},
        artifacts=[],
        trace={"path": "direct", "draft_id": "ppt-draft-1", "run_id": "ppt-run-1"},
    )

    assert payload.action["name"] == "generate.ppt.direct"
    assert payload.run["run_id"] == "ppt-run-1"
