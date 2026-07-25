"""Course service layer — storage access, scope resolution, and knowledge graph helpers.

Does NOT depend on HTTP or FastAPI.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from app.workspace_scope import SCOPE_TYPE_COURSE, collect_scope_ids_for_query
from core.config import Config
from core.course_storage import LIBRARY_TYPE_COURSE, CourseStorageManager, storage_manager

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "GIT_HTTP_PROXY",
    "GIT_HTTPS_PROXY",
)

DEFAULT_COURSES: List[Dict[str, Any]] = [
    {
        "id": "computational-thinking",
        "title": "计算思维",
        "description": "培养计算思维，学习问题分解、模式识别、抽象和算法设计",
        "icon": "CommentOutlined",
        "color": "#1890ff",
        "objectives": [
            "理解计算思维的核心概念和方法",
            "掌握问题分解和模式识别技巧",
            "培养抽象思维和算法设计能力",
            "通过实践项目提升计算思维能力",
        ],
        "knowledgeGraph": "",
    },
    {
        "id": "data-structures",
        "title": "数据结构",
        "description": "深入学习各种数据结构及其应用，掌握算法设计与分析",
        "icon": "DatabaseOutlined",
        "color": "#52c41a",
    },
    {
        "id": "operating-systems",
        "title": "操作系统",
        "description": "理解操作系统原理，学习进程管理、内存管理和文件系统",
        "icon": "CloudServerOutlined",
        "color": "#fa8c16",
    },
    {
        "id": "computer-networks",
        "title": "计算机网络",
        "description": "掌握网络协议、网络架构和网络安全等核心知识",
        "icon": "FileTextOutlined",
        "color": "#722ed1",
    },
    {
        "id": "computer-organization",
        "title": "计算机组成原理",
        "description": "学习计算机硬件组成、指令系统、存储系统和 I/O 系统",
        "icon": "CloudServerOutlined",
        "color": "#13c2c2",
    },
    {
        "id": "database-principles",
        "title": "数据库原理",
        "description": "掌握数据库设计、SQL 语言、事务处理和数据库管理系统",
        "icon": "DatabaseOutlined",
        "color": "#eb2f96",
    },
]


def _get_manager() -> CourseStorageManager:
    return storage_manager


def ensure_default_courses() -> None:
    mgr = _get_manager()
    for course in DEFAULT_COURSES:
        if mgr.get_course_info(course["id"]) is None:
            mgr.create_course_structure(course["id"])
            mgr.save_course_info(course["id"], dict(course))


def _resolve_scope_ids_for_course(
    *,
    mgr: CourseStorageManager,
    course_id: str,
    scope_type: str,
    scope_id: Optional[str],
) -> Optional[set[str]]:
    if scope_type != "knowledge_point":
        return None
    graph_root = mgr.get_knowledge_graph(course_id)
    return collect_scope_ids_for_query(
        graph_root,
        scope_type=scope_type,
        scope_id=scope_id,
    )


@contextmanager
def _without_proxy_env():
    previous = {key: os.environ.get(key) for key in _PROXY_ENV_KEYS}
    try:
        for key in _PROXY_ENV_KEYS:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _find_kg_node(root: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    if not isinstance(root, dict):
        return None
    if str(root.get("id")) == node_id:
        return root

    children = root.get("children")
    if not isinstance(children, list):
        return None

    for child in children:
        if not isinstance(child, dict):
            continue
        found = _find_kg_node(child, node_id)
        if found is not None:
            return found
    return None


def _call_knowledge_graph_hour_llm(prompt: str) -> str:
    from modules.rag_v2.api import get_rag_system

    rag_system = get_rag_system()
    model_config = Config.get_deep_model()
    with _without_proxy_env():
        raw = rag_system._call_llm(prompt, llm_config=model_config)  # type: ignore[attr-defined]
    return str(raw or "")
