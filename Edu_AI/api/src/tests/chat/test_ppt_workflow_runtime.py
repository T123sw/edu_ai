from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.chat.domain.contracts import ChatRequestV2
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.ppt_outline import PptOutline, PptOutlineChapter, PptOutlineSlide
from app.chat.domain.workflow_state import WorkflowState
from app.chat.workflows.ppt.runtime import PptWorkflowRuntime


def _ready_generation_context():
    return SimpleNamespace(
        conversation_id="conv-ppt",
        resource_type="ppt",
        summary_text="TCP handshake lesson",
        current_topics=["TCP three-way handshake"],
        user_goals=["generate ppt"],
        confirmed_facts=["audience is students", "focus on the handshake flow", "common misconceptions"],
        constraints={
            "audience": "students",
            "objective": "classroom explanation",
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


class StubHtml2PptClient:
    def __init__(self):
        self.calls = []

    def create_job(self, *, content_markdown, theme_id, metadata):
        self.calls.append(("create_job", content_markdown, theme_id, metadata))
        return {"job_id": "job_001", "status": "queued"}

    def get_job_status(self, job_id):
        self.calls.append(("get_job_status", job_id))
        return {
            "job_id": job_id,
            "status": "succeeded",
            "phase": "completed",
            "progress": 100,
            "message": "done",
            "latest_revision_id": "rev_0000",
        }

    def get_job_results(self, job_id):
        self.calls.append(("get_job_results", job_id))
        return {
            "job_id": job_id,
            "latest_revision_id": "rev_0000",
            "slide_count": 16,
            "results": {
                "pptx_url": "/ppt/artifacts/job_001/rev_0000/deck.pptx",
                "html_full_url": "/ppt/artifacts/job_001/rev_0000/deck.html",
                "manifest_url": "/ppt/artifacts/job_001/rev_0000/manifest.json",
            },
        }


class StubContentMarkdownGenerator:
    def __init__(self, markdown: str):
        self.markdown = markdown
        self.calls = []

    def generate(self, *, outline, preparation):
        self.calls.append({"deck_title": outline.deck_title, "theme_id": outline.theme_id})
        return self.markdown, {
            "generation_mode": "direct_content_markdown",
            "protocol_loaded": True,
            "prompt_preview": "prompt preview",
            "response_preview": "response preview",
        }


class PassingContentGate:
    def __init__(self):
        self.calls = []

    def apply(self, *, content_markdown, outline):
        self.calls.append((content_markdown, outline))
        return {
            "ok": True,
            "errors": [],
            "warnings": [],
            "issues": [],
            "transformations": [],
            "final_markdown": content_markdown,
        }


class RejectingContentGate:
    def __init__(self):
        self.calls = []

    def apply(self, *, content_markdown, outline):
        self.calls.append((content_markdown, outline))
        return {
            "ok": False,
            "errors": ["toc too long"],
            "warnings": [],
            "issues": [
                {
                    "code": "toc.too_many_items",
                    "severity": "error",
                    "slide_index": 2,
                    "field_path": "slides[1].toc",
                    "message": "TOC should only contain chapter-level entries.",
                    "suggested_action": "trim_toc_to_chapters",
                }
            ],
            "transformations": [],
            "final_markdown": content_markdown,
        }


def _request(question: str = "confirm"):
    return ChatRequestV2(question=question, action_hint="generate.ppt", conversation_id="conv-ppt")


def _outline_artifact():
    outline = PptOutline(
        deck_title="AI Agent中的Skills与MCP",
        deck_subtitle="Intro course",
        theme_id="heu_academic_elegant",
        chapters=[
            PptOutlineChapter(
                chapter_index=1,
                chapter_title="Skills Basics",
                chapter_goal="Teach the basics",
                slides=[
                    PptOutlineSlide(
                        slide_index=2,
                        role="content",
                        title="What Is A Skill",
                        goal="Explain the concept clearly.",
                        key_points=["definition", "use"],
                    )
                ],
            )
        ],
        slides=[
            PptOutlineSlide(slide_index=1, role="cover", title="AI Agent中的Skills与MCP", goal="封面", key_points=["intro"]),
            PptOutlineSlide(slide_index=2, role="content", title="What Is A Skill", goal="Explain the concept clearly.", key_points=["definition", "use"]),
            PptOutlineSlide(slide_index=3, role="thanks", title="Q&A", goal="Close", key_points=["questions"]),
        ],
    )
    return {
        "artifact_id": "conv-ppt:outline",
        "artifact_type": "ppt_outline",
        "title": "outline",
        "content": outline.model_dump(exclude_none=True),
        "generation_state": {"status": "awaiting_confirm", "phase": "awaiting_outline_confirmation"},
    }


def _snapshot(*, artifacts, filled_slots):
    return ConversationSnapshot(
        conversation_id="conv-ppt",
        workflow_state=WorkflowState(
            workflow_id="conv-ppt",
            workflow_type="ppt",
            status="awaiting_confirm",
            stage="awaiting_outline_confirmation",
            required_slots=[],
            filled_slots=filled_slots,
            artifacts=artifacts,
        ),
    )


def test_ppt_runtime_asks_followup_when_core_information_is_missing():
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(
            SimpleNamespace(
                conversation_id="conv-ppt",
                resource_type="ppt",
                summary_text="make a ppt",
                current_topics=[],
                user_goals=["generate ppt"],
                confirmed_facts=[],
                constraints={},
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
                source_scope={"from_summary": True},
            )
        ),
        html2ppt_client=StubHtml2PptClient(),
        content_markdown_generator=StubContentMarkdownGenerator("# Deck\n## Slide 1\n- Role: cover\n- Title: Intro\n### Blocks\n- Lead: Open\n"),
    )

    result = runtime.run(request=_request("help me make a ppt"), snapshot=ConversationSnapshot(conversation_id="conv-ppt"), decision=None)

    assert result["workflow"]["type"] == "ppt"
    assert result["workflow"]["status"] == "awaiting_confirm"
    assert result["workflow"]["phase"] == "collecting_inputs"
    assert result["workflow"]["required_slots"]


def test_ppt_runtime_generates_outline_when_information_is_ready():
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_generation_context()),
        html2ppt_client=StubHtml2PptClient(),
        content_markdown_generator=StubContentMarkdownGenerator("# Deck\n## Slide 1\n- Role: cover\n- Title: Intro\n### Blocks\n- Lead: Open\n"),
    )

    result = runtime.run(request=_request("generate tcp handshake ppt"), snapshot=ConversationSnapshot(conversation_id="conv-ppt"), decision=None)

    assert result["workflow"]["type"] == "ppt"
    assert result["workflow"]["status"] == "awaiting_confirm"
    assert result["workflow"]["phase"] == "awaiting_outline_confirmation"
    assert result["artifacts"][0]["artifact_type"] == "ppt_outline"


