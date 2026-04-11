from types import SimpleNamespace

import httpx
from core.course_storage import CourseStorageManager

from app.chat.application.reply_service_v2 import ReplyServiceV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.workflow_state import WorkflowState
from app.chat.workflows.ppt.runtime import PptWorkflowRuntime


class DummyStore:
    def __init__(self):
        self.saved = []

    def write_v2_result(self, conversation_id, request, result):
        self.saved.append((conversation_id, request.question, result))


class DummyStatusCardBuilder:
    def build(self, *, snapshot, workflow, capability):
        return {"mode": "workflow", "status_label": "ok", "source_labels": ["当前会话"]}


class StubGenerationContextBuilder:
    def __init__(self, context):
        self.context = context

    def build_for_resource(self, *, request, snapshot, resource_type):
        return self.context


class StubContentMarkdownGenerator:
    def generate(self, *, outline, preparation):
        return (
            """# Deck
- Title: TCP 三次握手
- Theme: heu_academic_elegant

---

## Slide 1
- Role: cover
- Title: TCP 三次握手

### Blocks
- Lead: 课堂讲解

---

## Slide 2
- Role: thanks
- Title: Q&A

### Blocks
- Lead: 欢迎提问
""",
            {
                "generation_mode": "direct_content_markdown",
                "protocol_path": "html2ppt/content-protocol.md",
                "protocol_loaded": True,
                "prompt_preview": "prompt",
                "response_preview": "response",
            },
        )


class StubHtml2PptClient:
    def create_job(self, *, content_markdown, theme_id, metadata):
        return {"job_id": "job_001", "status": "queued"}

    def get_job_status(self, job_id):
        return {
            "job_id": job_id,
            "status": "succeeded",
            "phase": "completed",
            "progress": 100,
            "message": "done",
            "latest_revision_id": "rev_0000",
        }

    def get_job_results(self, job_id):
        return {
            "job_id": job_id,
            "latest_revision_id": "rev_0000",
            "results": {
                "pptx_url": "/ppt/artifacts/job_001/rev_0000/deck.pptx",
                "html_full_url": "/ppt/artifacts/job_001/rev_0000/deck.html",
                "manifest_url": "/ppt/artifacts/job_001/rev_0000/manifest.json",
            },
        }


class FailingHtml2PptClient:
    def create_job(self, *, content_markdown, theme_id, metadata):
        raise httpx.ConnectError(
            "[WinError 10061] 由于目标计算机积极拒绝，无法连接。",
            request=httpx.Request("POST", "http://127.0.0.1:46080/ppt/jobs"),
        )


def _ready_context():
    return SimpleNamespace(
        conversation_id="conv-ppt",
        resource_type="ppt",
        summary_text="围绕 TCP 三次握手做课堂讲解。",
        current_topics=["TCP 三次握手"],
        user_goals=["生成PPT"],
        confirmed_facts=["受众是大一学生", "重点讲三次握手流程", "加入常见误区"],
        constraints={
            "audience": "大一学生",
            "objective": "课堂讲解",
            "theme": "heu_academic_elegant",
            "page_count": 6,
        },
        teaching_issues=[],
        student_signals=[],
        evidence_points=[],
        user_claims=[],
        assistant_hypotheses=[],
        external_evidence=[],
        selected_doc_ids=[],
        referenced_artifact_ids=[],
        current_course_id=None,
        active_artifact_id=None,
        active_artifact_type=None,
        recent_relevant_messages=[],
        source_scope={"from_summary": True, "from_memory": True, "from_recent_messages": True},
    )


