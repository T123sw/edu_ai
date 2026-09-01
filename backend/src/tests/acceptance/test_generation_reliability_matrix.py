from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.chat.api.routes_v2 import router as chat_router
from app.chat.tasks.task_store import TaskStore
from app.services.classroom_job_service import create_classroom_job
from app.services.classroom_persistence import persist_classroom_result
from app.services.durable_executor_pool import DurableExecutorPool
from app.services.durable_task_handlers import (
    DurableExecutionContext,
    DurableTaskHandlerRegistry,
)
from app.services.generation_command import (
    GenerationCommand,
    GenerationCommandService,
)
from app.services.generation_source_errors import GenerationSourceError
from app.services.generation_source_resolver import (
    GenerationSourceResolver,
    SourceDocumentRecord,
)
from app.services.generation_task_handlers import (
    GenerationTaskHandler,
    register_generation_task_handlers,
)
from app.services.job_completion_service import JobCompletionService
from app.services.job_store import JobStatus, get_job, update_job
from app.services.platform_task_handlers import PlatformTaskHandlers
from core.course_storage import CourseStorageManager
from tests.acceptance.fake_generation_providers import (
    FakeDocumentCatalog,
    FakeDocumentContentReader,
    NoNetworkGenerationProvider,
    fake_classroom_result,
)


@dataclass(frozen=True)
class ResourceCase:
    resource_type: str
    path: str


RESOURCE_CASES = (
    ResourceCase("report", "/api/chat/v2/report/direct"),
    ResourceCase("lesson_plan", "/api/chat/v2/lesson-plan/direct"),
    ResourceCase("blog", "/api/chat/v2/blog/direct"),
    ResourceCase("quiz", "/api/chat/v2/quiz/direct"),
    ResourceCase("flashcard", "/api/chat/v2/flashcard/direct"),
    ResourceCase("graph", "/api/chat/v2/graph/direct"),
    ResourceCase("game", "/api/chat/v2/game/direct"),
    ResourceCase("classroom", "/api/courses/c1/classrooms/generate"),
)

SOURCE_CASES = (
    ("course_auto", []),
    ("selected_documents", ["doc-1"]),
    ("none", []),
)


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    original_connect = socket.socket.connect

    def deny_network(active_socket, address):
        host = str(address[0]) if isinstance(address, tuple) and address else ""
        if host in {"127.0.0.1", "::1"}:
            return original_connect(active_socket, address)
        raise AssertionError("acceptance tests must not use live network")

    monkeypatch.setattr(socket.socket, "connect", deny_network)


def build_source_resolver():
    catalog = FakeDocumentCatalog(
        [
            SourceDocumentRecord(
                course_id="c1",
                document_id="doc-1",
                name="Mechanics.pdf",
                status="ready",
                rag_index_key="rag-mechanics",
                chunk_count=12,
            ),
            SourceDocumentRecord(
                course_id="c2",
                document_id="doc-wrong-course",
                name="Other.pdf",
                status="ready",
                rag_index_key="rag-other",
                chunk_count=5,
            ),
        ]
    )
    reader = FakeDocumentContentReader(
        {
            "rag-mechanics": "Newton's laws course evidence",
            "rag-other": "Evidence from another course",
        }
    )
    return GenerationSourceResolver(
        catalog,
        reader,
        clock=lambda: datetime(2026, 8, 7, tzinfo=timezone.utc),
    )


def durable_context(task_id: str) -> DurableExecutionContext:
    return DurableExecutionContext(
        task_id=task_id,
        owner_user_id="teacher-a",
        course_id="c1",
        config_snapshot_id="cfg-acceptance",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )


def assert_material(
    manager: CourseStorageManager,
    *,
    material_type: str,
    material_id: str,
    source_mode: str,
):
    material = manager.get_generated_material(
        "c1",
        material_type,
        material_id,
        owner_user_id="teacher-a",
    )
    assert material is not None
    assert manager.get_generated_material(
        "c1",
        material_type,
        material_id,
        owner_user_id="teacher-b",
    ) is None
    assert material["source_snapshot"]["mode"] == source_mode
    assert material["source_job_id"]
    if source_mode == "none":
        assert material["source_snapshot"]["documents"] == []
    else:
        assert material["source_snapshot"]["documents"][0][
            "document_id"
        ] == "doc-1"
    return material


