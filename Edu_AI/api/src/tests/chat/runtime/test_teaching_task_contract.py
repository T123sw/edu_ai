from types import SimpleNamespace

from app.chat.runtime.planning.compiler import compile_plan
from app.chat.runtime.planning.task_contract_extractor import extract_task_contract


def capability(**overrides):
    values = {
        "source_mode": "none",
        "selected_doc_ids": [],
        "allow_rag": False,
        "allow_web": False,
        "allow_image_search": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def request(question: str):
    return SimpleNamespace(question=question, course_id="course-1", conversation_id="conv-1")


def test_selected_documents_are_authoritative_over_model_like_text():
    contract = extract_task_contract(
        request("不要检索，按资料生成快速排序教案"),
        capability(source_mode="selected_documents", selected_doc_ids=["doc-1"], allow_rag=True),
        {},
    )

    assert contract.intent == "generate_single"
    assert contract.resource_types == ["lesson_plan"]
    assert contract.source_mode == "selected_documents"
    assert contract.selected_document_ids == ["doc-1"]
    assert contract.requires_rag is True


def test_explicit_resource_types_win_and_keep_user_scope():
    contract = extract_task_contract(
        request("生成教案和五道练习题"), capability(), {}
    )

    assert contract.intent == "generate_single"
    assert contract.resource_types == ["lesson_plan", "quiz"]
    assert contract.constraints["question_count"] == 5


def test_material_request_uses_bundle_intent_and_default_resources():
    contract = extract_task_contract(request("帮我准备快速排序教学材料"), capability(), {})

    assert contract.intent == "prepare_bundle"
    assert contract.resource_types == ["lesson_plan", "quiz", "graph"]
    assert contract.confirmation_policy == "required"


def test_bundle_confirmation_restores_all_resources_from_active_outline():
    active_outline = {
        "subject": "快速排序",
        "resource_type": "lesson_plan",
        "resource_types": ["lesson_plan", "quiz", "graph"],
        "origin_intent": "prepare_bundle",
    }

    contract = extract_task_contract(
        request("确认生成"), capability(), {"active_draft_outline": active_outline}
    )

    assert contract.intent == "confirm"
    assert contract.resource_types == ["lesson_plan", "quiz", "graph"]


def test_control_intents_are_not_generation_requests():
    assert extract_task_contract(request("做到哪了"), capability(), {}).intent == "status"
    assert extract_task_contract(request("取消刚才的 AI 课堂"), capability(), {}).intent == "cancel"
    assert extract_task_contract(request("请停止生成"), capability(), {}).intent == "cancel"
    assert extract_task_contract(request("把练习题改简单一点"), capability(), {}).intent == "modify"


def test_algorithm_stop_conditions_are_knowledge_questions_not_cancel_commands():
    questions = (
        "递归为什么必须有停止条件？",
        "有限状态机的终止状态是什么？",
        "请根据资料说明循环停止条件",
    )

    for question in questions:
        assert extract_task_contract(request(question), capability(), {}).intent == "qa"


def test_modify_keeps_the_active_outline_subject_across_long_dialogue():
    contract = extract_task_contract(
        request("把刚才的大纲改得更适合基础薄弱学生"), capability(),
        {"active_draft_outline": {"subject": "快速排序", "resource_type": "report"}},
    )

    assert contract.intent == "modify"
    assert contract.topic == "快速排序"


def test_visual_and_web_requests_become_required_policies():
    contract = extract_task_contract(
        request("查找网络并生成带流程图的快速排序报告"),
        capability(allow_web=True, allow_image_search=True),
        {},
    )

    assert contract.web_policy == "required"
    assert contract.image_policy == "required"
    assert contract.requires_web is True
    assert contract.requires_images is True


def test_confirmation_inherits_visual_requirement_from_active_outline():
    active_outline = {
        "subject": "归并排序教学",
        "resource_type": "report",
        "resource_types": ["report"],
        "needs_visuals": True,
    }

    contract = extract_task_contract(
        request("确认生成"), capability(allow_image_search=True),
        {"active_draft_outline": active_outline},
    )
    plan = compile_plan(contract, {"active_draft_outline": active_outline})

    assert contract.requires_images is True
    assert plan.steps[0].expected_tools == ["image_search"]


def test_topic_excludes_visual_format_directive():
    contract = extract_task_contract(
        request("帮我生成一份带流程图的归并排序教学报告"), capability(), {}
    )

    assert contract.topic == "归并排序教学"


def test_knowledge_question_containing_modify_word_is_not_a_modify_command():
    contract = extract_task_contract(
        request("链表插入节点时需要修改哪些指针"), capability(), {}
    )

    assert contract.intent == "qa"
    assert contract.clarification.required is False


def test_resource_names_without_generation_request_remain_normal_questions():
    questions = (
        "教案通常包含哪些部分？",
        "PPT 和教案有什么区别？",
        "思维导图适合在什么时候使用？",
    )

    for question in questions:
        contract = extract_task_contract(request(question), capability(), {})
        assert contract.intent == "qa"
        assert contract.clarification.required is False


def test_contract_v2_records_field_origin_confidence_and_explicit_constraints():
    contract = extract_task_contract(
        request("为基础薄弱的高一学生生成一份40分钟快速排序教案"),
        capability(source_mode="course_auto", allow_rag=True),
        {},
    )

    assert contract.schema_version == "2026-08-10.v3"
    assert contract.audience == "基础薄弱的高一学生"
    assert contract.lesson_duration == 40
    assert contract.field_evidence["source_mode"].origin == "ui"
    assert contract.field_evidence["source_mode"].confidence == 1.0
    assert contract.field_evidence["audience"].origin == "user"
    assert contract.field_evidence["lesson_duration"].origin == "user"


def test_topic_excludes_audience_duration_and_generation_scaffolding():
    contract = extract_task_contract(
        request("请为高一学生生成一份40分钟链表教学报告"), capability(), {}
    )

    assert contract.topic == "链表教学"
    assert contract.audience == "高一学生"
    assert contract.lesson_duration == 40


def test_topic_preserves_merge_sort_conjunction_character():
    contract = extract_task_contract(
        request("生成一份讲解归并排序的互动 AI 课堂"), capability(), {}
    )

    assert contract.topic == "归并排序"
    assert contract.resource_types == ["classroom"]


def test_ambiguous_generation_request_asks_one_bounded_clarifying_question():
    contract = extract_task_contract(request("帮我生成一个教学资源"), capability(), {})

    assert contract.intent == "generate_single"
    assert contract.clarification.required is True
    assert contract.clarification.field == "resource_types"
    assert contract.clarification.budget == 1
    assert len(contract.ambiguities) == 1


def test_status_with_multiple_tasks_requires_task_disambiguation():
    contract = extract_task_contract(
        request("做到哪了"),
        capability(),
        {"pending_tasks": [
            {"task_id": "job_1", "workflow_type": "report"},
            {"task_id": "job_2", "workflow_type": "quiz"},
        ]},
    )

    assert contract.intent == "status"
    assert contract.clarification.required is True
    assert contract.clarification.field == "task_reference"
    assert contract.task_domain == "generation_job"
    assert contract.conversation_refs["generation_job_ids"] == ["job_1", "job_2"]
    assert contract.conversation_refs["learning_task_ids"] == []
