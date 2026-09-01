from __future__ import annotations

import time

from app.chat.domain.artifact_ref import ArtifactRef
from app.chat.domain.conversation_snapshot import ConversationSnapshot
from app.chat.domain.workflow_state import WorkflowState
from app.chat.persistence.conversation_store_adapter import ConversationStoreAdapter


class ContextBuilder:
    def __init__(
        self,
        *,
        conversation_store=None,
        memory_reader=None,
        learning_context_reader=None,
    ):
        self.conversation_store = conversation_store or ConversationStoreAdapter()
        self.memory_reader = memory_reader
        self.learning_context_reader = learning_context_reader

    def _read_learning_context(self, request) -> dict:
        if (
            self.learning_context_reader is None
            or not getattr(request, "owner", None)
            or not getattr(request, "course_id", None)
        ):
            return {}
        try:
            return dict(
                self.learning_context_reader.read(
                    user_id=request.owner,
                    course_id=request.course_id,
                    actor_role=getattr(request, "actor_role", "teacher"),
                )
                or {}
            )
        except Exception:
            # Learning telemetry must never make the chat path unavailable.
            return {}

    def _read_agent_memory_context(self, request) -> dict:
        if self.memory_reader is None or not getattr(request, "owner", None):
            return {}
        read_for_agent = getattr(self.memory_reader, "read_for_agent", None)
        if not callable(read_for_agent):
            return {}
        try:
            context = read_for_agent(
                actor={
                    "user_id": request.owner,
                    "role": getattr(request, "actor_role", "teacher"),
                },
                conversation_id=getattr(request, "conversation_id", None) or "",
                course_id=getattr(request, "course_id", None),
                task_id=None,
                query=str(getattr(request, "question", "") or ""),
                token_budget=1500,
            )
            return context.model_dump(mode="json") if hasattr(context, "model_dump") else dict(context or {})
        except Exception:
            return {"retrieval_notes": ["agent_memory_read_failed"]}

    @staticmethod
    def _normalize_conversation_reference(value) -> dict:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            return dict(value.model_dump(exclude_none=True))
        if isinstance(value, dict):
            return dict(value)
        return {}

    @staticmethod
    def _extract_summary_from_state(state: dict) -> str:
        return str(((state.get("conversation_summary") or {}).get("summary_text")) or "").strip()

    @staticmethod
    def _build_reference_message(*, title: str, summary: str, recent_messages: list[dict]) -> dict | None:
        parts: list[str] = []
        label = f"《{title}》" if title else "该历史对话"
        if summary:
            parts.append(f"你当前引用了历史对话{label}。参考对话摘要：{summary}")

        excerpt_lines: list[str] = []
        for message in list(recent_messages or [])[-4:]:
            role = "用户" if str(message.get("role") or "").strip() == "user" else "助手"
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            excerpt_lines.append(f"- {role}：{content}")
        if excerpt_lines:
            parts.append(f"{label}最近消息摘录：\n" + "\n".join(excerpt_lines))

        if not parts:
            return None
        return {"role": "system", "content": "\n\n".join(parts)}

    def build(self, request) -> ConversationSnapshot:
        learning_context = self._read_learning_context(request)
        agent_memory_context = self._read_agent_memory_context(request)
        if not request.conversation_id:
            summary = ""
            if self.memory_reader and request.owner:
                memory = self.memory_reader.read(user_id=request.owner, conversation_id=None) or {}
                summary = str(memory.get("summary") or "")
            return ConversationSnapshot(
                conversation_id="",
                summary=summary,
                learning_context=learning_context,
                agent_memory_context=agent_memory_context,
                capability=request.capability,
            )

        t_ctx = time.perf_counter()
        raw_snapshot = self.conversation_store.load_snapshot(request.conversation_id)
        state = raw_snapshot.get("state") or {}
        print(f"[CTX] context 加载 {(time.perf_counter() - t_ctx) * 1000:.0f}ms | cid={str(request.conversation_id or '')[-8:]}", flush=True)
        workflow_state = None
        if state.get("workflow_state"):
            workflow_state = WorkflowState.model_validate(
                {
                    "workflow_id": str(state["workflow_state"].get("workflow_id") or ""),
                    "workflow_type": str(state["workflow_state"].get("workflow_type") or ""),
                    "status": str(state["workflow_state"].get("status") or "running"),
                    "stage": str(state["workflow_state"].get("stage") or "collecting"),
                    "required_slots": list(state["workflow_state"].get("required_slots") or []),
                    "filled_slots": dict(state["workflow_state"].get("filled_slots") or {}),
                    "artifacts": list(state["workflow_state"].get("artifacts") or []),
                    "resume_token": str(state["workflow_state"].get("resume_token") or ""),
                }
            )

        summary = ""
        if self.memory_reader and request.owner:
            memory = self.memory_reader.read(
                user_id=request.owner,
                conversation_id=request.conversation_id,
            ) or {}
            summary = str(memory.get("summary") or "")
        summary = str(((state.get("conversation_summary") or {}).get("summary_text")) or summary or "")
        conversation_memory = dict(state.get("conversation_memory") or {})
        active_context = dict(state.get("active_context") or {})
        referenced_artifact_ids = list(
            state.get("referenced_artifact_ids")
            or conversation_memory.get("referenced_artifact_ids")
            or []
        )

        active_artifact = None
        if state.get("active_artifact"):
            active_artifact = ArtifactRef.model_validate(
                {
                    "artifact_id": str(state["active_artifact"].get("artifact_id") or ""),
                    "artifact_type": str(state["active_artifact"].get("artifact_type") or ""),
                    "title": state["active_artifact"].get("title"),
                }
            )

        recent_messages = list(raw_snapshot.get("messages") or [])
        conversation_reference = self._normalize_conversation_reference(
            getattr(request, "conversation_reference", None)
        )
        referenced_conversation_id = str(conversation_reference.get("conversation_id") or "").strip()
        if referenced_conversation_id and referenced_conversation_id != (request.conversation_id or ""):
            referenced_detail = self.conversation_store.load_conversation_detail(
                referenced_conversation_id,
                owner=getattr(request, "owner", None),
            )
            referenced_state = dict((referenced_detail or {}).get("state") or {})
            referenced_messages = list((referenced_detail or {}).get("history") or [])
            referenced_summary = self._extract_summary_from_state(referenced_state)
            referenced_title = str(conversation_reference.get("title") or (referenced_detail or {}).get("title") or "").strip()
            reference_message = self._build_reference_message(
                title=referenced_title,
                summary=referenced_summary,
                recent_messages=referenced_messages,
            )
            if reference_message is not None:
                recent_messages = [reference_message, *recent_messages]
            if referenced_summary:
                summary = (
                    f"{summary}\n参考对话摘要：{referenced_summary}"
                    if summary
                    else f"参考对话摘要：{referenced_summary}"
                )
            active_context = {
                **active_context,
                "referenced_conversation_id": referenced_conversation_id,
                "referenced_conversation_title": referenced_title or None,
            }

        return ConversationSnapshot(
            conversation_id=request.conversation_id or "",
            recent_messages=recent_messages,
            summary=summary,
            conversation_memory=conversation_memory,
            active_context=active_context,
            learning_context=learning_context,
            agent_memory_context=agent_memory_context,
            referenced_artifact_ids=referenced_artifact_ids,
            active_task=state.get("active_task"),
            active_artifact=active_artifact,
            workflow_state=workflow_state,
            capability=request.capability,
        )
