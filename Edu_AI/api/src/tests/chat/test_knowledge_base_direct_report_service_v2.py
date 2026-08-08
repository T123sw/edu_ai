from types import SimpleNamespace

from app.chat.application.knowledge_base_direct_report_service_v2 import KnowledgeBaseDirectReportServiceV2
from app.services.visual_assets.pipeline import VisualAssetPipeline


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


def test_direct_report_applies_every_visible_report_configuration():
    llm = DummyLlm("# 配置生效的报告")
    service = KnowledgeBaseDirectReportServiceV2(
        content_provider=DummyContentProvider({"documents": []}),
        llm=llm,
        course_storage_manager=DummyCourseStorageManager(),
    )

    service.generate(
        SimpleNamespace(
            question="链表教学分析",
            selected_doc_ids=[],
            source_mode="none",
            owner="tester",
            course_id="course-1",
            report_config={
                "template": "study_plan",
                "audience": "新教师",
                "depth": "deep",
                "structure_emphasis": "结论、依据、行动项",
                "special_requirements": "加入课堂案例",
            },
        )
    )

    prompt = str(llm.calls[0])
    assert "study_plan" in prompt
    assert "新教师" in prompt
    assert "deep" in prompt
    assert "结论、依据、行动项" in prompt
    assert "加入课堂案例" in prompt


def test_direct_report_plans_images_before_body_and_assembles_locked_visuals():
    class SequencedLlm:
        def __init__(self):
            self.calls = []
            self.responses = [
                """
                {"outline":[{"section_id":"implementation","title":"实现方式"}],
                 "visuals":[{"slot_id":"linked-list","section_id":"implementation",
                 "purpose":"解释 next 指针","query":"linked list next pointer diagram",
                 "preferred_kind":"diagram","caption_hint":"链表节点连接关系"}]}
                """,
                "# 链表实现\n\n## 实现方式\n\n{{VISUAL:linked-list}}\n\n正文。",
            ]

        def invoke(self, messages):
            self.calls.append(messages)
            return SimpleNamespace(content=self.responses.pop(0))

    llm = SequencedLlm()
    visual_pipeline = VisualAssetPipeline(
        knowledge_search=lambda **kwargs: [
            {
                "url": "/api/courses/course-1/knowledge-base/documents/doc-1/media?path=list.png",
                "source_page": "knowledge://doc-1",
                "title": "链表节点图",
                "width": 1200,
                "height": 700,
            }
        ],
        localize=lambda candidate, **kwargs: {
            **candidate,
            "local_url": candidate["url"],
            "content_hash": "kb-linked-list",
        },
    )
    service = KnowledgeBaseDirectReportServiceV2(
        content_provider=DummyContentProvider(
            {
                "documents": [
                    {
                        "title": "链表课程资料",
                        "summary": "链表节点包含数据与 next 指针。",
                        "content": "节点通过 next 指向后继节点。",
                    }
                ],
                "truncated": False,
            }
        ),
        llm=llm,
        course_storage_manager=DummyCourseStorageManager(),
        visual_pipeline=visual_pipeline,
    )

    result = service.generate(
        SimpleNamespace(
            question="链表如何实现",
            selected_doc_ids=["doc-1"],
            source_context="节点通过 next 指向后继节点。",
            source_mode="selected_documents",
            owner="tester",
            course_id="course-1",
            report_config={"include_visuals": True},
        )
    )

    content = result["artifacts"][0]["content"]
    assert len(llm.calls) == 2
    assert "![链表节点连接关系]" in content
    assert "{{VISUAL:" not in content
    assert result["trace"]["visuals"]["selected_count"] == 1