def test_ppt_runtime_defaults_workflow_timeouts_to_thirty_minutes():
    runtime = PptWorkflowRuntime()

    assert runtime.max_poll_seconds == 1800.0
    assert runtime._phase_timeout_seconds("generating_slides") == 1800.0
    assert runtime._phase_timeout_seconds("exporting_pptx") == 1800.0
    assert runtime._phase_timeout_seconds("polling_ppt_job") == 1800.0


def test_ppt_runtime_confirms_outline_and_submits_html2ppt_job():
    client = StubHtml2PptClient()
    generator = StubContentMarkdownGenerator(
        "# Deck\n## Slide 1\n- Role: cover\n- Title: Intro\n### Blocks\n- Lead: Open\n\n## Slide 2\n- Role: content\n- Title: Flow\n### Blocks\n- Lead: Explain\n"
    )
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_generation_context()),
        html2ppt_client=client,
        content_markdown_generator=generator,
    )
    initial = runtime.run(request=_request("generate tcp handshake ppt"), snapshot=ConversationSnapshot(conversation_id="conv-ppt"), decision=None)

    resumed = runtime.run(request=_request("yes"), snapshot=_snapshot(artifacts=initial["artifacts"], filled_slots=initial["workflow"]["filled_slots"]), decision=None)

    assert resumed["workflow"]["status"] == "completed"
    assert generator.calls
    assert client.calls[0][0] == "create_job"
    assert client.calls[0][2] == "heu_academic_elegant"
    assert "## Slide 2" in client.calls[0][1]
    assert any(artifact["artifact_type"] == "ppt_content_markdown" for artifact in resumed["artifacts"])
    assert resumed["artifacts"][-1]["content"]["slide_count"] == 16
    assert resumed["trace"]["ppt_content_generation_debug"]["generation_mode"] == "direct_content_markdown"


