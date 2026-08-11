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


def test_knowledge_repository_persists_build_preview_and_candidates(engine):
    from app.persistence.postgres_knowledge_repository import PostgresKnowledgeRepository

    repository = PostgresKnowledgeRepository(engine)
    preview = repository.create_build_preview(
        course_id="course-1",
        triggered_by="teacher-1",
        plan={
            "course_id": "course-1",
            "course_snapshot": {"id": "course-1", "title": "线性代数"},
            "topics": [{"topic_id": "topic-1", "title": "矩阵"}],
            "source_candidates": [
                {
                    "candidate_id": "source-1",
                    "topic_id": "topic-1",
                    "title": "矩阵",
                    "url": "https://zh.wikipedia.org/wiki/矩阵",
                    "domain": "zh.wikipedia.org",
                    "source_type": "web",
                    "language": "zh-CN",
                    "license_name": "CC BY-SA 4.0",
                    "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                    "authority_tier": "reviewed_reference",
                    "review_status": "approved",
                    "review_reason": "已通过预审",
                    "selected": True,
                    "relevance_score": 1.0,
                    "metadata": {"snippet": "矩阵是线性代数的基础。"},
                }
            ],
            "warnings": [],
        },
    )

    loaded = repository.get_build(preview["build_id"])
    assert loaded is not None
    assert loaded["library_id"] == "course-1"
    assert loaded["status"] == "draft"
    assert loaded["phase"] == "source_review"
    assert loaded["course_snapshot"]["title"] == "线性代数"
    assert loaded["source_candidates"][0]["license_name"] == "CC BY-SA 4.0"
    assert loaded["source_candidates"][0]["selected"] is True
    graph_review = repository.update_build_draft(
        preview["build_id"],
        expected_revision=1,
        changes={"graph_draft": {"id": "root", "children": []}},
        phase="graph_review",
    )
    repository.confirm_build_graph(
        preview["build_id"],
        expected_revision=graph_review["revision"],
        confirmed_by="teacher-1",
    )
    repository.queue_build(preview["build_id"], selected_source_count=1)
    assert repository.get_build(preview["build_id"])["status"] == "queued"
    with pytest.raises(ValueError, match="已经启动"):
        repository.queue_build(preview["build_id"], selected_source_count=1)
    repository.replace_documents(
        "course-1",
        [{
            "id": "doc-staged",
            "filename": "staged.md",
            "course_id": "course-1",
            "library_type": "course",
            "status": "received",
            "uploaded_at": "2026-08-10T10:00:00+00:00",
        }],
    )
    repository.update_build(preview["build_id"], status="publishing", phase="publishing", progress=95)
    version = repository.publish_build(
        preview["build_id"],
        graph={"id": "root", "data": {"publication_status": "published", "source_build_id": preview["build_id"]}},
        document_ids=["doc-staged"],
        metrics={"persisted_document_count": 1},
        quality_score=92,
    )
    assert version == 1
    assert repository.get_build(preview["build_id"])["status"] == "succeeded"
    assert repository.list_documents("course-1")[0]["status"] == "ready"
    assert repository.get_graph("course-1")["data"]["source_build_id"] == preview["build_id"]


def test_knowledge_build_draft_uses_revision_and_requires_graph_confirmation(engine):
    from app.persistence.postgres_knowledge_repository import (
        KnowledgeBuildRevisionConflict,
        PostgresKnowledgeRepository,
    )

    repository = PostgresKnowledgeRepository(engine)
    draft = repository.create_build_draft(
        course_id="course-1",
        triggered_by="teacher-1",
        plan={
            "course_id": "course-1",
            "course_snapshot": {"id": "course-1", "title": "线性代数"},
            "config": {"preset": "standard", "target_module_count": 4},
            "graph_draft": None,
            "warnings": [],
        },
    )

    assert draft["phase"] == "draft_config"
    assert draft["revision"] == 1
    assert draft["graph_confirmed_at"] is None

    updated = repository.update_build_draft(
        draft["build_id"],
        expected_revision=1,
        changes={"config": {"preset": "small", "target_module_count": 3}},
    )
    assert updated["revision"] == 2
    assert updated["config"]["preset"] == "small"

    with pytest.raises(KnowledgeBuildRevisionConflict):
        repository.update_build_draft(
            draft["build_id"],
            expected_revision=1,
            changes={"warnings": ["stale"]},
        )

    with pytest.raises(ValueError, match="图谱草案"):
        repository.confirm_build_graph(
            draft["build_id"], expected_revision=2, confirmed_by="teacher-1"
        )

    with_graph = repository.update_build_draft(
        draft["build_id"],
        expected_revision=2,
        changes={"graph_draft": {"id": "root", "label": "线性代数", "children": []}},
        phase="graph_review",
    )
    confirmed = repository.confirm_build_graph(
        draft["build_id"],
        expected_revision=with_graph["revision"],
        confirmed_by="teacher-1",
    )
    assert confirmed["phase"] == "graph_confirmed"
    assert confirmed["confirmed_graph_revision"] == confirmed["revision"]
    assert confirmed["confirmed_by"] == "teacher-1"
    assert confirmed["graph_confirmed_at"]

    repository.queue_build(draft["build_id"], selected_source_count=0)
    assert repository.get_build(draft["build_id"])["status"] == "queued"


