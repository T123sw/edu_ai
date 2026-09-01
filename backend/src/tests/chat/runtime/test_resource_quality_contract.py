import pytest

from app.chat.runtime.verification.plan_verifier import verify_plan_execution
from app.chat.runtime.verification.resource_verifier import verify_resource_quality


@pytest.mark.parametrize(
    ("resource_type", "artifact"),
    [
        ("report", {"title": "二次函数", "content": "## 概念\n" + "核心知识。" * 50}),
        ("lesson_plan", {"learning_objectives": ["理解概念"], "activities": ["探究活动"], "assessment": ["退出条"]}),
        ("quiz", {"questions": [{"question": "1+1?", "answer": "2"}], "answers": ["2"]}),
        ("blog", {"title": "课堂观察", "body": "这是一篇完整的教学反思。"}),
        ("flashcard", {"cards": [{"front": "牛顿第一定律", "back": "惯性定律"}]}),
        ("graph", {"root": {"id": "a", "children": [{"id": "b"}]}, "max_depth": 3}),
        ("game", {"title": "分数分类", "game_data": {"items": ["1/2"]}, "html_url": "/games/1"}),
        ("classroom", {"stage": {"id": "stage-1"}, "scenes": ["导入", "探究", "评价"]}),
    ],
)
def test_eight_resource_contracts_accept_complete_artifacts(resource_type, artifact):
    assessment = verify_resource_quality(resource_type, artifact)
    assert assessment.valid is True
    assert assessment.score == 1.0


def test_quiz_contract_rejects_missing_answers():
    assessment = verify_resource_quality("quiz", {"questions": ["1+1?"]})
    assert assessment.valid is False
    assert "answers" in assessment.missing_requirements


def test_invalid_artifact_never_retries_successful_generation():
    report = verify_plan_execution(
        {
            "steps": [
                {"internal_action": "generate_resource", "expected_tools": ["generate_quiz"], "tool_allowlist": ["generate_quiz"]},
                {"internal_action": "verify", "expected_tools": ["verify_task"], "tool_allowlist": ["verify_task"]},
            ]
        },
        {"agent_steps": [{"tool": "generate_quiz", "ok": True, "args": {"subject": "分数"}, "task_id": "job-quiz-1"}]},
        artifact_readback={"readable": True, "artifacts": [{"resource_type": "quiz", "artifact": {"questions": ["1+1?"]}}]},
    )
    assert report.artifact_contract_valid is False
    assert report.repair_directive.action == "stop"
    assert report.repair_directive.requires_user_confirmation is True
    assert report.repair_directive.target_tool is None
    assert report.repair_directive.preserve_successful_task_ids == ["job-quiz-1"]


def test_failed_retrieval_repairs_only_failed_step():
    report = verify_plan_execution(
        {
            "steps": [
                {"internal_action": "retrieve_context", "expected_tools": ["rag_search"], "tool_allowlist": ["rag_search"]},
                {"internal_action": "generate_resource", "expected_tools": ["generate_report"], "tool_allowlist": ["generate_report"]},
            ]
        },
        {"agent_steps": [{"tool": "rag_search", "ok": False, "args": {"query": "光合作用"}}]},
    )
    assert report.repair_directive.action == "retry_step"
    assert report.repair_directive.target_step_index == 0
    assert report.repair_directive.target_tool == "rag_search"
    assert report.repair_directive.max_attempts == 1


def test_valid_readback_completes_artifact_audit():
    report = verify_plan_execution(
        {"steps": [{"internal_action": "generate_resource", "expected_tools": ["generate_report"], "tool_allowlist": ["generate_report"]}]},
        {"agent_steps": [{"tool": "generate_report", "ok": True, "args": {}, "task_id": "job-1"}]},
        artifact_readback={"readable": True, "artifacts": [{"resource_type": "report", "artifact": {"title": "报告", "content": "## 正文\n" + "内容。" * 60}}]},
    )
    assert report.decision == "pass"
    assert report.artifact_contract_valid is True
    assert report.repair_directive.action == "none"
