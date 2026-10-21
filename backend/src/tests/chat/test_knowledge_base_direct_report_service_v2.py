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


def test_course_context_is_included_in_report_model_messages():
    llm = DummyLlm('# 变量\n\n变量与对象的绑定。')
    service = KnowledgeBaseDirectReportServiceV2(content_provider=DummyContentProvider({'documents': []}), llm=llm, course_storage_manager=DummyCourseStorageManager())
    service.generate(SimpleNamespace(question='补充变量说明', selected_doc_ids=[], course_id='course-context-test', owner='alice', research_context='Python 课程原文：名字到对象的绑定。', report_config={'include_visuals': False}))
    assert '名字到对象的绑定' in str(llm.calls[0])


def test_report_ignores_retired_visual_flag_and_generates_body_once(monkeypatch):
    def fail_if_visuals_called(*args, **kwargs):
        raise AssertionError('Report generation must not plan, retrieve, or insert images')
    for method in ('plan_with_model', 'run', 'assemble'):
        monkeypatch.setattr('app.services.visual_assets.pipeline.VisualAssetPipeline.' + method, fail_if_visuals_called)
    progress = []
    storage = DummyCourseStorageManager()
    llm = DummyLlm('# 排序\n\n报告正文')
    service = KnowledgeBaseDirectReportServiceV2(llm=llm, course_storage_manager=storage)
    result = service.generate(SimpleNamespace(question='排序', selected_doc_ids=[], owner='alice',
        course_id='c1', report_config={'include_visuals': True}),
        progress=lambda value, step, message: progress.append((value, step)))
    assert result['artifacts'][0]['content'] == '# 排序\n\n报告正文'
    assert len(storage.saved) == 1
    assert len(llm.calls) == 1
    assert '图片占位符' in str(llm.calls[0])
    assert 'visuals' not in result['trace']
    assert progress == [(15, 'writing'), (90, 'saving')]
