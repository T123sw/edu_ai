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
        "graph_draft": {
            "id": "course-linear-algebra",
            "label": "线性代数知识体系",
            "children": [
                {
                    "id": "module-core",
                    "label": "线性结构与运算",
                    "children": [
                        {
                            "id": "topic-1",
                            "label": "向量空间",
                            "children": [],
                            "data": {"level": 2, "type": "knowledge_point", "summary": "理解向量空间"},
                        },
                        {
                            "id": "topic-2",
                            "label": "矩阵",
                            "children": [],
                            "data": {"level": 2, "type": "knowledge_point", "summary": "掌握矩阵运算"},
                        },
                    ],
                    "data": {"level": 1, "type": "knowledge_module", "summary": "线性代数核心结构"},
                }
            ],
            "data": {"level": 0, "type": "course", "summary": "线性代数课程"},
        },
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


@pytest.fixture(autouse=True)
def _stub_source_discovery(monkeypatch):
    record = _build_record()
    candidates = [
        {
            **item,
            "review_status": "relevant",
            "metadata": {"query": f"{item['topic_id']} 课程资料"},
        }
        for item in record["source_candidates"]
    ]
    monkeypatch.setattr(
        builder,
        "discover_course_knowledge_sources",
        lambda _build: {
            "topics": record["topics"],
            "source_candidates": candidates,
            "warnings": [],
            "metrics": {
                "leaf_count": 2,
                "candidate_count": 2,
                "selected_candidate_count": 2,
                "search_failure_count": 0,
            },
        },
    )


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

    def replace_build_source_candidates(
        self, build_id, *, topics, candidates, warnings, discovery_metrics
    ):
        assert build_id == "kb-1"
        self.build["topics"] = topics
        self.build["source_candidates"] = candidates
        self.build["warnings"] = warnings
        self.build.setdefault("metrics", {})["source_discovery"] = discovery_metrics
        return dict(self.build)

    def update_source_candidate_result(
        self, build_id, candidate_id, *, review_status, review_reason, metadata=None
    ):
        assert build_id == "kb-1"
        for candidate in self.build["source_candidates"]:
            if candidate["candidate_id"] == candidate_id:
                candidate["review_status"] = review_status
                candidate["review_reason"] = review_reason
                candidate.setdefault("metadata", {}).update(metadata or {})
                return
        raise AssertionError(candidate_id)

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
            "content_hash": kwargs["candidate"]["candidate_id"],
            "final_url": kwargs["candidate"]["url"],
        },
    )
    generated = []
    monkeypatch.setattr(
        builder,
        "_generate_and_persist_supplement",
        lambda **kwargs: generated.append(kwargs["topic"]["topic_id"]) or {
            "document_id": f"generated-{kwargs['topic']['topic_id']}-{kwargs['sequence']}",
            "scope_id": kwargs["topic"]["topic_id"],
            "source_url": "",
            "reused": False,
            "source_type": "model_generated",
            "review_score": 90,
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
    assert len(repository.checks) == 4
    assert result["document_count"] == 6
    assert sorted(generated) == ["topic-1", "topic-1", "topic-2", "topic-2"]
    assert repository.published_graph["data"]["publication_status"] == "published"
    assert repository.published_graph["data"]["source_build_id"] == "kb-1"
    assert completed_jobs[-1][1]["status"].value == "succeeded"


def test_plan_build_blocks_publish_when_sources_cannot_be_ingested(monkeypatch):
    repository = FakeRepository()
    manager = FakeManager()
    monkeypatch.setattr(builder, "get_postgres_knowledge_repository", lambda: repository)
    monkeypatch.setattr(builder, "_persist_candidate", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("crawl failed")))
    monkeypatch.setattr(builder, "_generate_and_persist_supplement", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("model unavailable")))
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


def test_published_graph_has_three_levels_and_three_documents_per_leaf(monkeypatch):
    repository = FakeRepository()
    monkeypatch.setattr(builder, "get_postgres_knowledge_repository", lambda: repository)
    monkeypatch.setattr(
        builder,
        "_persist_candidate",
        lambda **kwargs: {
            "document_id": kwargs["candidate"]["candidate_id"],
            "scope_id": kwargs["candidate"]["topic_id"],
            "source_url": kwargs["candidate"]["url"],
            "reused": False,
            "content_hash": kwargs["candidate"]["candidate_id"],
            "final_url": kwargs["candidate"]["url"],
        },
    )
    monkeypatch.setattr(
        builder,
        "_generate_and_persist_supplement",
        lambda **kwargs: {
            "document_id": f"generated-{kwargs['topic']['topic_id']}-{kwargs['sequence']}",
            "scope_id": kwargs["topic"]["topic_id"],
            "source_url": "",
            "reused": False,
            "source_type": "model_generated",
            "review_score": 90,
        },
    )
    monkeypatch.setattr(builder, "update_job", lambda *args, **kwargs: None)

    builder.run_course_knowledge_plan_build_job(
        job_id="job-1",
        manager=FakeManager(),
        rag_system=object(),
        course_id="course-1",
        owner_user_id="teacher-1",
        build_id="kb-1",
    )

    root = repository.published_graph
    assert root["data"]["level"] == 0
    assert root["children"][0]["data"]["level"] == 1
    leaves = root["children"][0]["children"]
    assert {leaf["data"]["level"] for leaf in leaves} == {2}
    assert all(len(leaf["data"]["document_ids"]) == 3 for leaf in leaves)


def test_reviewed_staged_documents_are_resumed_and_promoted():
    class ManagerWithStaging:
        def get_knowledge_base_index(self, course_id):
            assert course_id == "course-1"
            return [
                {
                    "id": "staged-1",
                    "scope_id": "topic-1",
                    "source_type": "model_generated",
                    "generation_review_score": 93,
                    "status": "received",
                },
                {
                    "id": "rejected-1",
                    "scope_id": "topic-1",
                    "source_type": "model_generated",
                    "generation_review_score": 75,
                    "status": "received",
                },
            ]

    resumed = builder._reviewed_generated_documents(
        ManagerWithStaging(), course_id="course-1", scope_id="topic-1", limit=3
    )

    assert resumed == [
        {
            "document_id": "staged-1",
            "scope_id": "topic-1",
            "source_url": "",
            "reused": False,
            "resumed": True,
            "source_type": "model_generated",
            "review_score": 93,
        }
    ]


def test_extract_page_accepts_missing_license_and_uses_linked_section(monkeypatch):
    class Response:
        headers = {"content-type": "text/html; charset=utf-8"}
        text = """
        <html><head><title>Python manual</title></head><body><main>
          <section id="unrelated"><h2>Unrelated</h2><p>{unrelated}</p></section>
          <section id="if-statements"><h2>if 语句</h2><p>{target}</p></section>
        </main></body></html>
        """.format(unrelated="unrelated text " * 80, target="条件判断 if elif else 示例 " * 40)

        def raise_for_status(self):
            return None

    class Client:
        def get(self, _url):
            return Response()

    monkeypatch.setattr(builder, "_robots_allows", lambda _client, _url: True)
    title, content, final_url, content_hash = builder._extract_reviewed_page(
        Client(),
        {
            "url": "https://docs.python.org/zh-cn/3/tutorial/controlflow.html#if-statements",
            "title": "Python 官方教程：if 语句",
            "review_status": "relevant",
        },
    )

    assert title == "Python 官方教程：if 语句"
    assert "条件判断" in content
    assert "unrelated text" not in content
    assert final_url == "https://docs.python.org/zh-cn/3/tutorial/controlflow.html"
    assert len(content_hash) == 64