def test_editing_confirmed_build_clears_confirmation(engine):
    from app.persistence.postgres_knowledge_repository import PostgresKnowledgeRepository

    repository = PostgresKnowledgeRepository(engine)
    draft = repository.create_build_draft(
        course_id="course-1",
        triggered_by="teacher-1",
        plan={
            "course_id": "course-1",
            "config": {"preset": "small"},
            "graph_draft": {"id": "root", "label": "课程", "children": []},
        },
    )
    confirmed = repository.confirm_build_graph(
        draft["build_id"], expected_revision=1, confirmed_by="teacher-1"
    )
    edited = repository.update_build_draft(
        draft["build_id"],
        expected_revision=confirmed["revision"],
        changes={"config": {"preset": "large"}},
    )

    assert edited["revision"] == confirmed["revision"] + 1
    assert edited["phase"] == "draft_config"
    assert edited["graph_confirmed_at"] is None
    assert edited["confirmed_graph_revision"] is None
    with pytest.raises(ValueError, match="确认"):
        repository.queue_build(draft["build_id"], selected_source_count=0)


def test_running_build_replaces_and_updates_discovered_source_candidates(engine):
    from app.persistence.postgres_knowledge_repository import PostgresKnowledgeRepository

    repository = PostgresKnowledgeRepository(engine)
    draft = repository.create_build_draft(
        course_id="course-1",
        triggered_by="teacher-1",
        plan={
            "course_id": "course-1",
            "graph_draft": {"id": "root", "label": "课程", "children": []},
            "topics": [],
            "source_candidates": [],
        },
    )
    repository.confirm_build_graph(
        draft["build_id"], expected_revision=1, confirmed_by="teacher-1"
    )
    repository.queue_build(draft["build_id"], selected_source_count=0)

    loaded = repository.replace_build_source_candidates(
        draft["build_id"],
        topics=[{"topic_id": "leaf-1", "title": "向量空间"}],
        candidates=[
            {
                "candidate_id": "source-1",
                "topic_id": "leaf-1",
                "title": "向量空间教程",
                "url": "https://example.edu/vector-space",
                "domain": "example.edu",
                "source_type": "web",
                "language": "zh-CN",
                "license_name": None,
                "license_url": None,
                "authority_tier": "web_discovered",
                "review_status": "relevant",
                "review_reason": "等待正文抓取",
                "selected": True,
                "relevance_score": 0.8,
                "metadata": {"query": "向量空间 教程"},
            }
        ],
        warnings=[],
        discovery_metrics={"leaf_count": 1, "selected_candidate_count": 1},
    )

    assert loaded["topics"][0]["topic_id"] == "leaf-1"
    assert loaded["source_candidates"][0]["review_status"] == "relevant"
    assert loaded["source_candidates"][0]["license_name"] is None
    assert loaded["metrics"]["source_discovery"]["selected_candidate_count"] == 1

    repository.update_source_candidate_result(
        draft["build_id"],
        "source-1",
        review_status="ready",
        review_reason="正文抓取与索引成功",
        metadata={"content_hash": "abc123"},
    )
    candidate = repository.get_build(draft["build_id"])["source_candidates"][0]
    assert candidate["review_status"] == "ready"
    assert candidate["metadata"]["content_hash"] == "abc123"


def test_knowledge_repository_versions_and_rolls_back_published_graph(engine):
    from app.persistence.postgres_knowledge_repository import PostgresKnowledgeRepository

    repository = PostgresKnowledgeRepository(engine)
    repository.upsert_graph(
        "course-1",
        {"id": "v1", "data": {"publication_status": "published", "source_build_id": "kb-1", "node_count": 2}},
    )
    repository.upsert_graph(
        "course-1",
        {"id": "v2", "data": {"publication_status": "published", "source_build_id": "kb-2", "node_count": 3}},
    )

    versions = repository.list_graph_versions("course-1")
    rollback = repository.rollback_graph("course-1", 1)

    assert [item["version"] for item in versions] == [2, 1]
    assert versions[0]["source_build_id"] == "kb-2"
    assert rollback["version"] == 3
    assert repository.get_graph("course-1")["id"] == "v1"
    assert repository.get_graph("course-1")["data"]["rolled_back_from_version"] == 1


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
