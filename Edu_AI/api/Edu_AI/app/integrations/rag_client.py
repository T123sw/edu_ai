"""RAG integration — document loading and ID resolution.

All RAG system access goes through here so business layers don't
directly inspect rag_v2 internals.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rag_v2.document_resolver import load_rag_document_content, resolve_rag_document_ids


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
) -> Optional[List[str]]:
    """Resolve document IDs through the RAG resolver. Falls back to original IDs."""
    if not selected_doc_ids:
        return selected_doc_ids
    resolved_ids = resolve_rag_document_ids(rag_system, selected_doc_ids, owner=owner)
    return resolved_ids or selected_doc_ids
