from __future__ import annotations

from typing import Any

from rag_v2.api import get_rag_system
from rag_v2.document_resolver import resolve_rag_document


class KnowledgeBaseSummaryProvider:
    def __init__(self, *, rag_system_factory=get_rag_system):
        self._rag_system_factory = rag_system_factory

    def get_selected_document_summaries(self, *, selected_doc_ids: list[str], owner: str | None) -> dict[str, Any]:
        rag_system = self._rag_system_factory()

        resolved_documents: list[dict[str, Any]] = []
        summary_timestamps: list[str] = []

        for doc_id in list(selected_doc_ids or []):
            normalized_doc_id = str(doc_id or "").strip()
            if not normalized_doc_id:
                continue

            resolved = resolve_rag_document(rag_system, normalized_doc_id, owner=owner)
            if resolved is None:
                continue

            public_record = dict(resolved.listed_document or {})
            index_record = dict(resolved.record or {})
            summary_text = str(public_record.get("summary") or index_record.get("summary") or "").strip()
            summary_updated_at = str(
                public_record.get("summary_updated_at") or index_record.get("summary_updated_at") or ""
            ).strip()

            if not summary_text:
                try:
                    summary_owner = index_record.get("owner")
                    generated = rag_system.summarize_document(
                        resolved.index_key,
                        force_refresh=False,
                        owner=summary_owner,
                    )
                except Exception:
                    generated = {}
                summary_text = str((generated or {}).get("summary") or "").strip()
                summary_updated_at = str((generated or {}).get("summary_updated_at") or "").strip()

            if not summary_text:
                continue

            title = str(public_record.get("file_name") or index_record.get("file_name") or resolved.file_name).strip()
            resolved_documents.append(
                {
                    "doc_id": normalized_doc_id,
                    "title": title,
                    "summary": summary_text,
                    "summary_updated_at": summary_updated_at or None,
                }
            )
            if summary_updated_at:
                summary_timestamps.append(summary_updated_at)

        return {
            "documents": resolved_documents,
            "summary_updated_at_snapshot": sorted(summary_timestamps),
            "fallback_used": len(resolved_documents) == 0,
        }
