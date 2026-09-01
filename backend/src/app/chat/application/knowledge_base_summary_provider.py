from __future__ import annotations

from typing import Any

from modules.rag_v2.api import get_rag_system
from modules.rag_v2.document_resolver import resolve_rag_document


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

    def get_resolved_document_summaries(
        self,
        *,
        rag_index_keys: list[str],
    ) -> dict[str, Any]:
        """Read summaries by canonical RAG key without public-ID resolution."""
        rag_system = self._rag_system_factory()
        documents: list[dict[str, Any]] = []
        timestamps: list[str] = []
        for rag_index_key in list(rag_index_keys or []):
            normalized_key = str(rag_index_key or "").strip()
            if not normalized_key:
                continue
            record = dict(
                getattr(rag_system, "document_index", {}).get(normalized_key)
                or {}
            )
            if not record:
                continue
            summary = str(record.get("summary") or "").strip()
            updated_at = str(record.get("summary_updated_at") or "").strip()
            if not summary:
                try:
                    generated = rag_system.summarize_document(
                        normalized_key,
                        force_refresh=False,
                        owner=record.get("owner"),
                    )
                except Exception:
                    generated = {}
                summary = str((generated or {}).get("summary") or "").strip()
                updated_at = str(
                    (generated or {}).get("summary_updated_at") or ""
                ).strip()
            if not summary:
                continue
            documents.append(
                {
                    "rag_index_key": normalized_key,
                    "title": str(record.get("file_name") or normalized_key),
                    "summary": summary,
                    "summary_updated_at": updated_at or None,
                }
            )
            if updated_at:
                timestamps.append(updated_at)
        return {
            "documents": documents,
            "summary_updated_at_snapshot": sorted(timestamps),
            "fallback_used": len(documents) == 0,
        }

    def get_document_image_sources(
        self,
        *,
        selected_doc_ids: list[str],
        owner: str | None,
        query_text: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Query RAG for image-type chunks from the selected documents.

        Returns a list of dicts with keys: modality, image_url, content.
        Returns empty list on any error (non-fatal).
        """
        from modules.rag_v2.rag_main.api import _get_server_url, _scrub_response_sources

        if not selected_doc_ids or not query_text:
            return []
        try:
            rag_system = self._rag_system_factory()
            result = rag_system.query(
                query_text,
                top_k=top_k,
                use_rag=True,
                selected_doc_ids=list(selected_doc_ids),
                owner=owner,
            )
            raw_sources = list((result or {}).get("sources") or [])
            safe_sources = _scrub_response_sources(raw_sources, _get_server_url())
            image_sources: list[dict[str, Any]] = []
            for src in safe_sources:
                metadata = dict((src or {}).get("metadata") or {})
                modality = str(metadata.get("modality") or "").strip().lower()
                image_url = str(metadata.get("image_url") or "").strip()
                if modality == "image" and image_url:
                    image_sources.append({
                        "modality": "image",
                        "image_url": image_url,
                        "content": str((src or {}).get("content") or "").strip(),
                    })
            return image_sources
        except Exception:
            return []
