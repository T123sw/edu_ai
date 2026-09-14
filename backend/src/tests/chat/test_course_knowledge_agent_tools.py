from types import SimpleNamespace
from pathlib import Path

import pytest

from app.chat.harness.knowledge_tools import (
    KNOWLEDGE_TOOLS,
    KnowledgePlanArgs,
    KnowledgeQueryArgs,
    KnowledgeRetryArgs,
    KnowledgeToolsMixin,
)
from app.chat.harness.runtime import HarnessRuntime
from app.chat.harness.tools import ReportTools
from app.chat.api.schemas_v2 import ChatResponseV2


class Session:
    def __init__(self):
        self.data = {}
        self.saved = 0

    def save(self):
        self.saved += 1


class Tools(KnowledgeToolsMixin):
    def __init__(self):
        self.request = SimpleNamespace(
            course_id="course-1", owner="teacher-1", actor_role="teacher"
        )
        self.course_storage = object()
        self.session = Session()


class Application:
    def __init__(self):
        self.calls = []

    def create_draft(self, **kwargs):
        self.calls.append(("create_draft", kwargs))
        return {"build_id": "kb-1", "revision": 1}

    def plan(self, **kwargs):
        self.calls.append(("plan", kwargs))
        return {
            "build_id": "kb-1",
            "revision": 2,
            "status": "awaiting_review",
            "phase": "proposal_review",
            "progress": 0,
            "summary": "三档课程大纲已生成",
            "proposal": {"mode": "create", "summary": "三档课程大纲已生成"},
            "intent": {"schema_version": "2.0", "course_profile": {"audience": "大二学生"}},
            "quality_score": None,
            "quality_status": None,
            "quality_checks": [],
            "error": None,
            "published_version": None,
        }

    def status(self, **kwargs):
        self.calls.append(("status", kwargs))
        return {
            "build_id": kwargs["build_id"],
            "revision": 4,
            "status": "running",
            "phase": "ingesting",
            "progress": 42,
            "summary": "",
            "proposal": None,
            "quality_score": None,
            "error": None,
            "published_version": None,
        }

    def retry(self, **kwargs):
        self.calls.append(("retry", kwargs))
        return {
            "build_id": kwargs["build_id"],
            "revision": 4,
            "status": "queued",
            "phase": "retry_queued",
            "progress": 0,
            "summary": "",
            "proposal": None,
            "quality_score": None,
            "error": None,
            "published_version": None,
            "job": {"job_id": "job-1", "status": "queued"},
        }


@pytest.fixture
def authorized(monkeypatch):
    access = SimpleNamespace(
        require=lambda *args, **kwargs: SimpleNamespace(user_id="teacher-1")
    )
    monkeypatch.setattr(
        "app.api.course_dependencies.get_course_access_service", lambda: access
    )


def test_agent_tools_plan_query_and_retry_through_application_service(authorized):
    tools = Tools()
    application = Application()
    tools.knowledge_application = application

    planned = tools.plan_course_knowledge(
        KnowledgePlanArgs(requirements="适合 16 学时")
    )
    queried = tools.query_course_knowledge_build(KnowledgeQueryArgs())
    retried = tools.retry_course_knowledge_build(KnowledgeRetryArgs(build_id="kb-1"))

    assert [name for name, _ in application.calls] == [
        "create_draft", "plan", "status", "retry",
    ]
    assert planned["review_url"] == (
        "#knowledge?course_id=course-1&build_id=kb-1&action=build"
    )
    assert queried["status"] == "running"
    assert planned["intent"]["course_profile"]["audience"] == "大二学生"
    assert retried["job"]["job_id"] == "job-1"
    assert tools.session.data["knowledge_plan"]["status"] == "queued"
    assert tools.session.saved == 4


def test_failed_agent_plan_reuses_the_same_persisted_draft(authorized):
    tools = Tools()

    class FailingApplication(Application):
        def plan(self, **kwargs):
            self.calls.append(("plan", kwargs))
            raise RuntimeError("proposal provider failed")

        def status(self, **kwargs):
            self.calls.append(("status", kwargs))
            return {
                "build_id": kwargs["build_id"],
                "revision": 1,
                "status": "draft",
                "phase": "draft_config",
                "proposal": None,
            }

    application = FailingApplication()
    tools.knowledge_application = application

    with pytest.raises(RuntimeError, match="proposal provider failed"):
        tools.plan_course_knowledge(KnowledgePlanArgs(requirements="本科基础"))
    with pytest.raises(RuntimeError, match="proposal provider failed"):
        tools.plan_course_knowledge(KnowledgePlanArgs(requirements="本科基础且含实验"))

    assert [name for name, _ in application.calls].count("create_draft") == 1
    plan_calls = [kwargs for name, kwargs in application.calls if name == "plan"]
    assert [call["build_id"] for call in plan_calls] == ["kb-1", "kb-1"]
    assert [call["expected_revision"] for call in plan_calls] == [1, 1]
    assert tools.session.data["knowledge_plan_inflight"] == {
        "course_id": "course-1",
        "build_id": "kb-1",
    }


