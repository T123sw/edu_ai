from types import SimpleNamespace
from pathlib import Path
import uuid

from core.course_storage import CourseStorageManager

from app.chat.application.reply_service_v2 import ReplyServiceV2
from app.chat.application.report_service_v2 import _persist_ppt_course_material
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.workflow_state import WorkflowState
from app.chat.workflows.ppt.runtime import PptWorkflowRuntime


class DummyStore:
    def write_v2_result(self, conversation_id, request, result):
        return None


class DummyStatusCardBuilder:
    def build(self, *, snapshot, workflow, capability):
        return {"mode": "workflow", "status_label": "ok", "source_labels": ["current"]}


class StubGenerationContextBuilder:
    def __init__(self, context):
        self.context = context

    def build_for_resource(self, *, request, snapshot, resource_type):
        return self.context


class StubContentMarkdownGenerator:
    def generate(self, *, outline, preparation):
        return (
            """# Deck
- Title: TCP
- Theme: heu_academic_elegant

---

## Slide 1
- Role: cover
- Title: TCP

### Blocks
- Lead: class explanation

---

## Slide 2
- Role: thanks
- Title: Q&A

### Blocks
- Lead: welcome questions
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


def _ready_context():
    return SimpleNamespace(
        conversation_id="conv-ppt",
        resource_type="ppt",
        summary_text="TCP overview",
        current_topics=["TCP"],
        user_goals=["generate ppt"],
        confirmed_facts=["audience: freshmen", "focus: handshake"],
        constraints={
            "audience": "freshmen",
            "objective": "class explanation",
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
        current_course_id="course-ppt",
        active_artifact_id=None,
        active_artifact_type=None,
        recent_relevant_messages=[],
        source_scope={"from_summary": True, "from_memory": True, "from_recent_messages": True},
    )


def test_completed_ppt_is_persisted_into_course_materials():
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_context()),
        content_markdown_generator=StubContentMarkdownGenerator(),
        html2ppt_client=StubHtml2PptClient(),
    )
    temp_root = Path("tests/.tmp") / f"ppt-course-materials-{uuid.uuid4().hex}"
    temp_root.mkdir(parents=True, exist_ok=True)
    storage_manager = CourseStorageManager(root_path=str(temp_root))

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
        course_storage_manager=storage_manager,
    )

    first = service.reply(
        SimpleNamespace(
            question="Generate TCP PPT",
            conversation_id="conv-ppt",
            model_id=None,
            course_id="course-ppt",
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

    service.reply(
        SimpleNamespace(
            question="yes",
            conversation_id="conv-ppt",
            model_id=None,
            course_id="course-ppt",
            artifact_id=None,
            allow_rag=False,
            allow_web=False,
            selected_doc_ids=[],
            action_hint=None,
            owner="u1",
        )
    )

    materials = storage_manager.list_generated_materials("course-ppt", "ppt")
    assert len(materials) == 1
    assert materials[0]["material_type"] == "ppt"
    assert materials[0]["title"].endswith(".pptx")
    assert materials[0]["content"]["pptx_url"].endswith("deck.pptx")


def test_direct_ppt_generation_persists_completed_ppt_course_material():
    saved = {}

    class DummyStorage:
        def save_generated_material(self, *, course_id, material_type, material_id, material_data):
            saved["course_id"] = course_id
            saved["material_type"] = material_type
            saved["material_id"] = material_id
            saved["material_data"] = material_data

    result = {
        "artifacts": [
            {
                "artifact_id": "ppt-run-1:deck",
                "artifact_type": "ppt_deck",
                "title": "Agent Basics.pptx",
                "content": {
                    "job_id": "job-1",
                    "html_full_url": "/ppt/artifacts/job-1/rev_0000/deck.html",
                    "pptx_url": "/ppt/artifacts/job-1/rev_0000/deck.pptx",
                },
                "generation_state": {"status": "completed"},
            }
        ]
    }

    _persist_ppt_course_material(
        payload=SimpleNamespace(course_id="course-1"),
        result=result,
        course_storage_manager=DummyStorage(),
    )

    assert saved["course_id"] == "course-1"
    assert saved["material_type"] == "ppt"
    assert saved["material_id"] == "ppt-run-1:deck"
