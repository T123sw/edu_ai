"""P2-5 编排单测：RAG Top-K 检索（course 知识库收窄+优雅降级）、
researchContext 合并、以及端到端 generate_classroom_for_course（成功/校验
失败两条完成语义分支）。
"""

import sys
import uuid
from types import SimpleNamespace
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

pytestmark = pytest.mark.anyio

from core.course_storage import CourseStorageManager
from app.services.job_store import JobStatus
from app.services.classroom_service import (
    fetch_course_rag_snippets,
    merge_research_context,
    generate_classroom_for_course,
)


def _make_manager() -> CourseStorageManager:
    root = Path("tests/.tmp") / f"classroom-service-{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    manager = CourseStorageManager(root_path=str(root))
    manager.create_course_structure("course-1")
    manager.save_course_info("course-1", {"id": "course-1", "title": "course"})
    return manager


class FakeRagSystem:
    def __init__(self, *, chunks=None):
        self.chunks = chunks if chunks is not None else [
            {"document": "复利公式是本金乘以增长因子。", "metadata": {"source": "textbook.pdf"}},
        ]
        self.embedding_client = SimpleNamespace(embed_query=lambda q: [0.1, 0.2, 0.3])
        self.vector_store = SimpleNamespace(hybrid_search=self._hybrid_search)
        self.hybrid_search_calls = []

    def _hybrid_search(self, *, query, query_embedding, top_k, allowed_sources):
        self.hybrid_search_calls.append(
            {"query": query, "top_k": top_k, "allowed_sources": allowed_sources}
        )
        return self.chunks


# ── merge_research_context ───────────────────────────────────────────────


def test_merge_research_context_joins_both_parts():
    assert merge_research_context("web part", "rag part") == "web part\n\nrag part"


def test_merge_research_context_skips_empty_parts():
    assert merge_research_context("", "rag part") == "rag part"
    assert merge_research_context(None, None) is None
    assert merge_research_context("   ", None) is None


# ── fetch_course_rag_snippets ─────────────────────────────────────────────


def test_fetch_rag_snippets_returns_none_when_course_has_no_kb_docs():
    manager = _make_manager()
    rag_system = FakeRagSystem()

    result = fetch_course_rag_snippets(
        course_storage_manager=manager, course_id="course-1", query="复利", rag_system=rag_system
    )

    assert result is None
    assert rag_system.hybrid_search_calls == []  # 没有课程文档，压根不该发起检索


def test_fetch_rag_snippets_returns_none_when_docs_dont_resolve(monkeypatch):
    manager = _make_manager()
    manager.save_knowledge_base_index("course-1", [{"id": "doc-1", "path": "foo.pdf"}])
    rag_system = FakeRagSystem()

    monkeypatch.setattr(
        "modules.rag_v2.document_resolver.resolve_rag_document",
        lambda rag_system, document_id, owner=None: None,
    )

    result = fetch_course_rag_snippets(
        course_storage_manager=manager, course_id="course-1", query="复利", rag_system=rag_system
    )

    assert result is None
    assert rag_system.hybrid_search_calls == []


def test_fetch_rag_snippets_formats_chunks_with_source_when_docs_resolve(monkeypatch):
    manager = _make_manager()
    manager.save_knowledge_base_index("course-1", [{"id": "doc-1", "path": "foo.pdf"}])
    rag_system = FakeRagSystem()

    monkeypatch.setattr(
        "modules.rag_v2.document_resolver.resolve_rag_document",
        lambda rag_system, document_id, owner=None: SimpleNamespace(source_key="source::foo.pdf"),
    )

    result = fetch_course_rag_snippets(
        course_storage_manager=manager, course_id="course-1", query="复利公式", top_k=3, rag_system=rag_system
    )

    assert result == "[来源: textbook.pdf]\n复利公式是本金乘以增长因子。"
    assert rag_system.hybrid_search_calls == [
        {"query": "复利公式", "top_k": 3, "allowed_sources": ["source::foo.pdf"]}
    ]


def test_fetch_rag_snippets_returns_none_when_hybrid_search_empty(monkeypatch):
    manager = _make_manager()
    manager.save_knowledge_base_index("course-1", [{"id": "doc-1", "path": "foo.pdf"}])
    rag_system = FakeRagSystem(chunks=[])

    monkeypatch.setattr(
        "modules.rag_v2.document_resolver.resolve_rag_document",
        lambda rag_system, document_id, owner=None: SimpleNamespace(source_key="source::foo.pdf"),
    )

    result = fetch_course_rag_snippets(
        course_storage_manager=manager, course_id="course-1", query="x", rag_system=rag_system
    )
    assert result is None


