from app.chat.orchestrator.report_edit_intent_parser import parse_report_edit_intent


def test_parse_edit_intent_for_summary_compress():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="把摘要压缩到150字以内",
        structure_nodes=[
            {"node_id": "summary-1", "node_type": "summary", "title": "摘要", "order_index": 1},
            {"node_id": "section-2", "node_type": "section", "title": "第二部分", "order_index": 2},
        ],
    )

    assert request["target_type"] == "report"
    assert request["action_type"] == "compress"
    assert request["target_node_id"] == "summary-1"


def test_parse_edit_intent_for_outline_regenerate():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "outline-1", "artifact_type": "report_outline", "version_id": "v1"},
        question="基于这个大纲重新生成一版正式报告",
        structure_nodes=[
            {"node_id": "outline-1:1", "node_type": "section", "title": "问题界定", "order_index": 1},
        ],
    )

    assert request["target_type"] == "outline"
    assert request["action_type"] == "regenerate"
    assert request["target_node_id"] is None


def test_parse_edit_intent_for_conclusion_rewrite():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="保留结构，重写结论",
        structure_nodes=[
            {"node_id": "summary-1", "node_type": "summary", "title": "摘要", "order_index": 1},
            {"node_id": "conclusion-3", "node_type": "conclusion", "title": "结论", "order_index": 3},
        ],
    )

    assert request["target_type"] == "report"
    assert request["action_type"] == "rewrite"
    assert request["target_node_id"] == "conclusion-3"


def test_parse_edit_intent_marks_ambiguous_reference_for_disambiguation():
    request = parse_report_edit_intent(
        artifact_reference={"artifact_id": "report-1", "artifact_type": "report", "version_id": "v1"},
        question="修改这一部分，更强调课堂互动",
        structure_nodes=[
            {"node_id": "summary-1", "node_type": "summary", "title": "摘要", "order_index": 1},
            {"node_id": "section-2", "node_type": "section", "title": "课堂问题分析", "order_index": 2},
            {"node_id": "conclusion-3", "node_type": "conclusion", "title": "结论", "order_index": 3},
        ],
    )

    assert request["needs_disambiguation"] is True
    assert request["target_node_id"] is None
    assert request["candidate_labels"] == ["摘要", "课堂问题分析", "结论"]
