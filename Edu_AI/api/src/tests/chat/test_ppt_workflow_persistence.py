from pathlib import Path
from types import SimpleNamespace
import uuid

from app.chat.domain.contracts import ChatRequestV2
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.chat.workflows.ppt.runtime import PptWorkflowRuntime
from core.conversation_storage import ConversationStorage


def _ready_generation_context():
    return SimpleNamespace(
        conversation_id="conv-ppt-persist",
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


def test_ppt_workflow_persists_intermediate_artifacts_across_turns():
    temp_dir = Path("tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    storage = ConversationStorage(storage_file=temp_dir / f"conversations-{uuid.uuid4().hex}.json")
    adapter = ConversationStoreAdapter(storage=storage)
    context_builder = ContextBuilder(conversation_store=adapter)
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_generation_context()),
        content_markdown_generator=StubContentMarkdownGenerator(),
        html2ppt_client=StubHtml2PptClient(),
    )

    first_request = ChatRequestV2(
        question="生成 TCP 三次握手 PPT",
        action_hint="generate.ppt",
        conversation_id="conv-ppt-persist",
    )
    first_snapshot = context_builder.build(first_request)
    first_result = runtime.run(request=first_request, snapshot=first_snapshot, decision=None)
    adapter.write_v2_result("conv-ppt-persist", first_request, first_result)

    state_after_outline = storage.get_state("conv-ppt-persist")
    assert state_after_outline["workflow_state"]["stage"] == "awaiting_outline_confirmation"
    assert [artifact["artifact_type"] for artifact in state_after_outline["workflow_state"]["artifacts"]] == ["ppt_outline"]
    assert state_after_outline["active_artifact"]["artifact_type"] == "ppt_outline"

    second_request = ChatRequestV2(
        question="确认",
        conversation_id="conv-ppt-persist",
    )
    second_snapshot = context_builder.build(second_request)
    second_result = runtime.run(request=second_request, snapshot=second_snapshot, decision=None)
    adapter.write_v2_result("conv-ppt-persist", second_request, second_result)

    state_after_submit = storage.get_state("conv-ppt-persist")
    artifact_types = [artifact["artifact_type"] for artifact in state_after_submit["workflow_state"]["artifacts"]]
    assert artifact_types == ["ppt_outline", "ppt_content_markdown", "ppt_deck"]
    assert state_after_submit["active_artifact"]["artifact_type"] == "ppt_deck"
    assert state_after_submit["workflow_state"]["status"] == "completed"
