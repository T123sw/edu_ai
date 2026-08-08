from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.course import GenerateClassroomRequest
from app.services.classroom_job_service import create_classroom_job
from app.services.classroom_persistence import persist_classroom_result
from app.services.classroom_service import submit_classroom_generation_job
from app.services.durable_task_handlers import DurableExecutionContext
from app.services.generation_source_resolver import ResolvedGenerationSource
from app.services.job_store import JobStatus, update_job
from app.services.platform_task_handlers import PlatformTaskHandlers
from app.chat.tasks.task_store import TaskStore
from core.course_storage import CourseStorageManager


def _valid_result():
    return {
        "id": "stage-1",
        "url": "http://sidecar-test:3000/classroom/stage-1",
        "createdAt": "2026-08-07T00:00:00Z",
        "scenesCount": 1,
        "stage": {"id": "stage-1", "name": "Newton's laws"},
        "scenes": [
            {
                "id": "scene-1",
                "type": "slide",
                "content": {
                    "type": "slide",
                    "canvas": {
                        "id": "slide-1",
                        "viewportRatio": 0.5625,
                        "elements": [{"id": "text-1", "type": "text"}],
                    },
                },
                "actions": [
                    {"id": "speech-1", "type": "speech", "text": "hello"}
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    "mode,ids",
    [
        ("course_auto", []),
        ("selected_documents", ["doc-1"]),
        ("none", []),
    ],
)
def test_classroom_request_accepts_shared_source_modes(mode, ids):
    payload = GenerateClassroomRequest(
        requirement="Teach Newton's laws",
        topic="Newton's laws",
        audience="first-year undergraduate",
        scene_count=6,
        enable_tts=False,
        source_mode=mode,
        selected_doc_ids=ids,
    )

    assert payload.source_mode == mode
    assert payload.selected_doc_ids == ids


def test_classroom_request_rejects_contradictory_source_selection():
    with pytest.raises(ValidationError):
        GenerateClassroomRequest(
            requirement="Teach Newton's laws",
            source_mode="none",
            selected_doc_ids=["doc-1"],
        )


@pytest.mark.anyio
async def test_classroom_submission_persists_source_intent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.job_store.Config.STORAGE_ROOT", tmp_path / "jobs"
    )
    task_store = TaskStore(str(tmp_path / "tasks.db"))
    monkeypatch.setattr(
        "app.services.platform_task_handlers.get_task_store",
        lambda: task_store,
    )
    monkeypatch.setattr(
        "app.services.runtime_config_resolver.runtime_config_resolver.capture_snapshot",
        lambda owner: {},
    )
    manager = CourseStorageManager(root_path=str(tmp_path / "courses"))
    manager.create_course_structure("course-1")

    job = await submit_classroom_generation_job(
        course_id="course-1",
        requirement="Teach without course documents",
        owner="teacher-a",
        course_storage_manager=manager,
        source_mode="none",
        selected_doc_ids=[],
        topic="Newton's laws",
        audience="first-year undergraduate",
        scene_count=6,
        enable_tts=False,
    )

    durable = task_store.get_durable(job.edu_job_id)
    assert durable is not None
    assert durable.command["source_mode"] == "none"
    assert durable.command["selected_doc_ids"] == []
    assert durable.command["topic"] == "Newton's laws"
    assert durable.command["scene_count"] == 6
    task_store.close()


class _SpyResolver:
    def __init__(self):
        self.calls = []

    def resolve(self, course_id, mode, selected_document_ids):
        self.calls.append((course_id, mode, tuple(selected_document_ids)))
        return ResolvedGenerationSource(
            course_id=course_id,
            mode=mode,
            requested_document_ids=tuple(selected_document_ids),
            documents=(),
            context_text=("resolved classroom evidence" if mode != "none" else ""),
            resolved_at=datetime(2026, 8, 7, tzinfo=timezone.utc).isoformat(),
        )


@pytest.mark.parametrize(
    "mode,ids",
    [
        ("course_auto", []),
        ("selected_documents", ["doc-1"]),
        ("none", []),
    ],
)
def test_classroom_worker_resolves_source_once(
    tmp_path,
    monkeypatch,
    mode,
    ids,
):
    monkeypatch.setattr(
        "app.services.job_store.Config.STORAGE_ROOT", tmp_path / "jobs"
    )
    manager = CourseStorageManager(root_path=str(tmp_path / "courses"))
    manager.create_course_structure("course-1")
    manager.save_knowledge_graph(
        "course-1",
        {"id": "newton", "name": "Newton's laws", "children": []},
    )
    resolver = _SpyResolver()
    captured = {}
    job = create_classroom_job(owner="teacher-a", course_id="course-1")

    class _FakeClient:
        pass

    monkeypatch.setattr(
        "app.integrations.openmaic.get_openmaic_client",
        lambda owner_user_id=None: _FakeClient(),
    )

    def fake_callback(**kwargs):
        captured["source_snapshot"] = kwargs["source_snapshot"]

        async def callback(_result):
            return {"classroom_id": "stage-1"}

        return callback

    async def fake_run(active_job, **kwargs):
        captured["research_context"] = kwargs["research_context"]
        return update_job(
            active_job.edu_job_id,
            status=JobStatus.SUCCEEDED,
            result_ref={"classroom_id": "stage-1"},
        )

    monkeypatch.setattr(
        "app.services.classroom_service._make_on_sidecar_succeeded",
        fake_callback,
    )
    monkeypatch.setattr(
        "app.services.classroom_service.fetch_knowledge_graph_context",
        lambda **kwargs: "knowledge graph evidence",
    )
    monkeypatch.setattr(
        "app.services.classroom_job_service.run_generate_classroom_job",
        fake_run,
    )
    handler = PlatformTaskHandlers(
        course_storage_factory=lambda: manager,
        generation_source_resolver_factory=lambda _manager: resolver,
    )
    context = DurableExecutionContext(
        task_id=job.edu_job_id,
        owner_user_id="teacher-a",
        course_id="course-1",
        config_snapshot_id="cfg-classroom",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )

    result = handler.classroom_generate(
        {
            "course_id": "course-1",
            "requirement": "Teach Newton's laws",
            "source_mode": mode,
            "selected_doc_ids": ids,
            "enable_tts": False,
        },
        context,
    )

    assert result["saved"] is True
    assert resolver.calls == [("course-1", mode, tuple(ids))]
    assert captured["source_snapshot"]["mode"] == mode
    if mode == "none":
        assert captured["research_context"] is None
    else:
        assert "resolved classroom evidence" in captured["research_context"]


def test_classroom_manifest_persists_source_snapshot(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    source_snapshot = {
        "mode": "selected_documents",
        "requested_document_ids": ["doc-1"],
        "documents": [],
        "resolved_at": "2026-08-07T00:00:00+00:00",
    }

    persist_classroom_result(
        course_storage_manager=manager,
        course_id="course-1",
        owner="teacher-a",
        result=_valid_result(),
        source_snapshot=source_snapshot,
        source_job_id="job-classroom-1",
    )

    material = manager.get_generated_material(
        "course-1", "classroom", "stage-1", owner_user_id="teacher-a"
    )
    assert material["source_snapshot"] == source_snapshot
    assert material["source_job_id"] == "job-classroom-1"
