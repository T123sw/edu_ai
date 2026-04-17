from app.chat.orchestrator.report_edit_intent_parser import parse_report_edit_intent


def test_parse_edit_intent_for_summary_compress():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="\u628a\u6458\u8981\u538b\u7f29\u5230150\u5b57\u4ee5\u5185",
        structure_nodes=[
            {"node_id": "summary-1", "node_type": "summary", "title": "\u6458\u8981", "order_index": 1},
            {"node_id": "section-2", "node_type": "section", "title": "\u7b2c\u4e8c\u90e8\u5206", "order_index": 2},
        ],
    )

    assert request["target_type"] == "report"
    assert request["action_type"] == "compress"
    assert request["target_node_id"] == "summary-1"


def test_parse_edit_intent_for_outline_regenerate():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "outline-1", "artifact_type": "report_outline", "version_id": "v1"},
        question="\u57fa\u4e8e\u8fd9\u4e2a\u5927\u7eb2\u91cd\u65b0\u751f\u6210\u4e00\u7248\u6b63\u5f0f\u62a5\u544a",
        structure_nodes=[
            {"node_id": "outline-1:1", "node_type": "section", "title": "\u95ee\u9898\u754c\u5b9a", "order_index": 1},
        ],
    )

    assert request["target_type"] == "outline"
    assert request["action_type"] == "regenerate"
    assert request["target_node_id"] is None


def test_parse_edit_intent_for_conclusion_rewrite():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="\u4fdd\u7559\u7ed3\u6784\uff0c\u91cd\u5199\u7ed3\u8bba",
        structure_nodes=[
            {"node_id": "summary-1", "node_type": "summary", "title": "\u6458\u8981", "order_index": 1},
            {"node_id": "conclusion-3", "node_type": "conclusion", "title": "\u7ed3\u8bba", "order_index": 3},
        ],
    )

    assert request["target_type"] == "report"
    assert request["action_type"] == "rewrite"
    assert request["target_node_id"] == "conclusion-3"


def test_parse_edit_intent_marks_ambiguous_reference_for_disambiguation():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="\u4fee\u6539\u8fd9\u4e00\u90e8\u5206\uff0c\u66f4\u5f3a\u8c03\u8bfe\u5802\u4e92\u52a8",
        structure_nodes=[
            {"node_id": "summary-1", "node_type": "summary", "title": "\u6458\u8981", "order_index": 1},
            {"node_id": "section-2", "node_type": "section", "title": "\u8bfe\u5802\u95ee\u9898\u5206\u6790", "order_index": 2},
            {"node_id": "conclusion-3", "node_type": "conclusion", "title": "\u7ed3\u8bba", "order_index": 3},
        ],
    )

    assert request["needs_disambiguation"] is True
    assert request["target_node_id"] is None
    assert request["candidate_labels"] == ["\u6458\u8981", "\u8bfe\u5802\u95ee\u9898\u5206\u6790", "\u7ed3\u8bba"]


def test_parse_edit_intent_matches_section_title_before_fallback():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="\u628a\u201c\u7b2c\u4e8c\u90e8\u5206\u201d\u8fd9\u4e00\u8282\u6539\u77ed\u4e00\u70b9",
        structure_nodes=[
            {"node_id": "summary-1", "node_type": "summary", "title": "\u6458\u8981", "order_index": 1, "content": "\u539f\u6458\u8981"},
            {"node_id": "section-2", "node_type": "section", "title": "\u7b2c\u4e8c\u90e8\u5206", "order_index": 2, "content": "\u539f\u7b2c\u4e8c\u90e8\u5206"},
        ],
    )

    assert request["intent_type"] == "edit_artifact"
    assert request["target_locator_type"] == "title"
    assert request["target_node_id"] == "section-2"


def test_parse_edit_intent_matches_quoted_snippet_to_single_node():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="\u628a\u201c\u539f\u7b2c\u4e8c\u90e8\u5206\u201d\u8fd9\u53e5\u6539\u5f97\u66f4\u6b63\u5f0f",
        structure_nodes=[
            {"node_id": "summary-1", "node_type": "summary", "title": "\u6458\u8981", "order_index": 1, "content": "\u539f\u6458\u8981"},
            {"node_id": "section-2", "node_type": "section", "title": "\u7b2c\u4e8c\u90e8\u5206", "order_index": 2, "content": "\u539f\u7b2c\u4e8c\u90e8\u5206"},
        ],
    )

    assert request["intent_type"] == "edit_artifact"
    assert request["target_locator_type"] == "snippet"
    assert request["matched_snippet"] == "\u539f\u7b2c\u4e8c\u90e8\u5206"
    assert request["target_node_id"] == "section-2"
