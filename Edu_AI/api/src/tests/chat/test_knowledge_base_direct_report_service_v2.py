from types import SimpleNamespace

from app.chat.application.knowledge_base_direct_report_service_v2 import KnowledgeBaseDirectReportServiceV2


class DummyContentProvider:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get_selected_document_contents(self, *, selected_doc_ids, owner):
        self.calls.append((list(selected_doc_ids), owner))
        return self.result


class DummyLlm:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.content)


class DummyCourseStorageManager:
    def __init__(self):
        self.saved = []

    def save_generated_material(
        self,
        *,
        course_id,
        material_type,
        material_id,
        material_data,
        file_data=None,
        **_kwargs,
    ):
        self.saved.append(
            {
                "course_id": course_id,
                "material_type": material_type,
                "material_id": material_id,
                "material_data": material_data,
            }
        )
        return True


def test_direct_report_service_generates_report_artifact_without_workflow(monkeypatch):
    content_provider = DummyContentProvider(
        {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "课堂观察记录",
                    "summary": "围绕课堂观察和学习重点。",
                    "content": "这是完整文档内容。",
                    "content_updated_at": "2026-04-07T10:00:00",
                }
            ],
            "content_updated_at_snapshot": ["2026-04-07T10:00:00"],
            "fallback_used": False,
            "truncated": False,
        }
    )
    llm = DummyLlm("# 自定义报告标题\n\n这是生成的报告正文。")
    storage = DummyCourseStorageManager()
    monkeypatch.setattr(
        "app.chat.application.knowledge_base_direct_report_service_v2.uuid4",
        lambda: SimpleNamespace(hex="abcdef1234567890"),
    )
    service = KnowledgeBaseDirectReportServiceV2(
        content_provider=content_provider,
        llm=llm,
        course_storage_manager=storage,
    )

    result = service.generate(
        SimpleNamespace(
            question="请围绕课堂观察生成报告",
            final_user_prompt="请围绕课堂观察生成报告",
            prompt_draft="默认草稿",
            selected_card={"card_id": "preset-brief", "card_type": "preset", "preset_key": "brief"},
            selected_doc_ids=["doc-1"],
            course_id="course-1",
            report_config={"title": "课堂观察分析"},
            owner="tester",
        )
    )

    assert content_provider.calls == [(["doc-1"], "tester")]
    assert result["action"]["name"] == "generate.report.direct"
    assert result["trace"]["path"] == "direct"
    assert result["artifacts"][0]["artifact_type"] == "report"
    assert result["artifacts"][0]["title"] == "课堂观察分析.md"
    assert result["artifacts"][0]["artifact_id"] == "report-abcdef123456"
    assert "课堂观察" in str(llm.calls[0])
    assert len(storage.saved) == 1
    assert storage.saved[0]["course_id"] == "course-1"


def test_direct_report_service_generates_from_topic_when_source_mode_is_none():
    content_provider = DummyContentProvider(
        {"documents": [], "fallback_used": True, "truncated": False}
    )
    service = KnowledgeBaseDirectReportServiceV2(
        content_provider=content_provider,
        llm=DummyLlm("# Agent principles\n\nGenerated report."),
        course_storage_manager=DummyCourseStorageManager(),
    )

    result = service.generate(
        SimpleNamespace(
            question="Agent principles",
            selected_doc_ids=[],
            source_mode="none",
            owner="tester",
            course_id="course-1",
            report_config={},
        )
    )

    assert content_provider.calls == []
    assert result["artifacts"][0]["content"] == "# Agent principles\n\nGenerated report."
    assert result["trace"]["selected_doc_count"] == 0
