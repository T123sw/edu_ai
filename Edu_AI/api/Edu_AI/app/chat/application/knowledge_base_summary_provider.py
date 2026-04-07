from __future__ import annotations

from pathlib import Path
from typing import Any

from new_rag.api import get_rag_system


class KnowledgeBaseSummaryProvider:
    def __init__(self, *, rag_system_factory=get_rag_system):
        self._rag_system_factory = rag_system_factory

    def get_selected_document_summaries(self, *, selected_doc_ids: list[str], owner: str | None) -> dict[str, Any]:
        rag_system = self._rag_system_factory()
        listed_documents = list(rag_system.list_documents(owner=owner) or [])
        documents_by_id = {
            str(item.get("file_path") or "").strip(): item
            for item in listed_documents
            if str(item.get("file_path") or "").strip()
        }

        resolved_documents: list[dict[str, Any]] = []
        summary_timestamps: list[str] = []

        for doc_id in list(selected_doc_ids or []):
            normalized_doc_id = str(doc_id or "").strip()
            if not normalized_doc_id:
                continue

            record = documents_by_id.get(normalized_doc_id)
            summary_text = str((record or {}).get("summary") or "").strip()
            summary_updated_at = str((record or {}).get("summary_updated_at") or "").strip()

            if not summary_text:
                try:
                    generated = rag_system.summarize_document(
                        normalized_doc_id,
                        force_refresh=False,
                        owner=owner,
                    )
                except Exception:
                    generated = {}
                summary_text = str((generated or {}).get("summary") or "").strip()
                summary_updated_at = str((generated or {}).get("summary_updated_at") or "").strip()

            if not summary_text:
                continue

            title = str((record or {}).get("file_name") or Path(normalized_doc_id).name or normalized_doc_id).strip()
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