def test_fetch_rag_snippets_swallows_exceptions_and_returns_none(monkeypatch):
    manager = _make_manager()
    manager.save_knowledge_base_index("course-1", [{"id": "doc-1", "path": "foo.pdf"}])

    class ExplodingRagSystem(FakeRagSystem):
        def _hybrid_search(self, **kwargs):
            raise RuntimeError("vector store unavailable")

    monkeypatch.setattr(
        "modules.rag_v2.document_resolver.resolve_rag_document",
        lambda rag_system, document_id, owner=None: SimpleNamespace(source_key="source::foo.pdf"),
    )

    result = fetch_course_rag_snippets(
        course_storage_manager=manager,
        course_id="course-1",
        query="x",
        rag_system=ExplodingRagSystem(),
    )
    assert result is None


# ── generate_classroom_for_course（端到端编排） ──────────────────────────


class FakeClient:
    def __init__(self, *, final_status="succeeded", stage_id="stage-1"):
        self.final_status = final_status
        self.stage_id = stage_id
        self.submitted_body = {}

    async def generate_classroom(self, **kwargs):
        self.submitted_body = kwargs
        return {
            "jobId": "sidecar-job-1",
            "status": "queued",
            "step": "initializing",
            "message": "Queued",
            "pollUrl": "http://sidecar-test:3000/api/generate-classroom/sidecar-job-1",
            "pollIntervalMs": 5000,
        }

    async def wait_job(self, poll_url, *, on_progress=None):
        if self.final_status == "succeeded":
            return {
                "jobId": "sidecar-job-1",
                "status": "succeeded",
                "step": "completed",
                "progress": 100,
                "message": "Done",
                "pollUrl": poll_url,
                "pollIntervalMs": 5000,
                "done": True,
                "result": {
                    "id": self.stage_id,
                    "url": "http://sidecar-test:3000/classroom/stage-1",
                    "createdAt": "2026-07-24T00:00:00.000Z",
                    "scenesCount": 1,
                    "stage": {"id": self.stage_id, "name": "Compound Interest"},
                    "scenes": [
                        {
                            "id": "scene-1",
                            "type": "slide",
                            "content": {
                                "type": "slide",
                                "canvas": {
                                    "id": "slide-1",
                                    "viewportRatio": 0.5625,
                                    "elements": [{"id": "el-1", "type": "text"}],
                                },
                            },
                            "actions": [{"id": "act-1", "type": "speech", "text": "hi"}],
                        }
                    ],
                },
            }
        return {
            "jobId": "sidecar-job-1",
            "status": "failed",
            "step": "failed",
            "message": "sidecar failed",
            "pollUrl": poll_url,
            "pollIntervalMs": 5000,
            "done": True,
            "error": "LLM error",
        }


async def test_generate_classroom_for_course_merges_context_and_persists_on_success(monkeypatch):
    manager = _make_manager()
    monkeypatch.setattr(
        "app.services.classroom_service.fetch_course_rag_snippets",
        lambda **kwargs: "[来源: textbook.pdf]\nRAG snippet",
    )
    client = FakeClient()

    job = await generate_classroom_for_course(
        course_id="course-1",
        requirement="Teach compound interest",
        owner="teacher-a",
        course_storage_manager=manager,
        web_research_context="web snippet",
        client=client,
    )

    assert job.status == JobStatus.SUCCEEDED
    assert job.result_ref == {"classroom_id": "stage-1", "course_id": "course-1", "scenes_count": 1}
    assert client.submitted_body["research_context"] == "web snippet\n\n[来源: textbook.pdf]\nRAG snippet"

    saved = manager.get_generated_material("course-1", "classroom", "stage-1")
    assert saved is not None
    assert saved["title"] == "Compound Interest"


async def test_generate_classroom_for_course_marks_validation_failed_on_bad_stage(monkeypatch):
    manager = _make_manager()
    monkeypatch.setattr(
        "app.services.classroom_service.fetch_course_rag_snippets", lambda **kwargs: None
    )
    client = FakeClient(stage_id="")  # Stage.id 缺失 → 校验失败

    job = await generate_classroom_for_course(
        course_id="course-1",
        requirement="Teach compound interest",
        owner="teacher-a",
        course_storage_manager=manager,
        client=client,
    )

    assert job.status == JobStatus.FAILED
    assert job.error_code == "VALIDATION_FAILED"


async def test_generate_classroom_for_course_marks_internal_error_when_sidecar_fails(monkeypatch):
    manager = _make_manager()
    monkeypatch.setattr(
        "app.services.classroom_service.fetch_course_rag_snippets", lambda **kwargs: None
    )
    client = FakeClient(final_status="failed")

    job = await generate_classroom_for_course(
        course_id="course-1",
        requirement="Teach compound interest",
        owner="teacher-a",
        course_storage_manager=manager,
        client=client,
    )

    assert job.status == JobStatus.FAILED
    assert job.error == "LLM error"
