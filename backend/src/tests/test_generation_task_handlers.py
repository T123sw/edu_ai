from types import SimpleNamespace

import pytest

from app.services.durable_task_handlers import DurableExecutionContext
from app.services.generation_task_handlers import GenerationTaskHandler
from app.services.generation_source_resolver import (
    ResolvedGenerationSource,
    ResolvedSourceDocument,
)
from core.course_storage import CourseStorageManager


@pytest.fixture(autouse=True)
def isolated_persistence(monkeypatch):
    for kind in ['JOB', 'TASK', 'COURSE', 'COURSE_MEMBERSHIP', 'MATERIAL', 'KNOWLEDGE', 'APP_STATE']:
        monkeypatch.setenv(kind + '_PERSISTENCE_MODE', 'json')


RESOURCE_CASES = [
    ("report", {"question": "Write report"}),
    ("lesson_plan", {"subject": "Sorting", "grade": "Grade 7"}),
    ("blog", {"topic": "Sorting"}),
    ("quiz", {"quiz_config": {"topic": "Sorting", "question_count": 5}}),
    ("flashcard", {"flashcard_config": {"title": "Sorting", "count": 8}}),
    ("graph", {"title": "Sorting graph", "max_depth": 3}),
    ("game", {"game_type": "quiz"}),
]


@pytest.mark.parametrize(
    "resource_type",
    ["report", "lesson_plan", "blog", "quiz", "flashcard", "graph", "game"],
)
def test_factory_payload_preserves_review_specification(resource_type):
    context = DurableExecutionContext(
        task_id="job-factory-spec",
        owner_user_id="teacher-a",
        course_id="course-1",
        config_snapshot_id="cfg-factory-spec",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )
    config = {
        "entrypoint": "generation_factory",
        "title": "数组的实现",
        "subject": "数组的实现",
        "audience": "计算机专业低年级学生",
        "focus": "连续内存、地址映射与动态扩容",
        "confirmed_outline": "存储布局；访问；扩容",
        "harness_chapters": [{"title": "存储布局"}],
        "harness_organization": {"objectives": ["解释地址映射"]},
        "harness_interaction_mode": "direct",
        "harness_execution_context": {"stage": "write_and_review"},
    }

    payload = GenerationTaskHandler._build_payload(
        {
            "resource_type": resource_type,
            "course_id": "course-1",
            "scope_type": "course",
            "source_mode": "none",
            "selected_doc_ids": [],
            "config": config,
        },
        context,
    )

    assert payload.subject == "数组的实现"
    assert payload.audience == "计算机专业低年级学生"
    assert payload.focus == "连续内存、地址映射与动态扩容"
    assert payload.confirmed_outline == "存储布局；访问；扩容"
    assert payload.harness_chapters == [{"title": "存储布局"}]
    assert payload.harness_organization == {"objectives": ["解释地址映射"]}
    assert payload.harness_interaction_mode == "direct"
    assert payload.harness_execution_context == {"stage": "write_and_review"}


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
        "source_mode": "none",
        "selected_doc_ids": [],
        "config": config,
        "material_id": f"{resource_type}-stable",
    }

    result = handler(command, context)

    assert isinstance(fake.payload, SimpleNamespace)
    assert fake.payload.owner == "teacher-a"
    assert fake.payload.course_id == "course-1"
    assert fake.payload.material_id == f"{resource_type}-stable"
    assert result["saved"] is True
    assert {
        key: result["result_ref"][key]
        for key in ("resource_type", "course_id", "material_type", "material_id")
    } == {
        "resource_type": "course_material",
        "course_id": "course-1",
        "material_type": resource_type,
        "material_id": f"{resource_type}-stable",
    }
    assert result["result_ref"]["version"] >= 1
    assert result["result_ref"]["content_hash"]
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
            "source_mode": "none",
            "selected_doc_ids": [],
            "config": {"question": "Report"},
            "material_id": "report-stable",
        },
        context,
    )

    assert result["result_ref"]["material_id"] == "report-stable"
    material = manager.get_generated_material(
        "course-1", "report", "report-stable", owner_user_id="teacher-a"
    )
    assert material["source_snapshot"]["mode"] == "none"
    assert material["config_snapshot"] == {"question": "Report"}


