from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.chat.api.routes_v2 import router
from app.chat.tasks.task_store import TaskStore
from app.services.durable_task_handlers import DurableExecutionContext
from app.services.generation_command import GenerationCommandService
from app.services.generation_source_resolver import ResolvedGenerationSource
from app.services.generation_task_handlers import GenerationTaskHandler
from core.course_storage import CourseStorageManager


def _task_command(store: TaskStore, task_id: str):
    durable = store.get_durable(task_id)
    assert durable is not None
    return durable.command


def test_lesson_plan_direct_creates_durable_job(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.job_store.Config.STORAGE_ROOT", tmp_path / "jobs"
    )
    task_store = TaskStore(str(tmp_path / "tasks.db"))
    command_service = GenerationCommandService(
        task_store=task_store,
        snapshot_provider=lambda owner: {"llm": "test"},
    )
    monkeypatch.setattr(
        "app.chat.api.routes_v2.generation_command_service",
        command_service,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "teacher-a"
    }
    client = TestClient(app)

    response = client.post(
        "/api/chat/v2/lesson-plan/direct",
        json={
            "course_id": "course-1",
            "topic": "Newton's laws",
            "duration_minutes": 45,
            "audience": "first-year undergraduate",
            "objectives": ["Explain force and acceleration"],
            "source_mode": "course_auto",
            "selected_doc_ids": [],
        },
    )

    assert response.status_code == 202
    assert response.json()["workflow_type"] == "lesson_plan_direct"
    command = _task_command(task_store, response.json()["task_id"])
    assert command["resource_type"] == "lesson_plan"
    assert command["course_id"] == "course-1"
    assert command["source_mode"] == "course_auto"
    assert command["config"]["topic"] == "Newton's laws"
    assert command["config"]["duration_minutes"] == 45
    task_store.close()


def test_lesson_plan_direct_rejects_contradictory_source_request():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "teacher-a"
    }

    response = TestClient(app).post(
        "/api/chat/v2/lesson-plan/direct",
        json={
            "course_id": "course-1",
            "topic": "Newton's laws",
            "source_mode": "selected_documents",
            "selected_doc_ids": [],
        },
    )

    assert response.status_code == 422


class _FakeLessonPlanEngine:
    def __init__(self):
        self.states = []

    def invoke(self, state):
        self.states.append(state)
        if state.get("lesson_plan_outline") is None:
            return {
                "lesson_plan_outline": {
                    "basic_info": {"topic": state["lesson_plan_slots"]["topic"]},
                    "lesson_flow": [],
                }
            }
        return {
            "status": "completed",
            "artifacts": [
                {
                    "artifact_type": "lesson_plan",
                    "title": f"{state['lesson_plan_slots']['topic']} lesson plan",
                    "content": {"process": [], "objectives": []},
                }
            ],
        }


class _NoSourceResolver:
    def __init__(self):
        self.calls = []

    def resolve(self, course_id, mode, selected_document_ids):
        self.calls.append((course_id, mode, tuple(selected_document_ids)))
        return ResolvedGenerationSource(
            course_id=course_id,
            mode=mode,
            requested_document_ids=(),
            documents=(),
            context_text="resolved mechanics evidence",
            resolved_at=datetime(2026, 8, 7, tzinfo=timezone.utc).isoformat(),
        )


def test_lesson_plan_handler_uses_resolved_context_and_publishes_shared_artifact(
    tmp_path,
):
    from app.services.direct_lesson_plan_service import DirectLessonPlanService

    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    engine = _FakeLessonPlanEngine()
    service = DirectLessonPlanService(engine=engine)
    resolver = _NoSourceResolver()
    handler = GenerationTaskHandler(
        course_storage_manager=manager,
        source_resolver=resolver,
        service_factories={"lesson_plan": lambda: service},
    )
    context = DurableExecutionContext(
        task_id="job-lesson-1",
        owner_user_id="teacher-a",
        course_id="course-1",
        config_snapshot_id="cfg-lesson-1",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )

    result = handler(
        {
            "resource_type": "lesson_plan",
            "course_id": "course-1",
            "source_mode": "course_auto",
            "selected_doc_ids": [],
            "config": {
                "topic": "Newton's laws",
                "audience": "first-year undergraduate",
                "duration_minutes": 45,
                "objectives": ["Explain force and acceleration"],
            },
            "material_id": "lesson-plan-1",
        },
        context,
    )

    assert result["saved"] is True
    assert engine.states[0]["gathered_context"]["source_context"] == (
        "resolved mechanics evidence"
    )
    artifact = manager.get_generated_material(
        "course-1",
        "lesson_plan",
        "lesson-plan-1",
        owner_user_id="teacher-b",
    )
    assert artifact is not None
    assert artifact["visibility"] == "course"
    assert artifact["source_job_id"] == "job-lesson-1"
