"""Shared helpers for resolving public RAG document identifiers.

Callers may still pass legacy physical paths while newer APIs expose index keys.
This module centralizes that compatibility logic so business code does not need
to inspect ``document_index`` directly in multiple slightly different ways.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class ResolvedRAGDocument:
    requested_id: str
    index_key: str
    record: Mapping[str, Any]
    physical_path: str
    source_key: str
    file_name: str
    listed_document: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class LoadedRAGDocumentContent:
    requested_id: str
    index_key: str
    physical_path: str
    source_key: str
    file_name: str
    content: str
    resolved_document: ResolvedRAGDocument


def _normalize_identifier(value: Any) -> str:
    return str(value or "").strip()


def _append_unique(candidates: list[str], value: Any) -> None:
    normalized = _normalize_identifier(value)
    if normalized and normalized not in candidates:
        candidates.append(normalized)


def _normalize_path_for_compare(value: Any) -> str:
    return str(value or "").replace("\\", "/").lower().strip()


def _basename_for_compare(value: Any) -> str:
    normalized = _normalize_path_for_compare(value)
    if not normalized:
        return ""
    return normalized.rsplit("/", 1)[-1]


def _owner_matches(record: Mapping[str, Any], owner: Optional[str]) -> bool:
    if owner is None:
        return True

    record_owner = record.get("owner")
    if record_owner is None:
        return True

    if isinstance(record_owner, str) and not record_owner.strip():
        return True

    return record_owner == owner


def find_rag_record_for_legacy_identifiers(
    document_index: Mapping[str, Any],
    identifiers: list[Any],
    *,
    owner: Optional[str] = None,
    allow_basename_fallback: bool = True,
) -> tuple[str, Mapping[str, Any]] | None:
    """Find one unambiguous RAG record for old path-based identifiers."""
    normalized = {
        _normalize_path_for_compare(item)
        for item in identifiers
        if _normalize_identifier(item)
    }
    basenames = {_basename_for_compare(item) for item in identifiers}
    basenames.discard("")
    exact: list[tuple[str, Mapping[str, Any]]] = []
    basename_matches: list[tuple[str, Mapping[str, Any]]] = []
    for index_key, value in (document_index or {}).items():
        if not isinstance(value, Mapping) or not _owner_matches(value, owner):
            continue
        record_identifiers = (
            index_key,
            value.get("physical_path"),
            value.get("path"),
            value.get("course_document_id"),
        )
        record_paths = {
            _normalize_path_for_compare(item)
            for item in record_identifiers
            if _normalize_identifier(item)
        }
        match = (str(index_key), value)
        if normalized & record_paths:
            exact.append(match)
            continue
        record_basenames = {
            _basename_for_compare(item)
            for item in (*record_identifiers, value.get("file_name"))
        }
        record_basenames.discard("")
        if allow_basename_fallback and basenames & record_basenames:
            basename_matches.append(match)
    if len(exact) == 1:
        return exact[0]
    if not exact and len(basename_matches) == 1:
        return basename_matches[0]
    return None


def _make_key(rag_system: Any, method_name: str, document_id: str, owner: Optional[str]) -> str | None:
    method = getattr(rag_system, method_name, None)
    if method is None:
        return None
    try:
        return _normalize_identifier(method(document_id, owner))
    except Exception:
        return None


def _listed_documents_by_id(rag_system: Any, owner: Optional[str]) -> dict[str, Mapping[str, Any]]:
    try:
        listed_documents = rag_system.list_documents(owner=owner) or []
    except Exception:
        return {}

    by_id: dict[str, Mapping[str, Any]] = {}
    for item in listed_documents:
        if not isinstance(item, Mapping):
            continue
        file_path = _normalize_identifier(item.get("file_path"))
        if file_path:
            by_id[file_path] = item
    return by_id


def resolve_rag_document(rag_system: Any, document_id: Any, owner: Optional[str] = None) -> ResolvedRAGDocument | None:
    requested_id = _normalize_identifier(document_id)
    if not requested_id:
        return None

    document_index = getattr(rag_system, "document_index", {}) or {}
    if not isinstance(document_index, Mapping):
        return None

    listed_by_id = _listed_documents_by_id(rag_system, owner)
    candidates: list[str] = []
    _append_unique(candidates, requested_id)
    _append_unique(candidates, _make_key(rag_system, "_make_index_key", requested_id, owner))

    for candidate in candidates:
        record = document_index.get(candidate)
        if isinstance(record, Mapping) and _owner_matches(record, owner):
            return _build_resolved_document(
                rag_system=rag_system,
                requested_id=requested_id,
                index_key=candidate,
                record=record,
                owner=owner,
                listed_document=listed_by_id.get(candidate),
            )

    requested_norm = _normalize_path_for_compare(requested_id)
    requested_basename = _basename_for_compare(requested_id)
    allow_basename_fallback = bool(
        requested_basename
        and not requested_norm.startswith("user_")
        and ":" not in requested_norm
    )
    legacy_identifiers = [requested_id]
    legacy_match = find_rag_record_for_legacy_identifiers(
        document_index,
        legacy_identifiers,
        owner=owner,
        allow_basename_fallback=allow_basename_fallback,
    )
    if legacy_match is not None and (
        requested_norm or (allow_basename_fallback and requested_basename)
    ):
        index_key, record = legacy_match
        return _build_resolved_document(
            rag_system=rag_system,
            requested_id=requested_id,
            index_key=index_key,
            record=record,
            owner=owner,
            listed_document=listed_by_id.get(index_key),
        )

    return None


def resolve_rag_document_ids(
    rag_system: Any,
    document_ids: list[Any],
    owner: Optional[str] = None,
) -> list[str]:
    """Resolve external document identifiers to public RAG v2 index keys only."""

    resolved_ids: list[str] = []
    seen: set[str] = set()

    for document_id in document_ids or []:
        resolved = resolve_rag_document(rag_system, document_id, owner=owner)
        if resolved is None or resolved.index_key in seen:
            continue
        seen.add(resolved.index_key)
        resolved_ids.append(resolved.index_key)

    return resolved_ids


def _build_resolved_document(
    *,
    rag_system: Any,
    requested_id: str,
    index_key: str,
    record: Mapping[str, Any],
    owner: Optional[str],
    listed_document: Mapping[str, Any] | None,
) -> ResolvedRAGDocument:
    physical_path = _normalize_identifier(record.get("physical_path")) or index_key
    source_key = _normalize_identifier(record.get("source_key"))
    if not source_key:
        source_key = _make_key(rag_system, "_make_source_key", physical_path, owner) or index_key

    file_name = _normalize_identifier(
        (listed_document or {}).get("file_name")
        or record.get("file_name")
        or Path(physical_path).name
        or index_key
    )

    return ResolvedRAGDocument(
        requested_id=requested_id,
        index_key=index_key,
        record=record,
        physical_path=physical_path,
        source_key=source_key,
        file_name=file_name,
        listed_document=listed_document,
    )


def load_rag_document_content(rag_system: Any, document_id: Any, owner: Optional[str] = None) -> LoadedRAGDocumentContent | None:
    resolved = resolve_rag_document(rag_system, document_id, owner=owner)
    if resolved is None:
        return None

    file_path = Path(resolved.physical_path)
    if not file_path.exists() or not file_path.is_file():
        return None

    processor = getattr(rag_system, "document_processor", None)
    if processor is None:
        return None

    file_ext = file_path.suffix.lower()
    if file_ext == ".pdf":
        documents = list(processor.load_pdf(str(file_path)) or [])
        documents.sort(key=lambda item: int(getattr(item, "metadata", {}).get("page", 0)))
    elif file_ext in {".doc", ".docx"}:
        documents = list(processor.load_doc(str(file_path)) or [])
    elif file_ext in {".txt", ".md", ".markdown"}:
        documents = list(processor.load_text_like(str(file_path)) or [])
    else:
        return None

    content = "\n\n".join(
        str(getattr(document, "page_content", "") or "").strip()
        for document in documents
        if str(getattr(document, "page_content", "") or "").strip()
    )
    if not content:
        return None

    return LoadedRAGDocumentContent(
        requested_id=resolved.requested_id,
        index_key=resolved.index_key,
        physical_path=resolved.physical_path,
        source_key=resolved.source_key,
        file_name=resolved.file_name,
        content=content,
        resolved_document=resolved,
    )
