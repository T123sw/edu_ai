from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import course_knowledge_plan_builder as builder


def test_ingest_online_textbook_expands_audited_linked_pdf_bundle(monkeypatch):
    fetched_urls: list[str] = []

    def fake_fetch(_client, candidate, **_kwargs):
        url = candidate["url"]
        fetched_urls.append(url)
        is_pdf = url.endswith(".pdf")
        return SimpleNamespace(
            title=candidate.get("title", url),
            original_url=url,
            final_url=url,
            content_format="pdf" if is_pdf else "html",
            content_hash=("pdf-" if is_pdf else "html-") + str(len(fetched_urls)),
            payload=b"%PDF-test" if is_pdf else b"<html><body></body></html>",
            content_type="application/pdf" if is_pdf else "text/html",
            retrieved_at="2026-09-11T00:00:00+00:00",
        )

    monkeypatch.setattr(builder, "fetch_source", fake_fetch)
    monkeypatch.setattr(
        builder,
        "parse_html_source",
        lambda _fetched: {"parser": "structured-html", "chunks": [], "outline": [], "warnings": []},
    )

    def fake_parse_pdf(fetched, *, pdf_parser=None):
        del pdf_parser
        slug = fetched.final_url.rsplit("/", 1)[-1]
        return {
            "parser": "mineru",
            "parser_metadata": {},
            "summary": slug,
            "outline": [{"id": slug, "title": slug, "level": 1, "order": 1}],
            "chunks": [{
                "chunk_id": slug,
                "chapter_id": slug,
                "chapter_title": slug,
                "content": f"content for {slug}",
                "content_hash": f"hash-{slug}",
                "order": 1,
            }],
            "char_count": 100,
            "chapter_count": 1,
            "chunk_count": 1,
            "warnings": [],
            "parsed_at": "2026-09-11T00:00:00+00:00",
        }

    monkeypatch.setattr(builder, "parse_pdf_source", fake_parse_pdf)
    candidate = {
        "candidate_id": "ostep",
        "title": "Operating Systems: Three Easy Pieces",
        "url": "https://pages.cs.wisc.edu/~remzi/OSTEP/",
        "domain": "pages.cs.wisc.edu",
        "authority_tier": "authoritative_source",
        "metadata": {
            "linked_chapter_urls": [
                "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf",
                "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-sema.pdf",
            ],
        },
    }

    textbook = builder._ingest_online_textbook_candidate(candidate)

    assert fetched_urls == [candidate["url"], *candidate["metadata"]["linked_chapter_urls"]]
    assert textbook["parse_result"]["parser"] == "linked-pdf-bundle"
    assert textbook["parse_result"]["chunk_count"] == 2
    assert {item["source_url"] for item in textbook["parse_result"]["chunks"]} == set(
        candidate["metadata"]["linked_chapter_urls"]
    )


