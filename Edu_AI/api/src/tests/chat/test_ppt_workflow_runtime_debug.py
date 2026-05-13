from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.ppt_outline import PptOutline, PptOutlineSlide
from app.chat.domain.workflow_state import WorkflowState
from app.chat.workflows.ppt.runtime import PptWorkflowRuntime


class StubContentMarkdownGenerator:
    def generate(self, *, outline, preparation):
        return (
            """# Deck
- Title: Skills And MCP

---

## Slide 1
- Role: cover
- Title: Skills And MCP

### Blocks
- Lead: Open the lesson clearly.

---

## Slide 2
- Role: thanks
- Title: Q&A

### Blocks
- Lead: Questions welcome.
""",
            {
                "generation_mode": "direct_content_markdown",
                "protocol_path": "D:/Edu_AI_1/Edu_AI/api/src/modules/html2ppt/content-protocol.md",
                "protocol_loaded": True,
                "prompt_preview": "prompt preview",
                "response_preview": "response preview",
            },
        )


class PassingContentGate:
    def apply(self, *, content_markdown, outline):
        return {
            "ok": True,
            "errors": [],
            "warnings": [],
            "issues": [],
            "transformations": [],
            "final_markdown": content_markdown,
        }


class StubHtml2PptClient:
    def create_job(self, *, content_markdown, theme_id, metadata):
        return {"job_id": "job_debug", "status": "queued"}

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
                "pptx_url": "/ppt/artifacts/job_debug/rev_0000/deck.pptx",
                "html_full_url": "/ppt/artifacts/job_debug/rev_0000/deck.html",
                "manifest_url": "/ppt/artifacts/job_debug/rev_0000/manifest.json",
            },
        }


def test_ppt_runtime_trace_contains_content_generation_debug():
    outline = PptOutline(
        deck_title="Skills And MCP",
        deck_subtitle="Intro course",
        theme_id="heu_academic_elegant",
        slides=[
            PptOutlineSlide(slide_index=1, role="cover", title="Skills And MCP", goal="Open", key_points=["intro"]),
            PptOutlineSlide(slide_index=2, role="thanks", title="Q&A", goal="Close", key_points=["questions"]),
        ],
    )
    runtime = PptWorkflowRuntime(
        content_markdown_generator=StubContentMarkdownGenerator(),
        content_gate=PassingContentGate(),
        html2ppt_client=StubHtml2PptClient(),
    )

    snapshot = ConversationSnapshot(
        conversation_id="conv-debug",
        workflow_state=WorkflowState(
            workflow_id="conv-debug",
            workflow_type="ppt",
            status="awaiting_confirm",
            stage="awaiting_outline_confirmation",
            artifacts=[
                {
                    "artifact_id": "conv-debug:outline",
                    "artifact_type": "ppt_outline",
                    "title": "outline",
                    "content": outline.model_dump(exclude_none=True),
                    "generation_state": {"status": "awaiting_confirm", "phase": "awaiting_outline_confirmation"},
                }
            ],
            filled_slots={
                "deck_topic": "Skills And MCP",
                "audience": "students",
                "objective": "classroom explanation",
                "slide_count": "15",
                "__ppt_followup_rounds": "0",
            },
        ),
    )

    result = runtime.run(
        request=ChatRequestV2(question="确认", action_hint="generate.ppt", conversation_id="conv-debug"),
        snapshot=snapshot,
        decision=None,
    )

    trace = result["trace"]
    assert trace["ppt_content_generation_debug"]["generation_mode"] == "direct_content_markdown"
    assert trace["ppt_content_generation_debug"]["protocol_loaded"] is True
    assert trace["ppt_content_generation_debug"]["protocol_path"].endswith("content-protocol.md")
    assert "## Slide 2" in trace["ppt_content_markdown"]
    assert result["workflow"]["status"] == "completed"
