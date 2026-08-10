from pathlib import Path
from threading import RLock

import pytest
from sqlalchemy import create_engine

from app.database import Base


@pytest.fixture
def engine(tmp_path: Path):
    value = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'knowledge.db').as_posix()}")
    Base.metadata.create_all(value)
    try:
        yield value
    finally:
        value.dispose()


def test_knowledge_repository_round_trips_documents_graph_and_runtime_indexes(engine):
    from app.persistence.postgres_knowledge_repository import PostgresKnowledgeRepository

    repository = PostgresKnowledgeRepository(engine)
    documents = [
        {
            "id": "doc-1",
            "filename": "book.pdf",
            "path": "knowledge_base/documents/book.pdf",
            "course_id": "course-1",
            "library_type": "course",
            "scope_type": "course",
            "uploaded_at": "2026-08-10T10:00:00+00:00",
        }
    ]
    repository.replace_documents("course-1", documents)
    repository.upsert_graph("course-1", {"id": "root", "children": []})
    repository.replace_runtime_index("document", {"source-key": {"hash": "abc"}})

    assert repository.list_documents("course-1") == documents
    assert repository.get_graph("course-1")["id"] == "root"
    assert repository.load_runtime_index("document") == {"source-key": {"hash": "abc"}}


def test_course_knowledge_metadata_uses_database_without_index_json(
    engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from core.course_storage import CourseStorageManager

    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("KNOWLEDGE_PERSISTENCE_MODE", "postgres")
    manager = CourseStorageManager(str(tmp_path / "course-data"))
    manager.create_course_structure("course-1")
    assert manager.save_knowledge_base_index(
        "course-1",
        [{"id": "doc-1", "filename": "book.pdf", "path": "book.pdf"}],
    )
    assert manager.save_knowledge_graph("course-1", {"id": "root"})

    assert manager.get_knowledge_base_index("course-1")[0]["id"] == "doc-1"
    assert manager.get_knowledge_graph("course-1") == {"id": "root"}
    course_dir = tmp_path / "course-data" / "courses" / "course-1"
    assert not (course_dir / "knowledge_base" / "index.json").exists()
    assert not (course_dir / "knowledge_graph.json").exists()


def test_rag_document_registry_uses_database_without_json(
    engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from modules.rag_v2.rag_main.system import RAGSystem

    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("KNOWLEDGE_PERSISTENCE_MODE", "postgres")
    registry_path = tmp_path / "document_index.json"
    system = object.__new__(RAGSystem)
    system.index_file = registry_path
    system._index_write_lock = RLock()
    system.document_index = {"source-key": {"hash": "abc"}}

    system._save_index()
    assert system._load_index() == system.document_index
    assert registry_path.exists() is False
