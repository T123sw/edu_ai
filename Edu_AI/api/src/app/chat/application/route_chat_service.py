from __future__ import annotations

import threading
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from app.chat.application.chat_app_service import ChatAppService
from app.chat.application.request_normalizer import normalize_chat_request
from app.chat.application.response_builder import build_http_response
from app.chat.legacy.compat_service import CompatChatService
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.orchestrator.main_orchestrator import MainOrchestrator
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
from app.chat.runtime.model_registry import build_agent_gateway, build_default_gateway
from app.chat.runtime.react_agent import ReActAgent
from app.chat.tasks import background_runner
from app.chat.workflows.lesson_plan.runtime import LessonPlanWorkflowRuntime
from app.workspace_scope import SCOPE_TYPE_COURSE, normalize_workspace_scope
from core.config import Config
from core.course_storage import storage_manager as default_course_storage_manager


class _ResponseBuilderAdapter:
    @staticmethod
    def build_http_response(result: dict) -> dict:
        return build_http_response(result)


def _persist_lesson_plan_course_material(*, payload, result: dict, course_storage_manager=None) -> None:
    course_id = str(getattr(payload, "course_id", "") or "").strip()
    if not course_id or course_storage_manager is None:
        return

    workflow = result.get("workflow") or {}
    if str(workflow.get("type") or "").strip() != "lesson_plan":
        return
    if str(workflow.get("status") or "").strip() != "completed":
        return

    artifacts = list(result.get("artifacts") or [])
    lesson_plan_artifact = next(
        (
            artifact
            for artifact in artifacts
            if isinstance(artifact, dict) and str(artifact.get("artifact_type") or "").strip() == "lesson_plan"
        ),
        None,
    )
    if not lesson_plan_artifact:
        return

    material_id = str(lesson_plan_artifact.get("artifact_id") or "").strip()
    if not material_id:
        return

    now = datetime.now().isoformat()
    course_storage_manager.save_generated_material(
        course_id=course_id,
        material_type="lesson_plan",
        material_id=material_id,
        scope_type=getattr(payload, "scope_type", SCOPE_TYPE_COURSE),
        scope_id=getattr(payload, "scope_id", None),
        material_data={
            "title": str(lesson_plan_artifact.get("title") or "教案").strip(),
            "material_type": "lesson_plan",
            "created_at": now,
            "updated_at": now,
            "plan": lesson_plan_artifact.get("content"),
        },
    )


