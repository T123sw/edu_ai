from types import SimpleNamespace

import pytest

from app.services.durable_task_handlers import DurableExecutionContext
from app.services.generation_task_handlers import GenerationTaskHandler
from core.course_storage import CourseStorageManager


RESOURCE_CASES = [
    ("report", {"question": "Write report"}),
    ("lesson_plan", {"subject": "Sorting", "grade": "Grade 7"}),
    ("blog", {"topic": "Sorting"}),
    ("quiz", {"quiz_config": {"topic": "Sorting", "question_count": 5}}),
    ("ppt", {"draft_id": "draft-1", "confirm": True, "outline": None}),
    ("flashcard", {"flashcard_config": {"title": "Sorting", "count": 8}}),
    ("graph", {"title": "Sorting graph", "max_depth": 3}),
    ("game", {"game_type": "quiz"}),
]


class FakeGenerationService:
    def __init__(self, resource_type: str):
        self.resource_type = resource_type
        self.payload = None
        self.job_id = None
        self.config_snapshot_id = None

    def generate(
        self,
        payload,
        *,
        job_id: str | None = None,
        config_snapshot_id: str | None = None,
    ):
        self.payload = payload
        self.job_id = job_id
        self.config_snapshot_id = config_snapshot_id
        return {
            "artifacts": [
                {
                    "artifact_id": f"temporary-{self.resource_type}",
                    "artifact_type": self.resource_type,
                    "title": f"{self.resource_type} title",
                    "content": {"ok": True},
                }
            ]
        }


@pytest.mark.parametrize("resource_type,config", RESOURCE_CASES)
def test_generation_handler_rebuilds_requests_and_publishes_stable_resource(
    tmp_path,
    resource_type,
    config,
):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    fake = FakeGenerationService(resource_type)
    handler = GenerationTaskHandler(
        course_storage_manager=manager,
        service_factories={resource_type: lambda: fake},
    )
    context = DurableExecutionContext(
        task_id="job-1",
        owner_user_id="teacher-a",
        course_id="course-1",
        config_snapshot_id="cfg-1",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )
    command = {
        "resource_type": resource_type,
        "owner_user_id": "teacher-a",
        "course_id": "course-1",
        "scope_type": "course",
        "scope_id": None,
        "selected_doc_ids": ["doc-1"],
        "config": config,
        "material_id": f"{resource_type}-stable",
    }

    result = handler(command, context)

    assert isinstance(fake.payload, SimpleNamespace)
    assert fake.payload.owner == "teacher-a"
    assert fake.payload.course_id == "course-1"
    assert fake.payload.material_id == f"{resource_type}-stable"
    assert result["saved"] is True
    assert result["result_ref"] == {
        "resource_type": "course_material",
        "course_id": "course-1",
        "material_type": resource_type,
        "material_id": f"{resource_type}-stable",
    }
    material = manager.get_generated_material(
        "course-1",
        resource_type,
        f"{resource_type}-stable",
        owner_user_id="teacher-a",
    )
    assert material is not None
    assert material["source_job_id"] == "job-1"


def test_generation_handler_preserves_a_verified_service_result(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")

    class PersistingService(FakeGenerationService):
        def generate(self, payload, *, job_id=None, config_snapshot_id=None):
            manager.save_generated_material(
                "course-1",
                "report",
                "report-stable",
                {"title": "Report"},
                owner_user_id="teacher-a",
                source_job_id=job_id,
                config_snapshot_id=config_snapshot_id,
            )
            return {
                "saved": True,
                "result_ref": {
                    "resource_type": "course_material",
                    "course_id": "course-1",
                    "material_type": "report",
                    "material_id": "report-stable",
                },
            }

    handler = GenerationTaskHandler(
        course_storage_manager=manager,
        service_factories={"report": lambda: PersistingService("report")},
    )
    context = DurableExecutionContext(
        task_id="job-1",
        owner_user_id="teacher-a",
        course_id="course-1",
        config_snapshot_id="cfg-1",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )

    result = handler(
        {
            "resource_type": "report",
            "owner_user_id": "teacher-a",
            "course_id": "course-1",
            "scope_type": "course",
            "scope_id": None,
            "selected_doc_ids": ["doc-1"],
            "config": {"question": "Report"},
            "material_id": "report-stable",
        },
        context,
    )

    assert result["result_ref"]["material_id"] == "report-stable"
