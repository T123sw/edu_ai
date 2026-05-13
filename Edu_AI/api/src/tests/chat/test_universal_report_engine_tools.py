from app.chat.agents.universal_report_engine import generator_node, outliner_node


def test_outliner_node_uses_injected_submit_tool():
    seen = {}

    def fake_submit_outline_for_review(*, outline_json_str: str):
        seen["outline_json_str"] = outline_json_str
        return {"ok": True, "payload": {"outline": []}}

    result = outliner_node(
        {
            "report_slots": {"core_topic": "topic", "focus_area": "focus"},
            "report_outline": [],
            "human_feedback": "",
        },
        tool_registry={
            "submit_outline_for_review": {
                "callable": fake_submit_outline_for_review,
            }
        },
    )

    assert "outline_json_str" in seen
    assert result["status"] == "awaiting_human"


def test_generator_node_uses_injected_generate_tool():
    seen = {}

    def fake_generate_long_report_content(*, slots, outline):
        seen["slots"] = slots
        seen["outline"] = outline
        return {
            "ok": True,
            "payload": {
                "content": "generated-content",
                "checkpoint": {},
            },
        }

    result = generator_node(
        {
            "soft_confirmed": True,
            "outline_confirmed": True,
            "report_slots": {"core_topic": "topic"},
            "report_outline": [{"chapter_title": "chapter-1"}],
            "replan_count": 0,
            "max_replans": 3,
        },
        tool_registry={
            "generate_long_report_content": {
                "callable": fake_generate_long_report_content,
            }
        },
    )

    assert seen["slots"]["core_topic"] == "topic"
    assert seen["outline"][0]["chapter_title"] == "chapter-1"
    assert result["report_content"] == "generated-content"
