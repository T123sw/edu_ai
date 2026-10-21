from __future__ import annotations

from types import SimpleNamespace

from app.chat.application.knowledge_base_direct_graph_service_v2 import (
    KnowledgeBaseDirectGraphServiceV2,
)


class _Provider:
    def get_selected_document_contents(self, *, selected_doc_ids, owner):
        assert selected_doc_ids == ["doc-1"]
        assert owner == "teacher-a"
        return {
            "documents": [
                {
                    "doc_id": "doc-1",
                    "title": "变量",
                    "content": "变量由名称、类型和值构成，可在程序运行中变化。",
                }
            ]
        }


class _Llm:
    def __init__(self):
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return SimpleNamespace(
            content=(
                '{"title":"变量","summary":"程序中的数据容器","children":['
                '{"title":"组成","summary":"名称、类型和值","children":[]},'
                '{"title":"特征","summary":"值可以变化","children":[]}'
                "]}"
            )
        )


class _Storage:
    def __init__(self):
        self.saved = None

    def save_generated_material(self, **kwargs):
        self.saved = kwargs
        return True


class _NoSourceProvider:
    def get_selected_document_contents(self, **_kwargs):
        raise AssertionError("none source mode must not read the knowledge base")


def test_graph_generation_validates_tree_and_persists_formal_resource():
    storage = _Storage()
    service = KnowledgeBaseDirectGraphServiceV2(
        content_provider=_Provider(),
        llm=_Llm(),
        course_storage_manager=storage,
    )

    result = service.generate(
        SimpleNamespace(
            owner="teacher-a",
            course_id="course-1",
            scope_type="course",
            scope_id=None,
            selected_doc_ids=["doc-1"],
            graph_config={"title": "变量知识图谱", "max_depth": 3},
        ),
        job_id="job-1",
        config_snapshot_id="cfg-1",
    )

    artifact = result["artifacts"][0]
    assert artifact["artifact_type"] == "graph"
    assert artifact["content"]["root"]["title"] == "变量"
    assert len(artifact["content"]["root"]["children"]) == 2
    assert artifact["content"]["root"]["id"] == "root"
    assert [node["id"] for node in artifact["content"]["root"]["children"]] == [
        "root-1",
        "root-2",
    ]
    assert storage.saved["material_type"] == "graph"
    assert storage.saved["owner_user_id"] == "teacher-a"
    assert storage.saved["source_job_id"] == "job-1"
    assert storage.saved["config_snapshot_id"] == "cfg-1"
    assert result["saved"] is True


def test_graph_generation_drops_duplicate_siblings_and_caps_depth():
    service = KnowledgeBaseDirectGraphServiceV2(
        content_provider=_Provider(),
        llm=_Llm(),
        course_storage_manager=_Storage(),
    )
    normalized = service._normalize_node(
        {
            "title": "根",
            "children": [
                {"title": "重复", "children": [{"title": "越界", "children": []}]},
                {"title": "重复", "children": []},
            ],
        },
        depth=1,
        max_depth=2,
    )
    assert len(normalized["children"]) == 1
    assert normalized["children"][0]["children"] == []


def test_graph_generation_uses_configured_topic_without_documents():
    llm = _Llm()
    service = KnowledgeBaseDirectGraphServiceV2(
        content_provider=_NoSourceProvider(),
        llm=llm,
        course_storage_manager=_Storage(),
    )

    result = service.generate(
        SimpleNamespace(
            owner="teacher-a",
            course_id="course-1",
            scope_type="course",
            scope_id=None,
            source_mode="none",
            selected_doc_ids=[],
            graph_config={
                "title": "Variable knowledge map",
                "description": "Show definitions and relationships",
                "max_depth": 3,
            },
            research_context="Agent evidence: a variable has name, type, and value.",
            research_bundle_id="bundle-1",
        ),
        job_id="job-none",
        config_snapshot_id="cfg-none",
    )

    assert result["artifacts"][0]["title"] == "Variable knowledge map"
    assert "Agent evidence" in str(llm.messages[0])


def test_graph_focus_reaches_model_and_depth_caps_saved_tree():
    class DeepLlm:
        def invoke(self, messages):
            assert '说明：比较赋值与复制的关系' in messages[1]['content']
            assert '最大层级：2' in messages[1]['content']
            return SimpleNamespace(content='{"title":"变量","children":[{"title":"赋值","children":[{"title":"不应保留的第三层"}]}]}')
    storage = _Storage()
    service = KnowledgeBaseDirectGraphServiceV2(content_provider=_NoSourceProvider(), llm=DeepLlm(), course_storage_manager=storage)
    service.generate(SimpleNamespace(owner='teacher-a', course_id='course-1', selected_doc_ids=[],
        graph_config={'title': '变量', 'description': '比较赋值与复制的关系', 'max_depth': 2}),
        job_id='test-depth', config_snapshot_id='test-config')
    assert storage.saved['material_data']['content']['root']['children'][0]['children'] == []


def test_model_receives_concise_summary_guidance_and_output_is_not_truncated():
    explanation = '选择基准后，把较小的元素移至左侧，较大的移至右侧；相等元素的处理取决于具体划分实现。'
    class Model:
        def invoke(self, messages):
            assert '一个短语或短句' in messages[0]['content']
            assert 'summary 可以留空' in messages[0]['content']
            assert '不要截取原文首句' in messages[0]['content']
            return SimpleNamespace(content=__import__('json').dumps({'title': '划分', 'summary': explanation, 'children': []}, ensure_ascii=False))
    storage = _Storage()
    service = KnowledgeBaseDirectGraphServiceV2(content_provider=_NoSourceProvider(), llm=Model(), course_storage_manager=storage)
    service.generate(SimpleNamespace(owner='teacher-a', course_id='course-1', selected_doc_ids=[], graph_config={'title': '快速排序', 'max_depth': 3}), job_id='concise', config_snapshot_id='cfg')
    assert storage.saved['material_data']['content']['root']['summary'] == explanation
