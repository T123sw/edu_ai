"""Seed the approved minimal Database course fixture after an external backup."""

from __future__ import annotations

import argparse
import json
from typing import Any

from app.standard_resources.models import extract_leaf_nodes
from core.course_storage import CourseStorageManager


TARGET_COURSE_ID = "course-a385a289be0d44e480e343472f6cc8cd"
TEST_LECTURE_FILENAME = "database-minimal-test-lecture.md"


class SeedSafetyError(RuntimeError):
    pass


def build_database_graph() -> dict[str, Any]:
    return {
        "id": "db-root",
        "label": "数据库",
        "data": {
            "type": "course",
            "summary": "数据库课程最小可用测试知识结构",
            "publication_status": "published",
        },
        "children": [
            {
                "id": "db-relational-model",
                "label": "关系模型",
                "data": {"type": "chapter"},
                "children": [
                    {
                        "id": "db-relationships-and-keys",
                        "label": "关系与键",
                        "data": {"type": "knowledge_point"},
                        "children": [],
                    },
                    {
                        "id": "db-integrity-constraints",
                        "label": "完整性约束",
                        "data": {"type": "knowledge_point"},
                        "children": [],
                    },
                ],
            },
            {
                "id": "db-sql-query",
                "label": "SQL 查询",
                "data": {"type": "chapter"},
                "children": [
                    {
                        "id": "db-single-table-query",
                        "label": "单表查询",
                        "data": {"type": "knowledge_point"},
                        "children": [],
                    },
                    {
                        "id": "db-multi-table-join",
                        "label": "多表连接",
                        "data": {"type": "knowledge_point"},
                        "children": [],
                    },
                ],
            },
            {
                "id": "db-transactions",
                "label": "事务",
                "data": {"type": "chapter"},
                "children": [
                    {
                        "id": "db-acid",
                        "label": "ACID",
                        "data": {"type": "knowledge_point"},
                        "children": [],
                    },
                    {
                        "id": "db-concurrency-control",
                        "label": "并发控制",
                        "data": {"type": "knowledge_point"},
                        "children": [],
                    },
                ],
            },
        ],
    }


def build_database_lecture() -> str:
    return """# 数据库基础：最小测试讲义

本讲义用于验证按叶子知识点生成标准学习资源。内容有意保持简洁，正式课程资料迁移后应由真实教材替代。

## 关系与键

关系模型用二维表描述数据。元组对应行，属性对应列；候选键能唯一标识元组，主键是被选定的候选键，外键用于表达表之间的引用关系。

## 完整性约束

实体完整性要求主键唯一且非空；参照完整性要求外键引用存在的目标键，或按规则为空；用户定义完整性负责业务范围、格式与状态约束。

## 单表查询

单表查询通常由 SELECT、FROM、WHERE、GROUP BY、HAVING 和 ORDER BY 组成。执行时应先明确筛选条件、需要的列以及是否聚合，避免无意义地读取全部数据。

## 多表连接

连接根据关联条件组合多张表。INNER JOIN 只保留匹配行，LEFT JOIN 保留左表全部行。连接条件缺失会产生笛卡尔积，是常见错误。

## ACID

原子性保证事务整体成功或回滚；一致性保证约束在事务前后成立；隔离性控制并发事务的相互影响；持久性保证提交后的结果不会因普通故障丢失。

## 并发控制

并发控制用于避免脏读、不可重复读、幻读和丢失更新。常见机制包括锁、时间戳与多版本并发控制；隔离级别需要在一致性和吞吐量之间权衡。
"""


def _same_fixture_graph(graph: dict[str, Any] | None) -> bool:
    expected = [item.leaf_id for item in extract_leaf_nodes(build_database_graph())]
    actual = [item.leaf_id for item in extract_leaf_nodes(graph)]
    return actual == expected


def seed_test_course(
    *,
    manager: CourseStorageManager,
    course_id: str,
    dry_run: bool = False,
    force: bool = False,
    allow_other_course: bool = False,
) -> dict[str, Any]:
    normalized_course_id = str(course_id or "").strip()
    if normalized_course_id != TARGET_COURSE_ID and not allow_other_course:
        raise SeedSafetyError(
            f"Refusing course {normalized_course_id!r}; expected {TARGET_COURSE_ID!r}"
        )
    if manager.get_course_info(normalized_course_id) is None:
        raise SeedSafetyError(f"Course {normalized_course_id!r} does not exist")

    existing_graph = manager.get_knowledge_graph(normalized_course_id)
    existing_leaves = extract_leaf_nodes(existing_graph)
    graph_matches = _same_fixture_graph(existing_graph)
    if existing_leaves and not graph_matches and not force:
        raise SeedSafetyError(
            "Course already has a non-test knowledge structure; pass --force only after review"
        )

    documents = list(manager.get_knowledge_base_index(normalized_course_id))
    test_documents = [
        item for item in documents if item.get("filename") == TEST_LECTURE_FILENAME
    ]
    other_documents = [
        item for item in documents if item.get("filename") != TEST_LECTURE_FILENAME
    ]
    if other_documents and not force:
        raise SeedSafetyError(
            "Course already has official or non-test documents; pass --force only after review"
        )

    write_graph = not graph_matches
    write_document = not test_documents
    result = {
        "course_id": normalized_course_id,
        "dry_run": dry_run,
        "would_write_graph": write_graph,
        "would_write_document": write_document,
        "leaf_count": 6,
        "document_filename": TEST_LECTURE_FILENAME,
    }
    if dry_run:
        return result

    if write_graph and not manager.save_knowledge_graph(
        normalized_course_id, build_database_graph()
    ):
        raise RuntimeError("Failed to save test knowledge structure")
    if write_document:
        relative_path = manager.save_knowledge_base_file(
            normalized_course_id,
            build_database_lecture().encode("utf-8"),
            TEST_LECTURE_FILENAME,
            scope_type="course",
            scope_id=normalized_course_id,
            library_type="course",
            owner_user_id=None,
        )
        if not relative_path:
            raise RuntimeError("Failed to save test lecture")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-id", default=TARGET_COURSE_ID)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-other-course", action="store_true")
    args = parser.parse_args()
    result = seed_test_course(
        manager=CourseStorageManager(),
        course_id=args.course_id,
        dry_run=args.dry_run,
        force=args.force,
        allow_other_course=args.allow_other_course,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
