"""RAG integration — document loading and ID resolution.

All RAG system access goes through here so business layers don't
directly inspect rag_v2 internals.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.course_storage import storage_manager

from modules.rag_v2.document_resolver import load_rag_document_content, resolve_rag_document_ids


def load_selected_rag_documents(
    rag_system: Any,
    selected_doc_ids: List[str],
    *,
    owner: str,
    log_prefix: str,
) -> List[Dict[str, str]]:
    """Load full document content for a list of document IDs via the RAG resolver."""
    documents_content: List[Dict[str, str]] = []
    print(f"[{log_prefix}] 开始通过 rag_v2 resolver 处理 {len(selected_doc_ids)} 个选中文档")

    for doc_id in selected_doc_ids:
        try:
            loaded_document = load_rag_document_content(rag_system, doc_id, owner=owner)
            if loaded_document is None:
                print(f"[{log_prefix}] 文档未通过 rag_v2 resolver 加载: {doc_id}")
                continue
            documents_content.append(
                {"file_name": loaded_document.file_name, "content": loaded_document.content}
            )
            print(
                f"[{log_prefix}] rag_v2 resolver 已加载文档 {loaded_document.file_name}，"
                f"内容长度: {len(loaded_document.content)} 字符"
            )
        except Exception as exc:
            print(f"[{log_prefix}] 通过 rag_v2 resolver 获取文档 {doc_id} 内容失败: {exc}")
            continue

    return documents_content


def resolve_selected_doc_ids_for_query(
    rag_system: Any,
    selected_doc_ids: Optional[List[str]],
    *,
    owner: str,
    course_id: Optional[str] = None,
) -> Optional[List[str]]:
    """Resolve public course-document aliases to RAG index keys.

    The teacher UI may submit a stable ``doc-v2-*`` ID, a source URL, a
    course-relative path, or the RAG index key itself.  Only the final form is
    accepted by the vector-store filter, so translate all known aliases before
    querying while retaining the old safe fallback for unknown identifiers.
    """
    candidates: List[str] = []
    seen_candidates: set[str] = set()

    def append(value: Any) -> None:
        normalized = str(value or "").strip()
        if normalized and normalized not in seen_candidates:
            seen_candidates.add(normalized)
            candidates.append(normalized)

    requested_doc_ids = list(selected_doc_ids or [])
    selected = {str(value or "").strip() for value in requested_doc_ids if str(value or "").strip()}
    for value in requested_doc_ids:
        append(value)

    if course_id:
        for document in storage_manager.get_knowledge_base_index(str(course_id)):
            if not requested_doc_ids:
                if str(document.get("library_type") or "course").strip().lower() != "course":
                    continue
                if str(document.get("status") or "ready").strip().lower() not in {"ready", "partially_ready"}:
                    continue
            aliases = {
                str(document.get(key) or "").strip()
                for key in ("id", "source_url", "path", "filename", "rag_index_key")
            }
            aliases.discard("")
            if requested_doc_ids and not selected.intersection(aliases):
                continue
            for key in ("rag_index_key", "id", "path", "filename", "source_url"):
                append(document.get(key))

    if not candidates:
        # RAG treats an empty selection as "search every accessible document".
        # For an empty course this sentinel deliberately resolves to no source,
        # preventing an automatic course query from leaking into personal data.
        return ["__edu_ai_no_authorized_document__"] if course_id else selected_doc_ids

    resolved_ids = resolve_rag_document_ids(rag_system, candidates, owner=owner)
    return resolved_ids or candidates
