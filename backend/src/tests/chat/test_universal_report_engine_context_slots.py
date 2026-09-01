from app.chat.agents.universal_report_engine import evaluator_node, extractor_node


def test_extractor_node_prefills_report_slots_from_gathered_context_hints():
    patch = extractor_node(
        {
            "user_input": "请基于当前内容生成一份报告",
            "human_feedback": "",
            "phase": "extracting",
            "report_slots": {},
            "gathered_context": {
                "summary": "当前围绕课堂参与度和开场控制进行分析",
                "slot_hints": {
                    "core_topic": "课堂参与度",
                    "focus_area": "开场吸引力不足",
                    "length_requirement": "800字左右",
                    "dynamic_constraints": '{"audience": "教研组"}',
                },
                "context_digest": "主题：课堂参与度；问题：开场吸引力不足",
            },
        },
        extractor_llm=None,
    )

    assert patch["report_slots"]["core_topic"] == "课堂参与度"
    assert patch["report_slots"]["focus_area"] == "开场吸引力不足"
    assert patch["report_slots"]["length_requirement"] == "800字左右"
    assert patch["report_slots"]["dynamic_constraints"] == '{"audience": "教研组"}'


def test_evaluator_does_not_ask_for_core_topic_when_context_prefill_exists():
    decision = evaluator_node(
        {
            "phase": "evaluating",
            "report_slots": {
                "core_topic": "课堂参与度",
                "focus_area": "开场吸引力不足",
            },
            "user_input": "请基于当前内容生成一份报告",
            "human_feedback": "",
            "focus_sufficient": False,
            "soft_confirmed": False,
            "outline_confirmed": False,
        }
    )

    assert decision["phase"] != "asking"
