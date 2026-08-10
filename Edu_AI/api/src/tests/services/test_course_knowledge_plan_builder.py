from __future__ import annotations

import pytest

from app.services import course_knowledge_plan_builder as builder


def _build_record():
    return {
        "build_id": "kb-1",
        "library_id": "course-1",
        "course_id": "course-1",
        "status": "draft",
        "course_snapshot": {"title": "线性代数"},
        "topics": [
            {"topic_id": "topic-1", "title": "向量空间", "objective": "理解向量空间"},
            {"topic_id": "topic-2", "title": "矩阵", "objective": "掌握矩阵运算"},
        ],
        "source_candidates": [
            {
                "candidate_id": "source-1",
                "topic_id": "topic-1",
                "url": "https://zh.wikipedia.org/wiki/向量空间",
                "license_name": "CC BY-SA 4.0",
                "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                "review_status": "approved",
                "selected": True,
            },
            {
                "candidate_id": "source-2",
                "topic_id": "topic-2",
                "url": "https://zh.wikipedia.org/wiki/矩阵",
                "license_name": "CC BY-SA 4.0",
                "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                "review_status": "approved",
                "selected": True,
            },
        ],
    }


class FakeRepository:
    def __init__(self):
        self.build = _build_record()
        self.checks = []
        self.published_graph = None

    def get_build(self, build_id):
        return dict(self.build) if build_id == "kb-1" else None

    def update_build(self, build_id, **fields):
        assert build_id == "kb-1"
        self.build.update(fields)
        return dict(self.build)

    def record_quality_check(self, build_id, **fields):
        assert build_id == "kb-1"
        self.checks.append(fields)

    def publish_build(self, build_id, *, graph, document_ids, metrics, quality_score):
        assert build_id == "kb-1"
        self.published_graph = graph
        self.build.update(
            status="succeeded",
            phase="published",
            progress=100,
            metrics=metrics,
            quality_score=quality_score,
        )
        return 1


class FakeManager:
    def __init__(self):
        self.graphs = []

    def save_knowledge_graph(self, course_id, graph):
        self.graphs.append((course_id, graph))
        return True


def test_plan_build_publishes_only_after_quality_gate(monkeypatch):
    repository = FakeRepository()
    manager = FakeManager()
    completed_jobs = []
    monkeypatch.setattr(builder, "get_postgres_knowledge_repository", lambda: repository)
    monkeypatch.setattr(
        builder,
        "_persist_candidate",
        lambda **kwargs: {
            "document_id": kwargs["candidate"]["candidate_id"],
            "scope_id": kwargs["candidate"]["topic_id"],
            "source_url": kwargs["candidate"]["url"],
        },
    )
    monkeypatch.setattr(builder, "update_job", lambda job_id, **fields: completed_jobs.append((job_id, fields)))

    result = builder.run_course_knowledge_plan_build_job(
        job_id="job-1",
        manager=manager,
        rag_system=object(),
        course_id="course-1",
        owner_user_id="teacher-1",
        build_id="kb-1",
    )

    assert result["quality_score"] == 100
    assert repository.build["status"] == "succeeded"
    assert len(repository.checks) == 3
    assert repository.published_graph["data"]["publication_status"] == "published"
    assert repository.published_graph["data"]["source_build_id"] == "kb-1"
    assert completed_jobs[-1][1]["status"].value == "succeeded"


def test_plan_build_blocks_publish_when_sources_cannot_be_ingested(monkeypatch):
    repository = FakeRepository()
    manager = FakeManager()
    monkeypatch.setattr(builder, "get_postgres_knowledge_repository", lambda: repository)
    monkeypatch.setattr(builder, "_persist_candidate", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("crawl failed")))
    monkeypatch.setattr(builder, "update_job", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="质量门禁未通过"):
        builder.run_course_knowledge_plan_build_job(
            job_id="job-1",
            manager=manager,
            rag_system=object(),
            course_id="course-1",
            owner_user_id="teacher-1",
            build_id="kb-1",
        )

    assert repository.build["status"] == "blocked"
    assert repository.published_graph is None
