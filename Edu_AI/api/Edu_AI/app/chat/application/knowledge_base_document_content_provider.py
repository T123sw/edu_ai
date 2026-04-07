from __future__ import annotations

from pathlib import Path
from typing import Any

from new_rag.api import get_rag_system


class KnowledgeBaseDocumentContentProvider:
    def __init__(
        self,
        *,
        rag_system_factory=get_rag_system,
        max_chars_per_doc: int = 12000,
        max_total_chars: int = 40000,
    ):
        self._rag_system_factory = rag_system_factory
        self.max_chars_per_doc = max_chars_per_doc
        self.max_total_chars = max_total_chars

    def get_selected_document_contents(self, *, selected_doc_ids: list[str], owner: str | None) -> dict[str, Any]:
        rag_system = self._rag_system_factory()
        listed_documents = list(rag_system.list_documents(owner=owner) or [])
        documents_by_id = {
            str(item.get("file_path") or "").strip(): item
            for item in listed_documents
            if str(item.get("file_path") or "").strip()
        }

        resolved_documents: list[dict[str, Any]] = []
        content_timestamps: list[str] = []
        total_chars = 0
        truncated = False

        for doc_id in list(selected_doc_ids or []):
            normalized_doc_id = str(doc_id or "").strip()
            if not normalized_doc_id or total_chars >= self.max_total_chars:
                continue

            listed_record = documents_by_id.get(normalized_doc_id) or {}
            index_key = rag_system._make_index_key(normalized_doc_id, owner)
            record = rag_system.document_index.get(index_key)
            if record is None:
                continue

            physical_path = str(record.get("physical_path") or normalized_doc_id).strip()
            source_key = record.get("source_key") or rag_system._make_source_key(physical_path, owner)
            documents = list(rag_system.vector_store.get_documents_by_source(source_key) or [])
            if not documents:
                continue

            documents.sort(key=lambda item: int((item.get("metadata") or {}).get("page", 0)))
            full_content = "\n\n".join(str(doc.get("content") or "").strip() for doc in documents if str(doc.get("content") or "").strip())
            if not full_content:
                continue

            limited_content = full_content
            if len(limited_content) > self.max_chars_per_doc:
                limited_content = limited_content[: self.max_chars_per_doc].rstrip() + "\n\n...（该文档内容过长，已按上限截断）"
                truncated = True

            remaining_chars = self.max_total_chars - total_chars
            if remaining_chars <= 0:
                break
            if len(limited_content) > remaining_chars:
                limited_content = limited_content[:remaining_chars].rstrip() + "\n\n...（本次报告上下文已达长度上限，后续内容已截断）"
                truncated = True

            title = str(listed_record.get("file_name") or Path(physical_path).name or normalized_doc_id).strip()
            summary = str(listed_record.get("summary") or "").strip()
            content_updated_at = str(
                listed_record.get("summary_updated_at")
                or listed_record.get("imported_at")
                or record.get("imported_at")
                or ""
            ).strip()

            resolved_documents.append(
                {
                    "doc_id": normalized_doc_id,
                    "title": title,
                    "summary": summary,
                    "content": limited_content,
                    "content_updated_at": content_updated_at or None,
                }
            )
            if content_updated_at:
                content_timestamps.append(content_updated_at)
            total_chars += len(limited_content)

        return {
            "documents": resolved_documents,
            "content_updated_at_snapshot": sorted(content_timestamps),
            "fallback_used": len(resolved_documents) == 0,
            "truncated": truncated,
        }
