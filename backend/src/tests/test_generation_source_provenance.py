from __future__ import annotations

from datetime import datetime, timezone

from app.services.durable_task_handlers import DurableExecutionContext
from app.services.generation_source_resolver import (
    ResolvedGenerationSource,
    ResolvedSourceDocument,
)
from app.services.generation_task_handlers import GenerationTaskHandler
from core.course_storage import CourseStorageManager


class SpyGenerationSourceResolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, tuple[str, ...]]] = []

    def resolve(self, course_id, mode, selected_document_ids):
        self.calls.append((course_id, mode, tuple(selected_document_ids)))
        return ResolvedGenerationSource(
            course_id=course_id,
            mode=mode,
            requested_document_ids=tuple(selected_document_ids),
            documents=(
                ResolvedSourceDocument(
                    document_id="doc-1",
                    name="Mechanics.pdf",
                    rag_index_key="rag/course-1/doc-1",
                    chunk_count=12,
                ),
            ),
            context_text="resolved course evidence",
            resolved_at=datetime(2026, 8, 7, tzinfo=timezone.utc).isoformat(),
        )


class SpyResourceGenerator:
    def __init__(self) -> None:
        self.contexts = []
        self.payloads = []

    def generate(
        self,
        payload,
        *,
        job_id,
        config_snapshot_id,
        execution_context,
    ):
        self.contexts.append(execution_context)
        self.payloads.append(payload)
        return {
            "artifacts": [
                {
                    "artifact_type": "report",
                    "title": "Mechanics report",
                    "content": "generated",
                }
            ]
        }


def test_handler_resolves_once_and_publishes_same_snapshot(tmp_path):
    storage = CourseStorageManager(root_path=str(tmp_path))
    storage.create_course_structure("course-1")
    resolver = SpyGenerationSourceResolver()
    generator = SpyResourceGenerator()
    handler = GenerationTaskHandler(
        course_storage_manager=storage,
        source_resolver=resolver,
        service_factories={"report": lambda: generator},
    )
    durable_context = DurableExecutionContext(
        task_id="job-1",
        owner_user_id="teacher-a",
        course_id="course-1",
        config_snapshot_id="cfg-1",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )
    command = {
        "resource_type": "report",
        "owner_user_id": "teacher-a",
        "course_id": "course-1",
        "scope_type": "course",
        "source_mode": "selected_documents",
        "selected_doc_ids": ["doc-1"],
        "config": {"subject": "Mechanics", "length": "short"},
        "material_id": "report-1",
    }

    handler.handle(command, durable_context)

    assert resolver.calls == [
        ("course-1", "selected_documents", ("doc-1",))
    ]
    assert len(generator.contexts) == 1
    execution_context = generator.contexts[0]
    assert execution_context.source.context_text == "resolved course evidence"
    assert generator.payloads[0].selected_doc_ids == ["rag/course-1/doc-1"]
    assert generator.payloads[0].source_context == "resolved course evidence"

    material = storage.get_generated_material(
        "course-1", "report", "report-1", owner_user_id="teacher-a"
    )
    assert material["source_snapshot"] == execution_context.source.to_snapshot()
    assert material["source_snapshot"]["documents"][0]["document_id"] == "doc-1"
    assert material["config_snapshot"] == {
        "subject": "Mechanics",
        "length": "short",
    }
    assert material["created_by"] == "teacher-a"
    assert material["source_job_id"] == "job-1"


def test_execution_context_config_is_immutable(tmp_path):
    storage = CourseStorageManager(root_path=str(tmp_path))
    storage.create_course_structure("course-1")
    resolver = SpyGenerationSourceResolver()

    class MutationProbe(SpyResourceGenerator):
        def generate(self, payload, **kwargs):
            context = kwargs["execution_context"]
            try:
                context.config["subject"] = "changed"
            except TypeError:
                pass
            else:  # pragma: no cover - documents the required boundary
                raise AssertionError("generation config must be immutable")
            return super().generate(payload, **kwargs)

    generator = MutationProbe()
    handler = GenerationTaskHandler(
        course_storage_manager=storage,
        source_resolver=resolver,
        service_factories={"report": lambda: generator},
    )
    durable_context = DurableExecutionContext(
        task_id="job-2",
        owner_user_id="teacher-a",
        course_id="course-1",
        config_snapshot_id="cfg-2",
        progress=lambda progress, step, message: None,
        is_cancel_requested=lambda: False,
    )

    handler.handle(
        {
            "resource_type": "report",
            "course_id": "course-1",
            "source_mode": "selected_documents",
            "selected_doc_ids": ["doc-1"],
            "config": {"subject": "Mechanics"},
            "material_id": "report-2",
        },
        durable_context,
    )

    assert generator.contexts[0].config["subject"] == "Mechanics"
