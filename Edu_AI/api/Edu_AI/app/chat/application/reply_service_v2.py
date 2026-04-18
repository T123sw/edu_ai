from __future__ import annotations

import os
from uuid import uuid4

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.request_normalizer import normalize_chat_request
from app.chat.application.artifact_reference_intent import classify_artifact_reference_intent
from app.chat.application.artifact_context_loader import load_artifact_context
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.orchestrator.generation_readiness_judge import GenerationReadinessJudge
from app.chat.orchestrator.lesson_plan_context_organizer import LessonPlanContextOrganizer
from app.chat.orchestrator.lesson_plan_readiness_judge import LessonPlanReadinessJudge
from app.chat.orchestrator.main_orchestrator import MainOrchestrator
from app.chat.orchestrator.ppt_context_organizer import PptContextOrganizer
from app.chat.orchestrator.quiz_context_organizer import QuizContextOrganizer
from app.chat.orchestrator.quiz_readiness_judge import QuizReadinessJudge
from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer
from app.chat.orchestrator.status_card_builder import StatusCardBuilder
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
from app.chat.runtime.model_registry import build_default_gateway
from app.chat.tools.agent_tools import rag_search_tool, web_search_tool
from app.chat.tools.video_search import video_search_tool
from app.chat.workflows.ppt.content_validator import PptContentValidator
from app.chat.workflows.ppt.edit_runtime import PptEditRuntime
from app.chat.workflows.ppt.content_markdown_generator import PptContentMarkdownGenerator
from app.chat.workflows.ppt.html2ppt_client import Html2PptClient
from app.chat.workflows.ppt.outline_builder import PptOutlineBuilder
from app.chat.workflows.ppt.readiness_judge import PptReadinessJudge
from app.chat.workflows.ppt.runtime import PptWorkflowRuntime
from app.chat.workflows.quiz.assembler import QuizAssembler
from app.chat.workflows.quiz.generator import QuizGenerator
from app.chat.workflows.quiz.runtime import QuizWorkflowRuntime
from app.chat.workflows.lesson_plan.runtime import LessonPlanWorkflowRuntime
from app.chat.workflows.report.edit_runtime import ReportEditRuntime
from app.chat.workflows.report.assembler import ReportAssembler
from app.chat.workflows.report.runtime import ReportWorkflowRuntime
from core.course_storage import storage_manager as default_course_storage_manager

from .lesson_plan_service_v2 import build_default_lesson_plan_engine
from .report_service_v2 import build_default_report_engine, finalize_report_result


def _persist_quiz_course_material(*, payload, result: dict, course_storage_manager=None) -> None:
    course_id = str(getattr(payload, "course_id", "") or "").strip()
    if not course_id or course_storage_manager is None:
        return

    artifacts = list(result.get("artifacts") or [])
    quiz_artifact = next(
        (
            artifact
            for artifact in artifacts
            if isinstance(artifact, dict) and str(artifact.get("artifact_type") or "").strip() == "quiz"
        ),
        None,
    )
    if not quiz_artifact:
        return

    material_id = str(quiz_artifact.get("artifact_id") or "").strip()
    if not material_id:
        return

    course_storage_manager.save_generated_material(
        course_id=course_id,
        material_type="quiz",
        material_id=material_id,
        material_data={
            "title": str(quiz_artifact.get("title") or "quiz").strip(),
            "material_type": "quiz",
            "content": quiz_artifact.get("content"),
            "generation_state": dict(quiz_artifact.get("generation_state") or {}),
        },
    )


