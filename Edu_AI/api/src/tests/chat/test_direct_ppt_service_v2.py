from __future__ import annotations

from types import SimpleNamespace

from app.chat.application.knowledge_base_direct_ppt_service_v2 import (
    KnowledgeBaseDirectPptServiceV2,
)
from app.chat.application.ppt_direct_draft_store import PptDirectDraftStore
from app.chat.domain.ppt_outline import PptOutline, PptOutlineSlide


def _outline():
    return PptOutline(
        deck_title="变量",
        theme_id="heu_academic_elegant",
        slides=[
            PptOutlineSlide(
                slide_index=1,
                role="cover",
                title="变量",
                goal="引入主题",
                key_points=["变量"],
            ),
            PptOutlineSlide(
                slide_index=2,
                role="content",
                title="核心概念",
                goal="理解变量",
                key_points=["名称", "类型", "值"],
            ),
        ],
    )


class _SummaryProvider:
    def get_selected_document_summaries(self, *, selected_doc_ids, owner):
        assert owner == "teacher-a"
        return {
            "documents": [
                {"doc_id": "doc-1", "title": "变量", "summary": "变量保存数据。"}
            ]
        }


class _OutlineBuilder:
    def build(self, *, preparation):
        assert preparation.slide_count == 8
        return _outline()


class _ContentGenerator:
    def generate(self, *, outline, preparation):
        return "## Slide 1\n### Blocks\n- 变量\n## Slide 2\n### Blocks\n- 名称、类型和值", {}


class _Gate:
    def apply(self, *, content_markdown, outline):
        return {"ok": True, "final_markdown": content_markdown}


class _Engine:
    def create_job(self, **_kwargs):
        return {"job_id": "provider-1", "status": "queued"}

    def get_job_status(self, _job_id):
        return {"status": "succeeded", "phase": "completed", "progress": 100}

    def get_job_results(self, _job_id):
        return {
            "slide_count": 2,
            "results": {
                "pptx_url": "http://ppt.local/deck.pptx",
                "html_full_url": "http://ppt.local/index.html",
            },
        }


class _Storage:
    def __init__(self):
        self.saved = None

    def save_generated_material(self, **kwargs):
        self.saved = kwargs
        return True


def test_ppt_draft_is_owner_scoped_and_generation_persists_job_metadata(tmp_path):
    storage = _Storage()
    service = KnowledgeBaseDirectPptServiceV2(
        summary_provider=_SummaryProvider(),
        outline_builder=_OutlineBuilder(),
        content_generator=_ContentGenerator(),
        content_gate=_Gate(),
        draft_store=PptDirectDraftStore(tmp_path / "drafts"),
        html2ppt_client=_Engine(),
        course_storage_manager=storage,
        poll_interval_seconds=0,
    )
    outline_response = service.generate_outline(
        SimpleNamespace(
            owner="teacher-a",
            course_id="course-1",
            scope_type="course",
            scope_id=None,
            selected_doc_ids=["doc-1"],
            ppt_config={
                "deck_title": "变量",
                "length_option": "short",
                "theme_id": "heu_academic_elegant",
            },
        )
    )
    draft_id = outline_response["draft"]["draft_id"]
    result = service.generate(
        SimpleNamespace(
            owner="teacher-a",
            draft_id=draft_id,
            confirm=True,
            outline=None,
        ),
        job_id="job-1",
        config_snapshot_id="cfg-1",
    )
    assert result["saved"] is True
    assert storage.saved["material_type"] == "ppt"
    assert storage.saved["owner_user_id"] == "teacher-a"
    assert storage.saved["source_job_id"] == "job-1"
    assert storage.saved["material_data"]["content"]["pptx_url"].endswith(".pptx")

    try:
        service.get_draft(owner="teacher-b", draft_id=draft_id)
    except KeyError:
        pass
    else:
        raise AssertionError("another owner must not read the PPT draft")

