from __future__ import annotations

import threading
import time

from app.chat.domain.extraction_trigger import ExtractionTrigger
from app.chat.orchestrator.conversation_memory_extractor_v2 import ConversationMemoryExtractor
from app.chat.orchestrator.llm_enhancement_router import LLMEnhancementRouter
from app.workspace_scope import SCOPE_TYPE_COURSE
from core.conversation_storage import conversation_storage


class ConversationStoreAdapter:
    def __init__(self, *, storage=None, memory_extractor=None, enhancement_router=None, enhancement_trace_enabled: bool = False):
        self.storage = storage or conversation_storage
        self.memory_extractor = memory_extractor or ConversationMemoryExtractor()
        self.enhancement_router = enhancement_router or LLMEnhancementRouter()
        self.enhancement_trace_enabled = bool(enhancement_trace_enabled)

    def load_snapshot(self, conversation_id: str):
        return {
            "messages": self.storage.get_messages(conversation_id, limit=20),
            "state": self.storage.get_state(conversation_id),
        }

    def load_conversation_detail(self, conversation_id: str, *, owner: str | None = None):
        return self.storage.get_conversation(conversation_id, owner=owner)

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        sources=None,
        input_images=None,
        input_videos=None,
        message_kind: str | None = None,
        tool_calls=None,
        tool_call_id: str | None = None,
    ):
        self.storage.append_message(
            conversation_id,
            role,
            content,
            sources=sources,
            input_images=input_images,
            input_videos=input_videos,
            message_kind=message_kind,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
        )

    def update_workflow_state(self, conversation_id: str, workflow_state: dict):
        self.storage.update_state(conversation_id, {"workflow_state": workflow_state})

    @staticmethod
    def _normalize_artifact_reference(value) -> dict:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            return dict(value.model_dump(exclude_none=True))
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "__dict__"):
            return {
                key: raw
                for key, raw in dict(vars(value)).items()
                if not key.startswith("_") and raw is not None
            }
        return {}

    @staticmethod
    def _normalize_conversation_reference(value) -> dict:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            return dict(value.model_dump(exclude_none=True))
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "__dict__"):
            return {
                key: raw
                for key, raw in dict(vars(value)).items()
                if not key.startswith("_") and raw is not None
            }
        return {}

    @staticmethod
    def _normalize_input_images(values) -> list[dict]:
        normalized: list[dict] = []
        for item in list(values or []):
            if hasattr(item, "model_dump"):
                normalized.append(dict(item.model_dump(exclude_none=True)))
            elif isinstance(item, dict):
                normalized.append(dict(item))
            elif hasattr(item, "__dict__"):
                normalized.append(
                    {
                        key: raw
                        for key, raw in dict(vars(item)).items()
                        if not key.startswith("_") and raw is not None
                    }
                )
        return normalized

    @staticmethod
    def _normalize_input_videos(values) -> list[dict]:
        normalized: list[dict] = []
        for item in list(values or []):
            if hasattr(item, "model_dump"):
                normalized.append(dict(item.model_dump(exclude_none=True)))
            elif isinstance(item, dict):
                normalized.append(dict(item))
            elif hasattr(item, "__dict__"):
                normalized.append(
                    {
                        key: raw
                        for key, raw in dict(vars(item)).items()
                        if not key.startswith("_") and raw is not None
                    }
                )
        return normalized

    @staticmethod
    def _build_extraction_trigger(*, conversation_id: str, request, result: dict) -> ExtractionTrigger:
        workflow_type = str(((result.get("workflow") or {}).get("type")) or "").strip()
        action_name = str(((result.get("action") or {}).get("name")) or "").strip()
        if workflow_type:
            event = f"workflow.{workflow_type}.requested"
        else:
            event = "reply.completed"
        return ExtractionTrigger(
            event=event,
            conversation_id=conversation_id,
            question=str(getattr(request, "question", "") or ""),
            action_name=action_name or None,
            workflow_type=workflow_type or None,
        )

    def build_memory_state_patch_with_observation(self, *, conversation_id: str, request, result: dict, existing_state: dict, recent_messages: list[dict]) -> tuple[dict, dict]:
        rule_patch = self.memory_extractor.build_state_patch(
            request=request,
            result=result,
            existing_state=existing_state,
            recent_messages=recent_messages,
        )
        trigger = self._build_extraction_trigger(
            conversation_id=conversation_id,
            request=request,
            result=result,
        )

        if not self.enhancement_router.should_run(trigger):
            # Enhancement disabled or unsupported — return rule_patch synchronously
            base_obs = self.enhancement_router._base_observation(trigger=trigger, rule_patch=rule_patch)
            base_obs["fallback_reason"] = "disabled_or_unsupported_event"
            return rule_patch, base_obs

        # Enhancement enabled — run LLM call in background thread to avoid blocking response
        context = {
            "resource_type": str(((result.get("workflow") or {}).get("type")) or "chat"),
            "action_name": str(((result.get("action") or {}).get("name")) or "").strip(),
            "recent_messages": recent_messages,
        }

        def _run_enhancement():
            try:
                # The rule-based patch is persisted by the caller immediately
                # after this method returns. Wait for that baseline before
                # writing the asynchronous LLM delta; otherwise a fast
                # enhancer can be overwritten by the caller's later state
                # update and silently disappear.
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    current_state = self.storage.get_state(conversation_id)
                    baseline_ready = all(
                        not value or current_state.get(key) == value
                        for key, value in rule_patch.items()
                    )
                    if baseline_ready:
                        break
                    time.sleep(0.005)
                merged_patch, _ = self.enhancement_router.apply_with_observation(
                    trigger=trigger,
                    existing_state=existing_state,
                    rule_patch=rule_patch,
                    context=context,
                )
                # Write only the fields that the LLM enhanced beyond the rule patch
                delta: dict = {}
                for key in ("conversation_memory", "conversation_summary"):
                    rule_val = rule_patch.get(key)
                    merged_val = merged_patch.get(key)
                    if merged_val and merged_val != rule_val:
                        delta[key] = merged_val
                if delta:
                    self.storage.update_state(conversation_id, delta)
            except Exception:
                pass

        threading.Thread(target=_run_enhancement, daemon=True).start()

        observation = {
            "trigger_event": trigger.event,
            "candidate_fields": [],
            "accepted_fields": [],
            "rejected_fields": [],
            "fallback_reason": None,
            "deferred": True,
            "final_patch": {
                "summary_text": str(((rule_patch.get("conversation_summary") or {}).get("summary_text")) or ""),
                "memory": dict(rule_patch.get("conversation_memory") or {}),
            },
        }
        return rule_patch, observation

    def build_memory_state_patch(self, *, conversation_id: str, request, result: dict, existing_state: dict, recent_messages: list[dict]) -> dict:
        patch, _ = self.build_memory_state_patch_with_observation(
            conversation_id=conversation_id,
            request=request,
            result=result,
            existing_state=existing_state,
            recent_messages=recent_messages,
        )
        return patch

    @staticmethod
    def _pick_active_artifact(*, artifacts: list[dict], artifact_reference: dict) -> dict:
        if artifacts:
            for artifact in reversed(list(artifacts or [])):
                if not isinstance(artifact, dict):
                    continue
                if str(artifact.get("artifact_type") or "").strip() == "ppt_deck":
                    return artifact
            return artifacts[0]
        return artifact_reference

    @staticmethod
    def _build_active_context_patch(*, request, workflow: dict | None, workflow_status: str, artifacts: list[dict]):
        capability = getattr(request, "capability", None)
        selected_doc_ids = list(getattr(capability, "selected_doc_ids", []) or [])
        artifact_reference = ConversationStoreAdapter._normalize_artifact_reference(
            getattr(request, "artifact_reference", None)
        )
        conversation_reference = ConversationStoreAdapter._normalize_conversation_reference(
            getattr(request, "conversation_reference", None)
        )
        active_artifact = ConversationStoreAdapter._pick_active_artifact(
            artifacts=list(artifacts or []),
            artifact_reference=artifact_reference,
        )
        active_artifact_id = str(active_artifact.get("artifact_id") or artifact_reference.get("artifact_id") or "")
        active_artifact_type = str(active_artifact.get("artifact_type") or artifact_reference.get("artifact_type") or "")
        active_reference_mode = ""
        if artifact_reference:
            active_reference_mode = "artifact_edit"
        elif conversation_reference:
            active_reference_mode = "conversation_reference"
        return {
            "active_workflow_type": (workflow or {}).get("type") or "",
            "active_workflow_status": workflow_status or str((workflow or {}).get("status") or ""),
            "active_artifact_id": active_artifact_id,
            "active_artifact_type": active_artifact_type,
            "active_reference_mode": active_reference_mode,
            "referenced_conversation_id": str(conversation_reference.get("conversation_id") or ""),
            "referenced_conversation_title": conversation_reference.get("title"),
            "current_course_id": getattr(request, "course_id", None),
            "scope_type": getattr(request, "scope_type", SCOPE_TYPE_COURSE),
            "scope_id": getattr(request, "scope_id", None),
            "pinned_doc_ids": selected_doc_ids,
        }

    @staticmethod
    def _build_workflow_filled_slots(*, result: dict) -> dict[str, str]:
        workflow = dict(result.get("workflow") or {})
        direct_filled_slots = dict(workflow.get("filled_slots") or {})
        if direct_filled_slots:
            return direct_filled_slots

        trace = dict(result.get("trace") or {})
        preparation = dict(trace.get("report_preparation_result") or {})
        filled_slots: dict[str, str] = {}
        subject = str(preparation.get("report_subject") or "").strip()
        focus = str(preparation.get("report_focus") or "").strip()
        source = str(preparation.get("preparation_source") or "").strip()
        model = str(preparation.get("preparation_model") or "").strip()
        if subject:
            filled_slots["core_topic"] = subject
        if focus:
            filled_slots["focus_area"] = focus
        if source:
            filled_slots["__preparation_source"] = source
        if model:
            filled_slots["__preparation_model"] = model
        if filled_slots:
            return filled_slots

        preparation = dict(trace.get("ppt_preparation_result") or {})
        topic = str(preparation.get("topic") or "").strip()
        audience = str(preparation.get("audience") or "").strip()
        objective = str(preparation.get("objective") or "").strip()
        key_points = [str(item).strip() for item in list(preparation.get("key_points") or []) if str(item).strip()]
        theme_id = str(preparation.get("theme") or "").strip()
        page_count = preparation.get("page_count")
        source_basis = [str(item).strip() for item in list(preparation.get("source_basis") or []) if str(item).strip()]
        if topic:
            filled_slots["deck_topic"] = topic
        if audience:
            filled_slots["audience"] = audience
        if objective:
            filled_slots["objective"] = objective
        if key_points:
            filled_slots["key_points"] = " | ".join(key_points)
        if theme_id:
            filled_slots["theme_id"] = theme_id
        if page_count:
            filled_slots["slide_count"] = str(page_count)
        if source_basis:
            filled_slots["__ppt_source_basis"] = " | ".join(source_basis)
        return filled_slots

    def write_v2_result(self, conversation_id: str, request, result: dict, *, append_user_message: bool = True):
        self.storage.ensure_conversation(
            conversation_id,
            request.question,
            owner=getattr(request, "owner", None),
        )
        existing_state = self.storage.get_state(conversation_id)
        workflow = result.get("workflow") or None
        action_name = str(((result.get("action") or {}).get("name")) or "").strip()
        artifacts = result.get("artifacts") or []
        normalized_input_images = self._normalize_input_images(getattr(request, "input_images", []) or [])
        normalized_input_videos = self._normalize_input_videos(getattr(request, "input_videos", []) or [])
        if append_user_message:
            user_message_kind = self.memory_extractor.classify_message_kind(
                role="user",
                text=request.question,
                workflow_type=str((workflow or {}).get("type") or ""),
                action_name=action_name,
                artifacts=artifacts,
            )
            self.append_message(
                conversation_id,
                "user",
                request.question,
                input_images=normalized_input_images or None,
                input_videos=normalized_input_videos or None,
                message_kind=user_message_kind,
            )
        # 持久化工具调用轮次（assistant tool_calls + tool results），让多轮对话上下文完整
        for exchange_msg in result.get("tool_exchange") or []:
            ex_role = str(exchange_msg.get("role") or "")
            ex_content = str(exchange_msg.get("content") or "")
            ex_tool_calls = exchange_msg.get("tool_calls") or None
            ex_tool_call_id = str(exchange_msg.get("tool_call_id") or "") or None
            if ex_role in ("assistant", "tool"):
                self.append_message(
                    conversation_id,
                    ex_role,
                    ex_content,
                    message_kind="tool_exchange",
                    tool_calls=ex_tool_calls,
                    tool_call_id=ex_tool_call_id,
                )

        answer = str(((result.get("message") or {}).get("content")) or "").strip()
        if answer:
            assistant_message_kind = self.memory_extractor.classify_message_kind(
                role="assistant",
                text=answer,
                workflow_type=str((workflow or {}).get("type") or ""),
                action_name=action_name,
                artifacts=artifacts,
            )
            self.append_message(
                conversation_id,
                "assistant",
                answer,
                sources=result.get("sources") or None,
                message_kind=assistant_message_kind,
            )
        recent_messages = self.storage.get_messages(conversation_id, limit=8)

        state_patch = {}
        state_patch["course_id"] = getattr(request, "course_id", None) or existing_state.get("course_id")
        state_patch["scope_type"] = (
            getattr(request, "scope_type", None)
            or existing_state.get("scope_type")
            or SCOPE_TYPE_COURSE
        )
        state_patch["scope_id"] = (
            getattr(request, "scope_id", None)
            if getattr(request, "scope_id", None) is not None
            else existing_state.get("scope_id")
        )
        workflow_status = str((workflow or {}).get("status") or "").strip()
        if workflow_status == "interrupted":
            state_patch["active_task"] = ""
        elif action_name:
            state_patch["active_task"] = action_name

        if workflow:
            state_patch["workflow_state"] = {
                "workflow_id": conversation_id,
                "workflow_type": workflow.get("type") or "",
                "status": workflow.get("status") or "running",
                "stage": workflow.get("phase") or workflow.get("stage") or "",
                "required_slots": list(workflow.get("required_slots") or []),
                "filled_slots": self._build_workflow_filled_slots(result=result),
                "artifacts": result.get("artifacts") or [],
            }

        artifacts = result.get("artifacts") or []
        artifact_reference = self._normalize_artifact_reference(getattr(request, "artifact_reference", None))
        conversation_reference = self._normalize_conversation_reference(getattr(request, "conversation_reference", None))
        if artifacts:
            first = self._pick_active_artifact(
                artifacts=list(artifacts or []),
                artifact_reference=artifact_reference,
            )
            state_patch["active_artifact"] = {
                "artifact_id": first.get("artifact_id") or "",
                "artifact_type": first.get("artifact_type") or "",
                "title": first.get("title"),
            }
        elif artifact_reference:
            state_patch["active_artifact"] = {
                "artifact_id": artifact_reference.get("artifact_id") or "",
                "artifact_type": artifact_reference.get("artifact_type") or "",
                "title": artifact_reference.get("title"),
            }
        if (
            workflow
            or artifacts
            or getattr(request, "course_id", None)
            or getattr(getattr(request, "capability", None), "selected_doc_ids", None)
            or conversation_reference
        ):
            state_patch["active_context"] = self._build_active_context_patch(
                request=request,
                workflow=workflow,
                workflow_status=workflow_status,
                artifacts=artifacts,
            )
        elif artifact_reference or conversation_reference:
            state_patch["active_context"] = self._build_active_context_patch(
                request=request,
                workflow=workflow,
                workflow_status=workflow_status,
                artifacts=artifacts,
            )
        capability = getattr(request, "capability", None)
        if capability is not None:
            state_patch["capability_policy"] = {
                "allow_rag": bool(getattr(capability, "allow_rag", False)),
                "allow_web": bool(getattr(capability, "allow_web", False)),
                "selected_doc_ids": list(getattr(capability, "selected_doc_ids", []) or []),
            }
        if hasattr(request, "input_images"):
            state_patch["last_input_images"] = normalized_input_images
            state_patch["last_input_image_count"] = len(normalized_input_images)
        if hasattr(request, "input_videos"):
            state_patch["last_input_videos"] = normalized_input_videos
            state_patch["last_input_video_count"] = len(normalized_input_videos)
        if artifacts:
            state_patch["referenced_artifact_ids"] = [
                str(artifact.get("artifact_id") or "")
                for artifact in artifacts
                if artifact.get("artifact_id")
            ]
        elif artifact_reference.get("artifact_id"):
            state_patch["referenced_artifact_ids"] = [str(artifact_reference.get("artifact_id") or "")]
        if artifact_reference:
            next_reference = dict(artifact_reference)
            if artifacts:
                active_reference = self._pick_active_artifact(
                    artifacts=list(artifacts or []),
                    artifact_reference=artifact_reference,
                )
                next_reference = {
                    **next_reference,
                    "artifact_id": str(active_reference.get("artifact_id") or next_reference.get("artifact_id") or ""),
                    "artifact_type": str(active_reference.get("artifact_type") or next_reference.get("artifact_type") or ""),
                    "title": active_reference.get("title") or next_reference.get("title"),
                    "version_id": str((active_reference.get("version") or {}).get("version_id") or next_reference.get("version_id") or "") or None,
                    "source_conversation_id": str(next_reference.get("source_conversation_id") or conversation_id or "") or None,
                    "source_course_id": str(next_reference.get("source_course_id") or getattr(request, "course_id", None) or "") or None,
                }
            state_patch["artifact_reference"] = next_reference
        if conversation_reference:
            state_patch["conversation_reference"] = dict(conversation_reference)
        extraction_patch, enhancement_observation = self.build_memory_state_patch_with_observation(
            conversation_id=conversation_id,
            request=request,
            result=result,
            existing_state=existing_state,
            recent_messages=recent_messages,
        )
        state_patch.update(extraction_patch)
        if self.enhancement_trace_enabled:
            state_patch["llm_enhancement_trace"] = enhancement_observation
            trace = dict(result.get("trace") or {})
            trace["llm_enhancement"] = enhancement_observation
            result["trace"] = trace

        if state_patch:
            self.storage.update_state(conversation_id, state_patch)

    def write_v2_poll_result(self, conversation_id: str, request, result: dict):
        self.write_v2_result(
            conversation_id,
            request,
            result,
            append_user_message=False,
        )
