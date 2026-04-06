from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


def test_generation_context_builder_selects_older_relevant_messages_over_newer_unrelated_ones():
    snapshot = ConversationSnapshot(
        conversation_id="conv-rel",
        recent_messages=[
            {"role": "user", "content": "先看课堂参与度的问题"},
            {"role": "assistant", "content": "我先整理课堂参与度和后排学生走神的现象"},
            {"role": "user", "content": "另外也要关注互动推进不足"},
            {"role": "assistant", "content": "下面我们聊点别的"},
            {"role": "user", "content": "今天食堂怎么样"},
            {"role": "assistant", "content": "食堂菜单还可以"},
            {"role": "user", "content": "周末值班安排确认了吗"},
            {"role": "assistant", "content": "值班安排稍后通知"},
            {"role": "user", "content": "会议室空调修好了吗"},
        ],
        summary="当前围绕课堂参与度进行分析",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "confirmed_facts": ["后排学生多次走神"],
            "teaching_issues": ["互动推进不足"],
            "student_signals": ["后排学生走神"],
        },
    )
    request = ChatRequestV2(
        question="生成报告",
        conversation_id="conv-rel",
        owner="teacher-a",
        capability={"allow_rag": False, "allow_web": False, "allow_tools": True, "selected_doc_ids": []},
    )

    context = GenerationContextBuilder().build_for_resource(
        request=request,
        snapshot=snapshot,
        resource_type="report",
    )

    contents = [item["content"] for item in context.recent_relevant_messages]

    assert "先看课堂参与度的问题" in contents
    assert "我先整理课堂参与度和后排学生走神的现象" in contents
    assert "另外也要关注互动推进不足" in contents
    assert "今天食堂怎么样" not in contents
    assert contents == [
        "先看课堂参与度的问题",
        "我先整理课堂参与度和后排学生走神的现象",
        "另外也要关注互动推进不足",
    ]


def test_generation_context_builder_falls_back_to_recent_window_when_no_relevance_signal_matches():
    snapshot = ConversationSnapshot(
        conversation_id="conv-fallback",
        recent_messages=[
            {"role": "user", "content": "第1条"},
            {"role": "assistant", "content": "第2条"},
            {"role": "user", "content": "第3条"},
            {"role": "assistant", "content": "第4条"},
            {"role": "user", "content": "第5条"},
            {"role": "assistant", "content": "第6条"},
            {"role": "user", "content": "第7条"},
        ],
        summary="",
        conversation_memory={"current_topics": ["课堂参与度"]},
    )
    request = ChatRequestV2(
        question="生成报告",
        conversation_id="conv-fallback",
        owner="teacher-a",
        capability={"allow_rag": False, "allow_web": False, "allow_tools": True, "selected_doc_ids": []},
    )

    context = GenerationContextBuilder().build_for_resource(
        request=request,
        snapshot=snapshot,
        resource_type="report",
    )

    assert [item["content"] for item in context.recent_relevant_messages] == [
        "第2条",
        "第3条",
        "第4条",
        "第5条",
        "第6条",
        "第7条",
    ]


def test_report_runtime_uses_relevance_selected_messages_in_gathered_context():
    seen = {}

    class InspectingEngine:
        def invoke(self, state):
            seen.update(state)
            return {"reply": "ok", "status": "running"}

    snapshot = ConversationSnapshot(
        conversation_id="conv-runtime-rel",
        recent_messages=[
            {"role": "user", "content": "先看课堂参与度的问题"},
            {"role": "assistant", "content": "后排学生走神比较明显"},
            {"role": "user", "content": "今天食堂怎么样"},
            {"role": "assistant", "content": "食堂菜单还可以"},
        ],
        summary="当前围绕课堂参与度进行分析",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "student_signals": ["后排学生走神"],
        },
    )

    runtime = ReportWorkflowRuntime(engine=InspectingEngine())
    runtime.run(
        request=ChatRequestV2(
            question="生成报告",
            conversation_id="conv-runtime-rel",
            owner="teacher-a",
            capability={"allow_rag": False, "allow_web": False, "allow_tools": True, "selected_doc_ids": []},
        ),
        snapshot=snapshot,
        decision=None,
    )

    assert [item["content"] for item in seen["gathered_context"]["recent_messages"]] == [
        "先看课堂参与度的问题",
        "后排学生走神比较明显",
    ]


def test_generation_context_builder_skips_workflow_control_and_assistant_meta_messages():
    snapshot = ConversationSnapshot(
        conversation_id="conv-kind-filter",
        recent_messages=[
            {"role": "user", "content": "先看课堂参与度的问题", "message_kind": "user_content"},
            {"role": "assistant", "content": "这是一个非常好的问题，我们先看后排学生走神。", "message_kind": "assistant_meta"},
            {"role": "assistant", "content": "后排学生走神比较明显", "message_kind": "assistant_content"},
            {"role": "user", "content": "请基于当前内容生成一份报告", "message_kind": "workflow_control"},
            {"role": "assistant", "content": "我将基于当前内容先生成一版报告。可以直接开始吗？", "message_kind": "workflow_control"},
        ],
        summary="当前围绕课堂参与度进行分析",
        conversation_memory={
            "current_topics": ["课堂参与度"],
            "user_goals": ["生成报告"],
            "student_signals": ["后排学生走神"],
        },
    )
    request = ChatRequestV2(
        question="生成报告",
        conversation_id="conv-kind-filter",
        owner="teacher-a",
        capability={"allow_rag": False, "allow_web": False, "allow_tools": True, "selected_doc_ids": []},
    )

    context = GenerationContextBuilder().build_for_resource(
        request=request,
        snapshot=snapshot,
        resource_type="report",
    )

    assert [item["content"] for item in context.recent_relevant_messages] == [
        "先看课堂参与度的问题",
        "后排学生走神比较明显",
    ]


def test_generation_context_builder_uses_external_evidence_and_constraints_as_relevance_signals():
    snapshot = ConversationSnapshot(
        conversation_id="conv-signal",
        recent_messages=[
            {"role": "user", "content": "我更关注课堂前10分钟举手响应较少这个现象"},
            {"role": "assistant", "content": "这个现象更适合面向教研组写成分析报告"},
            {"role": "user", "content": "今天食堂怎么样"},
            {"role": "assistant", "content": "食堂菜单还可以"},
        ],
        summary="",
        conversation_memory={
            "current_topics": [],
            "user_goals": ["生成报告"],
            "constraints": {"audience": "教研组", "extra_constraints": ["正式"]},
            "external_evidence": [
                {
                    "content": "课堂前10分钟举手响应较少",
                    "source_type": "external_source",
                    "status": "supported",
                }
            ],
        },
    )
    request = ChatRequestV2(
        question="开始生成",
        conversation_id="conv-signal",
        owner="teacher-a",
        capability={"allow_rag": False, "allow_web": False, "allow_tools": True, "selected_doc_ids": []},
    )

    context = GenerationContextBuilder().build_for_resource(
        request=request,
        snapshot=snapshot,
        resource_type="report",
    )

    assert [item["content"] for item in context.recent_relevant_messages] == [
        "我更关注课堂前10分钟举手响应较少这个现象",
        "这个现象更适合面向教研组写成分析报告",
    ]
