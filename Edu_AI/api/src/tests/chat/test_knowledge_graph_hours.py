import pytest

from app.knowledge_graph_hours import (
    KnowledgeGraphHourAllocationError,
    allocate_graph_hours_from_llm,
    collect_leaf_nodes,
    parse_llm_allocations,
    rollup_hours,
    validate_total_hours_to_tenths,
)


def sample_graph():
    return {
        "id": "root",
        "label": "Course",
        "data": {"summary": "Course summary", "type": "concept"},
        "children": [
            {
                "id": "chapter-1",
                "label": "Chapter 1",
                "data": {"summary": "Basics", "type": "chapter"},
                "children": [
                    {
                        "id": "leaf-a",
                        "label": "Core concept",
                        "data": {"summary": "Important prerequisite", "type": "concept"},
                        "children": [],
                    },
                    {
                        "id": "leaf-b",
                        "label": "Practice task",
                        "data": {"summary": "Practice-heavy task", "type": "topic"},
                    },
                ],
            },
            {
                "id": "leaf-c",
                "label": "Reference topic",
                "data": {"summary": "Optional reference", "type": "concept"},
                "children": [],
            },
        ],
    }


def test_collect_leaf_nodes_includes_path_depth_and_metadata():
    leaves = collect_leaf_nodes(sample_graph())

    assert [leaf.node_id for leaf in leaves] == ["leaf-a", "leaf-b", "leaf-c"]
    assert leaves[0].label == "Core concept"
    assert leaves[0].path == ["Course", "Chapter 1", "Core concept"]
    assert leaves[0].depth == 2
    assert leaves[1].summary == "Practice-heavy task"
    assert leaves[2].node_type == "concept"


def test_validate_total_hours_uses_integer_tenths():
    assert validate_total_hours_to_tenths(32) == 320
    assert validate_total_hours_to_tenths(32.5) == 325
    assert validate_total_hours_to_tenths("0.1") == 1


@pytest.mark.parametrize("value", [-1, "2.25", "abc", None])
def test_validate_total_hours_rejects_invalid_values(value):
    with pytest.raises(KnowledgeGraphHourAllocationError):
        validate_total_hours_to_tenths(value)


def test_parse_llm_allocations_accepts_json_object_and_ignores_reasons():
    raw = """
    {
      "allocations": [
        {"node_id": "leaf-a", "hours": 1.5, "reason": "core"},
        {"node_id": "leaf-b", "hours": "0.5"}
      ]
    }
    """

    assert parse_llm_allocations(raw) == {"leaf-a": 1.5, "leaf-b": 0.5}


def test_parse_llm_allocations_accepts_fenced_json():
    raw = """```json
    {"allocations": [{"node_id": "leaf-a", "hours": 2}]}
    ```"""

    assert parse_llm_allocations(raw) == {"leaf-a": 2.0}


def test_parse_llm_allocations_rejects_unparseable_output():
    with pytest.raises(KnowledgeGraphHourAllocationError):
        parse_llm_allocations("not json")


def test_allocate_graph_hours_normalizes_missing_extra_and_over_total_values():
    def fake_llm(prompt: str) -> str:
        assert "leaf-a" in prompt
        assert "chapter-1" not in prompt
        return """
        {
          "allocations": [
            {"node_id": "leaf-a", "hours": 9.4},
            {"node_id": "leaf-b", "hours": 0.2},
            {"node_id": "unknown", "hours": 99}
          ]
        }
        """

    updated, meta = allocate_graph_hours_from_llm(sample_graph(), 2.5, fake_llm)

    leaves = {child["id"]: child for child in updated["children"][0]["children"]}
    assert leaves["leaf-a"]["data"]["hours"] == 2.3
    assert leaves["leaf-b"]["data"]["hours"] == 0.2
    assert updated["children"][1]["data"]["hours"] == 0
    assert updated["children"][0]["data"]["hours"] == 2.5
    assert updated["data"]["hours"] == 2.5
    assert meta == {
        "total_hours": 2.5,
        "leaf_count": 3,
        "source": "llm",
        "normalized": True,
    }


def test_allocate_graph_hours_distributes_missing_tenths_and_allows_zero_leaf_hours():
    def fake_llm(prompt: str) -> str:
        return '{"allocations": [{"node_id": "leaf-a", "hours": 0.5}]}'

    updated, meta = allocate_graph_hours_from_llm(sample_graph(), "1.0", fake_llm)

    leaves = {child["id"]: child for child in updated["children"][0]["children"]}
    assert leaves["leaf-a"]["data"]["hours"] == 1.0
    assert leaves["leaf-b"]["data"]["hours"] == 0
    assert updated["children"][1]["data"]["hours"] == 0
    assert updated["data"]["hours"] == 1.0
    assert meta["normalized"] is True


def test_allocate_graph_hours_preserves_existing_metadata():
    def fake_llm(prompt: str) -> str:
        return '{"allocations": [{"node_id": "leaf-a", "hours": 1.0}]}'

    updated, _ = allocate_graph_hours_from_llm(sample_graph(), 1.0, fake_llm)

    leaf_a = updated["children"][0]["children"][0]
    assert leaf_a["data"]["summary"] == "Important prerequisite"
    assert leaf_a["data"]["type"] == "concept"
    assert leaf_a["data"]["hours"] == 1.0


def test_rollup_hours_uses_child_sums_not_existing_parent_values():
    graph = sample_graph()
    graph["data"]["hours"] = 999
    graph["children"][0]["data"]["hours"] = 999
    graph["children"][0]["children"][0]["data"]["hours"] = 1.2
    graph["children"][0]["children"][1]["data"]["hours"] = 0.8
    graph["children"][1]["data"]["hours"] = 0.5

    total_tenths = rollup_hours(graph)

    assert total_tenths == 25
    assert graph["children"][0]["data"]["hours"] == 2.0
    assert graph["data"]["hours"] == 2.5


def test_allocate_graph_hours_rejects_graph_without_leaves():
    with pytest.raises(KnowledgeGraphHourAllocationError):
        allocate_graph_hours_from_llm({"id": "root", "label": "Broken", "children": "bad"}, 1.0, lambda _: "{}")
