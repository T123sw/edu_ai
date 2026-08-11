"""P2-5 编排单测：RAG Top-K 检索（course 知识库收窄+优雅降级）、
researchContext 合并、以及端到端 generate_classroom_for_course（成功/校验
失败两条完成语义分支）。
"""

import sys
import uuid
from types import SimpleNamespace
from pathlib import Path

import anyio
import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

pytestmark = pytest.mark.anyio

from core.course_storage import CourseStorageManager
from app.services.job_store import JobStatus, get_job
from app.services.classroom_service import (
    fetch_course_rag_snippets,
    merge_research_context,
    generate_classroom_for_course,
    submit_classroom_generation_job,
)


@pytest.fixture(autouse=True)
def _isolate_job_storage(monkeypatch, tmp_path):
    """job_store.py 写 Config.STORAGE_ROOT/jobs，跟 CourseStorageManager 各自
    独立的 root_path 无关——不隔离会一直污染真实项目的 storage/jobs/
    （已实测发现：之前的测试运行留下了几十个 job_*.json 在真实目录里）。"""
    from core import Config
    from app.chat.tasks.task_store import TaskStore

    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path / f"jobs-{uuid.uuid4().hex}")
    task_store = TaskStore(str(tmp_path / f"tasks-{uuid.uuid4().hex}.db"))
    monkeypatch.setattr(
        "app.services.platform_task_handlers.get_task_store",
        lambda: task_store,
    )
    yield task_store
    task_store.close()


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
    """Models the real two-step completion flow (SPEC-04 §1.2 订正): the job
    envelope's `result` is only `{classroomId, url, scenesCount}` — the full
    `{id, stage, scenes, createdAt}` requires a separate `get_classroom` call.
    """

    def __init__(self, *, final_status="succeeded", stage_id="stage-1", with_audio=False):
        self.final_status = final_status
        self.stage_id = stage_id
        self.with_audio = with_audio
        self.submitted_body = {}
        self.get_classroom_calls: list[str] = []
        self.download_media_calls: list[str] = []
        self.synthesize_tts_calls: list[dict] = []
        # `migrate_classroom_speech_audio` reads `.config.base_url` unconditionally
        # (to know which audioUrl prefix counts as "still points at sidecar").
        self.config = SimpleNamespace(base_url="http://sidecar-test:3000")

    async def download_media(self, url: str):
        self.download_media_calls.append(url)
        return b"fake-audio-bytes", "audio/mpeg"

    async def synthesize_tts(self, **kwargs):
        self.synthesize_tts_calls.append(kwargs)
        return b"shared-tts-bytes", "mp3"

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
                    "classroomId": self.stage_id,
                    "url": "http://sidecar-test:3000/classroom/stage-1",
                    "scenesCount": 1,
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

    async def get_classroom(self, classroom_id: str) -> dict:
        self.get_classroom_calls.append(classroom_id)
        speech_action = {"id": "act-1", "type": "speech", "text": "hi"}
        if self.with_audio:
            speech_action["audioId"] = "tts_s1_act-1"
            speech_action["audioUrl"] = "http://sidecar-test:3000/api/classroom-media/stage-1/audio/tts_s1_act-1.mp3"
        return {
            "id": self.stage_id,
            "url": "http://sidecar-test:3000/classroom/stage-1",
            "createdAt": "2026-07-24T00:00:00.000Z",
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
                    "actions": [speech_action],
                }
            ],
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
    assert job.result_ref == {
        "classroom_id": "stage-1",
        "course_id": "course-1",
        "scenes_count": 1,
        "resource_type": "course_material",
        "material_type": "classroom",
        "material_id": "stage-1",
    }
    assert client.submitted_body["research_context"] == "web snippet\n\n[来源: textbook.pdf]\nRAG snippet"
    assert client.get_classroom_calls == ["stage-1"]  # job.result.classroomId -> get_classroom(id)
    assert client.synthesize_tts_calls == [
        {
            "text": "hi",
            "audio_id": "act-1",
            "provider_id": "qwen-tts",
            "voice": "Cherry",
            "speed": 1.0,
        }
    ]

    saved = manager.get_generated_material(
        "course-1", "classroom", "stage-1", owner_user_id="teacher-a"
    )
    assert saved is not None
    assert saved["title"] == "Compound Interest"