def _build_record():
    return {
        "build_id": "kb-1",
        "library_id": "course-1",
        "course_id": "course-1",
        "status": "draft",
        "course_snapshot": {"title": "线性代数"},
        "config": {
            "graph_depth": 3,
            "target_module_count": 1,
            "target_points_per_module": 2,
            "target_materials_per_leaf": 3,
            "minimum_web_materials_per_leaf": 1,
            "minimum_authoritative_sources_per_leaf": 0,
            "maximum_ai_materials_per_leaf": 2,
            "ai_supplement_enabled": True,
        },
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
        self.published_document_ids = []

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
        self.published_document_ids = list(document_ids)
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


def test_missing_preferred_domains_checks_each_domain_for_the_topic():
    topic = {
        "topic_id": "topic-1",
        "source_policy": {
            "preferred_domains": ["docs.docker.com", "docs.kernel.org"]
        },
    }
    persisted = [
        {
            "scope_id": "topic-1",
            "source_url": "https://docs.docker.com/engine/containers/resource_constraints/",
        }
    ]

    assert builder._missing_preferred_domains(topic, persisted) == ["docs.kernel.org"]
    assert builder._candidate_fills_preferred_gap(
        {"url": "https://docs.kernel.org/admin-guide/cgroup-v2.html"},
        ["docs.kernel.org"],
    )
    assert not builder._candidate_fills_preferred_gap(
        {"url": "https://docs.docker.com/engine/containers/run"},
        ["docs.kernel.org"],
    )


def test_candidate_merge_deduplicates_url_and_retains_all_topic_hits():
    merged = builder._merge_source_candidates(
        [{
            "candidate_id": "course-source",
            "topic_id": None,
            "url": "https://example.edu/os.pdf?utm_source=search",
            "selected": True,
            "review_status": "relevant",
            "metadata": {"matched_topic_ids": []},
        }],
        [{
            "candidate_id": "leaf-source",
            "topic_id": "processes",
            "url": "https://example.edu/os.pdf",
            "selected": True,
            "review_status": "relevant",
            "metadata": {"matched_topic_ids": ["processes"]},
        }],
    )

    assert len(merged) == 1
    assert merged[0]["metadata"]["matched_topic_ids"] == ["processes"]

    ready = builder._merge_source_candidates(
        [{**merged[0], "review_status": "ready"}],
        [{
            "candidate_id": "another-leaf-hit",
            "topic_id": "threads",
            "url": "https://example.edu/os.pdf",
            "selected": True,
            "review_status": "relevant",
            "metadata": {"matched_topic_ids": ["threads"]},
        }],
    )
    assert ready[0]["review_status"] == "ready"
    assert ready[0]["metadata"]["matched_topic_ids"] == ["processes", "threads"]


def test_source_semantic_evidence_rejects_navigation_noise():
    candidate = {
        "metadata": {
            "topic_title": "进程状态与转换",
            "topic_objective": "理解就绪、运行、阻塞状态及其转换条件",
        }
    }

    rejected, rejected_score = builder._source_semantic_evidence(
        candidate,
        "网站导航包含操作系统和进程栏目，但正文是教师讲课比赛新闻。",
    )
    accepted, accepted_score = builder._source_semantic_evidence(
        candidate,
        "进程状态与转换包括就绪、运行和阻塞。\n\n"
        "创建后的进程先进入就绪状态，获得处理器后转换为运行状态。" * 8
        + "\n\n等待 I/O 时会进入阻塞状态，事件完成后重新回到就绪队列。" * 8,
    )

    assert rejected is False
    assert accepted is True
    assert accepted_score > rejected_score


def test_intent_contract_controls_ai_fallback_over_legacy_default():
    assert builder._effective_build_config({
        "config": {"ai_supplement_enabled": True},
        "intent_contract": {"source_policy": {"allow_ai_fallback": False}},
    })["ai_supplement_enabled"] is False
    assert builder._effective_build_config({
        "config": {"ai_supplement_enabled": False},
        "intent_contract": {"source_policy": {"allow_ai_fallback": True}},
    })["ai_supplement_enabled"] is True


def test_source_semantic_evidence_rejects_short_news_mention():
    candidate = {
        "metadata": {
            "topic_title": "FCFS 与 SJF 调度",
            "topic_objective": "比较先来先服务和短作业优先并计算等待时间",
        }
    }

    passed, _ = builder._source_semantic_evidence(
        candidate,
        "学院举办教师讲课比赛。某教师围绕操作系统介绍了 FCFS 与 SJF 调度，"
        "比较了公平性和效率，随后评委为参赛教师颁奖。",
    )

    assert passed is False


def test_source_semantic_evidence_rejects_broad_course_page_for_specific_leaf():
    candidate = {
        "metadata": {
            "topic_title": "线程的概念与进程/线程区别",
            "topic_objective": "说明线程共享资源和独立执行上下文",
        }
    }

    passed, _ = builder._source_semantic_evidence(
        candidate,
        "操作系统由内核、系统程序和系统库构成。\n\n本文介绍 Linux 发行版、文件系统和软件包管理。" * 20,
    )

    assert passed is False


def test_source_semantic_evidence_accepts_english_official_cgroup_document():
    candidate = {
        "metadata": {
            "topic_title": "Linux cgroups 与容器资源隔离",
            "topic_objective": "理解 CPU、内存和 I/O 资源限制机制",
        }
    }
    content = (
        "Control Group v2 organizes processes into a hierarchy. Linux exposes cgroup controllers.\n\n"
        "The cpu controller distributes processor cycles and the memory controller enforces limits. "
        "The io controller controls access to block devices.\n\n"
        "Containers use these resource controls for isolation and administrators can verify limits. "
    ) * 8

    passed, _ = builder._source_semantic_evidence(candidate, content)

    assert passed is True


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
    assert len(repository.checks) == 9
    assert result["document_count"] == 6
    assert sorted(generated) == ["topic-1", "topic-1", "topic-2", "topic-2"]
    assert repository.published_graph["data"]["publication_status"] == "published"
    assert repository.published_graph["data"]["source_build_id"] == "kb-1"
    assert len(repository.published_document_ids) == 6
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


def test_plan_build_stops_crawling_after_each_leaf_reaches_its_target(monkeypatch):
    repository = FakeRepository()
    repository.build["config"].update(
        target_materials_per_leaf=1,
        minimum_web_materials_per_leaf=1,
        maximum_ai_materials_per_leaf=0,
    )
    candidates = [
        {
            "candidate_id": f"source-{topic}-{sequence}",
            "topic_id": topic,
            "url": f"https://example.com/{topic}/{sequence}",
            "review_status": "relevant",
            "selected": True,
            "metadata": {"query": topic},
        }
        for topic in ("topic-1", "topic-2")
        for sequence in (1, 2)
    ]
    monkeypatch.setattr(builder, "get_postgres_knowledge_repository", lambda: repository)
    monkeypatch.setattr(
        builder,
        "discover_course_knowledge_sources",
        lambda _build: {
            "topics": repository.build["topics"],
            "source_candidates": candidates,
            "warnings": [],
            "metrics": {
                "leaf_count": 2,
                "candidate_count": 4,
                "selected_candidate_count": 4,
                "search_failure_count": 0,
            },
        },
    )
    crawled = []

    def persist(**kwargs):
        candidate = kwargs["candidate"]
        crawled.append(candidate["candidate_id"])
        return {
            "document_id": candidate["candidate_id"],
            "scope_id": candidate["topic_id"],
            "source_url": candidate["url"],
            "content_hash": candidate["candidate_id"],
            "final_url": candidate["url"],
        }

    progress = []
    monkeypatch.setattr(builder, "_persist_candidate", persist)
    monkeypatch.setattr(
        builder,
        "_generate_and_persist_supplement",
        lambda **_kwargs: pytest.fail("web target already satisfies coverage"),
    )
    monkeypatch.setattr(builder, "update_job", lambda *args, **kwargs: None)

    builder.run_course_knowledge_plan_build_job(
        job_id="job-1",
        manager=FakeManager(),
        rag_system=object(),
        course_id="course-1",
        owner_user_id="teacher-1",
        build_id="kb-1",
        progress=lambda *args: progress.append(args),
    )

    assert crawled == ["source-topic-1-1", "source-topic-2-1"]
    assert any(item[1] == "indexing" for item in progress)


def test_ai_supplement_disabled_never_calls_model(monkeypatch):
    repository = FakeRepository()
    repository.build["config"]["ai_supplement_enabled"] = False
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
    monkeypatch.setattr(
        builder,
        "_generate_and_persist_supplement",
        lambda **_kwargs: pytest.fail("AI supplement must remain disabled"),
    )
    monkeypatch.setattr(builder, "update_job", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="content_sufficiency"):
        builder.run_course_knowledge_plan_build_job(
            job_id="job-1", manager=FakeManager(), rag_system=object(),
            course_id="course-1", owner_user_id="teacher-1", build_id="kb-1",
        )


def test_textbook_persistence_keeps_original_visible_and_groups_hidden_leaf_chunks(tmp_path):
    course_dir = tmp_path / "course-1"
    staged = course_dir / "inputs" / "original.md"
    staged.parent.mkdir(parents=True)
    staged.write_text("# 方程\n解方程", encoding="utf-8")

    class Manager:
        def __init__(self):
            self.index = []

        def get_course_dir(self, _course_id):
            return course_dir

        def get_knowledge_base_index(self, _course_id):
            return self.index

        def save_knowledge_base_file(self, _course_id, payload, filename, **metadata):
            target = course_dir / "knowledge_base" / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            relative = target.relative_to(course_dir).as_posix()
            self.index.append({"id": f"doc-{len(self.index) + 1}", "path": relative, **metadata})
            return relative

        def save_knowledge_base_index(self, _course_id, index):
            self.index = index

    class Rag:
        def import_document(self, _path, **_kwargs):
            return {"chunk_count": 1}

    manager = Manager()
    persisted = builder._persist_textbook_materials(
        manager=manager,
        rag_system=Rag(),
        course_id="course-1",
        owner_user_id="teacher-1",
        build={
            "build_id": "kb-1",
            "textbooks": [{
                "textbook_id": "book-1", "filename": "教材.md", "status": "ready",
                "relative_path": "inputs/original.md", "content_hash": "hash-book",
            }],
        },
        mapping_result={
            "mappings": [{
                "textbook_id": "book-1", "knowledge_node_id": "leaf-1",
                "chapter_title": "方程", "page": 3, "content": "解方程",
                "mapping_confidence": 1.0,
            }]
        },
    )

    assert [item["source_type"] for item in persisted] == ["textbook_original", "textbook"]
    original = next(item for item in manager.index if item["source_type"] == "textbook_original")
    mapped = next(item for item in manager.index if item["source_type"] == "textbook")
    assert original.get("display_in_library") is not False
    assert mapped["display_in_library"] is False
    assert mapped["textbook_mappings"][0]["page"] == 3


def test_online_pdf_is_saved_once_and_only_leaf_markdown_is_indexed(tmp_path):
    course_dir = tmp_path / "course-1"

    class Manager:
        def __init__(self):
            self.index = []

        def get_course_dir(self, _course_id):
            return course_dir

        def get_knowledge_base_index(self, _course_id):
            return self.index

        def save_knowledge_base_file(self, _course_id, payload, filename, **metadata):
            target = course_dir / "knowledge_base" / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            relative = target.relative_to(course_dir).as_posix()
            self.index.append({"id": f"doc-{len(self.index) + 1}", "path": relative, **metadata})
            return relative

        def save_knowledge_base_index(self, _course_id, index):
            self.index = index

    class Rag:
        def __init__(self):
            self.paths = []

        def import_document(self, path, **_kwargs):
            self.paths.append(path)
            return {"chunk_count": 2}

    rag = Rag()
    manager = Manager()
    persisted = builder._persist_textbook_materials(
        manager=manager,
        rag_system=rag,
        course_id="course-1",
        owner_user_id="teacher-1",
        build={
            "build_id": "kb-1",
            "textbooks": [],
            "online_textbooks": [{
                "textbook_id": "online-book",
                "filename": "线性代数教材.pdf",
                "status": "ready",
                "payload": b"%PDF-fixture",
                "content_hash": "online-hash",
                "source_url": "https://example.edu/linear-algebra.pdf",
                "retrieved_at": "2026-08-31T00:00:00+00:00",
                "parse_result": {"chunk_count": 2},
                "is_online_textbook": True,
            }],
        },
        mapping_result={"mappings": [
            {
                "textbook_id": "online-book", "knowledge_node_id": "leaf-1",
                "chapter_title": "向量空间", "content": "向量空间定义" * 500,
                "content_hash": "chapter-1", "mapping_confidence": 0.9,
            },
            {
                "textbook_id": "online-book", "knowledge_node_id": "leaf-2",
                "chapter_title": "矩阵", "content": "矩阵运算" * 500,
                "content_hash": "chapter-2", "mapping_confidence": 0.8,
            },
        ]},
    )

    assert [item["source_type"] for item in persisted] == [
        "textbook_original", "textbook", "textbook"
    ]
    assert len(rag.paths) == 2
    assert all(path.endswith(".md") for path in rag.paths)
    assert all(item["is_online_textbook"] for item in persisted[1:])
    assert all(item["source_artifact_id"] == "online-book" for item in persisted[1:])
    original = next(item for item in manager.index if item["source_type"] == "textbook_original")
    assert original["source_url"] == "https://example.edu/linear-algebra.pdf"


def test_textbook_first_build_searches_only_gap_and_retries_before_ai(monkeypatch):
    repository = FakeRepository()
    repository.build["config"].update(
        prefer_complete_textbooks=True,
        max_online_textbooks=1,
        max_search_rounds_per_leaf=2,
        target_materials_per_leaf=1,
        minimum_web_materials_per_leaf=0,
        maximum_ai_materials_per_leaf=1,
    )
    textbook_candidate = {
        "candidate_id": "course-book",
        "topic_id": None,
        "url": "https://example.edu/linear-algebra.pdf",
        "title": "线性代数完整教材",
        "selected": True,
        "review_status": "relevant",
        "metadata": {"content_format_hint": "pdf", "institutional_authority": True},
    }
    monkeypatch.setattr(builder, "get_postgres_knowledge_repository", lambda: repository)
    monkeypatch.setattr(
        builder,
        "discover_course_textbook_sources",
        lambda _build: {
            "source_candidates": [textbook_candidate],
            "warnings": [],
            "metrics": {"selected_textbook_count": 1},
        },
    )
    monkeypatch.setattr(
        builder,
        "_ingest_online_textbook_candidate",
        lambda _candidate: {
            "textbook_id": "online-book", "filename": "线性代数.pdf", "status": "ready",
            "source_url": textbook_candidate["url"], "content_hash": "book-hash",
            "parse_result": {"chunks": []}, "is_online_textbook": True,
        },
    )
    monkeypatch.setattr(
        builder,
        "map_textbook_chunks_to_graph",
        lambda _build: {"mappings": [], "unmapped": [], "metrics": {}},
    )
    monkeypatch.setattr(
        builder,
        "_persist_textbook_materials",
        lambda **_kwargs: [{
            "document_id": "book-leaf-1", "scope_id": "topic-1", "source_type": "textbook",
            "source_artifact_id": "online-book", "content_hash": "book-leaf-hash",
            "content_chars": 1200, "mapping_confidence": 0.9, "provenance_ok": True,
            "is_online_textbook": True, "chunk_count": 2,
        }],
    )
    searched = []

    def discover_gap(_build, *, topic_ids, round_index):
        searched.append((set(topic_ids), round_index))
        candidate = {
            "candidate_id": f"gap-{round_index}", "topic_id": "topic-2",
            "url": f"https://example.org/matrix-{round_index}", "selected": True,
            "review_status": "relevant", "metadata": {"search_round": round_index + 1},
        }
        return {
            "topics": repository.build["topics"], "source_candidates": [candidate],
            "warnings": [], "metrics": {"search_round": round_index + 1},
        }

    monkeypatch.setattr(builder, "discover_leaf_gap_sources", discover_gap)

    def persist(**kwargs):
        candidate = kwargs["candidate"]
        if candidate["candidate_id"] == "gap-0":
            raise RuntimeError("first round failed")
        return {
            "document_id": "web-topic-2", "scope_id": "topic-2", "source_type": "web",
            "source_url": candidate["url"], "final_url": candidate["url"],
            "content_hash": "web-hash", "content_chars": 900,
            "provenance_ok": True, "chunk_count": 1,
        }

    monkeypatch.setattr(builder, "_persist_candidate", persist)
    monkeypatch.setattr(
        builder,
        "_generate_and_persist_supplement",
        lambda **_kwargs: pytest.fail("second non-AI round filled the gap"),
    )
    monkeypatch.setattr(builder, "update_job", lambda *args, **kwargs: None)

    result = builder.run_course_knowledge_plan_build_job(
        job_id="job-1", manager=FakeManager(), rag_system=object(),
        course_id="course-1", owner_user_id="teacher-1", build_id="kb-1",
    )

    assert searched == [({"topic-2"}, 0), ({"topic-2"}, 1)]
    assert result["quality_score"] == 100
    assert repository.build["metrics"]["acquisition_order"] == [
        "textbook", "gap_web", "model_generated"
    ]


def test_textbook_first_build_calls_ai_only_after_all_search_rounds_exhausted(monkeypatch):
    repository = FakeRepository()
    repository.build["config"].update(
        prefer_complete_textbooks=True,
        max_online_textbooks=1,
        max_search_rounds_per_leaf=2,
        target_materials_per_leaf=1,
        minimum_web_materials_per_leaf=0,
        maximum_ai_materials_per_leaf=1,
    )
    monkeypatch.setattr(builder, "get_postgres_knowledge_repository", lambda: repository)
    monkeypatch.setattr(
        builder,
        "discover_course_textbook_sources",
        lambda _build: {"source_candidates": [], "warnings": [], "metrics": {}},
    )
    rounds = []

    def discover_gap(_build, *, topic_ids, round_index):
        rounds.append((set(topic_ids), round_index))
        return {
            "topics": repository.build["topics"],
            "source_candidates": [
                {
                    "candidate_id": f"gap-{round_index}-{topic_id}",
                    "topic_id": topic_id,
                    "url": f"https://example.org/{topic_id}/{round_index}",
                    "selected": True,
                    "review_status": "relevant",
                    "metadata": {"search_round": round_index + 1},
                }
                for topic_id in topic_ids
            ],
            "warnings": [],
            "metrics": {"search_round": round_index + 1},
        }

    monkeypatch.setattr(builder, "discover_leaf_gap_sources", discover_gap)
    monkeypatch.setattr(
        builder,
        "_persist_candidate",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("crawl failed")),
    )
    audits = []

    def generate(**kwargs):
        audit = kwargs["fallback_audit"]
        audits.append(audit)
        topic_id = kwargs["topic"]["topic_id"]
        return {
            "document_id": f"ai-{topic_id}", "scope_id": topic_id,
            "source_type": "model_generated", "content_hash": f"ai-{topic_id}",
            "content_chars": 900, "chunk_count": 1, "review_score": 90,
            "fallback_audit": audit,
        }

    monkeypatch.setattr(builder, "_generate_and_persist_supplement", generate)
    monkeypatch.setattr(builder, "update_job", lambda *args, **kwargs: None)

    result = builder.run_course_knowledge_plan_build_job(
        job_id="job-1", manager=FakeManager(), rag_system=object(),
        course_id="course-1", owner_user_id="teacher-1", build_id="kb-1",
    )

    assert rounds == [({"topic-1", "topic-2"}, 0), ({"topic-1", "topic-2"}, 1)]
    assert len(audits) == 2
    assert all(item["fallback_reason"] == "non_ai_search_exhausted" for item in audits)
    assert all(item["non_ai_attempt_count"] == 2 for item in audits)
    assert result["quality_score"] == 100


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
                    "learning_artifacts": [{
                        "requirement_id": "req-case",
                        "topic_id": "topic-1",
                        "type": "worked_case",
                        "count": 1,
                        "validation_status": "passed",
                    }],
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
            "learning_artifacts": [{
                "requirement_id": "req-case",
                "topic_id": "topic-1",
                "type": "worked_case",
                "count": 1,
                "validation_status": "passed",
            }],
        }
    ]


