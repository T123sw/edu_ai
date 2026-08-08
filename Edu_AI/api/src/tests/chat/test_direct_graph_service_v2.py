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
    def invoke(self, _messages):
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
    service = KnowledgeBaseDirectGraphServiceV2(
        content_provider=_NoSourceProvider(),
        llm=_Llm(),
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
        ),
        job_id="job-none",
        config_snapshot_id="cfg-none",
    )

    assert result["artifacts"][0]["title"] == "Variable knowledge map"
