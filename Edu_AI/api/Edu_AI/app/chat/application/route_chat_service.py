from __future__ import annotations

from types import SimpleNamespace

from app.chat.application.chat_app_service import ChatAppService
from app.chat.application.request_normalizer import normalize_chat_request
from app.chat.application.response_builder import build_http_response
from app.chat.legacy.compat_service import CompatChatService
from app.chat.orchestrator.context_builder import ContextBuilder
from app.chat.orchestrator.main_orchestrator import MainOrchestrator
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter
from app.chat.runtime.fast_chat_runtime import FastChatRuntime
from app.chat.runtime.model_registry import build_default_gateway


class _ResponseBuilderAdapter:
    @staticmethod
    def build_http_response(result: dict) -> dict:
        return build_http_response(result)


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
        enforce_capability_policy: bool = False,
        conversation_store=None,
        enhancement_router=None,
        enhancement_trace_enabled: bool = False,
    ):
        self.legacy_service = legacy_service
        self.gateway_factory = gateway_factory
        self.enable_new_chat = enable_new_chat
        self.enable_fast_runtime = enable_fast_runtime
        self.report_engine = report_engine
        self.enable_report_workflow = enable_report_workflow
        self.enforce_capability_policy = enforce_capability_policy
        self.enhancement_trace_enabled = bool(enhancement_trace_enabled)
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

    def _resolve_report_engine(self):
        getter = getattr(self.legacy_service, "get_report_engine", None)
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
        orchestrator = MainOrchestrator(
            fast_runtime=fast_runtime,
            workflow_registry=workflow_registry,
            context_builder=ContextBuilder(conversation_store=self.conversation_store),
        )
        return ChatAppService(
            normalizer=normalize_chat_request,
            orchestrator=orchestrator,
            response_builder=_ResponseBuilderAdapter(),
        )

    def _resolve_course_id(self, *, conversation_id, course_id, question=None):
        if not conversation_id:
            return course_id

        if course_id:
            self.conversation_store.storage.ensure_conversation(conversation_id, question)
            self.conversation_store.storage.update_state(conversation_id, {"course_id": course_id})
            return course_id

        state = self.conversation_store.storage.get_state(conversation_id)
        return state.get("course_id")

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
                "pinned_doc_ids": list(getattr(payload, "selected_doc_ids", None) or []),
            }
        state_patch["capability_policy"] = {
            "allow_rag": bool(getattr(payload, "allow_rag", False) or getattr(payload, "use_rag", False)),
            "allow_web": bool(getattr(payload, "allow_web", False)),
            "selected_doc_ids": list(getattr(payload, "selected_doc_ids", None) or []),
        }
        recent_messages = self.conversation_store.storage.get_messages(conversation_id, limit=8)
        extraction_request = SimpleNamespace(
            question=getattr(payload, "question", ""),
            course_id=getattr(payload, "course_id", None),
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
        if state_patch:
            self.conversation_store.storage.update_state(conversation_id, state_patch)

    @staticmethod
    def _resolve_rag_flags(*, use_rag=False, allow_rag=None, selected_doc_ids=None):
        resolved_allow_rag = bool(use_rag) if allow_rag is None else bool(allow_rag)
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
            allow_web=bool(getattr(payload, "allow_web", False)),
            action_hint=getattr(payload, "action_hint", None),
            artifact_id=getattr(payload, "artifact_id", None),
        )

    def _run_new_path(self, payload):
        if not self.enable_new_chat:
            return self._delegate_legacy(payload)
        if not self.enable_fast_runtime and getattr(payload, "action_hint", None) in {None, "", "chat.reply", "chat.rewrite"}:
            return self._delegate_legacy(payload)

        app_service = self._build_chat_app_service(model_id=getattr(payload, "model_id", None))
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
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    ):
        course_id = self._resolve_course_id(
            conversation_id=conversation_id,
            course_id=course_id,
            question=question,
        )
        return self._compat.chat(
            question=question,
            conversation_id=conversation_id,
            model_id=model_id,
            use_rag=use_rag,
            allow_rag=allow_rag,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
            course_id=course_id,
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
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    ):
        course_id = self._resolve_course_id(
            conversation_id=conversation_id,
            course_id=course_id,
            question=question,
        )
        payload = self._build_payload(
            question=question,
            conversation_id=conversation_id,
            model_id=model_id,
            use_rag=use_rag,
            allow_rag=allow_rag,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
            course_id=course_id,
            allow_web=allow_web,
            action_hint=action_hint,
            artifact_id=artifact_id,
        )
        result = self._run_new_path(payload)
        if "answer" in result and "intent_category" in result:
            return self.legacy_service.chat_stream_with_meta(
                question=question,
                conversation_id=conversation_id,
                model_id=model_id,
                use_rag=use_rag,
                selected_doc_ids=selected_doc_ids,
                owner=owner,
                course_id=course_id,
                allow_web=allow_web,
                action_hint=action_hint,
                artifact_id=artifact_id,
            )

        meta = self._compat._adapt_result(result, payload)
        stream = [
            {"type": "meta", "payload": {"path": ((result.get("trace") or {}).get("path") or "fast")}},
            {"type": "delta", "delta": meta["answer"]},
            {"type": "done"},
        ]
        return meta, stream

    def skill_health_check(self, meta):
        return self.legacy_service.skill_health_check(meta)