async def test_generate_classroom_for_course_migrates_tts_audio_before_persisting(monkeypatch):
    """D1（SPEC-04 §5）：sidecar 回填的 audioUrl 必须先搬到 edu_ai 自己的
    存储、改写成 edu_ai 地址，落库的数据里不能再出现 sidecar 的临时地址
    （否则 SPEC-02 §6 不变量 5 会拒绝落库，见 classroom_validation）。"""
    manager = _make_manager()
    monkeypatch.setattr(
        "app.services.classroom_service.fetch_course_rag_snippets", lambda **kwargs: None
    )
    client = FakeClient(with_audio=True)

    job = await generate_classroom_for_course(
        course_id="course-1",
        requirement="Teach compound interest",
        owner="teacher-a",
        course_storage_manager=manager,
        client=client,
    )

    assert job.status == JobStatus.SUCCEEDED
    assert client.download_media_calls == [
        "http://sidecar-test:3000/api/classroom-media/stage-1/audio/tts_s1_act-1.mp3"
    ]

    saved = manager.get_generated_material(
        "course-1", "classroom", "stage-1", owner_user_id="teacher-a"
    )
    assert saved is not None
    migrated_url = saved["scenes"][0]["actions"][0]["audioUrl"]
    assert migrated_url == "/api/courses/course-1/classrooms/stage-1/audio/tts_s1_act-1.mp3"

    audio_dir = manager.get_classroom_audio_dir("course-1", "stage-1")
    assert (audio_dir / "tts_s1_act-1.mp3").read_bytes() == b"fake-audio-bytes"


async def test_generate_classroom_for_course_merges_knowledge_graph_as_third_layer(monkeypatch):
    """web + RAG + 知识图谱三路都命中时，三段都要出现在最终 researchContext 里
    （Phase 2.5/D4：知识图谱是新加的第三路，不能顶掉/短路前两路）。"""
    manager = _make_manager()
    manager.get_course_dir("course-1").mkdir(parents=True, exist_ok=True)
    (manager.get_course_dir("course-1") / "knowledge_graph.json").write_text(
        '{"id":"root","label":"Finance","data":{},'
        '"children":[{"id":"n1","label":"Compound interest","data":{"hours":2},"children":[]}]}',
        encoding="utf-8",
    )
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
    assert client.submitted_body["research_context"] == (
        "web snippet\n\n[来源: textbook.pdf]\nRAG snippet"
        "\n\n[知识图谱] Finance > Compound interest（课时 2 学时）"
    )


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


# ── submit_classroom_generation_job（异步提交，P3-2） ───────────────────
#
# asyncio.create_task 内部要求一个真正在跑的 asyncio 事件循环——trio backend
# 下会直接报错（同一类问题这个会话里已经踩过两次：asyncio.sleep/to_thread）。
# 这次刻意不改用 anyio 的结构化并发（TaskGroup 的 async with 生命周期会等
# 子任务跑完才退出，正好违背"提交立即返回"的本意），因为生产环境
# （uvicorn）本来就只跑 asyncio，不会真的遇到 trio——所以用
# `anyio_backend` 参数化把这两条测试限定在 asyncio-only，而不是假装两个
# backend 都要支持。


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_submit_classroom_generation_job_persists_recoverable_command(
    monkeypatch,
    _isolate_job_storage,
):
    manager = _make_manager()
    monkeypatch.setattr(
        "app.services.classroom_service.fetch_course_rag_snippets", lambda **kwargs: None
    )
    client = FakeClient()

    job = await submit_classroom_generation_job(
        course_id="course-1",
        requirement="Teach compound interest",
        owner="teacher-a",
        course_storage_manager=manager,
        client=client,
    )

    assert job.status == JobStatus.QUEUED
    durable = _isolate_job_storage.get_durable(job.edu_job_id)
    assert durable is not None
    assert durable.status == "pending"
    assert durable.workflow_type == "classroom_generate"
    assert durable.command["requirement"] == "Teach compound interest"
    assert client.get_classroom_calls == []


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_submit_classroom_generation_job_does_not_depend_on_request_client(
    monkeypatch,
    _isolate_job_storage,
):
    manager = _make_manager()
    monkeypatch.setattr(
        "app.services.classroom_service.fetch_course_rag_snippets", lambda **kwargs: None
    )
    client = FakeClient(final_status="failed")

    job = await submit_classroom_generation_job(
        course_id="course-1",
        requirement="Teach compound interest",
        owner="teacher-a",
        course_storage_manager=manager,
        client=client,
    )

    durable = _isolate_job_storage.get_durable(job.edu_job_id)
    assert durable is not None
    assert durable.status == "pending"
    assert "client" not in durable.command
    assert client.submitted_body == {}


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_submit_classroom_generation_job_reuses_idempotent_agent_request(
    monkeypatch,
    _isolate_job_storage,
):
    manager = _make_manager()
    monkeypatch.setattr(
        "app.services.classroom_service.fetch_course_rag_snippets", lambda **kwargs: None
    )

    first = await submit_classroom_generation_job(
        course_id="course-1", requirement="Teach compound interest", owner="teacher-a",
        course_storage_manager=manager, client=FakeClient(), idempotency_key="agent-classroom-1",
    )
    second = await submit_classroom_generation_job(
        course_id="course-1", requirement="Teach compound interest", owner="teacher-a",
        course_storage_manager=manager, client=FakeClient(), idempotency_key="agent-classroom-1",
    )

    assert second.edu_job_id == first.edu_job_id