@pytest.mark.parametrize("case", RESOURCE_CASES, ids=lambda item: item.resource_type)
@pytest.mark.parametrize("source_mode,selected_doc_ids", SOURCE_CASES)
def test_generation_reliability_source_matrix(
    case,
    source_mode,
    selected_doc_ids,
    tmp_path,
    monkeypatch,
):
    manager = CourseStorageManager(root_path=str(tmp_path / "courses"))
    manager.create_course_structure("c1")
    manager.create_course_structure("c2")
    resolver = build_source_resolver()

    if case.resource_type == "classroom":
        _run_classroom_case(
            manager=manager,
            resolver=resolver,
            source_mode=source_mode,
            selected_doc_ids=selected_doc_ids,
            monkeypatch=monkeypatch,
        )
        material_id = "classroom-acceptance"
    else:
        provider = NoNetworkGenerationProvider(case.resource_type)
        handler = GenerationTaskHandler(
            course_storage_manager=manager,
            source_resolver=resolver,
            service_factories={case.resource_type: lambda: provider},
        )
        material_id = f"{case.resource_type}-{source_mode}"
        result = handler.handle(
            {
                "resource_type": case.resource_type,
                "course_id": "c1",
                "scope_type": "course",
                "source_mode": source_mode,
                "selected_doc_ids": selected_doc_ids,
                "config": {"title": f"{case.resource_type} acceptance"},
                "material_id": material_id,
            },
            durable_context(f"job-{case.resource_type}-{source_mode}"),
        )
        assert result["saved"] is True
        assert len(provider.calls) == 1
        if source_mode == "none":
            assert provider.calls[0]["source_context"] == ""
        else:
            assert "course evidence" in provider.calls[0]["source_context"]

        calls_before_wrong_course = len(provider.calls)
        with pytest.raises(
            GenerationSourceError,
            match="doc-wrong-course",
        ) as exc_info:
            handler.handle(
                {
                    "resource_type": case.resource_type,
                    "course_id": "c1",
                    "source_mode": "selected_documents",
                    "selected_doc_ids": ["doc-wrong-course"],
                    "config": {},
                    "material_id": f"{material_id}-wrong",
                },
                durable_context(f"job-{case.resource_type}-wrong"),
            )
        assert exc_info.value.code == "SOURCE_DOCUMENT_WRONG_COURSE"
        assert len(provider.calls) == calls_before_wrong_course

    assert case.path in _registered_generation_paths()
    assert_material(
        manager,
        material_type=case.resource_type,
        material_id=material_id,
        source_mode=source_mode,
    )


def _registered_generation_paths() -> set[str]:
    paths = {route.path for route in chat_router.routes}
    paths.add("/api/courses/c1/classrooms/generate")
    return paths


def _run_classroom_case(
    *,
    manager,
    resolver,
    source_mode,
    selected_doc_ids,
    monkeypatch,
):
    job = create_classroom_job(owner="teacher-a", course_id="c1")

    class FakeClient:
        pass

    monkeypatch.setattr(
        "app.integrations.openmaic.get_openmaic_client",
        lambda owner_user_id=None, **_kwargs: FakeClient(),
    )

    def fake_callback(**kwargs):
        async def persist(_result):
            persist_classroom_result(
                course_storage_manager=manager,
                course_id="c1",
                owner="teacher-a",
                result=fake_classroom_result("classroom-acceptance"),
                source_snapshot=kwargs["source_snapshot"],
                source_job_id=kwargs["source_job_id"],
            )
            return {
                "resource_type": "course_material",
                "course_id": "c1",
                "material_type": "classroom",
                "material_id": "classroom-acceptance",
            }

        return persist

    async def fake_run(active_job, **kwargs):
        result_ref = await kwargs["on_sidecar_succeeded"](
            {"classroomId": "classroom-acceptance"}
        )
        return update_job(
            active_job.edu_job_id,
            status=JobStatus.SUCCEEDED,
            result_ref=result_ref,
        )

    monkeypatch.setattr(
        "app.services.classroom_service._make_on_sidecar_succeeded",
        fake_callback,
    )
    monkeypatch.setattr(
        "app.services.classroom_job_service.run_generate_classroom_job",
        fake_run,
    )
    handler = PlatformTaskHandlers(
        course_storage_factory=lambda: manager,
        generation_source_resolver_factory=lambda _manager: resolver,
    )
    result = handler.classroom_generate(
        {
            "course_id": "c1",
            "requirement": "Teach Newton's laws",
            "source_mode": source_mode,
            "selected_doc_ids": selected_doc_ids,
            "enable_tts": False,
        },
        durable_context(job.edu_job_id),
    )
    assert result["saved"] is True

    with pytest.raises(GenerationSourceError) as exc_info:
        handler.classroom_generate(
            {
                "course_id": "c1",
                "requirement": "Wrong course",
                "source_mode": "selected_documents",
                "selected_doc_ids": ["doc-wrong-course"],
            },
            durable_context(job.edu_job_id),
        )
    assert exc_info.value.code == "SOURCE_DOCUMENT_WRONG_COURSE"