class RouteChatService:
    def __init__(
        self,
        *,
        legacy_service,
        gateway_factory=build_default_gateway,
        enable_new_chat: bool = True,
        enable_fast_runtime: bool = True,
        report_engine=None,
        enable_report_workflow: bool = True,
        lesson_plan_engine=None,
        enable_lesson_plan_workflow: bool = True,
        enforce_capability_policy: bool = False,
        conversation_store=None,
        enhancement_router=None,
        enhancement_trace_enabled: bool = False,
        course_storage_manager=None,
    ):
        self.legacy_service = legacy_service
        self.gateway_factory = gateway_factory
        self.enable_new_chat = enable_new_chat
        self.enable_fast_runtime = enable_fast_runtime
        self.report_engine = report_engine
        self.enable_report_workflow = enable_report_workflow
        self.lesson_plan_engine = lesson_plan_engine
        self.enable_lesson_plan_workflow = enable_lesson_plan_workflow
        self.enforce_capability_policy = enforce_capability_policy
        self.enhancement_trace_enabled = bool(enhancement_trace_enabled)
        self.course_storage_manager = course_storage_manager or default_course_storage_manager
        if conversation_store is not None:
            self.conversation_store = conversation_store
            if enhancement_router is not None:
                self.conversation_store.enhancement_router = enhancement_router
            self.conversation_store.enhancement_trace_enabled = self.enhancement_trace_enabled
        else:
            self.conversation_store = ConversationStoreAdapter(
                enhancement_router=enhancement_router,
                enhancement_trace_enabled=self.enhancement_trace_enabled,
            )
        self._compat = CompatChatService(delegate=self._run_new_path)
        # Fix #3: cache built service stacks per model_id to avoid rebuilding every request
        self._service_cache: dict[str | None, Any] = {}

    def _resolve_report_engine(self):
        getter = getattr(self.legacy_service, "get_report_engine", None)
        if callable(getter):
            return getter()
        return None

    def _resolve_lesson_plan_engine(self):
        getter = getattr(self.legacy_service, "get_lesson_plan_engine", None)
        if callable(getter):
            return getter()
        return None

    def _build_chat_app_service(self, *, model_id: str | None):
        gateway = self.gateway_factory(model_id)
        fast_runtime = FastChatRuntime(model_gateway=gateway)
        workflow_registry = {}
        if self.enable_report_workflow:
            from app.chat.agents.report_generation import get_fallback_llm
            from app.chat.orchestrator.generation_readiness_judge import GenerationReadinessJudge
            from app.chat.orchestrator.report_context_organizer import ReportContextOrganizer
            from app.chat.workflows.report.runtime import ReportWorkflowRuntime

            workflow_registry["report"] = ReportWorkflowRuntime(
                engine=self.report_engine,
                engine_factory=self._resolve_report_engine if self.report_engine is None else None,
                report_context_organizer=ReportContextOrganizer(llm=get_fallback_llm()),
                generation_readiness_judge=GenerationReadinessJudge(),
            )
        if self.enable_lesson_plan_workflow:
            from app.chat.orchestrator.lesson_plan_context_organizer import LessonPlanContextOrganizer
            from app.chat.orchestrator.lesson_plan_readiness_judge import LessonPlanReadinessJudge

            workflow_registry["lesson_plan"] = LessonPlanWorkflowRuntime(
                engine=self.lesson_plan_engine,
                engine_factory=self._resolve_lesson_plan_engine if self.lesson_plan_engine is None else None,
                lesson_plan_context_organizer=LessonPlanContextOrganizer(),
                lesson_plan_readiness_judge=LessonPlanReadinessJudge(),
            )
        react_agent = None
        if Config.USE_REACT_AGENT:
            from app.chat.runtime.agent_tools.handlers.providers import (
                build_default_image_search_provider,
            )
            from app.chat.runtime.model_registry import build_planner_gateway, build_vision_gateway
            from app.chat.tools.agent_tools import rag_search_tool, web_search_tool
            react_agent = ReActAgent(
                agent_gateway=build_agent_gateway(),
                planner_gateway=build_planner_gateway(),
                vision_gateway=build_vision_gateway(),
                rag_retriever=rag_search_tool,
                web_retriever=web_search_tool,
                image_search_provider=build_default_image_search_provider(),
                fast_runtime=fast_runtime,
                workflow_registry=workflow_registry,
                background_runner=background_runner,
                max_steps=Config.REACT_MAX_STEPS,
                timeout_seconds=Config.REACT_TIMEOUT_SECONDS,
            )
        orchestrator = MainOrchestrator(
            fast_runtime=fast_runtime,
            workflow_registry=workflow_registry,
            context_builder=ContextBuilder(conversation_store=self.conversation_store),
            react_agent=react_agent,
        )
        return ChatAppService(
            normalizer=normalize_chat_request,
            orchestrator=orchestrator,
            response_builder=_ResponseBuilderAdapter(),
        )

    def _get_cached_chat_app_service(self, model_id: str | None) -> ChatAppService:
        key = model_id or ""
        if key not in self._service_cache:
            self._service_cache[key] = self._build_chat_app_service(model_id=model_id)
        return self._service_cache[key]

    def _resolve_scope(self, *, conversation_id, course_id, scope_type, scope_id, question=None):
        state = {}
        if conversation_id:
            state = self.conversation_store.storage.get_state(conversation_id)

        resolved_course_id = course_id or state.get("course_id")
        resolved_scope_type = scope_type or state.get("scope_type") or SCOPE_TYPE_COURSE
        resolved_scope_id = scope_id if scope_id is not None else state.get("scope_id")

        if not resolved_course_id:
            return {
                "course_id": None,
                "scope_type": SCOPE_TYPE_COURSE,
                "scope_id": None,
            }

        normalized_scope = normalize_workspace_scope(
            course_id=resolved_course_id,
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
        )
        if conversation_id:
            self.conversation_store.storage.ensure_conversation(conversation_id, question)
            self.conversation_store.storage.update_state(conversation_id, normalized_scope)
        return normalized_scope

    def _persist_new_result(self, payload, result: dict) -> None:
        conversation_id = str(((result.get("conversation") or {}).get("conversation_id")) or getattr(payload, "conversation_id", "") or "").strip()
        if not conversation_id:
            return

        self.conversation_store.storage.ensure_conversation(conversation_id, getattr(payload, "question", None))
        existing_state = self.conversation_store.storage.get_state(conversation_id)
        self.conversation_store.append_message(conversation_id, "user", payload.question)
        answer = str(((result.get("message") or {}).get("content")) or "").strip()
        if answer:
            self.conversation_store.append_message(
                conversation_id,
                "assistant",
                answer,
                sources=result.get("sources") or None,
            )

        state_patch = {}
        workflow = result.get("workflow") or {}
        if workflow:
            state_patch["workflow_state"] = {
                "workflow_id": conversation_id,
                "workflow_type": workflow.get("type") or "",
                "status": workflow.get("status") or "running",
                "stage": workflow.get("phase") or workflow.get("stage") or "",
                "artifacts": result.get("artifacts") or [],
            }
        action = (result.get("action") or {}).get("name")
        if action:
            state_patch["active_task"] = action
        artifacts = result.get("artifacts") or []
        if artifacts:
            first_artifact = artifacts[0]
            state_patch["active_artifact"] = {
                "artifact_id": first_artifact.get("artifact_id") or "",
                "artifact_type": first_artifact.get("artifact_type") or "",
                "title": first_artifact.get("title"),
            }
            state_patch["referenced_artifact_ids"] = [
                str(artifact.get("artifact_id") or "")
                for artifact in artifacts
                if artifact.get("artifact_id")
            ]
        if workflow or artifacts or getattr(payload, "course_id", None) or getattr(payload, "selected_doc_ids", None):
            state_patch["active_context"] = {
                "active_workflow_type": workflow.get("type") or "",
                "active_workflow_status": workflow.get("status") or "",
                "active_artifact_id": first_artifact.get("artifact_id") if artifacts else "",
                "active_artifact_type": first_artifact.get("artifact_type") if artifacts else "",
                "current_course_id": getattr(payload, "course_id", None),
                "scope_type": getattr(payload, "scope_type", SCOPE_TYPE_COURSE),
                "scope_id": getattr(payload, "scope_id", None),
                "pinned_doc_ids": list(getattr(payload, "selected_doc_ids", None) or []),
            }
        state_patch["course_id"] = getattr(payload, "course_id", None)
        state_patch["scope_type"] = getattr(payload, "scope_type", SCOPE_TYPE_COURSE)
        state_patch["scope_id"] = getattr(payload, "scope_id", None)
        state_patch["capability_policy"] = {
            "allow_rag": bool(getattr(payload, "allow_rag", False) or getattr(payload, "use_rag", False)),
            "allow_web": bool(getattr(payload, "allow_web", False)),
            "selected_doc_ids": list(getattr(payload, "selected_doc_ids", None) or []),
        }
        recent_messages = self.conversation_store.storage.get_messages(conversation_id, limit=8)
        extraction_request = SimpleNamespace(
            question=getattr(payload, "question", ""),
            course_id=getattr(payload, "course_id", None),
            scope_type=getattr(payload, "scope_type", SCOPE_TYPE_COURSE),
            scope_id=getattr(payload, "scope_id", None),
            capability=SimpleNamespace(
                allow_rag=bool(getattr(payload, "allow_rag", False) or getattr(payload, "use_rag", False)),
                allow_web=bool(getattr(payload, "allow_web", False)),
                selected_doc_ids=list(getattr(payload, "selected_doc_ids", None) or []),
            ),
        )
        extraction_patch, enhancement_observation = self.conversation_store.build_memory_state_patch_with_observation(
            conversation_id=conversation_id,
            request=extraction_request,
            result=result,
            existing_state=existing_state,
            recent_messages=recent_messages,
        )
        state_patch.update(extraction_patch)
        if self.conversation_store.enhancement_trace_enabled:
            state_patch["llm_enhancement_trace"] = enhancement_observation
            trace = dict(result.get("trace") or {})
            trace["llm_enhancement"] = enhancement_observation
            result["trace"] = trace
        _persist_lesson_plan_course_material(
            payload=payload,
            result=result,
            course_storage_manager=self.course_storage_manager,
        )
        if state_patch:
            self.conversation_store.storage.update_state(conversation_id, state_patch)

    @staticmethod
    def _resolve_rag_flags(*, use_rag=False, allow_rag=None, selected_doc_ids=None):
        resolved_allow_rag = bool(use_rag) if allow_rag is None else bool(allow_rag)
        if not resolved_allow_rag and selected_doc_ids:
            resolved_allow_rag = True
        resolved_use_rag = bool(use_rag) or bool(selected_doc_ids) or resolved_allow_rag
        return resolved_use_rag, resolved_allow_rag

    def _delegate_legacy(self, payload):
        use_rag = bool(getattr(payload, "use_rag", False) or getattr(payload, "allow_rag", False))
        if self.enforce_capability_policy:
            use_rag = bool(getattr(payload, "allow_rag", False))
        return self.legacy_service.chat(
            question=payload.question,
            conversation_id=payload.conversation_id,
            model_id=payload.model_id,
            use_rag=use_rag,
            selected_doc_ids=getattr(payload, "selected_doc_ids", None),
            owner=getattr(payload, "owner", None),
            course_id=getattr(payload, "course_id", None),
            scope_type=getattr(payload, "scope_type", SCOPE_TYPE_COURSE),
            scope_id=getattr(payload, "scope_id", None),
            allow_web=bool(getattr(payload, "allow_web", False)),
            action_hint=getattr(payload, "action_hint", None),
            artifact_id=getattr(payload, "artifact_id", None),
        )

    def _run_new_path(self, payload):
        if not self.enable_new_chat:
            return self._delegate_legacy(payload)
        if not self.enable_fast_runtime and getattr(payload, "action_hint", None) in {None, "", "chat.reply", "chat.rewrite"}:
            return self._delegate_legacy(payload)

        app_service = self._get_cached_chat_app_service(model_id=getattr(payload, "model_id", None))
        try:
            result = app_service.chat(payload)
        except KeyError:
            return self._delegate_legacy(payload)
        self._persist_new_result(payload, result)
        return result

    def _build_payload(
        self,
        *,
        question,
        conversation_id,
        model_id,
        use_rag,
        allow_rag=None,
        selected_doc_ids,
        owner,
        course_id,
        scope_type,
        scope_id,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    ):
        resolved_use_rag, resolved_allow_rag = self._resolve_rag_flags(
            use_rag=use_rag,
            allow_rag=allow_rag,
            selected_doc_ids=selected_doc_ids,
        )
        return SimpleNamespace(
            question=question,
            conversation_id=conversation_id,
            model_id=model_id,
            use_rag=resolved_use_rag,
            allow_rag=resolved_allow_rag,
            allow_web=allow_web,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
            course_id=course_id,
            scope_type=scope_type,
            scope_id=scope_id,
            action_hint=action_hint,
            artifact_id=artifact_id,
        )

    def chat(
        self,
        *,
        question,
        conversation_id,
        model_id,
        use_rag=False,
        allow_rag=None,
        selected_doc_ids=None,
        owner=None,
        course_id=None,
        scope_type=None,
        scope_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    ):
        resolved_scope = self._resolve_scope(
            conversation_id=conversation_id,
            course_id=course_id,
            scope_type=scope_type,
            scope_id=scope_id,
            question=question,
        )
        resolved_use_rag, resolved_allow_rag = self._resolve_rag_flags(
            use_rag=use_rag,
            allow_rag=allow_rag,
            selected_doc_ids=selected_doc_ids,
        )
        return self._compat.chat(
            question=question,
            conversation_id=conversation_id,
            model_id=model_id,
            use_rag=resolved_use_rag,
            allow_rag=resolved_allow_rag,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
            course_id=resolved_scope["course_id"],
            scope_type=resolved_scope["scope_type"],
            scope_id=resolved_scope["scope_id"],
            allow_web=allow_web,
            action_hint=action_hint,
            artifact_id=artifact_id,
        )

    def chat_stream_with_meta(
        self,
        *,
        question,
        conversation_id,
        model_id,
        use_rag=False,
        allow_rag=None,
        selected_doc_ids=None,
        owner=None,
        course_id=None,
        scope_type=None,
        scope_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    ):
        resolved_scope = self._resolve_scope(
            conversation_id=conversation_id,
            course_id=course_id,
            scope_type=scope_type,
            scope_id=scope_id,
            question=question,
        )

        # Fall back to legacy streaming when the new path is disabled
        if not self.enable_new_chat or (
            not self.enable_fast_runtime
            and action_hint in {None, "", "chat.reply", "chat.rewrite"}
        ):
            resolved_use_rag, _ = self._resolve_rag_flags(
                use_rag=use_rag,
                allow_rag=allow_rag,
                selected_doc_ids=selected_doc_ids,
            )
            return self.legacy_service.chat_stream_with_meta(
                question=question,
                conversation_id=conversation_id,
                model_id=model_id,
                use_rag=resolved_use_rag,
                selected_doc_ids=selected_doc_ids,
                owner=owner,
                course_id=resolved_scope["course_id"],
                scope_type=resolved_scope["scope_type"],
                scope_id=resolved_scope["scope_id"],
                allow_web=allow_web,
                action_hint=action_hint,
                artifact_id=artifact_id,
            )

        payload = self._build_payload(
            question=question,
            conversation_id=conversation_id,
            model_id=model_id,
            use_rag=use_rag,
            allow_rag=allow_rag,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
            course_id=resolved_scope["course_id"],
            scope_type=resolved_scope["scope_type"],
            scope_id=resolved_scope["scope_id"],
            allow_web=allow_web,
            action_hint=action_hint,
            artifact_id=artifact_id,
        )

        # Fix #1b: true token-by-token streaming via dispatch_stream
        app_service = self._get_cached_chat_app_service(model_id=model_id)
        request = normalize_chat_request(payload)

        # Preliminary meta returned immediately so the SSE meta frame is sent before LLM starts
        preliminary_meta = {
            "answer": "",
            "conversation_id": str(payload.conversation_id or ""),
            "model_id": str(payload.model_id or ""),
            "intent_category": "chat",
            "meta": {},
        }

        # Capture self for use inside the generator closure
        service = self

        def _stream():
            final_result = None
            task_submitted = False
            for event in app_service.orchestrator.dispatch_stream(
                request,
                on_workflow_complete=lambda result: service._persist_new_result(payload, result),
            ):
                event_type = event.get("type")
                if event_type == "result":
                    final_result = event.get("payload") or {}
                    # Forward conversation_id so client can persist it for the next turn.
                    # Without this, multi-turn conversations cannot resume working memory.
                    conv_id = (final_result.get("conversation") or {}).get("conversation_id")
                    if conv_id:
                        yield {"type": "meta", "payload": {"conversation_id": conv_id}}
                elif event_type == "task_submitted":
                    # Workflow dispatched to background — forward event, persist handled by on_workflow_complete
                    yield event
                    task_submitted = True
                elif event_type == "metadata":
                    # FastChatRuntime emits "metadata"; translate to the legacy "meta" event
                    ep = event.get("payload") or {}
                    yield {
                        "type": "meta",
                        "payload": {"path": (ep.get("trace") or {}).get("path", "fast")},
                    }
                elif event_type == "delta":
                    content = (event.get("payload") or {}).get("content", "") or event.get("delta", "")
                    if content:
                        yield {"type": "delta", "delta": content}
                elif event_type == "status":
                    yield event
                elif event_type in ("tool_call", "tool_result", "plan", "plan_step_update", "reflect"):
                    # Forward ReAct agent's richer events so the client can render
                    # plan visibility, tool execution progress, and self-check feedback.
                    yield event

            # Send done frame to client before persisting
            yield {"type": "done"}

            # For fast-path results, persist in background thread so done reaches client first.
            # Workflow results are persisted via on_workflow_complete callback when task completes.
            if not task_submitted and final_result:
                threading.Thread(
                    target=service._persist_new_result,
                    args=(payload, final_result),
                    daemon=True,
                ).start()

        return preliminary_meta, _stream()

    def skill_health_check(self, meta):
        return self.legacy_service.skill_health_check(meta)
