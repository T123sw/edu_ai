from types import SimpleNamespace

from app.chat.application.knowledge_base_direct_ppt_generation_service_v2 import (
    KnowledgeBaseDirectPptGenerationServiceV2,
)


class DummyDraftStore:
    def get(self, draft_id):
        return {
            "draft_id": draft_id,
            "course_id": "course-1",
            "selected_doc_ids": ["doc-1"],
            "selected_doc_snapshot_id": "snap-1",
            "selected_doc_snapshot": [{"doc_id": "doc-1", "summary": "Agent definition"}],
            "summary_updated_at_snapshot": ["2026-04-11T12:00:00"],
            "normalized_ppt_config": {
                "deck_title": "Agent Basics",
                "audience": "Undergraduate students",
                "objective": "Classroom presentation",
                "theme_id": "heu_academic_elegant",
                "target_slide_count": 16,
                "key_points": ["Definition"],
            },
            "draft_outline": {
                "deck_title": "Agent Basics",
                "deck_subtitle": "Intro",
                "theme_id": "heu_academic_elegant",
                "slides": [],
            },
            "status": "outline_ready",
        }


class DummyExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, *, outline, request, metadata):
        self.calls.append(
            {
                "outline": outline,
                "request": request,
                "metadata": metadata,
            }
        )
        return {
            "action": {"name": "generate.ppt.direct"},
            "run": {"run_id": "ppt-run-1", "status": "running"},
            "artifacts": [],
            "trace": {"path": "direct", "draft_id": "ppt-draft-1", "run_id": "ppt-run-1"},
        }


def test_direct_ppt_generation_service_uses_draft_id_and_executor():
    executor = DummyExecutor()
    service = KnowledgeBaseDirectPptGenerationServiceV2(
        draft_store=DummyDraftStore(),
        post_outline_executor=executor,
    )

    result = service.generate(
        SimpleNamespace(
            draft_id="ppt-draft-1",
            confirm=True,
            outline=None,
            owner="tester",
        )
    )

    assert result["run"]["run_id"] == "ppt-run-1"
    assert executor.calls[0]["metadata"]["draft_id"] == "ppt-draft-1"
    assert executor.calls[0]["request"].owner == "tester"


def test_direct_ppt_generation_service_persists_completed_deck():
    class DummyStorage:
        def __init__(self):
            self.saved = []

        def save_generated_material(self, *, course_id, material_type, material_id, material_data):
            self.saved.append(
                {
                    "course_id": course_id,
                    "material_type": material_type,
                    "material_id": material_id,
                    "material_data": material_data,
                }
            )

    class PersistingExecutor:
        def execute(self, *, outline, request, metadata):
            return {
                "status": "completed",
                "phase": "completed",
                "message": "done",
                "artifacts": [
                    {
                        "artifact_id": "ppt-draft-1:outline",
                        "artifact_type": "ppt_outline",
                        "content": outline.model_dump(exclude_none=True),
                    },
                    {
                        "artifact_id": "ppt-draft-1:deck:job_1",
                        "artifact_type": "ppt_deck",
                        "title": "Agent Basics.pptx",
                        "content": {
                            "job_id": "job_1",
                            "pptx_url": "/ppt/artifacts/job_1/rev_0000/deck.pptx",
                        },
                        "generation_state": {"status": "completed"},
                    },
                ],
                "trace": {"path": "direct", "draft_id": "ppt-draft-1"},
                "run_id": "ppt-run-job_1",
                "job_id": "job_1",
            }

    storage = DummyStorage()
    service = KnowledgeBaseDirectPptGenerationServiceV2(
        draft_store=DummyDraftStore(),
        post_outline_executor=PersistingExecutor(),
        course_storage_manager=storage,
    )

    service.generate(SimpleNamespace(draft_id="ppt-draft-1", confirm=True, owner="tester"))

    assert storage.saved[0]["course_id"] == "course-1"
    assert storage.saved[0]["material_type"] == "ppt"
