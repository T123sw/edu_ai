import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import pytest

from modules.rag_v2.document_resolver import (
    load_rag_document_content,
    resolve_rag_document,
    resolve_rag_document_ids,
)


class FakeRAGSystem:
    def __init__(self, alice_path: str | None = None):
        self.alice_path = alice_path or r"D:\docs\alice\lesson.md"
        self.alice_course_relative_path = "knowledge_base/documents/lesson.md"
        self.public_path = r"D:\course\shared\course-lesson.md"
        self.public_course_relative_path = "knowledge_base/documents/course-lesson.md"
        self.public_legacy_path = r"D:\course\shared\legacy-lesson.md"
        self.public_legacy_course_relative_path = "knowledge_base/documents/legacy-lesson.md"
        self.bob_path = r"D:\docs\bob\lesson.md"
        self.alice_key = f"user_alice:{self.alice_path}"
        self.public_key = self.public_path
        self.public_legacy_key = self.public_legacy_path
        self.bob_key = f"user_bob:{self.bob_path}"
        self.document_index = {
            self.alice_key: {
                "physical_path": self.alice_path,
                "path": self.alice_course_relative_path,
                "source_key": self.alice_key,
                "file_name": "lesson.md",
                "owner": "alice",
            },
            self.public_key: {
                "physical_path": self.public_path,
                "path": self.public_course_relative_path,
                "source_key": self.public_key,
                "file_name": "course-lesson.md",
                "owner": None,
            },
            self.public_legacy_key: {
                "physical_path": self.public_legacy_path,
                "source_key": self.public_legacy_key,
                "file_name": "legacy-lesson.md",
                "owner": None,
            },
            self.bob_key: {
                "physical_path": self.bob_path,
                "source_key": self.bob_key,
                "file_name": "lesson.md",
                "owner": "bob",
            },
        }

    def _make_index_key(self, file_path, owner):
        if str(file_path).startswith("user_"):
            return str(file_path)
        return f"user_{owner}:{file_path}" if owner else str(file_path)

    def _make_source_key(self, file_path, owner):
        if str(file_path).startswith("user_"):
            return str(file_path)
        return f"user_{owner}:{file_path}" if owner else str(file_path)

    def list_documents(self, owner=None):
        return [
            {"file_path": key, "file_name": record["file_name"], "owner": record["owner"]}
            for key, record in self.document_index.items()
            if owner is None or record["owner"] in (None, owner)
        ]


class FakeDocument:
    def __init__(self, page_content, page=0):
        self.page_content = page_content
        self.metadata = {"page": page}


class FakeDocumentProcessor:
    def load_text_like(self, file_path):
        return [FakeDocument("text content", 1)]

    def load_pdf(self, file_path):
        return [FakeDocument("page two", 2), FakeDocument("page one", 1)]

    def load_doc(self, file_path):
        return [FakeDocument("doc content", 1)]


def test_resolve_rag_document_accepts_index_key():
    rag_system = FakeRAGSystem()

    resolved = resolve_rag_document(rag_system, rag_system.alice_key, owner="alice")

    assert resolved is not None
    assert resolved.index_key == rag_system.alice_key
    assert resolved.physical_path == rag_system.alice_path
    assert resolved.source_key == rag_system.alice_key
    assert resolved.file_name == "lesson.md"


def test_resolve_rag_document_accepts_legacy_physical_path():
    rag_system = FakeRAGSystem()

    resolved = resolve_rag_document(rag_system, rag_system.alice_path, owner="alice")

    assert resolved is not None
    assert resolved.index_key == rag_system.alice_key
    assert resolved.physical_path == rag_system.alice_path


def test_resolve_rag_document_accepts_course_relative_path():
    rag_system = FakeRAGSystem()

    resolved = resolve_rag_document(rag_system, rag_system.alice_course_relative_path, owner="alice")

    assert resolved is not None
    assert resolved.index_key == rag_system.alice_key
    assert resolved.physical_path == rag_system.alice_path


def test_resolve_rag_document_accepts_public_course_relative_path_for_named_owner():
    rag_system = FakeRAGSystem()

    resolved = resolve_rag_document(rag_system, rag_system.public_course_relative_path, owner="alice")

    assert resolved is not None
    assert resolved.index_key == rag_system.public_key
    assert resolved.physical_path == rag_system.public_path


def test_resolve_rag_document_accepts_legacy_public_course_relative_path_without_record_path():
    rag_system = FakeRAGSystem()

    resolved = resolve_rag_document(rag_system, rag_system.public_legacy_course_relative_path, owner="alice")

    assert resolved is not None
    assert resolved.index_key == rag_system.public_legacy_key
    assert resolved.physical_path == rag_system.public_legacy_path


def test_resolve_rag_document_rejects_cross_owner_record():
    rag_system = FakeRAGSystem()

    assert resolve_rag_document(rag_system, rag_system.bob_key, owner="alice") is None
    assert resolve_rag_document(rag_system, rag_system.bob_path, owner="alice") is None


def test_resolve_rag_document_returns_none_for_unknown_or_blank_ids():
    rag_system = FakeRAGSystem()

    assert resolve_rag_document(rag_system, "", owner="alice") is None
    assert resolve_rag_document(rag_system, r"D:\docs\alice\missing.md", owner="alice") is None


def test_resolve_rag_document_ids_returns_only_public_index_keys():
    rag_system = FakeRAGSystem()

    resolved_ids = resolve_rag_document_ids(
        rag_system,
        [
            rag_system.alice_path,
            rag_system.alice_key,
            rag_system.public_course_relative_path,
            rag_system.bob_path,
            r"D:\docs\alice\missing.md",
        ],
        owner="alice",
    )

    assert resolved_ids == [rag_system.alice_key, rag_system.public_key]


def test_load_rag_document_content_resolves_identifier_and_loads_text(monkeypatch):
    temp_file = Path(__file__).resolve().parents[5] / "_runtime_import_test_tmp_root" / "resolver_content.md"
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file.write_text("ignored by fake processor", encoding="utf-8")
    rag_system = FakeRAGSystem(str(temp_file))
    rag_system.document_processor = FakeDocumentProcessor()

    loaded = load_rag_document_content(rag_system, rag_system.alice_key, owner="alice")

    assert loaded is not None
    assert loaded.index_key == rag_system.alice_key
    assert loaded.file_name == "lesson.md"
    assert loaded.content == "text content"


def test_load_rag_document_content_sorts_pdf_pages(monkeypatch):
    temp_file = Path(__file__).resolve().parents[5] / "_runtime_import_test_tmp_root" / "resolver_content.pdf"
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file.write_bytes(b"%PDF fake")
    rag_system = FakeRAGSystem(str(temp_file))
    rag_system.document_processor = FakeDocumentProcessor()

    loaded = load_rag_document_content(rag_system, str(temp_file), owner="alice")

    assert loaded is not None
    assert loaded.content == "page one\n\npage two"
