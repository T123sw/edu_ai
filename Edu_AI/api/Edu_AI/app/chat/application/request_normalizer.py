from __future__ import annotations

from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.contracts import ChatRequestV2


def normalize_chat_request(payload) -> ChatRequestV2:
    allow_rag = getattr(payload, "allow_rag", None)
    if allow_rag is None:
        allow_rag = bool(getattr(payload, "use_rag", False))

    allow_web = bool(getattr(payload, "allow_web", False))

    return ChatRequestV2(
        question=payload.question,
        conversation_id=getattr(payload, "conversation_id", None),
        owner=getattr(payload, "owner", None),
        model_id=getattr(payload, "model_id", None),
        course_id=getattr(payload, "course_id", None),
        artifact_id=getattr(payload, "artifact_id", None),
        artifact_reference=getattr(payload, "artifact_reference", None),
        conversation_reference=getattr(payload, "conversation_reference", None),
        action_hint=getattr(payload, "action_hint", None),
        input_images=list(getattr(payload, "input_images", None) or []),
        input_videos=list(getattr(payload, "input_videos", None) or []),
        capability=CapabilityPolicy(
            allow_rag=bool(allow_rag),
            allow_web=allow_web,
            allow_tools=bool(allow_rag or allow_web),
            selected_doc_ids=list(getattr(payload, "selected_doc_ids", None) or []),
        ),
    )
