from app.chat.orchestrator.lesson_plan_structure_parser import parse_lesson_plan_nodes


def test_parse_lesson_plan_nodes_emits_field_and_process_nodes():
    nodes = parse_lesson_plan_nodes(
        artifact_id="lesson-plan-1",
        artifact_type="lesson_plan",
        content={
            "title": "\u5206\u6570\u7684\u610f\u4e49",
            "objectives": ["\u7406\u89e3\u5206\u6570\u7684\u610f\u4e49"],
            "process": [{"step": "\u5bfc\u5165", "goal": "\u8054\u7cfb\u751f\u6d3b\u7ecf\u9a8c", "duration": "5\u5206\u949f"}],
        },
    )

    assert nodes[0]["node_type"] == "field"
    assert any(node["node_label"] == "\u6559\u5b66\u76ee\u6807" for node in nodes)
    assert any(node["node_label"] == "\u5bfc\u5165" for node in nodes)


def test_parse_lesson_plan_outline_nodes_emits_basic_fields_and_flow_nodes():
    nodes = parse_lesson_plan_nodes(
        artifact_id="outline-1",
        artifact_type="lesson_plan_outline",
        content={
            "basic_info": {"topic": "\u5206\u6570\u7684\u610f\u4e49", "duration": "40\u5206\u949f"},
            "lesson_flow": [{"step": "\u5bfc\u5165", "goal": "\u8fdb\u5165\u4e3b\u9898"}],
        },
    )

    assert any(node["node_label"] == "topic" for node in nodes)
    assert any(node["node_label"] == "\u5bfc\u5165" for node in nodes)
