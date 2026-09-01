from types import SimpleNamespace

from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor


def _request(question: str):
    return SimpleNamespace(
        question=question,
        course_id="course-1",
        capability=SimpleNamespace(selected_doc_ids=[], allow_rag=False, allow_web=False),
    )


def test_extractor_separates_user_stated_facts_from_assistant_fact_candidates():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("这节课前10分钟学生多次走神，后排回应也比较少"),
        result={
            "message": {
                "content": "这说明前10分钟课堂启动较慢，开场吸引力不足，导致后排学生参与偏低。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["user_claims"][0]["source_type"] == "user_message"
    assert memory["assistant_hypotheses"][0]["source_type"] == "assistant_message"
    assert memory["user_stated_facts"] == ["这节课前10分钟学生多次走神", "后排回应也比较少"]
    assert memory["assistant_fact_candidates"]
    assert memory["assistant_fact_candidates"] != memory["confirmed_facts"]
    assert memory["confirmed_facts"] == ["这节课前10分钟学生多次走神", "后排回应也比较少"]


def test_report_control_turn_does_not_add_assistant_fact_candidates_to_confirmed_facts():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("请基于当前内容生成一份报告"),
        result={
            "message": {
                "content": "我将基于“关羽水淹七军战役”，重点围绕“战役全过程分析”，结合当前对话内容先生成一版报告。可以直接开始吗？"
            },
            "action": {"name": "generate.report"},
            "workflow": {"type": "report", "status": "awaiting_confirm", "phase": "soft_confirm"},
        },
        existing_state={
            "conversation_memory": {
                "confirmed_facts": ["水淹七军是关羽军事生涯的巅峰战役"],
            }
        },
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert memory["assistant_fact_candidates"] == []
    assert memory["confirmed_facts"] == ["水淹七军是关羽军事生涯的巅峰战役"]


def test_extractor_projects_external_sources_into_external_evidence_without_polluting_assistant_hypotheses():
    extractor = ConversationMemoryExtractor()

    patch = extractor.build_state_patch(
        request=_request("请结合文档继续分析课堂问题"),
        result={
            "message": {
                "content": "根据文档记录，课堂前10分钟举手响应较少，后排学生存在走神现象。"
            },
            "sources": [
                {"source": "doc-a", "content": "课堂前10分钟举手响应较少", "page": 1},
                {"source": "doc-b", "content": "后排学生存在走神现象", "page": 2},
            ],
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    memory = patch["conversation_memory"]

    assert [item["content"] for item in memory["external_evidence"]] == [
        "课堂前10分钟举手响应较少",
        "后排学生存在走神现象",
    ]
    assert all(item["source_type"] == "external_source" for item in memory["external_evidence"])
    assert "课堂前10分钟举手响应较少" in memory["confirmed_facts"]


def test_extractor_retracts_previous_user_claim_when_user_corrects_fact():
    extractor = ConversationMemoryExtractor()

    first_patch = extractor.build_state_patch(
        request=_request("前10分钟学生多次走神"),
        result={
            "message": {
                "content": "这说明课堂导入阶段吸引力不足。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state={},
        recent_messages=[],
    )

    second_patch = extractor.build_state_patch(
        request=_request("不是前10分钟，是后10分钟学生多次走神"),
        result={
            "message": {
                "content": "已按你更正后的观察继续分析。"
            },
            "action": {"name": "chat.reply"},
        },
        existing_state=first_patch,
        recent_messages=[],
    )

    memory = second_patch["conversation_memory"]

    assert memory["confirmed_facts"] == ["后10分钟学生多次走神"]
    assert any(
        item["content"] == "前10分钟学生多次走神" and item["status"] == "retracted"
        for item in memory["user_claims"]
    )
    assert any(
        item["content"] == "后10分钟学生多次走神" and item["status"] == "stated"
        for item in memory["user_claims"]
    )
