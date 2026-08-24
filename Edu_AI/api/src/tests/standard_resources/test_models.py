from __future__ import annotations

from app.standard_resources.models import (
    StandardKind,
    extract_leaf_nodes,
    stable_material_id,
    standard_material_type,
)


GRAPH = {
    "id": "database-root",
    "label": "数据库",
    "children": [
        {
            "id": "relational-model",
            "label": "关系模型",
            "children": [
                {"id": "relationships-and-keys", "label": "关系与键", "children": []},
                {"id": "integrity-constraints", "label": "完整性约束", "children": []},
            ],
        },
        {
            "id": "sql-query",
            "label": "SQL 查询",
            "children": [
                {"id": "single-table-query", "label": "单表查询", "children": []},
                {"id": "multi-table-join", "label": "多表连接", "children": []},
            ],
        },
    ],
}


def test_extract_leaf_nodes_returns_only_stably_ordered_leaves() -> None:
    leaves = extract_leaf_nodes(GRAPH)

    assert [item.leaf_id for item in leaves] == [
        "relationships-and-keys",
        "integrity-constraints",
        "single-table-query",
        "multi-table-join",
    ]
    assert leaves[0].chapter_id == "relational-model"
    assert leaves[0].chapter_title == "关系模型"
    assert leaves[0].path_titles == ("数据库", "关系模型", "关系与键")


def test_standard_slots_use_stable_ids_and_existing_generators() -> None:
    assert stable_material_id("single-table-query", StandardKind.CLASSROOM) == (
        "standard-single-table-query-classroom"
    )
    assert standard_material_type(StandardKind.CLASSROOM) == "classroom"
    assert standard_material_type(StandardKind.STUDY_GUIDE) == "report"
    assert standard_material_type(StandardKind.PRACTICE) == "quiz"
