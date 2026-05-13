from __future__ import annotations

from types import SimpleNamespace


class CompatChatService:
    def __init__(self, delegate=None):
        self.delegate = delegate or self._default_delegate

    def _default_delegate(self, payload):
        return {
            "answer": "",
            "conversation_id": getattr(payload, "conversation_id", "") or "",
            "model_id": getattr(payload, "model_id", "") or "",
            "intent_category": "chat",
            "meta": {},
        }

    def _adapt_result(self, result: dict, payload) -> dict:
        if "answer" in result and "intent_category" in result:
            return result
        if "answer" in result:
            adapted = dict(result)
            adapted["intent_category"] = str(adapted.get("intent_category") or "chat")
            adapted["conversation_id"] = str(adapted.get("conversation_id") or getattr(payload, "conversation_id", "") or "")
            adapted["model_id"] = str(adapted.get("model_id") or getattr(payload, "model_id", "") or "")
            adapted["meta"] = adapted.get("meta") or {}
            return adapted

        action_name = str(((result.get("action") or {}).get("name")) or "chat.reply")
        if action_name.startswith("research"):
            intent_category = "research"
        elif action_name.startswith("generate"):
            intent_category = "generate_content"
        else:
            intent_category = "chat"

        return {
            "answer": str(((result.get("message") or {}).get("content")) or ""),
            "conversation_id": str(((result.get("conversation") or {}).get("conversation_id")) or getattr(payload, "conversation_id", "") or ""),
            "model_id": str(getattr(payload, "model_id", "") or ""),
            "intent_category": intent_category,
            "meta": {
                "artifacts": result.get("artifacts") or [],
                "workflow": result.get("workflow"),
                "sources": result.get("sources") or [],
                "trace": result.get("trace") or {},
            },
        }

    def chat(
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
        scope_type=None,
        scope_id=None,
        allow_web=False,
        action_hint=None,
        artifact_id=None,
    ):
        if allow_rag is None:
            allow_rag = bool(use_rag)
        payload = SimpleNamespace(
            question=question,
            conversation_id=conversation_id,
            model_id=model_id,
            use_rag=use_rag,
            allow_rag=allow_rag,
            allow_web=allow_web,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
            course_id=course_id,
            scope_type=scope_type,
            scope_id=scope_id,
            action_hint=action_hint,
            artifact_id=artifact_id,
        )
        result = self.delegate(payload)
        return self._adapt_result(result, payload)