def test_reply_service_preserves_ppt_intermediate_artifacts_across_confirmation():
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_context()),
        content_markdown_generator=StubContentMarkdownGenerator(),
        html2ppt_client=StubHtml2PptClient(),
    )

    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(
            dispatch=lambda request: runtime.run(
                request=request,
                snapshot=ConversationSnapshot(conversation_id=request.conversation_id or "conv-ppt"),
                decision=None,
            )
        ),
        conversation_store=DummyStore(),
        context_builder=SimpleNamespace(build=lambda request: ConversationSnapshot(conversation_id=request.conversation_id or "conv-ppt")),
        status_card_builder=DummyStatusCardBuilder(),
    )

    first = service.reply(
        SimpleNamespace(
            question="生成 TCP 三次握手 PPT",
            conversation_id="conv-ppt",
            model_id=None,
            course_id=None,
            artifact_id=None,
            allow_rag=False,
            allow_web=False,
            selected_doc_ids=[],
            action_hint="generate.ppt",
            owner="u1",
        )
    )

    workflow_state = WorkflowState(
        workflow_id="conv-ppt",
        workflow_type="ppt",
        status=first["workflow"]["status"],
        stage=first["workflow"]["phase"],
        required_slots=[],
        filled_slots=first["workflow"]["filled_slots"],
        artifacts=first["artifacts"],
    )
    service.context_builder = SimpleNamespace(
        build=lambda request: ConversationSnapshot(conversation_id="conv-ppt", workflow_state=workflow_state)
    )
    service.orchestrator = SimpleNamespace(
        dispatch=lambda request: runtime.run(
            request=request,
            snapshot=ConversationSnapshot(conversation_id="conv-ppt", workflow_state=workflow_state),
            decision=None,
        )
    )

    second = service.reply(
        SimpleNamespace(
            question="确认",
            conversation_id="conv-ppt",
            model_id=None,
            course_id=None,
            artifact_id=None,
            allow_rag=False,
            allow_web=False,
            selected_doc_ids=[],
            action_hint=None,
            owner="u1",
        )
    )

    artifact_types = [artifact["artifact_type"] for artifact in second["artifacts"]]
    assert artifact_types == ["ppt_outline", "ppt_content_markdown", "ppt_deck"]
    assert second["artifacts"][0]["title"].endswith("-大纲")
    assert second["artifacts"][1]["title"].endswith("-content.md")
    assert second["artifacts"][2]["title"].endswith(".pptx")
    assert second["status_card"]["status_label"] == "ok"


def test_reply_service_returns_failed_ppt_workflow_when_html2ppt_is_down():
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_context()),
        content_markdown_generator=StubContentMarkdownGenerator(),
        html2ppt_client=FailingHtml2PptClient(),
    )

    service = ReplyServiceV2(
        orchestrator=SimpleNamespace(
            dispatch=lambda request: runtime.run(
                request=request,
                snapshot=ConversationSnapshot(conversation_id=request.conversation_id or "conv-ppt"),
                decision=None,
            )
        ),
        conversation_store=DummyStore(),
        context_builder=SimpleNamespace(build=lambda request: ConversationSnapshot(conversation_id=request.conversation_id or "conv-ppt")),
        status_card_builder=DummyStatusCardBuilder(),
    )

    first = service.reply(
        SimpleNamespace(
            question="生成 TCP 三次握手 PPT",
            conversation_id="conv-ppt",
            model_id=None,
            course_id=None,
            artifact_id=None,
            allow_rag=False,
            allow_web=False,
            selected_doc_ids=[],
            action_hint="generate.ppt",
            owner="u1",
        )
    )
    workflow_state = WorkflowState(
        workflow_id="conv-ppt",
        workflow_type="ppt",
        status=first["workflow"]["status"],
        stage=first["workflow"]["phase"],
        required_slots=[],
        filled_slots=first["workflow"]["filled_slots"],
        artifacts=first["artifacts"],
    )
    service.context_builder = SimpleNamespace(
        build=lambda request: ConversationSnapshot(conversation_id="conv-ppt", workflow_state=workflow_state)
    )
    service.orchestrator = SimpleNamespace(
        dispatch=lambda request: runtime.run(
            request=request,
            snapshot=ConversationSnapshot(conversation_id="conv-ppt", workflow_state=workflow_state),
            decision=None,
        )
    )

    second = service.reply(
        SimpleNamespace(
            question="确认",
            conversation_id="conv-ppt",
            model_id=None,
            course_id=None,
            artifact_id=None,
            allow_rag=False,
            allow_web=False,
            selected_doc_ids=[],
            action_hint=None,
            owner="u1",
        )
    )

    assert second["workflow"]["status"] == "failed"
    assert second["workflow"]["phase"] == "submitting_ppt_job"
    assert "PPT 引擎" in second["message"]["content"]
