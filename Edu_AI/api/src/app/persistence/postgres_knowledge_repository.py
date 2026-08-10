from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine

from app.database import (
    KnowledgeDocument,
    KnowledgeGraphVersion,
    KnowledgeLibrary,
    RuntimeIndexEntry,
    database_session,
)

from .postgres_repositories import _timestamp


class PostgresKnowledgeRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    @staticmethod
    def _ensure_library(session, library_id: str, entries=None) -> None:
        library = session.get(KnowledgeLibrary, library_id)
        if library is None:
            first = dict((entries or [{}])[0]) if entries else {}
            library = KnowledgeLibrary(
                library_id=library_id,
                library_type=str(first.get("library_type") or "course"),
                course_id=(
                    str(first.get("course_id") or library_id)
                    if str(first.get("library_type") or "course") != "personal"
                    else str(first.get("course_id") or "").strip() or None
                ),
                owner_user_id=str(first.get("owner_user_id") or "").strip() or None,
                metadata_payload={},
            )
            session.add(library)

    def replace_documents(
        self, library_id: str, documents: list[Mapping[str, Any]]
    ) -> None:
        normalized_library_id = str(library_id or "").strip()
        if not normalized_library_id:
            raise ValueError("library_id is required")
        payloads = [dict(item) for item in documents]
        with database_session(engine=self._engine) as session:
            self._ensure_library(session, normalized_library_id, payloads)
            session.execute(
                delete(KnowledgeDocument).where(
                    KnowledgeDocument.library_id == normalized_library_id
                )
            )
            for position, payload in enumerate(payloads):
                document_id = str(
                    payload.get("id")
                    or payload.get("document_id")
                    or hashlib.sha256(
                        str(payload.get("path") or position).encode("utf-8")
                    ).hexdigest()[:24]
                )
                created = payload.get("uploaded_at") or payload.get("created_at")
                session.add(
                    KnowledgeDocument(
                        library_id=normalized_library_id,
                        document_id=document_id,
                        filename=str(payload.get("filename") or payload.get("file_name") or ""),
                        path=str(payload.get("path") or payload.get("physical_path") or "").strip() or None,
                        content_hash=str(payload.get("hash") or payload.get("content_hash") or "").strip() or None,
                        scope_type=str(payload.get("scope_type") or "course"),
                        scope_id=str(payload.get("scope_id") or "").strip() or None,
                        status=str(payload.get("status") or "ready"),
                        created_at=_timestamp(created),
                        updated_at=_timestamp(payload.get("updated_at") or created),
                        raw_payload=payload,
                    )
                )

    def list_documents(self, library_id: str) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.library_id == library_id)
                .order_by(KnowledgeDocument.created_at, KnowledgeDocument.document_id)
            ).all()
            return [dict(record.raw_payload or {}) for record in records]

    def upsert_graph(self, library_id: str, graph: Mapping[str, Any]) -> None:
        with database_session(engine=self._engine) as session:
            self._ensure_library(session, library_id)
            current = session.scalar(
                select(func.max(KnowledgeGraphVersion.version)).where(
                    KnowledgeGraphVersion.library_id == library_id
                )
            )
            session.add(
                KnowledgeGraphVersion(
                    library_id=library_id,
                    version=int(current or 0) + 1,
                    graph_payload=dict(graph),
                )
            )

    def get_graph(self, library_id: str) -> dict[str, Any] | None:
        with database_session(engine=self._engine) as session:
            record = session.scalar(
                select(KnowledgeGraphVersion)
                .where(KnowledgeGraphVersion.library_id == library_id)
                .order_by(KnowledgeGraphVersion.version.desc())
                .limit(1)
            )
            return dict(record.graph_payload) if record is not None else None

    def replace_runtime_index(
        self, index_name: str, entries: Mapping[str, Mapping[str, Any]]
    ) -> None:
        normalized_name = str(index_name or "").strip()
        with database_session(engine=self._engine) as session:
            session.execute(
                delete(RuntimeIndexEntry).where(
                    RuntimeIndexEntry.index_name == normalized_name
                )
            )
            for entry_key, source in entries.items():
                payload = dict(source or {})
                session.add(
                    RuntimeIndexEntry(
                        index_name=normalized_name,
                        entry_key=str(entry_key),
                        owner_user_id=str(payload.get("owner") or payload.get("owner_user_id") or "").strip() or None,
                        content_hash=str(payload.get("hash") or payload.get("content_hash") or "").strip() or None,
                        payload=payload,
                    )
                )

    def load_runtime_index(self, index_name: str) -> dict[str, dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(RuntimeIndexEntry)
                .where(RuntimeIndexEntry.index_name == index_name)
                .order_by(RuntimeIndexEntry.entry_key)
            ).all()
            return {record.entry_key: dict(record.payload or {}) for record in records}