class ReplyServiceV2:
    def __init__(
        self,
        *,
        orchestrator=None,
        orchestrator_factory=None,
        conversation_store,
        context_builder=None,
        status_card_builder=None,
        course_storage_manager=None,
        report_edit_runtime=None,
        ppt_edit_runtime=None,
    ):
        self.orchestrator = orchestrator
        self.orchestrator_factory = orchestrator_factory
        self.conversation_store = conversation_store
        self.context_builder = context_builder
        self.status_card_builder = status_card_builder or StatusCardBuilder()
        self.course_storage_manager = course_storage_manager
        self.report_edit_runtime = report_edit_runtime
        self.ppt_edit_runtime = ppt_edit_runtime

    def _build_snapshot(self, request):
        return self.context_builder.build(request) if self.context_builder is not None else None

    def _prepare_artifact_route(self, *, request, snapshot):
        artifact_reference = getattr(request, "artifact_reference", None)
        if artifact_reference is None:
            return "", {"intent_class": "ask", "reason": "no_artifact_reference", "requires_confirmation": False}

        artifact_type = str(getattr(artifact_reference, "artifact_type", "") or "").strip()
        artifact_intent = classify_artifact_reference_intent(
            getattr(request, "question", ""),
            artifact_type=artifact_type,
        )
        if artifact_intent.get("intent_class") == "ask":
            artifact_context = load_artifact_context(
                artifact_reference=artifact_reference.model_dump(exclude_none=True),
                snapshot=snapshot,
                course_storage_manager=self.course_storage_manager,
                course_id=str(getattr(request, "course_id", "") or "").strip(),
            )
            if artifact_context is not None:
                setattr(request, "artifact_context", artifact_context)
        return artifact_type, artifact_intent

    @staticmethod
    def _build_artifact_clarification_result(*, request, artifact_type: str) -> dict:
        if artifact_type in {"ppt_deck", "ppt_outline", "ppt_content_markdown"}:
            message = "请先告诉我你想修改哪一页，比如“修改第 3 页”或“把第 2 页改成流程图风格”。"
        else:
            message = "请先告诉我你想修改哪一部分，可以直接说标题、引用一句原文，或说第几部分。"
        return {
            "message": {"role": "assistant", "content": message},
            "conversation": {"conversation_id": request.conversation_id},
            "action": {"name": "chat.reply"},
            "workflow": {"type": "artifact_reference", "status": "awaiting_input"},
            "artifacts": [],
            "sources": [],
            "trace": {"path": "artifact_reference", "intent": "unclear"},
        }

    def _run_artifact_edit(self, *, request, snapshot, artifact_type: str):
        if artifact_type in {"ppt_deck", "ppt_outline", "ppt_content_markdown"} and self.ppt_edit_runtime is not None:
            return self.ppt_edit_runtime.run_from_request(
                request=request,
                snapshot=snapshot,
                course_storage_manager=self.course_storage_manager,
            )
        if self.report_edit_runtime is not None:
            return self.report_edit_runtime.run_from_request(
                request=request,
                snapshot=snapshot,
                course_storage_manager=self.course_storage_manager,
            )
        return None

    def _finalize_result(self, *, payload, request, result: dict) -> dict:
        finalize_report_result(
            payload=payload,
            result=result,
            course_storage_manager=self.course_storage_manager,
            compact_message=True,
        )
        _persist_quiz_course_material(
            payload=payload,
            result=result,
            course_storage_manager=self.course_storage_manager,
        )

        conversation_id = str(((result.get("conversation") or {}).get("conversation_id")) or request.conversation_id or "").strip()
        result.setdefault("conversation", {"conversation_id": conversation_id})
        if conversation_id:
            self.conversation_store.write_v2_result(conversation_id, request, result)
            if self.context_builder is not None:
                refreshed_snapshot = self.context_builder.build(request)
                status_card = self.status_card_builder.build(
                    snapshot=refreshed_snapshot,
                    workflow=result.get("workflow"),
                    capability=request.capability,
                )
                result["status_card"] = status_card if isinstance(status_card, dict) else status_card.model_dump(exclude_none=True)
        return result

    def reply(self, payload):
        request = normalize_chat_request(payload)
        if not getattr(request, "conversation_id", None):
            request.conversation_id = f"conv-{uuid4().hex[:12]}"

        snapshot = self._build_snapshot(request)
        artifact_reference = getattr(request, "artifact_reference", None)
        artifact_type, artifact_intent = self._prepare_artifact_route(
            request=request,
            snapshot=snapshot,
        )
        intent_class = str(artifact_intent.get("intent_class") or "")
        if artifact_reference is not None and intent_class == "unclear":
            result = self._build_artifact_clarification_result(
                request=request,
                artifact_type=artifact_type,
            )
        elif artifact_reference is not None and intent_class == "edit":
            result = self._run_artifact_edit(
                request=request,
                snapshot=snapshot,
                artifact_type=artifact_type,
            )
            if result is None:
                orchestrator = self.orchestrator_factory(request) if self.orchestrator_factory is not None else self.orchestrator
                result = orchestrator.dispatch(request)
        else:
            orchestrator = self.orchestrator_factory(request) if self.orchestrator_factory is not None else self.orchestrator
            result = orchestrator.dispatch(request)
        return self._finalize_result(payload=payload, request=request, result=result)

    def reply_stream(self, payload):
        request = normalize_chat_request(payload)
        if not getattr(request, "conversation_id", None):
            request.conversation_id = f"conv-{uuid4().hex[:12]}"

        snapshot = self._build_snapshot(request)
        artifact_reference = getattr(request, "artifact_reference", None)
        artifact_type, artifact_intent = self._prepare_artifact_route(
            request=request,
            snapshot=snapshot,
        )
        intent_class = str(artifact_intent.get("intent_class") or "")
        if artifact_reference is not None and intent_class == "unclear":
            final_result = self._finalize_result(
                payload=payload,
                request=request,
                result=self._build_artifact_clarification_result(
                    request=request,
                    artifact_type=artifact_type,
                ),
            )
            yield {"type": "result", "payload": final_result}
            conversation_id = str(((final_result.get("conversation") or {}).get("conversation_id")) or request.conversation_id or "")
            yield {"type": "done", "payload": {"conversation_id": conversation_id}}
            return
        if artifact_reference is not None and intent_class == "edit":
            result = self._run_artifact_edit(
                request=request,
                snapshot=snapshot,
                artifact_type=artifact_type,
            )
            if result is not None:
                final_result = self._finalize_result(
                    payload=payload,
                    request=request,
                    result=result,
                )
                yield {"type": "result", "payload": final_result}
                conversation_id = str(((final_result.get("conversation") or {}).get("conversation_id")) or request.conversation_id or "")
                yield {"type": "done", "payload": {"conversation_id": conversation_id}}
                return

        orchestrator = self.orchestrator_factory(request) if self.orchestrator_factory is not None else self.orchestrator
        final_result = None
        for event in orchestrator.dispatch_stream(request):
            if event.get("type") == "result":
                final_result = self._finalize_result(
                    payload=payload,
                    request=request,
                    result=dict(event.get("payload") or {}),
                )
                yield {"type": "result", "payload": final_result}
            else:
                yield event

        conversation_id = str(((final_result or {}).get("conversation") or {}).get("conversation_id") or request.conversation_id or "")
        yield {"type": "done", "payload": {"conversation_id": conversation_id}}

    def refresh_running_conversation(self, request):
        if self.context_builder is None or self.ppt_edit_runtime is None:
            return None

        snapshot = self.context_builder.build(request)
        result = self.ppt_edit_runtime.resume_from_snapshot(
            request=request,
            snapshot=snapshot,
            course_storage_manager=self.course_storage_manager,
        )
        if not result:
            return None

        workflow_status = str(((result.get("workflow") or {}).get("status")) or "").strip()
        conversation_id = str(getattr(request, "conversation_id", "") or "").strip()
        if conversation_id and workflow_status in {"completed", "failed"}:
            self.conversation_store.write_v2_poll_result(conversation_id, request, result)
            refreshed_snapshot = self.context_builder.build(request)
            status_card = self.status_card_builder.build(
                snapshot=refreshed_snapshot,
                workflow=result.get("workflow"),
                capability=getattr(request, "capability", None),
            )
            result["status_card"] = status_card if isinstance(status_card, dict) else status_card.model_dump(exclude_none=True)
        return result


