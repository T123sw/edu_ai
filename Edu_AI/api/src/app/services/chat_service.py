"""Chat service — thin orchestration layer delegating to the chat/ subsystem."""

from __future__ import annotations

from datetime import datetime
from typing import List

from core import Config, conversation_storage


def chat(
    question: str,
    conversation_id: str | None,
    top_k: int,
    model_id: str | None,
    use_rag: bool,
    selected_doc_ids: List[str] | None,
    owner: str,
) -> dict:
    """Run a chat query through the RAG system and persist the conversation."""
    conversation_id = conversation_id or f"conv_{datetime.now().timestamp()}"
    conversation_storage.ensure_conversation(conversation_id, question)

    history_for_context = conversation_storage.get_messages(
        conversation_id, limit=Config.CHAT_HISTORY_WINDOW * 2
    )

    model_config = Config.get_llm_model(model_id or Config.DEFAULT_LLM_MODEL_ID)

    from app.dependencies import get_rag_system
    rag_system = get_rag_system()

    use_rag_flag = use_rag if use_rag is not None else True

    from app.integrations.rag_client import resolve_selected_doc_ids_for_query
    resolved_selected_doc_ids = resolve_selected_doc_ids_for_query(
        rag_system, selected_doc_ids, owner=owner,
    )

    result = rag_system.query(
        question,
        top_k=top_k,
        conversation_history=history_for_context,
        llm_config=model_config,
        use_rag=use_rag_flag,
        selected_doc_ids=resolved_selected_doc_ids,
        owner=owner,
    )

    sources = []
    for idx, source in enumerate(result.get("sources", []), start=1):
        sources.append(
            {
                "index": str(idx),
                "source": str(source.get("source", "unknown")),
                "source_path": source.get("source_path", ""),
                "page": str(source.get("page", "N/A")),
                "content": source.get("content", "")[:500],
            }
        )

    conversation_storage.append_message(
        conversation_id, role="user", content=question,
        timestamp=datetime.now().isoformat(),
    )
    conversation_storage.append_message(
        conversation_id, role="assistant", content=result.get("answer", ""),
        sources=result.get("sources"), timestamp=datetime.now().isoformat(),
    )

    conversation_meta = conversation_storage.get_conversation(conversation_id)

    return {
        "answer": result.get("answer", ""),
        "conversation_id": conversation_id,
        "sources": sources,
        "title": conversation_meta.get("title"),
        "model_id": model_config.get("id"),
    }
