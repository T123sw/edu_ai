from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.services.generation_source_errors import GenerationSourceError
from app.services.generation_source_resolver import (
    GenerationSourceResolver,
    SourceDocumentRecord,
)


class FakeDocumentCatalog:
    def __init__(self):
        self.records: list[SourceDocumentRecord] = []
        self.calls: list[tuple[str, str]] = []

    def add(self, **values):
        record = SourceDocumentRecord(
            course_id=values["course_id"],
            document_id=values["document_id"],
            name=values.get("name", values["document_id"]),
            status=values.get("status", "ready"),
            rag_index_key=values.get("rag_index_key", ""),
            chunk_count=values.get("chunk_count", 1),
        )
        self.records.append(record)
        return record

    def list_for_course(self, course_id: str):
        self.calls.append(("list", course_id))
        return [item for item in self.records if item.course_id == course_id]

    def get_by_public_id(self, document_id: str):
        self.calls.append(("get", document_id))
        return next(
            (item for item in self.records if item.document_id == document_id),
            None,
        )


class FakeDocumentContentReader:
    def __init__(self):
        self.calls: list[tuple[str, ...]] = []

    def read_many(self, rag_index_keys):
        keys = tuple(rag_index_keys)
        self.calls.append(keys)
        return "Newton course evidence: " + ", ".join(keys)

    def search_many(self, rag_index_keys, query_text, top_k=12):
        keys = tuple(rag_index_keys)
        self.calls.append(("search", query_text, *keys))
        return f"Relevant evidence for {query_text}: " + ", ".join(keys)


@pytest.fixture
def catalog():
    return FakeDocumentCatalog()


@pytest.fixture
def content_reader():
    return FakeDocumentContentReader()


@pytest.fixture
def resolver(catalog, content_reader):
    return GenerationSourceResolver(
        catalog,
        content_reader,
        clock=lambda: datetime(2026, 8, 7, tzinfo=timezone.utc),
    )


def test_selected_documents_resolve_public_ids_to_rag_keys(resolver, catalog):
    catalog.add(
        course_id="c1",
        document_id="doc-1",
        status="ready",
        rag_index_key="rag/course/c1/doc-1",
    )

    resolved = resolver.resolve("c1", "selected_documents", ["doc-1"])

    assert resolved.requested_document_ids == ("doc-1",)
    assert resolved.documents[0].rag_index_key == "rag/course/c1/doc-1"
    assert "Newton" in resolved.context_text


def test_none_does_not_query_catalog_or_content(
    resolver, catalog, content_reader
):
    resolved = resolver.resolve("c1", "none", [])

    assert resolved.documents == ()
    assert resolved.context_text == ""
    assert catalog.calls == []
    assert content_reader.calls == []


def test_selected_processing_document_fails_with_stable_code(resolver, catalog):
    catalog.add(
        course_id="c1",
        document_id="doc-1",
        status="processing",
        rag_index_key="",
    )

    with pytest.raises(GenerationSourceError) as caught:
        resolver.resolve("c1", "selected_documents", ["doc-1"])

    assert caught.value.code == "SOURCE_DOCUMENT_NOT_READY"


@pytest.mark.parametrize(
    ("mode", "selected", "code"),
    [
        ("none", ["doc-1"], "GENERATION_SOURCE_INVALID"),
        ("selected_documents", [], "GENERATION_SOURCE_INVALID"),
        ("selected_documents", ["missing"], "SOURCE_DOCUMENT_NOT_FOUND"),
    ],
)
def test_invalid_source_intent_has_stable_code(
    resolver, mode, selected, code
):
    with pytest.raises(GenerationSourceError) as caught:
        resolver.resolve("c1", mode, selected)
    assert caught.value.code == code


def test_selected_document_from_another_course_is_rejected(resolver, catalog):
    catalog.add(
        course_id="c2",
        document_id="doc-1",
        rag_index_key="rag/course/c2/doc-1",
    )
    with pytest.raises(GenerationSourceError) as caught:
        resolver.resolve("c1", "selected_documents", ["doc-1"])
    assert caught.value.code == "SOURCE_DOCUMENT_WRONG_COURSE"


def test_course_auto_uses_only_ready_documents_in_public_id_order(
    resolver, catalog, content_reader
):
    first = catalog.add(
        course_id="c1",
        document_id="doc-b",
        rag_index_key="rag-b",
    )
    catalog.records.append(replace(first, document_id="doc-a", rag_index_key="rag-a"))
    catalog.add(
        course_id="c1",
        document_id="doc-c",
        status="failed",
        rag_index_key="rag-c",
    )

    resolved = resolver.resolve(
        "c1", "course_auto", [], query_text="Newton's second law"
    )

    assert [item.document_id for item in resolved.documents] == ["doc-a", "doc-b"]
    assert content_reader.calls == [
        ("search", "Newton's second law", "rag-a", "rag-b")
    ]
    assert "Relevant evidence" in resolved.context_text
    assert resolved.to_snapshot()["mode"] == "course_auto"
