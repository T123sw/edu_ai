from __future__ import annotations

import pytest

from app.standard_resources.models import extract_leaf_nodes
from scripts.seed_standard_resource_test_course import (
    TARGET_COURSE_ID,
    TEST_LECTURE_FILENAME,
    SeedSafetyError,
    build_database_graph,
    build_database_lecture,
    seed_test_course,
)


class FakeManager:
    def __init__(self, *, graph=None, documents=None):
        self.graph = graph
        self.documents = list(documents or [])
        self.graph_writes = 0
        self.document_writes = 0

    def get_course_info(self, course_id):
        return {"id": course_id, "title": "数据库"}

    def get_knowledge_graph(self, _course_id):
        return self.graph

    def get_knowledge_base_index(self, _course_id):
        return list(self.documents)

    def save_knowledge_graph(self, _course_id, graph):
        self.graph = graph
        self.graph_writes += 1
        return True

    def save_knowledge_base_file(self, course_id, data, filename, **_kwargs):
        self.documents = [
            item for item in self.documents if item.get("filename") != filename
        ]
        self.documents.append(
            {
                "id": "doc-database-test-lecture",
                "filename": filename,
                "course_id": course_id,
                "content": data.decode("utf-8"),
            }
        )
        self.document_writes += 1
        return f"knowledge_base/documents/{filename}"


def test_database_graph_has_three_chapters_and_six_stable_leaves() -> None:
    graph = build_database_graph()
    assert [item["label"] for item in graph["children"]] == [
        "关系模型",
        "SQL 查询",
        "事务",
    ]
    assert [leaf.leaf_id for leaf in extract_leaf_nodes(graph)] == [
        "db-relationships-and-keys",
        "db-integrity-constraints",
        "db-single-table-query",
        "db-multi-table-join",
        "db-acid",
        "db-concurrency-control",
    ]
    lecture = build_database_lecture()
    for title in ("关系与键", "完整性约束", "单表查询", "多表连接", "ACID", "并发控制"):
        assert f"## {title}" in lecture


def test_seed_is_dry_run_safe_and_idempotent() -> None:
    manager = FakeManager()

    dry_run = seed_test_course(manager=manager, course_id=TARGET_COURSE_ID, dry_run=True)
    assert dry_run["would_write_graph"] is True
    assert manager.graph_writes == 0
    assert manager.document_writes == 0

    seed_test_course(manager=manager, course_id=TARGET_COURSE_ID)
    seed_test_course(manager=manager, course_id=TARGET_COURSE_ID)
    assert manager.graph_writes == 1
    assert manager.document_writes == 1
    assert manager.documents[0]["filename"] == TEST_LECTURE_FILENAME


def test_seed_refuses_other_course_or_existing_official_content() -> None:
    with pytest.raises(SeedSafetyError):
        seed_test_course(manager=FakeManager(), course_id="course-other")

    manager = FakeManager(
        documents=[{"id": "official", "filename": "official-textbook.pdf"}]
    )
    with pytest.raises(SeedSafetyError):
        seed_test_course(manager=manager, course_id=TARGET_COURSE_ID)
