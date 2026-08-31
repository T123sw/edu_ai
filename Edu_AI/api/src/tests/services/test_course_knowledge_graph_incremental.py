from __future__ import annotations

import copy

from app.services.course_knowledge_graph_incremental import (
    baseline_graph_issues,
    incremental_graph_issues,
    merge_incremental_graph,
    normalize_graph_name,
)


def node(node_id, label, node_type, summary, children=None, refs=None):
    return {
        "id": node_id,
        "label": label,
        "data": {
            "type": node_type,
            "summary": summary,
            "source_outline_refs": list(refs or []),
        },
        "children": list(children or []),
    }


BASELINE = node(
    "course-root",
    "课程",
    "course",
    "课程说明",
    [
        node(
            "module-a",
            "旧模块 A",
            "knowledge_module",
            "模块 A 说明",
            [
                node(
                    "point-a1",
                    "旧知识点 A1",
                    "knowledge_point",
                    "原说明",
                    refs=["old-ref"],
                ),
                node("point-a2", "旧知识点 A2", "knowledge_point", "A2 说明"),
            ],
        ),
        node(
            "module-b",
            "旧模块 B",
            "knowledge_module",
            "模块 B 说明",
            [node("point-b1", "同名知识", "knowledge_point", "B1 说明")],
        ),
    ],
)


def test_normalize_graph_name_handles_spacing_case_and_width():
    assert normalize_graph_name("  Ａ  BC  ") == "a bc"


def test_incremental_merge_preserves_existing_structure_and_appends_new_nodes():
    candidate = node(
        "course-root",
        "模型试图改根名称",
        "course",
        "课程补充",
        [
            node(
                "module-a",
                "模型试图改模块名称",
                "knowledge_module",
                "模块 A 补充",
                [
                    node(
                        "point-a1",
                        "模型试图改知识点名称",
                        "knowledge_point",
                        "候选补充说明",
                        refs=["new-ref"],
                    ),
                    node("point-new", "新增知识点", "knowledge_point", "新增说明"),
                ],
            )
        ],
    )

    merged = merge_incremental_graph(BASELINE, candidate)

    assert [item["id"] for item in merged["children"][:2]] == ["module-a", "module-b"]
    assert merged["label"] == "课程"
    assert merged["children"][0]["label"] == "旧模块 A"
    assert [item["id"] for item in merged["children"][0]["children"][:2]] == [
        "point-a1",
        "point-a2",
    ]
    updated = merged["children"][0]["children"][0]
    assert updated["label"] == "旧知识点 A1"
    assert updated["data"]["summary"].endswith("候选补充说明")
    assert updated["data"]["source_outline_refs"] == ["old-ref", "new-ref"]
    assert merged["children"][0]["children"][-1]["data"]["review_state"] == "new"
    assert incremental_graph_issues(BASELINE, merged) == []


def test_same_parent_same_name_reuses_node_but_different_parent_does_not():
    candidate = node(
        "course-root",
        "课程",
        "course",
        "课程说明",
        [
            node(
                "module-a",
                "旧模块 A",
                "knowledge_module",
                "模块说明",
                [
                    node("different-id", "  旧知识点  A1 ", "knowledge_point", "同父补充"),
                    node("same-name-new-parent", "同名知识", "knowledge_point", "不同父新增"),
                ],
            )
        ],
    )

    merged = merge_incremental_graph(BASELINE, candidate)
    children = merged["children"][0]["children"]

    assert [item["id"] for item in children].count("point-a1") == 1
    assert children[0]["data"]["summary"].endswith("同父补充")
    assert children[-1]["id"] == "same-name-new-parent"
    assert children[-1]["data"]["review_state"] == "new"


def test_new_id_collision_is_rewritten_deterministically_for_entire_subtree():
    candidate = node(
        "course-root",
        "课程",
        "course",
        "课程说明",
        [
            node(
                "new-module",
                "新增模块",
                "knowledge_module",
                "新增模块说明",
                [node("point-a1", "新增但 ID 冲突", "knowledge_point", "新增说明")],
            )
        ],
    )

    first = merge_incremental_graph(BASELINE, candidate)
    second = merge_incremental_graph(BASELINE, candidate)
    first_child = first["children"][-1]["children"][0]
    second_child = second["children"][-1]["children"][0]

    assert first_child["id"] == second_child["id"]
    assert first_child["id"].startswith("incremental-")
    assert first_child["data"]["review_state"] == "needs_review"


def test_baseline_violations_report_exact_node_and_rule():
    missing = copy.deepcopy(BASELINE)
    missing["children"][0]["children"].pop(0)
    renamed = copy.deepcopy(BASELINE)
    renamed["children"][0]["children"][0]["label"] = "被改名"
    moved = copy.deepcopy(BASELINE)
    moved_node = moved["children"][0]["children"].pop(0)
    moved["children"][1]["children"].append(moved_node)
    reordered = copy.deepcopy(BASELINE)
    reordered["children"][0]["children"].reverse()

    assert baseline_graph_issues(BASELINE, missing)[0]["code"] == "BASELINE_NODE_MISSING"
    assert baseline_graph_issues(BASELINE, renamed)[0] == {
        "code": "BASELINE_NODE_RENAMED",
        "node_id": "point-a1",
        "path": "point-a1",
        "message": "已有节点名称不可修改：旧知识点 A1",
    }
    assert any(
        item["code"] == "BASELINE_NODE_MOVED" and item["node_id"] == "point-a1"
        for item in baseline_graph_issues(BASELINE, moved)
    )
    assert any(
        item["code"] == "BASELINE_CHILD_ORDER_CHANGED" and item["node_id"] == "module-a"
        for item in baseline_graph_issues(BASELINE, reordered)
    )


def test_unresolved_new_parent_blocks_incremental_graph():
    graph = copy.deepcopy(BASELINE)
    graph["children"].append(
        node("new-orphan", "待选择父节点", "knowledge_module", "说明")
    )
    graph["children"][-1]["data"]["review_state"] = "needs_parent"

    assert any(
        item["code"] == "NEW_NODE_PARENT_UNRESOLVED"
        for item in incremental_graph_issues(BASELINE, graph)
    )
