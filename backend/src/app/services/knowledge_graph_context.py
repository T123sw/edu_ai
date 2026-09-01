"""知识图谱节点/关系 → researchContext 补充（SPEC-04 §4.3 D4，Phase 2.5）。

只读现有课程知识图谱树（`core.course_storage.CourseStorageManager.
get_knowledge_graph`，一课程一棵树：root→chapter→section→topic→concept，
见 `docs/计算思维知识图谱.md`），按 requirement 关键词命中相关节点，拼出
"该概念在教材体系里的位置（章节路径=隐含先修顺序）+ 课时占用"这段文本，
作为 `classroom_service` researchContext 的第三路叠加（web/RAG 之外）。

不建新的图数据库或语义匹配——现有图谱本来就是层级树，子字符串命中已经
够用；语义检索已经由 RAG Top-K 那一路（P2-5）覆盖。这里只做"结构化教学
元数据"这一层 RAG 天然缺失的信息（章节位置、课时分配）。
"""

from __future__ import annotations

from typing import Any, Optional

from core.course_storage import CourseStorageManager

_MIN_LABEL_LENGTH = 2


def _flatten(node: dict[str, Any], ancestors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        return []
    label = str(node.get("label") or "").strip()
    path = [*ancestors, label] if label else list(ancestors)
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    entries = [
        {
            "id": node.get("id"),
            "label": label,
            "type": data.get("type"),
            "hours": data.get("hours"),
            "path": path,
        }
    ]
    for child in node.get("children") or []:
        entries.extend(_flatten(child, path))
    return entries


def fetch_knowledge_graph_context(
    *,
    course_storage_manager: CourseStorageManager,
    course_id: str,
    query: str,
    max_nodes: int = 3,
) -> Optional[str]:
    """按关键词命中知识图谱节点，返回"章节路径(隐含先修)+课时"文本；
    没有图谱或没有命中都返回 None（这段补充可有可无，不阻断生成）。
    """
    query_norm = (query or "").strip()
    if not query_norm:
        return None

    try:
        graph = course_storage_manager.get_knowledge_graph(course_id)
    except Exception:
        return None
    if not isinstance(graph, dict):
        return None

    entries = _flatten(graph, [])
    query_lower = query_norm.lower()
    matches = [
        entry
        for entry in entries
        if entry["label"]
        and len(entry["label"]) >= _MIN_LABEL_LENGTH
        and (
            entry["label"].lower() in query_lower
            or query_lower in entry["label"].lower()
        )
    ]
    if not matches:
        return None

    # 越深（越具体的概念节点）优先；深度并列时保留原图谱的先序遍历顺序。
    matches.sort(key=lambda e: -len(e["path"]))

    blocks: list[str] = []
    for entry in matches[:max_nodes]:
        path_text = " > ".join(entry["path"])
        hours = entry.get("hours")
        hours_text = f"（课时 {hours} 学时）" if hours not in (None, "") else ""
        blocks.append(f"[知识图谱] {path_text}{hours_text}")

    return "\n".join(blocks) if blocks else None
