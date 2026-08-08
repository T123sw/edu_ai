from __future__ import annotations

from app.chat.domain.capability_policy import CapabilityPolicy
from app.chat.domain.contracts import ChatRequestV2


def normalize_chat_request(payload) -> ChatRequestV2:
    selected_doc_ids = list(getattr(payload, "selected_doc_ids", None) or [])
    allow_rag = getattr(payload, "allow_rag", None)
    if allow_rag is None:
        allow_rag = bool(getattr(payload, "use_rag", False))
    if not allow_rag and selected_doc_ids:
        allow_rag = True
    requested_source_mode = getattr(payload, "source_mode", None)
    if requested_source_mode in {"course_auto", "selected_documents", "none"}:
        source_mode = requested_source_mode
    elif selected_doc_ids:
        source_mode = "selected_documents"
    elif allow_rag:
        source_mode = "course_auto"
    else:
        source_mode = "none"

    if source_mode == "selected_documents":
        allow_rag = True
    elif source_mode == "course_auto":
        allow_rag = True
        selected_doc_ids = []
    else:
        allow_rag = False
        selected_doc_ids = []

    allow_web = bool(getattr(payload, "allow_web", False))
    # Phase 6-A.2 (decoupling fix): image_search is a separate capability from
    # web_search. It runs against the configured image provider.
    # cost/privacy concern in keeping it always-on, and tying it to allow_web
    # caused silent failures when users explicitly asked for visuals but
    # hadn't enabled Web search. The planner still gates actual usage by
    # detecting visual keywords in the question.
    explicit_image_search = getattr(payload, "allow_image_search", None)
    allow_image_search = True if explicit_image_search is None else bool(explicit_image_search)

    return ChatRequestV2(
        question=payload.question,
        conversation_id=getattr(payload, "conversation_id", None),
        owner=getattr(payload, "owner", None),
        model_id=getattr(payload, "model_id", None),
        course_id=getattr(payload, "course_id", None),
        scope_type=getattr(payload, "scope_type", None),
        scope_id=getattr(payload, "scope_id", None),
        artifact_id=getattr(payload, "artifact_id", None),
        artifact_reference=getattr(payload, "artifact_reference", None),
        conversation_reference=getattr(payload, "conversation_reference", None),
        action_hint=getattr(payload, "action_hint", None),
        input_images=list(getattr(payload, "input_images", None) or []),
        input_videos=list(getattr(payload, "input_videos", None) or []),
        capability=CapabilityPolicy(
            source_mode=source_mode,
            allow_rag=bool(allow_rag),
            allow_web=allow_web,
            allow_image_search=allow_image_search,
            allow_tools=bool(allow_rag or allow_web or allow_image_search),
            selected_doc_ids=selected_doc_ids,
        ),
    )
