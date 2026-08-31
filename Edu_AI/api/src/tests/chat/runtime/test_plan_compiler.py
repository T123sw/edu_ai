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


def actions(plan):
    return [step["internal_action"] for step in plan.to_dict()["steps"]]


def tools(plan):
    return [step["expected_tools"] for step in plan.to_dict()["steps"]]


def test_selected_rag_is_before_answer():
    contract = extract_task_contract(
        request("解释快速排序"),
        capability(source_mode="selected_documents", selected_doc_ids=["doc-1"], allow_rag=True),
        {},
    )
    plan = compile_plan(contract, {})

    assert actions(plan) == ["retrieve_context", "answer_question", "verify", "report_result"]
    assert tools(plan)[0] == ["rag_search"]
    assert tools(plan)[1:] == [[], ["verify_task"], []]


def test_web_report_requires_retrieval_then_outline_and_confirmation():
    contract = extract_task_contract(
        request("查找网络，生成快速排序报告"), capability(allow_web=True), {}
    )
    plan = compile_plan(contract, {})

    assert actions(plan) == ["retrieve_context", "draft_outline", "confirm_outline"]
    assert tools(plan)[0] == ["web_search"]
    assert plan.template_id == "single_confirmable"
    research_plan = plan.steps[0].constraints["research_plan"]
    assert research_plan["topic"] == "快速排序"
    assert research_plan["max_supplemental_queries"] == 1


def test_confirmed_outline_only_exposes_single_generation_tool_after_retrieval():
    contract = extract_task_contract(
        request("确认，就按这个大纲生成"), capability(allow_web=True),
        {"active_draft_outline": {"resource_type": "report", "subject": "快速排序"}},
    )
    plan = compile_plan(contract, {"active_draft_outline": {"resource_type": "report", "subject": "快速排序"}})

    assert actions(plan) == ["retrieve_context", "generate_resource", "verify", "report_result"]
    assert tools(plan)[1] == ["generate_report"]


def test_bare_start_after_report_outline_compiles_real_report_generation():
    state = {
        "active_draft_outline": {
            "resource_type": "report",
            "subject": "链表实现报告大纲",
            "outline_markdown": "# 链表实现报告大纲",
        }
    }
    contract = extract_task_contract(request("开始"), capability(), state)
    plan = compile_plan(contract, state)

    assert contract.intent == "confirm"
    assert actions(plan) == ["generate_resource", "verify", "report_result"]
    assert tools(plan)[0] == ["generate_report"]


def test_default_bundle_is_deterministic_and_has_one_confirmation_boundary():
    contract = extract_task_contract(request("准备快速排序教学材料"), capability(), {})
    plan = compile_plan(contract, {})

    assert actions(plan) == ["draft_outline", "confirm_outline"]
    assert plan.template_id == "default_bundle"


def test_confirmed_bundle_generates_every_persisted_resource_once():
    active_outline = {
        "resource_type": "lesson_plan",
        "resource_types": ["lesson_plan", "quiz", "graph"],
        "subject": "快速排序",
        "outline_markdown": "# 快速排序教学材料包",
    }
    contract = extract_task_contract(
        request("确认生成"), capability(), {"active_draft_outline": active_outline}
    )
    plan = compile_plan(contract, {"active_draft_outline": active_outline})

    assert plan.resource_type == "bundle"
    assert tools(plan) == [
        ["generate_lesson_plan"],
        ["generate_quiz"],
        ["generate_graph"],
        ["verify_task"],
        [],
    ]


def test_empty_tool_allowlist_is_explicitly_closed():
    contract = extract_task_contract(request("解释快速排序"), capability(), {})
    plan = compile_plan(contract, {})

    for step in plan.steps:
        if step.internal_action in {"answer_question", "report_result"}:
            assert step.tool_allowlist == []
            assert step.expected_tools == []


def test_modification_creates_a_new_confirmable_outline_revision():
    contract = extract_task_contract(
        request("把这份报告改简单一点"), capability(),
        {"active_draft_outline": {"resource_type": "report", "subject": "快速排序"}},
    )
    plan = compile_plan(contract, {"active_draft_outline": {"resource_type": "report", "subject": "快速排序"}})

    assert contract.intent == "modify"
    assert actions(plan) == ["draft_outline", "confirm_outline"]
    assert tools(plan) == [["draft_outline"], []]
    assert plan.template_id == "modify_outline"


def test_high_impact_ambiguity_compiles_to_a_closed_clarification_step():
    contract = extract_task_contract(
        request("帮我生成一个教学资源"), capability(), {}
    )
    plan = compile_plan(contract, {})

    assert actions(plan) == ["clarify"]
    assert tools(plan) == [[]]
    assert plan.template_id == "clarification"
    assert plan.contract["clarification"]["budget"] == 1


def test_generation_status_uses_generation_domain_tool():
    contract = extract_task_contract(
        request("生成任务进度怎样？"), capability(), {"pending_tasks": [{"task_id": "job_report"}]}
    )
    plan = compile_plan(contract, {})

    assert contract.task_domain == "generation_job"
    assert actions(plan) == ["generation_status", "report_result"]
    assert tools(plan) == [["query_generation_job_status"], []]


def test_learning_task_cancel_is_a_clarification_not_a_generation_cancel():
    contract = extract_task_contract(request("取消学习任务 lt_homework"), capability(), {})
    plan = compile_plan(contract, {})

    assert contract.task_domain == "course_learning"
    assert actions(plan) == ["clarify"]
    assert tools(plan) == [[]]