def test_retry_only_resumes_generated_documents_from_the_same_build():
    class ManagerWithTwoBuilds:
        def get_knowledge_base_index(self, _course_id):
            return [
                {
                    "id": "older",
                    "scope_id": "topic-1",
                    "source_type": "model_generated",
                    "generation_review_score": 95,
                    "generation_audit": {"build_id": "kb-old"},
                    "status": "received",
                },
                {
                    "id": "current",
                    "scope_id": "topic-1",
                    "source_type": "model_generated",
                    "generation_review_score": 92,
                    "generation_audit": {"build_id": "kb-current"},
                    "status": "received",
                },
            ]

    resumed = builder._reviewed_generated_documents(
        ManagerWithTwoBuilds(),
        course_id="course-1",
        scope_id="topic-1",
        limit=2,
        build_id="kb-current",
    )

    assert [item["document_id"] for item in resumed] == ["current"]


def test_required_artifacts_schedule_one_reviewed_generation_when_ai_is_allowed():
    topic = {
        "topic_id": "cgroups",
        "deliverables": [
            {
                "requirement_id": "req-exercises",
                "type": "exercise_with_solution",
                "count": 3,
                "hardness": "hard",
            }
        ],
        "source_policy": {"allow_ai_fallback": True},
    }
    deficits = []

    builder._ensure_required_artifact_generation(
        deficits,
        topics=[topic],
        persisted=[{
            "learning_artifacts": [{
                "requirement_id": "req-exercises",
                "type": "exercise_with_solution",
                "count": 1,
                "validation_status": "passed",
            }]
        }],
        ai_enabled=True,
        maximum_ai=1,
    )

    assert len(deficits) == 1
    assert deficits[0][0]["artifact_generation_only"] is True
    assert deficits[0][1] == 1