def build_default_reply_service_v2():
    conversation_store = ConversationStoreAdapter()
    context_builder = ContextBuilder(conversation_store=conversation_store)

    def build_orchestrator(request):
        gateway = build_default_gateway(getattr(request, "model_id", None))
        def runtime_video_search_tool(*, query, top_k=5, selected_doc_ids=None, owner=None):
            return video_search_tool(
                query=query,
                top_k=top_k,
                selected_doc_ids=selected_doc_ids,
                owner=owner,
                course_id=getattr(request, "course_id", None),
            )

        fast_runtime = FastChatRuntime(
            model_gateway=gateway,
            rag_retriever=rag_search_tool,
            web_retriever=web_search_tool,
            video_retriever=runtime_video_search_tool,
        )
        return MainOrchestrator(
            fast_runtime=fast_runtime,
            workflow_registry={
                "report": ReportWorkflowRuntime(
                    engine_resolver=lambda *, request, snapshot, decision: build_default_report_engine(
                        allow_rag=bool(getattr(request.capability, "allow_rag", False)),
                        allow_web=bool(getattr(request.capability, "allow_web", False)),
                    ),
                    generation_context_builder=GenerationContextBuilder(),
                    report_assembler=ReportAssembler(),
                    report_context_organizer=ReportContextOrganizer(llm=get_fallback_llm()),
                    generation_readiness_judge=GenerationReadinessJudge(),
                ),
                "ppt": PptWorkflowRuntime(
                    generation_context_builder=GenerationContextBuilder(),
                    ppt_context_organizer=PptContextOrganizer(llm=get_fallback_llm()),
                    readiness_judge=PptReadinessJudge(),
                    outline_builder=PptOutlineBuilder(llm=get_fallback_llm()),
                    content_markdown_generator=PptContentMarkdownGenerator(llm=get_fallback_llm()),
                    content_validator=PptContentValidator(),
                    html2ppt_client_factory=lambda: Html2PptClient(
                        base_url=os.getenv("HTML2PPT_BASE_URL", "http://127.0.0.1:46080")
                    ),
                ),
                "lesson_plan": LessonPlanWorkflowRuntime(
                    engine_resolver=lambda *, request, snapshot, decision: build_default_lesson_plan_engine(
                        llm=get_fallback_llm()
                    ),
                    generation_context_builder=GenerationContextBuilder(),
                    lesson_plan_context_organizer=LessonPlanContextOrganizer(),
                    lesson_plan_readiness_judge=LessonPlanReadinessJudge(),
                ),
                "quiz": QuizWorkflowRuntime(
                    generation_context_builder=GenerationContextBuilder(),
                    quiz_assembler=QuizAssembler(),
                    quiz_context_organizer=QuizContextOrganizer(llm=get_fallback_llm()),
                    quiz_readiness_judge=QuizReadinessJudge(llm=get_fallback_llm()),
                    quiz_generator=QuizGenerator(llm=get_fallback_llm(), rag_fetcher=rag_search_tool),
                ),
            },
            context_builder=context_builder,
        )

    return ReplyServiceV2(
        orchestrator_factory=build_orchestrator,
        conversation_store=conversation_store,
        context_builder=context_builder,
        status_card_builder=StatusCardBuilder(),
        course_storage_manager=default_course_storage_manager,
        report_edit_runtime=ReportEditRuntime(llm=get_fallback_llm()),
        ppt_edit_runtime=PptEditRuntime(
            html2ppt_client_factory=lambda: Html2PptClient(
                base_url=os.getenv("HTML2PPT_BASE_URL", "http://127.0.0.1:46080")
            )
        ),
    )
