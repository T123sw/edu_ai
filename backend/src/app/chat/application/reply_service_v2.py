from __future__ import annotations

from uuid import uuid4
import re

from app.chat.agents.report_generation import get_fallback_llm
from app.chat.application.request_normalizer import normalize_chat_request
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.orchestrator.generation_context_builder import GenerationContextBuilder
from app.chat.orchestrator.generation_readiness_judge import GenerationReadinessJudge
from app.chat.orchestrator.lesson_plan_context_organizer import LessonPlanContextOrganizer
from app.chat.orchestrator.lesson_plan_readiness_judge import LessonPlanReadinessJudge
from app.chat.orchestrator.main_orchestrator import MainOrchestrator
from app.chat.orchestrator.quiz_context_organizer import QuizContextOrganizer
from app.chat.orchestrator.quiz_readiness_judge import QuizReadinessJudge
from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer
from app.chat.orchestrator.status_card_builder import StatusCardBuilder
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
from app.chat.runtime.model_registry import build_agent_gateway, build_default_gateway
from app.chat.runtime.react_agent import ReActAgent
from app.chat.tasks import background_runner
from app.chat.tools.agent_tools import rag_search_tool, web_search_tool
from app.chat.tools.video_search import video_search_tool
from app.chat.workflows.quiz.assembler import QuizAssembler
from app.chat.workflows.quiz.generator import QuizGenerator
from app.chat.workflows.quiz.runtime import QuizWorkflowRuntime
from app.chat.workflows.lesson_plan.runtime import LessonPlanWorkflowRuntime
from app.chat.workflows.report.edit_runtime import ReportEditRuntime
from app.chat.workflows.report.assembler import ReportAssembler
from app.chat.workflows.report.runtime import ReportWorkflowRuntime
from app.workspace_scope import SCOPE_TYPE_COURSE
from core.config import Config
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
        owner_user_id=getattr(payload, "owner", None),
        scope_type=getattr(payload, "scope_type", SCOPE_TYPE_COURSE),
        scope_id=getattr(payload, "scope_id", None),
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
        memory_writer=None,
        knowledge_context_service=None,
        artifact_revision_service=None,
    ):
        self.orchestrator = orchestrator
        self.orchestrator_factory = orchestrator_factory
        self.conversation_store = conversation_store
        self.context_builder = context_builder
        self.status_card_builder = status_card_builder or StatusCardBuilder()
        self.course_storage_manager = course_storage_manager
        self.report_edit_runtime = report_edit_runtime
        self.memory_writer = memory_writer
        self.knowledge_context_service = knowledge_context_service
        self.artifact_revision_service = artifact_revision_service

    def _finalize_result(self, *, payload, request, result: dict) -> dict:
        if (result.get("trace") or {}).get("response_replayed"):
            return result
        if request.workspace_context is not None:
            result["workspace_context"] = request.workspace_context.model_dump()
            # Persist the resolved request, never the pre-clarification payload.
            payload = request
        if not result.get("artifact_revision") and (result.get("trace") or {}).get("path") != "deepseek-harness":
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
            if self.memory_writer is not None:
                try:
                    message = result.get("message") or {}
                    assistant_message = (
                        str(message.get("content") or "")
                        if isinstance(message, dict)
                        else str(getattr(message, "content", "") or "")
                    )
                    memory_write = self.memory_writer.persist_turn(
                        actor={
                            "user_id": str(getattr(request, "owner", "") or ""),
                            "role": str(getattr(request, "actor_role", "teacher") or "teacher"),
                        },
                        conversation_id=conversation_id,
                        course_id=getattr(request, "course_id", None),
                        user_message=str(getattr(request, "question", "") or ""),
                        assistant_message=assistant_message,
                        agent_state={},
                        tool_events=list(((result.get("trace") or {}).get("tool_events") or [])),
                    )
                    result.setdefault("trace", {})["agent_memory_write"] = memory_write.model_dump(
                        mode="json", exclude={"decisions"}
                    )
                except Exception as exc:
                    result.setdefault("trace", {})["agent_memory_write"] = {
                        "provider_status": "error",
                        "error": str(exc),
                    }
            if self.context_builder is not None:
                refreshed_snapshot = self.context_builder.build(request)
                status_card = self.status_card_builder.build(
                    snapshot=refreshed_snapshot,
                    workflow=result.get("workflow"),
                    capability=request.capability,
                )
                result["status_card"] = status_card if isinstance(status_card, dict) else status_card.model_dump(exclude_none=True)
        return result

    def _run_artifact_edit(self, *, request, snapshot):
        if self.artifact_revision_service is not None:
            storage = self.conversation_store.storage
            state = storage.get_state(request.conversation_id)
            pending = state.get("pending_operation") or {}
            revision_pending = pending.get("revision_pending") if pending.get("kind") == "artifact_revision" else None
            incoming = request.artifact_reference
            old_reference = (revision_pending or {}).get("reference") or {}
            if incoming and revision_pending and (incoming.artifact_id != old_reference.get("artifact_id") or incoming.source_course_id != old_reference.get("source_course_id")):
                revision_pending = None
                storage.update_state(request.conversation_id, {"pending_operation": None})
            operation_id = pending.get("id") if revision_pending else (request.request_id or uuid4().hex)
            source_course = getattr(request.artifact_reference, "source_course_id", None)
            if source_course and source_course != request.course_id and self.knowledge_context_service:
                self.knowledge_context_service.authorize(request.model_copy(update={"course_id": source_course}))
            outcome = self.artifact_revision_service.run(
                owner_user_id=request.owner, conversation_id=request.conversation_id,
                course_id=request.course_id, question=request.question,
                operation_id=operation_id, artifact_reference=request.artifact_reference,
                pending=revision_pending, scope_id=request.scope_id, actor_role=request.actor_role,
                session_artifacts=[state.get("active_artifact") or {}],
            )
            if outcome["status"] == "not_applicable":
                return None
            outcome["operation_id"] = operation_id
            if outcome.get("pending"):
                storage.update_state(request.conversation_id, {"pending_operation": {
                    "id": operation_id, "kind": "artifact_revision", "owner": request.owner,
                    "course_id": request.course_id, "scope_id": request.scope_id,
                    "revision_pending": outcome["pending"],
                }})
            elif outcome["status"] == "completed":
                storage.update_state(request.conversation_id, {"pending_operation": None})
            artifact = outcome.get("artifact") or {}
            reference = outcome.get("artifact_reference") or {}
            artifacts = [{**artifact, **reference}] if artifact else []
            return {
                "message": {"role": "assistant", "content": outcome.get("message", "")},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "artifact.read" if outcome["status"] == "answered" else "artifact.revise"}, "artifacts": artifacts, "sources": [],
                "artifact_revision": outcome, "trace": {"path": "fast"},
            }
        artifact_reference = getattr(request, "artifact_reference", None)
        if artifact_reference is None:
            return None

        if self.report_edit_runtime is not None:
            return self.report_edit_runtime.run_from_request(
                request=request,
                snapshot=snapshot,
                course_storage_manager=self.course_storage_manager,
            )
        return None

    def _model_plans(self, request):
        from app.chat.harness.runtime import HarnessRuntime
        storage = getattr(self.conversation_store, "storage", None)
        state = storage.get_state(request.conversation_id) if storage is not None else {}
        state = state or {}
        if (state.get("pending_operation") or {}).get("kind") == "artifact_revision":
            return False
        if re.search(r"修改|改写|重写|调整|简化|改一下|删掉", request.question) and re.search(r"报告|文档|教案|习题|闪卡|博客|导图|游戏|课堂", request.question) and "大纲" not in request.question:
            return False
        return bool(Config.USE_DEEPSEEK_HARNESS and HarnessRuntime.supports(request))

    def _prepare_workspace(self, request):
        if not self.knowledge_context_service:
            return None
        if self._model_plans(request):
            return self.knowledge_context_service.prepare_model(request)
        return self.knowledge_context_service.prepare(request)

    def reply(self, payload):
        request = normalize_chat_request(payload)
        if not getattr(request, "conversation_id", None):
            request.conversation_id = f"conv-{uuid4().hex[:12]}"

        scope_result = self._prepare_workspace(request)
        if scope_result is not None:
            return self._finalize_result(payload=payload, request=request, result=scope_result)

        snapshot = self.context_builder.build(request) if self.context_builder is not None else None
        result = None if self._model_plans(request) else self._run_artifact_edit(request=request, snapshot=snapshot)
        if result is None:
            orchestrator = self.orchestrator_factory(request) if self.orchestrator_factory is not None else self.orchestrator
            result = orchestrator.dispatch(request)
        return self._finalize_result(payload=payload, request=request, result=result)

    def reply_stream(self, payload):
        request = normalize_chat_request(payload)
        if not getattr(request, "conversation_id", None):
            request.conversation_id = f"conv-{uuid4().hex[:12]}"

        scope_result = self._prepare_workspace(request)
        if scope_result is not None:
            yield {"type": "result", "payload": self._finalize_result(payload=payload, request=request, result=scope_result)}
            yield {"type": "done", "payload": {"conversation_id": request.conversation_id}}
            return

        snapshot = self.context_builder.build(request) if self.context_builder is not None else None
        edit_result = None if self._model_plans(request) else self._run_artifact_edit(request=request, snapshot=snapshot)
        if edit_result is not None:
            final_result = self._finalize_result(
                payload=payload,
                request=request,
                result=edit_result,
            )
            conversation_id = str(((final_result.get("conversation") or {}).get("conversation_id")) or request.conversation_id or "")
            if (final_result.get("artifact_revision") or {}).get("status") == "queued":
                yield {"type": "metadata", "payload": {"conversation_id": conversation_id}}
                yield {"type": "task_submitted", "payload": {"task_id": final_result["artifact_revision"]["task_id"], "workflow_type": "artifact_revision", "conversation_id": conversation_id}}
            yield {"type": "result", "payload": final_result}
            yield {"type": "done", "payload": {"conversation_id": conversation_id}}
            return

        orchestrator = self.orchestrator_factory(request) if self.orchestrator_factory is not None else self.orchestrator

        service_ref = self

        def _on_workflow_complete(result: dict) -> None:
            service_ref._finalize_result(payload=payload, request=request, result=result)

        final_result = None
        for event in orchestrator.dispatch_stream(request, on_workflow_complete=_on_workflow_complete):
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

