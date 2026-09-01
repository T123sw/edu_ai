"""知识图谱 researchContext 补充单测（SPEC-04 §4.3 D4，Phase 2.5）。"""

import sys
import uuid
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from core.course_storage import CourseStorageManager
from app.services.knowledge_graph_context import fetch_knowledge_graph_context

GRAPH = {
    "id": "root",
    "label": "计算思维与程序设计",
    "data": {"level": 0, "type": "concept"},
    "children": [
        {
            "id": "C1",
            "label": "第1章 计算思维与问题求解",
            "data": {"level": 1, "type": "chapter"},
            "children": [
                {
                    "id": "C1_1",
                    "label": "1.1 计算、自动计算与计算机",
                    "data": {"level": 2, "type": "section", "hours": 2},
                    "children": [
                        {
                            "id": "C1_1_1",
                            "label": "计算的发展历程",
                            "data": {"level": 3, "type": "topic", "hours": 1},
                            "children": [],
                        }
                    ],
                }
            ],
        },
        {
            "id": "C2",
            "label": "第2章 算法基础",
            "data": {"level": 1, "type": "chapter"},
            "children": [],
        },
    ],
}


def _make_manager() -> CourseStorageManager:
    root = Path("tests/.tmp") / f"kg-context-{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    manager = CourseStorageManager(root_path=str(root))
    manager.create_course_structure("course-1")
    manager.save_course_info("course-1", {"id": "course-1", "title": "course"})
    graph_file = manager.get_course_dir("course-1") / "knowledge_graph.json"
    import json

    graph_file.write_text(json.dumps(GRAPH, ensure_ascii=False), encoding="utf-8")
    return manager


def test_returns_none_when_course_has_no_knowledge_graph():
    manager = CourseStorageManager(root_path=str(Path("tests/.tmp") / f"kg-empty-{uuid.uuid4().hex}"))
    manager.create_course_structure("course-1")
    manager.save_course_info("course-1", {"id": "course-1", "title": "course"})

    result = fetch_knowledge_graph_context(
        course_storage_manager=manager, course_id="course-1", query="计算的发展历程"
    )
    assert result is None


def test_returns_none_when_query_empty():
    manager = _make_manager()
    result = fetch_knowledge_graph_context(course_storage_manager=manager, course_id="course-1", query="")
    assert result is None


def test_returns_none_when_no_node_matches():
    manager = _make_manager()
    result = fetch_knowledge_graph_context(
        course_storage_manager=manager, course_id="course-1", query="完全不相关的主题"
    )
    assert result is None


def test_matches_deep_concept_node_with_path_and_hours():
    manager = _make_manager()
    result = fetch_knowledge_graph_context(
        course_storage_manager=manager,
        course_id="course-1",
        query="今天讲一下计算的发展历程",
    )
    assert result == (
        "[知识图谱] 计算思维与程序设计 > 第1章 计算思维与问题求解 > "
        "1.1 计算、自动计算与计算机 > 计算的发展历程（课时 1 学时）"
    )


def test_matches_chapter_without_hours_omits_hours_suffix():
    manager = _make_manager()
    result = fetch_knowledge_graph_context(
        course_storage_manager=manager, course_id="course-1", query="第2章 算法基础怎么讲"
    )
    assert result == "[知识图谱] 计算思维与程序设计 > 第2章 算法基础"


def test_prefers_deeper_nodes_and_respects_max_nodes():
    manager = _make_manager()
    result = fetch_knowledge_graph_context(
        course_storage_manager=manager,
        course_id="course-1",
        query="计算思维与问题求解 里 1.1 计算、自动计算与计算机 和 计算的发展历程",
        max_nodes=1,
    )
    # 三个节点都命中，但 max_nodes=1 只留深度最深（最具体）的那个
    assert result == (
        "[知识图谱] 计算思维与程序设计 > 第1章 计算思维与问题求解 > "
        "1.1 计算、自动计算与计算机 > 计算的发展历程（课时 1 学时）"
    )
