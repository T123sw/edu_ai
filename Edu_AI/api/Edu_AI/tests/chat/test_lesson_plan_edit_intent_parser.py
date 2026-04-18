from app.chat.orchestrator.lesson_plan_edit_intent_parser import parse_lesson_plan_edit_intent


def test_parse_lesson_plan_edit_intent_matches_named_field_exactly():
    request = parse_lesson_plan_edit_intent(
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan"},
        question="重写教学目标",
        structure_nodes=[
            {
                "node_id": "lp-1:objectives",
                "node_type": "field",
                "node_key": "objectives",
                "node_label": "教学目标",
                "content": ["理解分数"],
            },
        ],
    )

    assert request["target_confidence"] == "exact"
    assert request["target_node_id"] == "lp-1:objectives"


def test_parse_lesson_plan_edit_intent_returns_candidate_for_repeated_activity_steps():
    request = parse_lesson_plan_edit_intent(
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan"},
        question="把活动部分改一下",
        structure_nodes=[
            {"node_id": "lp-1:process:1", "node_type": "step", "node_label": "小组活动"},
            {"node_id": "lp-1:process:2", "node_type": "step", "node_label": "活动总结"},
        ],
    )

    assert request["target_confidence"] == "candidate"
    assert request["candidate_labels"] == ["小组活动", "活动总结"]


def test_parse_lesson_plan_edit_intent_returns_unclear_when_no_safe_target_exists():
    request = parse_lesson_plan_edit_intent(
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan"},
        question="优化一下这个教案",
        structure_nodes=[
            {"node_id": "lp-1:objectives", "node_type": "field", "node_label": "教学目标"},
            {"node_id": "lp-1:process:1", "node_type": "step", "node_label": "导入"},
        ],
    )

    assert request["target_confidence"] == "unclear"
    assert request["target_node_id"] is None


def test_parse_lesson_plan_edit_intent_matches_numbered_step_exactly():
    request = parse_lesson_plan_edit_intent(
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan_outline"},
        question="修改第2个环节",
        structure_nodes=[
            {"node_id": "lp-1:lesson_flow:1", "node_type": "step", "node_label": "导入", "order_index": 1},
            {"node_id": "lp-1:lesson_flow:2", "node_type": "step", "node_label": "合作探究", "order_index": 2},
        ],
    )

    assert request["target_confidence"] == "exact"
    assert request["target_node_id"] == "lp-1:lesson_flow:2"


def test_parse_lesson_plan_edit_intent_routes_question_to_ask_about_artifact():
    request = parse_lesson_plan_edit_intent(
        artifact_reference={"artifact_id": "lp-1", "artifact_type": "lesson_plan"},
        question="这份教案的教学重点是什么？",
        structure_nodes=[
            {"node_id": "lp-1:keyPoints", "node_type": "field", "node_label": "教学重点"},
        ],
    )

    assert request["intent_type"] == "ask_about_artifact"
    assert request["action_type"] == "ask_about_artifact"