def build_default_reply_service_v2():
    conversation_store = ConversationStoreAdapter()
    from app.chat.memory.dependencies import get_agent_memory_service
    from app.learning import get_learning_service
    from app.learning.context_reader import LearningContextReader
    from app.assessment import get_assessment_service

    memory_service = get_agent_memory_service()
    context_builder = ContextBuilder(
        conversation_store=conversation_store,
        memory_reader=memory_service,
        learning_context_reader=LearningContextReader(
            get_learning_service(), get_assessment_service()
        ),
    )

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
        workflow_registry = {
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
        }
        react_agent = None
        if Config.USE_REACT_AGENT:
            from app.chat.runtime.agent_tools.handlers.providers import (
                build_default_image_search_provider,
            )
            from app.chat.runtime.model_registry import (
                build_planner_gateway,
                build_vision_gateway,
            )
            react_agent = ReActAgent(
                agent_gateway=build_agent_gateway(),
                planner_gateway=build_planner_gateway(),
                vision_gateway=build_vision_gateway(),
                fast_runtime=fast_runtime,
                rag_retriever=rag_search_tool,
                web_retriever=web_search_tool,
                image_search_provider=build_default_image_search_provider(),
                workflow_registry=workflow_registry,
                background_runner=background_runner,
                max_steps=Config.REACT_MAX_STEPS,
                timeout_seconds=Config.REACT_TIMEOUT_SECONDS,
            )
        return MainOrchestrator(
            fast_runtime=fast_runtime,
            workflow_registry=workflow_registry,
            context_builder=context_builder,
            react_agent=react_agent,
        )

    from app.artifact_revision.service import ArtifactRevisionService
    from app.artifact_revision.jobs import ArtifactRevisionCommandService
    from app.chat.application.knowledge_context import KnowledgeContextService, authorize_workspace

    return ReplyServiceV2(
        orchestrator_factory=build_orchestrator,
        conversation_store=conversation_store,
        context_builder=context_builder,
        status_card_builder=StatusCardBuilder(),
        course_storage_manager=default_course_storage_manager,
        report_edit_runtime=ReportEditRuntime(llm=get_fallback_llm()),
        memory_writer=memory_service,
        artifact_revision_service=ArtifactRevisionService(default_course_storage_manager, submitter=ArtifactRevisionCommandService().submit),
        knowledge_context_service=KnowledgeContextService(
            course_storage=default_course_storage_manager,
            conversation_storage=conversation_store.storage,
            authorize=authorize_workspace,
        ),
    )