def test_generation_handler_passes_prevalidated_rag_keys_to_direct_service(
    tmp_path,
):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    fake = FakeGenerationService("flashcard")

    class SelectedSourceResolver:
        def resolve(self, course_id, mode, selected_doc_ids, **_kwargs):
            assert selected_doc_ids == ["course-doc-1"]
            return ResolvedGenerationSource(
                course_id=course_id,
                mode=mode,
                requested_document_ids=("course-doc-1",),
                documents=(
                    ResolvedSourceDocument(
                        document_id="course-doc-1",
                        name="Course document",
                        rag_index_key="user_teacher:D:/course/document.md",
                        chunk_count=4,
                    ),
                ),
                context_text="course content",
                resolved_at="2026-08-10T00:00:00+00:00",
            )

    handler = GenerationTaskHandler(
        course_storage_manager=manager,
        service_factories={"flashcard": lambda: fake},
        source_resolver=SelectedSourceResolver(),
    )
    context = DurableExecutionContext(
        task_id="job-student-course-source",
        owner_user_id="student",
        course_id="course-1",
        config_snapshot_id="cfg-student-course-source",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )

    handler(
        {
            "resource_type": "flashcard",
            "course_id": "course-1",
            "source_mode": "selected_documents",
            "selected_doc_ids": ["course-doc-1"],
            "config": {"flashcard_config": {"title": "Course cards"}},
            "material_id": "flashcard-course-source",
        },
        context,
    )

    assert fake.payload.authorized_rag_index_keys == [
        "user_teacher:D:/course/document.md"
    ]
    assert fake.payload.source_context == "course content"


def test_game_handler_preserves_topic_and_generation_options(tmp_path):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    fake = FakeGenerationService("game")
    handler = GenerationTaskHandler(
        course_storage_manager=manager,
        service_factories={"game": lambda: fake},
    )
    context = DurableExecutionContext(
        task_id="job-game",
        owner_user_id="teacher-a",
        course_id="course-1",
        config_snapshot_id="cfg-game",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )

    handler(
        {
            "resource_type": "game",
            "owner_user_id": "teacher-a",
            "course_id": "course-1",
            "scope_type": "course",
            "source_mode": "none",
            "selected_doc_ids": [],
            "config": {
                "title": "Agent matching",
                "game_type": "drag_match",
                "topic": "Agent principles",
                "card_count": 12,
                "difficulty": "hard",
                "duration_minutes": 8,
            },
            "material_id": "game-stable",
        },
        context,
    )

    assert fake.payload.topic == "Agent principles"
    assert fake.payload.card_count == 12
    assert fake.payload.difficulty == "hard"
    assert fake.payload.duration_minutes == 8


def test_required_review_policy_selects_reviewed_generator_without_outline_marker(
    tmp_path, monkeypatch,
):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure("course-1")
    direct = FakeGenerationService("flashcard")
    reviewed = FakeGenerationService("flashcard")

    monkeypatch.setattr(
        "app.chat.harness.reviewed_resource.ReviewedResourceGenerator",
        lambda progress: reviewed,
    )
    monkeypatch.setattr(
        "app.chat.harness.reviewed_resource.verified_resource",
        lambda artifact, resource_type: resource_type == "flashcard",
    )
    handler = GenerationTaskHandler(
        course_storage_manager=manager,
        service_factories={"flashcard": lambda: direct},
    )
    context = DurableExecutionContext(
        task_id="job-reviewed",
        owner_user_id="teacher-a",
        course_id="course-1",
        config_snapshot_id="cfg-reviewed",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )

    result = handler({
        "resource_type": "flashcard",
        "owner_user_id": "teacher-a",
        "course_id": "course-1",
        "scope_type": "course",
        "source_mode": "none",
        "selected_doc_ids": [],
        "review_policy": "required",
        "config": {"entrypoint": "agent", "title": "Agent flashcards"},
        "material_id": "flashcard-reviewed",
    }, context)

    assert reviewed.payload is not None
    assert reviewed.payload.review_policy == "required"
    assert direct.payload is None
    assert result["saved"] is True


def test_factory_report_uses_reviewed_adapter_before_any_material_is_saved(tmp_path, monkeypatch):
    manager = CourseStorageManager(root_path=str(tmp_path))
    manager.create_course_structure('course-1')
    direct = FakeGenerationService('report')
    captured = []
    def generate(payload):
        captured.append(payload)
        return '# Python\n\nx=1', {'report_review': {'decision': 'pass'}}
    monkeypatch.setattr('app.chat.harness.reviewed_report.generate_reviewed_report', generate)
    monkeypatch.setattr('app.chat.harness.reviewed_report.verified_review', lambda artifact: True)
    handler = GenerationTaskHandler(course_storage_manager=manager, service_factories={'report': lambda: direct})
    context = DurableExecutionContext(task_id='job-factory-report', owner_user_id='teacher-a', course_id='course-1', config_snapshot_id='cfg-report', progress=lambda *args: None, is_cancel_requested=lambda: False)
    result = handler({'resource_type': 'report', 'course_id': 'course-1', 'scope_type': 'course', 'source_mode': 'none', 'selected_doc_ids': [], 'review_policy': 'required', 'material_id': 'reviewed-factory-report', 'config': {'entrypoint': 'generation_factory', 'subject': 'Python', 'focus': 'x=1', 'harness_chapters': [{'title': '变量'}]}}, context)
    assert direct.payload is None
    assert captured[0].subject == 'Python'
    assert captured[0].review_policy == 'required'
    assert result['saved'] is True