def test_topic_scoped_artifacts_schedule_each_uncovered_topic():
    topics = [
        {
            "topic_id": topic_id,
            "deliverables": [{
                "requirement_id": "req-case",
                "type": "worked_case",
                "count": 1,
                "hardness": "hard",
                "application": "topic",
            }],
            "source_policy": {"allow_ai_fallback": True},
        }
        for topic_id in ("process", "memory")
    ]
    deficits = []

    builder._ensure_required_artifact_generation(
        deficits,
        topics=topics,
        persisted=[],
        ai_enabled=True,
        maximum_ai=1,
    )

    assert [item[0]["topic_id"] for item in deficits] == ["process", "memory"]


def test_builder_publishes_requested_artifacts_only_after_requirement_ids_pass(monkeypatch):
    repository = FakeRepository()
    repository.build["config"].update(
        target_materials_per_leaf=1,
        minimum_web_materials_per_leaf=1,
        maximum_ai_materials_per_leaf=1,
    )
    repository.build["intent_contract"] = {
        "source_policy": {"allow_ai_fallback": True},
        "deliverables": [{
            "requirement_id": "req-case",
            "type": "worked_case",
            "count": 1,
            "hardness": "hard",
        }],
    }
    monkeypatch.setattr(builder, "get_postgres_knowledge_repository", lambda: repository)
    monkeypatch.setattr(
        builder,
        "discover_course_knowledge_sources",
        lambda build: {
            "topics": builder.execution_topics(build),
            "source_candidates": [
                {
                    **item,
                    "review_status": "relevant",
                    "metadata": {"query": "official source"},
                }
                for item in repository.build["source_candidates"]
            ],
            "warnings": [],
            "metrics": {"leaf_count": 2, "candidate_count": 2},
        },
    )
    monkeypatch.setattr(
        builder,
        "_persist_candidate",
        lambda **kwargs: {
            "document_id": kwargs["candidate"]["candidate_id"],
            "scope_id": kwargs["candidate"]["topic_id"],
            "source_url": kwargs["candidate"]["url"],
            "content_hash": kwargs["candidate"]["candidate_id"],
            "content_chars": 1200,
            "chunk_count": 2,
            "final_url": kwargs["candidate"]["url"],
            "source_type": "web",
        },
    )
    generated = []

    def generate(**kwargs):
        generated.append(kwargs)
        return {
            "document_id": "artifact-doc",
            "scope_id": kwargs["topic"]["topic_id"],
            "source_url": "",
            "source_type": "model_generated",
            "content_hash": "artifact-hash",
            "content_chars": 1400,
            "chunk_count": 2,
            "review_score": 94,
            "learning_artifacts": [{
                "requirement_id": "req-case",
                "type": "worked_case",
                "count": 1,
                "validation_status": "passed",
            }],
        }

    monkeypatch.setattr(builder, "_generate_and_persist_supplement", generate)
    monkeypatch.setattr(builder, "update_job", lambda *args, **kwargs: None)

    result = builder.run_course_knowledge_plan_build_job(
        job_id="job-1",
        manager=FakeManager(),
        rag_system=object(),
        course_id="course-1",
        owner_user_id="teacher-1",
        build_id="kb-1",
    )

    assert repository.build["status"] == "succeeded"
    assert result["quality_score"] == 100
    assert len(generated) == 1
    assert generated[0]["sequence"] == 1
    assert generated[0]["topic"]["deliverables"][0]["requirement_id"] == "req-case"


