from app.services.visual_assets.models import SelectedVisual
from app.services.visual_assets.pipeline import VisualAssetPipeline
from app.services.visual_assets.planner import parse_visual_brief


def test_optional_visual_budget_skips_remaining_downloads_and_slots(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr('app.services.visual_assets.pipeline.time.monotonic', lambda: clock[0])
    brief = parse_visual_brief({'outline': [{'section_id': 'core', 'title': '核心'}],
        'visuals': [{'slot_id': str(i), 'section_id': 'core', 'purpose': '展示流程', 'query': 'sort'} for i in range(3)]}, resource_type='report', topic='排序')
    searches, downloads = [], []
    def search(**kwargs):
        searches.append(kwargs)
        return [{'url': f'https://example.com/{i}.png'} for i in range(6)]
    def download(candidate, **kwargs):
        downloads.append(kwargs)
        clock[0] += 16
        return {}
    result = VisualAssetPipeline(web_search=search, localize=download).run(
        brief, course_id='c1', owner='alice', selected_document_ids=[], time_budget_seconds=30)
    assert len(searches) == 1
    assert len(downloads) == 2
    assert all(0 < call['timeout_s'] <= 4 for call in downloads)
    assert result.selected == ()
    assert result.rejected_counts['time_budget'] > 0


def test_bounded_visual_search_stops_after_best_usable_candidate():
    brief = parse_visual_brief({'outline': [{'section_id': 'core', 'title': '核心'}],
        'visuals': [{'section_id': 'core', 'purpose': '展示流程', 'query': 'sort'}]}, resource_type='report', topic='排序')
    downloads = []
    def download(candidate, **kwargs):
        downloads.append(candidate['url'])
        return {**candidate, 'local_url': '/images/good.png', 'content_hash': 'good'}
    result = VisualAssetPipeline(web_search=lambda **kwargs: [
        {'url': 'https://example.com/small.png', 'width': 300, 'height': 300},
        {'url': 'https://example.com/best.png', 'width': 1200, 'height': 900}], localize=download).run(
        brief, course_id='c1', owner='alice', selected_document_ids=[], time_budget_seconds=30)
    assert downloads == ['https://example.com/best.png']
    assert len(result.selected) == 1


def test_pipeline_prefers_qualified_knowledge_image_and_deduplicates_web():
    brief = parse_visual_brief(
        {
            "outline": [{"section_id": "implementation", "title": "实现方式"}],
            "visuals": [
                {
                    "slot_id": "linked-list",
                    "section_id": "implementation",
                    "purpose": "解释 next 指针",
                    "query": "linked list next pointer",
                    "preferred_kind": "diagram",
                }
            ],
        },
        resource_type="report",
        topic="链表",
    )

    pipeline = VisualAssetPipeline(
        knowledge_search=lambda **kwargs: [
            {
                "url": "/api/courses/c1/knowledge-base/documents/doc-1/media?path=list.png",
                "source_page": "knowledge://doc-1",
                "title": "链表节点图",
                "width": 1200,
                "height": 700,
                "document_id": "doc-1",
            }
        ],
        web_search=lambda **kwargs: [
            {
                "url": "https://example.com/list.png",
                "source_page": "https://example.com/list",
                "title": "Web duplicate",
                "width": 1200,
                "height": 700,
            },
            {
                "url": "https://example.com/tiny.png",
                "source_page": "https://example.com/tiny",
                "title": "Tiny",
                "width": 100,
                "height": 80,
            },
        ],
        localize=lambda candidate, **kwargs: {
            **candidate,
            "local_url": candidate["url"],
            "content_hash": "same-image",
        },
    )

    result = pipeline.run(
        brief,
        course_id="c1",
        owner="teacher-a",
        selected_document_ids=["doc-1"],
    )

    assert len(result.selected) == 1
    assert result.selected[0].source_type == "knowledge_base"
    assert result.selected[0].slot_id == "linked-list"
    assert result.rejected_counts["too_small"] == 1
    assert result.rejected_counts["duplicate"] == 1


def test_assembler_uses_only_locked_slots_and_keeps_source_attribution():
    pipeline = VisualAssetPipeline()
    selected = [
        SelectedVisual(
            slot_id="linked-list",
            local_url="/api/images/searched/list.png",
            title="链表节点连接关系",
            caption="链表节点连接关系",
            source_page="https://example.com/list",
            source_type="web",
            score=0.9,
        )
    ]

    assembled = pipeline.assemble(
        "# 链表\n\n{{VISUAL:linked-list}}\n\n{{VISUAL:not-selected}}",
        selected,
    )

    assert "![链表节点连接关系](/api/images/searched/list.png)" in assembled
    assert "[图片来源](https://example.com/list)" in assembled
    assert "not-selected" not in assembled


def test_pipeline_asks_model_for_outline_and_visual_needs_before_retrieval():
    class FakeLlm:
        def invoke(self, messages):
            assert "outline" in messages[-1]["content"]
            return type(
                "Response",
                (),
                {
                    "content": """
                    {"outline":[{"section_id":"core","title":"核心概念"}],
                     "visuals":[{"section_id":"core","purpose":"解释节点关系",
                     "query":"linked list diagram","preferred_kind":"diagram"}]}
                    """
                },
            )()

    pipeline = VisualAssetPipeline()

    brief = pipeline.plan_with_model(
        FakeLlm(),
        resource_type="report",
        topic="链表",
        source_context="课程资料摘要",
    )

    assert brief.outline[0].title == "核心概念"
    assert brief.slots[0].purpose == "解释节点关系"
