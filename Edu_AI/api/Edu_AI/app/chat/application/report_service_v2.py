from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
import re

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.agents.universal_report_engine import build_universal_report_graph
from app.chat.application.request_normalizer import normalize_chat_request
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.orchestrator.generation_readiness_judge import GenerationReadinessJudge
from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer
from app.chat.orchestrator.status_card_builder import StatusCardBuilder
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.chat.skill_manager import SkillManager
from app.chat.tools.agent_tools import get_tool_registry_for_capability
from app.chat.workflows.report.assembler import ReportAssembler
from app.chat.workflows.report.runtime import ReportWorkflowRuntime
from core.course_storage import storage_manager as default_course_storage_manager


def _clean_report_title(value) -> str:
    return str(value or "").strip().strip("。")


def _ensure_markdown_filename(base_title: str, *, suffix: str = "") -> str:
    normalized = _clean_report_title(base_title)
    if not normalized:
        normalized = "报告"
    if normalized.lower().endswith(".md"):
        normalized = normalized[:-3].rstrip()
    if suffix:
        normalized = f"{normalized}{suffix}"
    return f"{normalized}.md"


def _derive_report_base_title(*, payload, result: dict) -> str:
    report_config = getattr(payload, "report_config", None)
    explicit_title = _clean_report_title((report_config or {}).get("title") if isinstance(report_config, dict) else None)
    if explicit_title:
        return explicit_title

    preparation = dict((result.get("trace") or {}).get("report_preparation_result") or {})
    subject_title = _clean_report_title(preparation.get("report_subject"))
    if subject_title:
        return subject_title

    for artifact in list(result.get("artifacts") or []):
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("artifact_type") or "").strip() != "report":
            continue
        for line in str(artifact.get("content") or "").splitlines():
            stripped = line.strip()
            match = re.match(r"^#{1,6}\s+(.+)$", stripped)
            if not match:
                continue
            heading = _clean_report_title(match.group(1))
            if heading and heading not in {"正文", "报告", "分析报告"}:
                return heading
    return ""


def _sync_report_artifact_titles(*, payload, result: dict) -> None:
    artifacts = list(result.get("artifacts") or [])
    if not artifacts:
        return

    base_title = _derive_report_base_title(payload=payload, result=result)
    if not base_title:
        return

    next_artifacts = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            next_artifacts.append(artifact)
            continue
        artifact_type = str(artifact.get("artifact_type") or "").strip()
        next_artifact = dict(artifact)
        if artifact_type == "report":
            next_artifact["title"] = _ensure_markdown_filename(base_title)
        elif artifact_type == "report_outline":
            next_artifact["title"] = _ensure_markdown_filename(base_title, suffix="-大纲")
        next_artifacts.append(next_artifact)
    result["artifacts"] = next_artifacts


def _persist_report_course_material(*, payload, result: dict, course_storage_manager=None) -> None:
    course_id = str(getattr(payload, "course_id", "") or "").strip()
    if not course_id or course_storage_manager is None:
        return

    artifacts = list(result.get("artifacts") or [])
    report_artifact = next(
        (
            artifact
            for artifact in artifacts
            if isinstance(artifact, dict) and str(artifact.get("artifact_type") or "").strip() == "report"
        ),
        None,
    )
    if not report_artifact:
        return

    report_id = str(report_artifact.get("artifact_id") or "").strip()
    if not report_id:
        return

    outline_artifact = next(
        (
            artifact
            for artifact in artifacts
            if isinstance(artifact, dict) and str(artifact.get("artifact_type") or "").strip() == "report_outline"
        ),
        None,
    )
    now = datetime.now().isoformat()
    course_storage_manager.save_generated_material(
        course_id=course_id,
        material_type="report",
        material_id=report_id,
        material_data={
            "title": str(report_artifact.get("title") or "报告").strip(),
            "material_type": "report",
            "created_at": now,
            "updated_at": now,
            "report": report_artifact.get("content"),
            "outline": outline_artifact.get("content") if isinstance(outline_artifact, dict) else None,
            "version": dict(report_artifact.get("version") or {}),
            "generation_state": dict(report_artifact.get("generation_state") or {}),
        },
    )