def _wait_for_terminal(task_store, task_ids, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        tasks = [task_store.get_durable(task_id) for task_id in task_ids]
        if all(task and task.status in {"succeeded", "failed", "canceled"} for task in tasks):
            return tasks
        time.sleep(0.01)
    return [task_store.get_durable(task_id) for task_id in task_ids]


def test_blocked_blog_isolated_from_quiz_flashcard_and_cancelled(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.job_store.Config.STORAGE_ROOT",
        tmp_path / "jobs",
    )
    manager = CourseStorageManager(root_path=str(tmp_path / "courses"))
    manager.create_course_structure("c1")
    store = TaskStore(str(tmp_path / "tasks.db"))
    entered = threading.Event()
    release = threading.Event()
    providers = {
        "blog": NoNetworkGenerationProvider(
            "blog",
            entered=entered,
            release=release,
        ),
        "quiz": NoNetworkGenerationProvider("quiz"),
        "flashcard": NoNetworkGenerationProvider("flashcard"),
    }
    handler = GenerationTaskHandler(
        course_storage_manager=manager,
        source_resolver=build_source_resolver(),
        service_factories={
            resource_type: (lambda provider=provider: provider)
            for resource_type, provider in providers.items()
        },
    )
    registry = DurableTaskHandlerRegistry()
    register_generation_task_handlers(registry, handler=handler)
    pool = DurableExecutorPool(
        task_store=store,
        handler_registry=registry,
        completion_service=JobCompletionService(
            task_store=store,
            course_storage_manager=manager,
        ),
        worker_count=3,
        lease_seconds=1,
        heartbeat_interval=0.05,
        poll_interval=0.01,
    )
    commands = GenerationCommandService(
        task_store=store,
        snapshot_provider=lambda owner: {},
    )
    jobs = {}
    for resource_type in ("blog", "quiz", "flashcard"):
        jobs[resource_type] = commands.submit(
            GenerationCommand(
                resource_type=resource_type,
                owner_user_id="teacher-a",
                course_id="c1",
                source_mode="none",
                selected_doc_ids=[],
                config={"title": resource_type},
                idempotency_key=f"acceptance-{resource_type}",
                material_id=f"acceptance-{resource_type}",
            )
        )

    pool.start()
    try:
        assert entered.wait(timeout=1)
        assert store.request_cancel(
            jobs["blog"].edu_job_id,
            owner_user_id="teacher-a",
        )
        release.set()
        tasks = _wait_for_terminal(
            store,
            [job.edu_job_id for job in jobs.values()],
        )
        statuses = {
            resource_type: store.get_durable(job.edu_job_id).status
            for resource_type, job in jobs.items()
        }
        assert statuses == {
            "blog": "canceled",
            "quiz": "succeeded",
            "flashcard": "succeeded",
        }
        assert all(task is not None for task in tasks)
    finally:
        release.set()
        assert pool.stop(timeout_seconds=2) == ()

    blog_materials = manager.list_generated_materials(
        "c1",
        "blog",
        owner_user_id="teacher-a",
    )
    assert not any(
        item.get("source_job_id") == jobs["blog"].edu_job_id
        for item in blog_materials
    )
    for resource_type in ("quiz", "flashcard"):
        assert manager.get_generated_material(
            "c1",
            resource_type,
            f"acceptance-{resource_type}",
            owner_user_id="teacher-a",
        ) is not None
        assert get_job(jobs[resource_type].edu_job_id).status == JobStatus.SUCCEEDED