def test_runtime_projects_latest_knowledge_action_as_structured_workflow():
    req = SimpleNamespace(
        conversation_id="conv-1", request_id="req-1"
    )
    knowledge_plan = {
        "build_id": "kb-1",
        "revision": 2,
        "status": "awaiting_review",
        "phase": "proposal_review",
        "progress": 0,
        "summary": "三档课程大纲已生成",
        "proposal": {"mode": "create"},
        "quality_score": None,
        "error": None,
        "published_version": None,
        "review_url": "#knowledge?course_id=course-1&build_id=kb-1&action=build",
    }
    tools = SimpleNamespace(
        outcomes=[{
            "ok": True,
            "tool": "plan_course_knowledge",
            "data": knowledge_plan,
        }],
        session=Session(),
    )

    result = HarnessRuntime._result(req, "模型自由文本", tools)

    assert result["action"] == {"name": "knowledge.review"}
    assert result["workflow"] == {
        "type": "course_knowledge_base",
        "status": "awaiting_confirm",
        "stage": "proposal_review",
    }
    assert result["knowledge_plan"] == knowledge_plan
    assert "审核方案" in result["message"]["content"]


@pytest.mark.parametrize(
    ("tool_name", "expected_action", "expected_status"),
    [
        ("query_course_knowledge_build", "knowledge.status", "running"),
        ("retry_course_knowledge_build", "knowledge.retry", "running"),
    ],
)
def test_runtime_projects_status_and_retry_actions(
    tool_name, expected_action, expected_status
):
    req = SimpleNamespace(conversation_id="conv-1", request_id="req-1")
    data = {
        "build_id": "kb-1",
        "revision": 4,
        "status": "running",
        "phase": "ingesting",
        "progress": 42,
        "summary": "",
        "proposal": None,
        "quality_score": None,
        "error": None,
        "published_version": None,
        "review_url": "#knowledge?course_id=course-1&build_id=kb-1&action=build",
    }
    tools = SimpleNamespace(
        outcomes=[{"ok": True, "tool": tool_name, "data": data}],
        session=Session(),
    )

    result = HarnessRuntime._result(req, "", tools)

    assert result["action"] == {"name": expected_action}
    assert result["workflow"]["type"] == "course_knowledge_base"
    assert result["workflow"]["status"] == expected_status
    assert result["knowledge_plan"]["progress"] == 42


@pytest.mark.parametrize(
    ("status", "published_version", "workflow_status", "action_name"),
    [
        ("draft", None, "awaiting_confirm", "knowledge.review"),
        ("queued", None, "running", "knowledge.status"),
        ("failed", None, "failed", "knowledge.retry_available"),
        ("succeeded", 5, "completed", "knowledge.completed"),
        ("succeeded", None, "failed", "knowledge.status"),
    ],
)
def test_runtime_maps_build_facts_without_false_completion(
    status, published_version, workflow_status, action_name
):
    req = SimpleNamespace(conversation_id="conv-1", request_id="req-1")
    data = {
        "build_id": "kb-1",
        "revision": 4,
        "status": status,
        "phase": "published" if status == "succeeded" else status,
        "progress": 100 if status == "succeeded" else 0,
        "summary": "",
        "proposal": None,
        "quality_score": 90 if status == "succeeded" else None,
        "error": None,
        "published_version": published_version,
        "review_url": "#knowledge?course_id=course-1&build_id=kb-1&action=build",
    }
    tools = SimpleNamespace(
        outcomes=[{
            "ok": True,
            "tool": "query_course_knowledge_build",
            "data": data,
        }],
        session=Session(),
    )

    result = HarnessRuntime._result(req, "", tools)

    assert result["workflow"]["status"] == workflow_status
    assert result["action"] == {"name": action_name}


def test_chat_response_schema_preserves_knowledge_plan():
    payload = {
        "message": {"role": "assistant", "content": "方案已生成"},
        "conversation": {"conversation_id": "conv-1"},
        "action": {"name": "knowledge.plan"},
        "workflow": {
            "type": "course_knowledge_base",
            "status": "awaiting_review",
            "stage": "proposal_review",
        },
        "trace": {"path": "deepseek-harness"},
        "knowledge_plan": {"build_id": "kb-1", "revision": 2},
    }

    response = ChatResponseV2.model_validate(payload)

    assert response.knowledge_plan == {"build_id": "kb-1", "revision": 2}


def test_course_knowledge_tools_are_teacher_scoped_and_cannot_confirm_or_publish():
    capability = SimpleNamespace(allow_rag=False, allow_web=False)
    student_tools = SimpleNamespace(
        request=SimpleNamespace(
            actor_role="student", course_id="course-1", capability=capability
        ),
        rag=None,
        web=None,
    )
    teacher_tools = SimpleNamespace(
        request=SimpleNamespace(
            actor_role="teacher", course_id="course-1", capability=capability
        ),
        rag=None,
        web=None,
    )

    student_names = {item["name"] for item in ReportTools.schemas(student_tools)}
    teacher_names = {item["name"] for item in ReportTools.schemas(teacher_tools)}

    assert not student_names.intersection(KNOWLEDGE_TOOLS)
    assert set(KNOWLEDGE_TOOLS).issubset(teacher_names)
    assert not any(
        token in name
        for name in KNOWLEDGE_TOOLS
        for token in ("confirm", "publish", "start")
    )


def test_course_knowledge_skill_requires_real_status_and_explicit_retry():
    skill = (
        Path(__file__).parents[2]
        / "app/chat/harness/skills/edu-course-knowledge/SKILL.md"
    ).read_text(encoding="utf-8")

    assert "query_course_knowledge_build" in skill
    assert "明确要求重试" in skill
    assert "published_version" in skill
    assert "不能确认或发布" in skill
    assert "需求合同" in skill
    assert "needs_teacher_decision" in skill