def test_ppt_runtime_stops_before_html2ppt_when_content_gate_rejects_markdown():
    client = StubHtml2PptClient()
    generator = StubContentMarkdownGenerator(
        "# Deck\n## Slide 1\n- Role: cover\n- Title: Intro\n### Blocks\n- Lead: Open\n\n## Slide 2\n- Role: content\n- Title: Flow\n### Blocks\n- Lead: Explain\n"
    )
    gate = RejectingContentGate()
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_generation_context()),
        html2ppt_client=client,
        content_markdown_generator=generator,
        content_gate=gate,
    )
    initial = runtime.run(request=_request("generate tcp handshake ppt"), snapshot=ConversationSnapshot(conversation_id="conv-ppt"), decision=None)

    resumed = runtime.run(request=_request("yes"), snapshot=_snapshot(artifacts=initial["artifacts"], filled_slots=initial["workflow"]["filled_slots"]), decision=None)

    assert resumed["workflow"]["status"] == "failed"
    assert resumed["workflow"]["phase"] == "validating_content_markdown"
    assert client.calls == []
    assert generator.calls
    assert gate.calls
    assert any(artifact["artifact_type"] == "ppt_content_markdown" for artifact in resumed["artifacts"])
    assert resumed["trace"]["ppt_content_generation_debug"]["generation_mode"] == "direct_content_markdown"
    assert resumed["trace"]["ppt_validation"]["ok"] is False


def test_ppt_runtime_polls_existing_job_for_running_html2ppt_phase():
    client = StubHtml2PptClient()
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_generation_context()),
        html2ppt_client=client,
        content_markdown_generator=StubContentMarkdownGenerator("# Deck\n## Slide 1\n- Role: cover\n- Title: Intro\n### Blocks\n- Lead: Open\n"),
    )

    snapshot = ConversationSnapshot(
        conversation_id="conv-ppt",
        workflow_state=WorkflowState(
            workflow_id="conv-ppt",
            workflow_type="ppt",
            status="running",
            stage="preprocessing",
            required_slots=[],
            filled_slots={"deck_topic": "TCP three-way handshake", "__ppt_followup_rounds": "0"},
            artifacts=[
                {
                    "artifact_id": "conv-ppt:outline",
                    "artifact_type": "ppt_outline",
                    "title": "outline",
                    "content": {
                        "deck_title": "TCP three-way handshake",
                        "deck_subtitle": "Intro",
                        "theme_id": "heu_academic_elegant",
                        "chapters": [],
                        "slides": [],
                    },
                },
                {
                    "artifact_id": "conv-ppt:deck:job_001",
                    "artifact_type": "ppt_deck",
                    "title": "deck.pptx",
                    "content": {"job_id": "job_001", "theme_id": "heu_academic_elegant", "slide_count": 2},
                    "generation_state": {"status": "running", "phase": "preprocessing", "progress": 10, "message": "running"},
                },
            ],
        ),
    )

    resumed = runtime.run(request=_request("continue"), snapshot=snapshot, decision=None)

    assert resumed["workflow"]["type"] == "ppt"
    assert resumed["workflow"]["status"] == "completed"
    assert [call[0] for call in client.calls] == ["get_job_status", "get_job_results"]


def test_ppt_runtime_uses_post_outline_executor_for_confirmed_outline():
    class StubExecutor:
        def __init__(self):
            self.calls = []

        def execute(self, *, outline, request, metadata):
            self.calls.append(
                {
                    "outline": outline,
                    "request": request,
                    "metadata": metadata,
                }
            )
            return {
                "artifacts": [
                    {
                        "artifact_id": "conv-ppt:outline",
                        "artifact_type": "ppt_outline",
                        "title": "outline",
                        "content": outline.model_dump(exclude_none=True),
                    },
                    {
                        "artifact_id": "conv-ppt:content_markdown",
                        "artifact_type": "ppt_content_markdown",
                        "title": "content.md",
                        "content": "# Deck",
                    },
                ],
                "status": "completed",
                "phase": "completed",
                "message": "PPT done",
                "trace": {
                    "ppt_validation": {"ok": True},
                    "ppt_content_generation_debug": {"generation_mode": "executor"},
                },
            }

    executor = StubExecutor()
    runtime = PptWorkflowRuntime(
        generation_context_builder=StubGenerationContextBuilder(_ready_generation_context()),
        html2ppt_client=StubHtml2PptClient(),
        content_markdown_generator=StubContentMarkdownGenerator("# Deck\n"),
        post_outline_executor=executor,
    )
    initial = runtime.run(
        request=_request("generate tcp handshake ppt"),
        snapshot=ConversationSnapshot(conversation_id="conv-ppt"),
        decision=None,
    )

    resumed = runtime.run(
        request=_request("yes"),
        snapshot=_snapshot(artifacts=initial["artifacts"], filled_slots=initial["workflow"]["filled_slots"]),
        decision=None,
    )

    assert resumed["workflow"]["status"] == "completed"
    assert resumed["message"]["content"] == "PPT done"
    assert executor.calls
    assert executor.calls[0]["metadata"]["trace_path"] == "workflow"