def test_satisfied_artifact_requirement_does_not_schedule_duplicate_generation():
    topic = {
        "topic_id": "cgroups",
        "deliverables": [
            {
                "requirement_id": "req-exercises",
                "type": "exercise_with_solution",
                "count": 3,
                "hardness": "hard",
            }
        ],
        "source_policy": {"allow_ai_fallback": True},
    }
    deficits = []

    builder._ensure_required_artifact_generation(
        deficits,
        topics=[topic],
        persisted=[{
            "learning_artifacts": [{
                "requirement_id": "req-exercises",
                "type": "exercise_with_solution",
                "count": 3,
                "validation_status": "passed",
            }]
        }],
        ai_enabled=True,
        maximum_ai=1,
    )

    assert deficits == []


def test_reviewed_artifact_is_resumed_after_textbooks_fill_numeric_deficit():
    topic = {
        "topic_id": "scheduling",
        "deliverables": [{
            "requirement_id": "req-case",
            "type": "worked_case",
            "count": 1,
            "hardness": "hard",
            "application": "topic",
        }],
        "source_policy": {"allow_ai_fallback": True},
    }

    assert builder._reviewed_generation_resume_limit(
        topic,
        ai_budget=0,
        ai_enabled=True,
        maximum_ai=1,
    ) == 1


def test_extract_page_accepts_missing_license_and_uses_linked_section(monkeypatch):
    class Response:
        headers = {"content-type": "text/html; charset=utf-8"}
        url = "https://docs.python.org/zh-cn/3/tutorial/controlflow.html#if-statements"
        encoding = "utf-8"
        text = """
        <html><head><title>Python manual</title></head><body><main>
          <section id="unrelated"><h2>Unrelated</h2><p>{unrelated}</p></section>
          <section id="if-statements"><h2>if 语句</h2><p>{target}</p></section>
        </main></body></html>
        """.format(unrelated="unrelated text " * 80, target="条件判断 if elif else 示例 " * 40)

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield self.text.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Client:
        def stream(self, _method, _url):
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
