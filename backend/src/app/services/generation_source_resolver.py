from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Literal, Protocol, Sequence

from app.services.generation_source_errors import GenerationSourceError


GenerationSourceMode = Literal[
    "course_auto", "selected_documents", "none"
]


@dataclass(frozen=True)
class ResolvedSourceDocument:
    document_id: str
    name: str
    rag_index_key: str
    chunk_count: int


@dataclass(frozen=True)
class SourceDocumentRecord:
    course_id: str
    document_id: str
    name: str
    status: str
    rag_index_key: str
    chunk_count: int


@dataclass(frozen=True)
class ResolvedGenerationSource:
    course_id: str
    mode: GenerationSourceMode
    requested_document_ids: tuple[str, ...]
    documents: tuple[ResolvedSourceDocument, ...]
    context_text: str
    resolved_at: str

    def to_snapshot(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "requested_document_ids": list(self.requested_document_ids),
            "documents": [asdict(item) for item in self.documents],
            "resolved_at": self.resolved_at,
        }


class DocumentCatalog(Protocol):
    def list_for_course(self, course_id: str) -> list[SourceDocumentRecord]: ...

    def get_by_public_id(
        self, document_id: str
    ) -> SourceDocumentRecord | None: ...


class DocumentContentReader(Protocol):
    def read_many(self, rag_index_keys: Sequence[str]) -> str: ...

    def search_many(
        self,
        rag_index_keys: Sequence[str],
        query_text: str,
        top_k: int = 12,
    ) -> str: ...


class GenerationSourceResolver:
    def __init__(
        self,
        document_catalog: DocumentCatalog,
        content_reader: DocumentContentReader,
        clock: Callable[[], datetime] | None = None,
    ):
        self._document_catalog = document_catalog
        self._content_reader = content_reader
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _normalize_ids(document_ids: Sequence[str]) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                str(item).strip() for item in document_ids if str(item).strip()
            )
        )

    def resolve(
        self,
        course_id: str,
        mode: GenerationSourceMode,
        selected_document_ids: Sequence[str],
        *,
        query_text: str = "",
        owner: str | None = None,
    ) -> ResolvedGenerationSource:
        normalized_course_id = str(course_id or "").strip()
        normalized = self._normalize_ids(selected_document_ids)
        self._validate_intent(mode, normalized)
        if mode == "none":
            return ResolvedGenerationSource(
                normalized_course_id,
                mode,
                (),
                (),
                "",
                self._clock().isoformat(),
            )

        documents = self.validate(
            normalized_course_id,
            mode,
            normalized,
            owner=owner,
        )
        rag_index_keys = [item.rag_index_key for item in documents]
        if mode == "course_auto":
            normalized_query = str(query_text or "").strip()
            if not normalized_query:
                raise GenerationSourceError(
                    "GENERATION_QUERY_REQUIRED",
                    "course_auto mode requires a generation topic",
                )
            context = (
                self._content_reader.search_many(
                    rag_index_keys, normalized_query, top_k=12
                )
                if documents
                else ""
            )
        else:
            context = (
                self._content_reader.read_many(rag_index_keys)
                if documents
                else ""
            )
        return ResolvedGenerationSource(
            normalized_course_id,
            mode,
            normalized,
            documents,
            context,
            self._clock().isoformat(),
        )

    def validate(
        self,
        course_id: str,
        mode: GenerationSourceMode,
        selected_document_ids: Sequence[str],
        *,
        owner: str | None = None,
    ) -> tuple[ResolvedSourceDocument, ...]:
        normalized = self._normalize_ids(selected_document_ids)
        self._validate_intent(mode, normalized)
        if mode == "none":
            return ()

        if mode == "selected_documents":
            records: list[SourceDocumentRecord] = []
            for document_id in normalized:
                record = self._document_catalog.get_by_public_id(document_id)
                if record is None and owner:
                    personal_resolver = getattr(
                        self._document_catalog,
                        "get_personal_by_public_id",
                        None,
                    )
                    if callable(personal_resolver):
                        record = personal_resolver(
                            document_id,
                            course_id=course_id,
                            owner=owner,
                        )
                if record is None:
                    raise GenerationSourceError(
                        "SOURCE_DOCUMENT_NOT_FOUND", document_id
                    )
                if record.course_id != course_id:
                    raise GenerationSourceError(
                        "SOURCE_DOCUMENT_WRONG_COURSE", document_id
                    )
                records.append(record)
        else:
            records = self._document_catalog.list_for_course(course_id)

        ready: list[ResolvedSourceDocument] = []
        for record in records:
            if record.status != "ready" or not record.rag_index_key:
                if mode == "selected_documents":
                    raise GenerationSourceError(
                        "SOURCE_DOCUMENT_NOT_READY", record.document_id
                    )
                continue
            ready.append(
                ResolvedSourceDocument(
                    document_id=record.document_id,
                    name=record.name,
                    rag_index_key=record.rag_index_key,
                    chunk_count=record.chunk_count,
                )
            )
        return tuple(sorted(ready, key=lambda item: item.document_id))

    @staticmethod
    def _validate_intent(
        mode: str, selected_document_ids: tuple[str, ...]
    ) -> None:
        if mode not in {"course_auto", "selected_documents", "none"}:
            raise GenerationSourceError(
                "GENERATION_SOURCE_INVALID", f"unknown source mode: {mode}"
            )
        if mode == "none" and selected_document_ids:
            raise GenerationSourceError(
                "GENERATION_SOURCE_INVALID",
                "none mode cannot include documents",
            )
        if mode == "course_auto" and selected_document_ids:
            raise GenerationSourceError(
                "GENERATION_SOURCE_INVALID",
                "course_auto mode cannot include selected documents",
            )
        if mode == "selected_documents" and not selected_document_ids:
            raise GenerationSourceError(
                "GENERATION_SOURCE_INVALID", "select at least one document"
            )