def finalize_report_result(*, payload, result: dict, course_storage_manager=None, compact_message: bool = False) -> None:
    _sync_report_artifact_titles(payload=payload, result=result)
    _persist_report_course_material(
        payload=payload,
        result=result,
        course_storage_manager=course_storage_manager,
    )

    if not compact_message:
        return

    has_final_report = any(
        isinstance(artifact, dict) and str(artifact.get("artifact_type") or "").strip() == "report"
        for artifact in list(result.get("artifacts") or [])
    )
    if not has_final_report:
        return

    next_message = dict(result.get("message") or {})
    next_message["content"] = "已生成，请在右侧查看。"
    result["message"] = next_message


class ReportServiceV2:
    def __init__(self, *, context_builder, report_runtime, conversation_store, status_card_builder=None, course_storage_manager=None):
        self.context_builder = context_builder
        self.report_runtime = report_runtime
        self.conversation_store = conversation_store
        self.status_card_builder = status_card_builder or StatusCardBuilder()
        self.course_storage_manager = course_storage_manager

    @staticmethod
    def _is_knowledge_base_entry(payload) -> bool:
        return str(getattr(payload, "entry_mode", "") or "").strip() == "knowledge_base_report"

    @staticmethod
    def _normalize_request_question(*, payload, request) -> None:
        final_user_prompt = str(getattr(payload, "final_user_prompt", "") or "").strip()
        if final_user_prompt:
            request.question = final_user_prompt

    def _build_runtime_snapshot(self, *, payload, request, snapshot):
        if not self._is_knowledge_base_entry(payload):
            return snapshot
        return ConversationSnapshot(
            conversation_id=str(getattr(request, "conversation_id", "") or ""),
            recent_messages=[],
            summary="",
            conversation_memory={},
            active_context={},
            referenced_artifact_ids=[],
            active_task=None,
            active_artifact=None,
            workflow_state=None,
            capability=getattr(request, "capability", None),
        )

    @staticmethod
    def _write_trace_input(*, payload, result: dict) -> None:
        trace = dict(result.get("trace") or {})
        trace_input = dict(trace.get("input") or {})

        report_config = getattr(payload, "report_config", None)
        if report_config is not None:
            trace_input["report_config"] = report_config

        entry_mode = str(getattr(payload, "entry_mode", "") or "").strip()
        if entry_mode:
            trace_input["entry_mode"] = entry_mode

        prompt_draft = str(getattr(payload, "prompt_draft", "") or "").strip()
        if prompt_draft:
            trace_input["prompt_draft"] = prompt_draft

        final_user_prompt = str(getattr(payload, "final_user_prompt", "") or "").strip()
        if final_user_prompt:
            trace_input["final_user_prompt"] = final_user_prompt

        selected_card = getattr(payload, "selected_card", None)
        if selected_card is not None:
            trace_input["selected_card"] = dict(selected_card) if isinstance(selected_card, dict) else dict(selected_card.__dict__)

        trace["input"] = trace_input
        result["trace"] = trace

    def report(self, payload):
        request = normalize_chat_request(payload)
        self._normalize_request_question(payload=payload, request=request)
        if not getattr(request, "conversation_id", None):
            request.conversation_id = f"conv-{uuid4().hex[:12]}"

        snapshot = self.context_builder.build(request)
        runtime_snapshot = self._build_runtime_snapshot(payload=payload, request=request, snapshot=snapshot)
        decision = SimpleNamespace(path="workflow", action="generate.report", workflow_name="report")
        result = self.report_runtime.run(request=request, snapshot=runtime_snapshot, decision=decision)
        finalize_report_result(
            payload=payload,
            result=result,
            course_storage_manager=self.course_storage_manager,
            compact_message=True,
        )
        self._write_trace_input(payload=payload, result=result)

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
        course_storage_manager=default_course_storage_manager,
    )
