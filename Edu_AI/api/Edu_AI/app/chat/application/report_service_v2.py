from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.chat.application.request_normalizer import normalize_chat_request
from app.chat.agents.report_generation import get_fallback_llm
from app.chat.agents.universal_report_engine import build_universal_report_graph
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.orchestrator.generation_readiness_judge import GenerationReadinessJudge
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer
from app.chat.orchestrator.status_card_builder import StatusCardBuilder
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.chat.skill_manager import SkillManager
from app.chat.tools.agent_tools import get_tool_registry_for_capability
from app.chat.workflows.report.assembler import ReportAssembler
from app.chat.workflows.report.runtime import ReportWorkflowRuntime


class ReportServiceV2:
    def __init__(self, *, context_builder, report_runtime, conversation_store, status_card_builder=None):
        self.context_builder = context_builder
        self.report_runtime = report_runtime
        self.conversation_store = conversation_store
        self.status_card_builder = status_card_builder or StatusCardBuilder()

    def report(self, payload):
        request = normalize_chat_request(payload)
        if not getattr(request, "conversation_id", None):
            request.conversation_id = f"conv-{uuid4().hex[:12]}"
        snapshot = self.context_builder.build(request)
        decision = SimpleNamespace(path="workflow", action="generate.report", workflow_name="report")
        result = self.report_runtime.run(request=request, snapshot=snapshot, decision=decision)
        report_config = getattr(payload, "report_config", None)
        if report_config is not None:
            trace = dict(result.get("trace") or {})
            trace_input = dict(trace.get("input") or {})
            trace_input["report_config"] = report_config
            trace["input"] = trace_input
            result["trace"] = trace
        conversation_id = str(((result.get("conversation") or {}).get("conversation_id")) or request.conversation_id or "").strip()
        result.setdefault("conversation", {"conversation_id": conversation_id})
        if conversation_id:
            self.conversation_store.write_v2_result(conversation_id, request, result)
            refreshed_snapshot = self.context_builder.build(request)
            status_card = self.status_card_builder.build(
                snapshot=refreshed_snapshot,
                workflow=result.get("workflow"),
                capability=request.capability,
            )
            result["status_card"] = status_card if isinstance(status_card, dict) else status_card.model_dump(exclude_none=True)
        return result


def build_default_report_engine(*, allow_rag: bool = False, allow_web: bool = False):
    planner_llm = get_fallback_llm()
    analyzer_llm = planner_llm
    extractor_llm = planner_llm
    skill_manager = SkillManager()
    return build_universal_report_graph(
        planner_llm=planner_llm,
        analyzer_llm=analyzer_llm,
        extractor_llm=extractor_llm,
        extractor_prompt_template=skill_manager.extract_section("edu-report-agent", "EXTRACTOR_SYSTEM_PROMPT"),
        planner_skill_prompt="",
        analyzer_skill_prompt="",
        tool_registry=get_tool_registry_for_capability(allow_rag=allow_rag, allow_web=allow_web),
    )


def build_default_report_service_v2():
    conversation_store = ConversationStoreAdapter()
    context_builder = ContextBuilder(conversation_store=conversation_store)
    runtime = ReportWorkflowRuntime(
        engine_resolver=lambda *, request, snapshot, decision: build_default_report_engine(
            allow_rag=bool(getattr(request.capability, "allow_rag", False)),
            allow_web=bool(getattr(request.capability, "allow_web", False)),
        ),
        generation_context_builder=GenerationContextBuilder(),
        report_assembler=ReportAssembler(),
        report_context_organizer=ReportContextOrganizer(llm=get_fallback_llm()),
        generation_readiness_judge=GenerationReadinessJudge(),
    )
    return ReportServiceV2(
        context_builder=context_builder,
        report_runtime=runtime,
        conversation_store=conversation_store,
        status_card_builder=StatusCardBuilder(),
    )
