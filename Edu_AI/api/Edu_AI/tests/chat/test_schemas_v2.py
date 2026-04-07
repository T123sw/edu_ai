from app.chat.api.schemas_v2 import (
    ChatReportCardsRequestV2,
    ChatReportCardsResponseV2,
    ChatDirectReportResponseV2,
    ChatReportRequestV2,
    ChatResponseV2,
    KnowledgeBaseDirectReportRequestV2,
    ReportEntryCardSelectionV2,
)
from app.chat.schemas import ChatRequest


def test_chat_request_supports_allow_rag_and_allow_web():
    payload = ChatRequest(question="你好")

    assert payload.allow_rag is False
    assert payload.allow_web is False
    assert payload.selected_doc_ids == []


def test_chat_response_v2_supports_new_top_level_shape():
    payload = ChatResponseV2(
        message={"role": "assistant", "content": "测试回复"},
        conversation={"conversation_id": "conv-1"},
        action={"name": "chat.reply"},
        artifacts=[],
        workflow=None,
        sources=[],
        trace={"path": "fast"},
    )

    assert payload.message["content"] == "测试回复"
    assert payload.trace.path == "fast"


def test_chat_report_cards_request_supports_selected_docs():
    payload = ChatReportCardsRequestV2(
        course_id="course-1",
        selected_doc_ids=["doc-1", "doc-2"],
    )

    assert payload.course_id == "course-1"
    assert payload.selected_doc_ids == ["doc-1", "doc-2"]


def test_chat_report_request_supports_knowledge_base_entry_fields():
    payload = ChatReportRequestV2(
        question="请基于已选文档生成报告",
        entry_mode="knowledge_base_report",
        selected_doc_ids=["doc-1"],
        prompt_draft="默认草稿",
        final_user_prompt="最终草稿",
        selected_card=ReportEntryCardSelectionV2(
            card_id="preset-brief",
            card_type="preset",
            preset_key="brief",
        ),
    )

    assert payload.entry_mode == "knowledge_base_report"
    assert payload.prompt_draft == "默认草稿"
    assert payload.final_user_prompt == "最终草稿"
    assert payload.selected_card.card_id == "preset-brief"


def test_chat_report_cards_response_supports_unified_card_model():
    payload = ChatReportCardsResponseV2(
        entry_mode="knowledge_base_report",
        cards=[
            {
                "card_id": "preset-brief",
                "card_type": "preset",
                "title": "简要报告",
                "description": "提炼核心信息",
                "prompt_draft": "请基于已选文档生成简要报告",
                "preset_key": "brief",
            },
            {
                "card_id": "rec-summary",
                "card_type": "recommended",
                "title": "核心内容总结",
                "description": "总结材料重点",
                "prompt_draft": "请基于已选文档总结核心内容",
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


def test_knowledge_base_direct_report_request_supports_selected_docs_and_prompt_fields():
    payload = KnowledgeBaseDirectReportRequestV2(
        question="请生成报告",
        course_id="course-1",
        selected_doc_ids=["doc-1"],
        prompt_draft="默认草稿",
        final_user_prompt="最终要求",
        selected_card=ReportEntryCardSelectionV2(
            card_id="preset-brief",
            card_type="preset",
            preset_key="brief",
        ),
        report_config={"source_scope": "selected_documents_only"},
    )

    assert payload.question == "请生成报告"
    assert payload.selected_doc_ids == ["doc-1"]
    assert payload.final_user_prompt == "最终要求"
    assert payload.selected_card.card_id == "preset-brief"


def test_chat_direct_report_response_supports_artifact_only_shape():
    payload = ChatDirectReportResponseV2(
        action={"name": "generate.report.direct"},
        artifacts=[
            {
                "artifact_id": "report-1",
                "artifact_type": "report",
                "title": "测试报告.md",
                "content": "# 测试报告\n\n正文",
            }
        ],
        trace={"path": "direct", "selected_doc_count": 1},
    )

    assert payload.action["name"] == "generate.report.direct"
    assert payload.trace.path == "direct"
    assert payload.artifacts[0]["artifact_type"] == "report"
