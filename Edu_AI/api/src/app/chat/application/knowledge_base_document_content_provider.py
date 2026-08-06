from __future__ import annotations

from typing import Any

from modules.rag_v2.api import get_rag_system
from modules.rag_v2.document_resolver import resolve_rag_document


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

        resolved_documents: list[dict[str, Any]] = []
        content_timestamps: list[str] = []
        total_chars = 0
        truncated = False

        for doc_id in list(selected_doc_ids or []):
            normalized_doc_id = str(doc_id or "").strip()
            if not normalized_doc_id or total_chars >= self.max_total_chars:
                continue

            resolved = resolve_rag_document(rag_system, normalized_doc_id, owner=owner)
            if resolved is None:
                continue

            listed_record = dict(resolved.listed_document or {})
            index_record = dict(resolved.record or {})
            documents = list(rag_system.vector_store.get_documents_by_source(resolved.source_key) or [])
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

            title = str(listed_record.get("file_name") or index_record.get("file_name") or resolved.file_name).strip()
            summary = str(listed_record.get("summary") or index_record.get("summary") or "").strip()
            content_updated_at = str(
                listed_record.get("summary_updated_at")
                or listed_record.get("imported_at")
                or index_record.get("imported_at")
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

    def get_resolved_document_contents(
        self,
        *,
        rag_index_keys: list[str],
    ) -> dict[str, Any]:
        """Read already-authorized RAG keys without resolving public IDs again."""
        rag_system = self._rag_system_factory()
        resolved_documents: list[dict[str, Any]] = []
        content_timestamps: list[str] = []
        total_chars = 0
        truncated = False
        for rag_index_key in list(rag_index_keys or []):
            normalized_key = str(rag_index_key or "").strip()
            if not normalized_key or total_chars >= self.max_total_chars:
                continue
            record = dict(
                getattr(rag_system, "document_index", {}).get(normalized_key)
                or {}
            )
            if not record:
                continue
            source_key = str(record.get("source_key") or normalized_key)
            documents = list(
                rag_system.vector_store.get_documents_by_source(source_key) or []
            )
            documents.sort(
                key=lambda item: int((item.get("metadata") or {}).get("page", 0))
            )
            full_content = "\n\n".join(
                str(item.get("content") or "").strip()
                for item in documents
                if str(item.get("content") or "").strip()
            )
            if not full_content:
                continue
            limited_content = full_content[: self.max_chars_per_doc].rstrip()
            truncated = truncated or len(full_content) > len(limited_content)
            remaining_chars = self.max_total_chars - total_chars
            if len(limited_content) > remaining_chars:
                limited_content = limited_content[:remaining_chars].rstrip()
                truncated = True
            updated_at = str(
                record.get("summary_updated_at")
                or record.get("imported_at")
                or ""
            ).strip()
            resolved_documents.append(
                {
                    "rag_index_key": normalized_key,
                    "title": str(record.get("file_name") or normalized_key),
                    "summary": str(record.get("summary") or ""),
                    "content": limited_content,
                    "content_updated_at": updated_at or None,
                }
            )
            if updated_at:
                content_timestamps.append(updated_at)
            total_chars += len(limited_content)
        return {
            "documents": resolved_documents,
            "content_updated_at_snapshot": sorted(content_timestamps),
            "fallback_used": len(resolved_documents) == 0,
            "truncated": truncated,
        }
