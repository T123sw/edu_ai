from __future__ import annotations

import json
from pathlib import Path

from app.services.course_knowledge_builder import (
    OpenTextbookSource,
    _parse_mkdocs_nav,
    _material_quality,
    _supplement_policy,
    build_course_knowledge_base,
    build_graph_from_textbook_pages,
    clean_stale_knowledge_records,
    quarantine_knowledge_records,
    reset_course_knowledge_graph,
    resolve_open_textbook_source,
    validate_open_textbook_license,
)
from core.course_storage import CourseStorageManager


def _create_course(manager: CourseStorageManager, course_id: str = "course-1") -> None:
    manager.create_course_structure(course_id)
    manager.save_course_info(
        course_id,
        {
            "id": course_id,
            "title": "计算思维",
            "description": "test",
            "icon": "BookOutlined",
            "color": "#123456",
        },
    )


def test_clean_stale_knowledge_records_keeps_real_files_and_creates_backup(tmp_path: Path):
    manager = CourseStorageManager(root_path=str(tmp_path / "course_data"))
    _create_course(manager)
    course_dir = manager.get_course_dir("course-1")
    documents_dir = course_dir / "knowledge_base" / "documents"
    real_file = documents_dir / "teacher-notes.md"
    real_file.write_text("# real notes", encoding="utf-8")
    manager.save_knowledge_base_index(
        "course-1",
        [
            {
                "id": "real",
                "filename": real_file.name,
                "path": "knowledge_base/documents/teacher-notes.md",
            },
            {
                "id": "missing",
                "filename": "placeholder.md",
                "path": "knowledge_base/documents/placeholder.md",
            },
            {
                "id": "duplicate",
                "filename": real_file.name,
                "path": "knowledge_base/documents/teacher-notes.md",
            },
        ],
    )

    report = clean_stale_knowledge_records(
        manager=manager,
        course_id="course-1",
        apply=True,
    )

    assert report["before_count"] == 3
    assert report["after_count"] == 1
    assert report["removed_by_reason"] == {"duplicate_path": 1, "missing_file": 1}
    assert real_file.exists()
    assert manager.get_knowledge_base_index("course-1")[0]["id"] == "real"
    backup_path = Path(report["backup_path"])
    assert backup_path.exists()
    assert len(json.loads(backup_path.read_text(encoding="utf-8"))) == 3


def test_quarantine_and_graph_reset_are_recoverable(tmp_path: Path):
    manager = CourseStorageManager(root_path=str(tmp_path / "course_data"))
    _create_course(manager)
    documents_dir = manager.get_course_dir("course-1") / "knowledge_base" / "documents"
    uploaded = documents_dir / "uploaded.pdf"
    legacy_web = documents_dir / "legacy-web.md"
    uploaded.write_bytes(b"pdf")
    legacy_web.write_text("legacy", encoding="utf-8")
    manager.save_knowledge_base_index(
        "course-1",
        [
            {"id": "uploaded", "filename": uploaded.name, "path": "knowledge_base/documents/uploaded.pdf"},
            {"id": "legacy", "filename": legacy_web.name, "path": "knowledge_base/documents/legacy-web.md"},
        ],
    )
    manager.save_knowledge_graph("course-1", {"id": "root", "label": "占位图谱", "children": []})

    quarantine = quarantine_knowledge_records(
        manager=manager,
        course_id="course-1",
        record_ids=["legacy"],
        reason="placeholder cleanup",
        apply=True,
    )
    reset = reset_course_knowledge_graph(manager=manager, course_id="course-1", apply=True)

    assert [item["id"] for item in manager.get_knowledge_base_index("course-1")] == ["uploaded"]
    assert uploaded.exists()
    assert not legacy_web.exists()
    quarantine_path = Path(quarantine["quarantine_path"])
    assert (quarantine_path / "manifest.json").exists()
    assert any(path.name.endswith("legacy-web.md") for path in quarantine_path.iterdir())
    assert Path(reset["backup_path"]).exists()
    assert manager.get_knowledge_graph("course-1")["data"]["status"] == "empty"


def test_open_textbook_policy_accepts_cc_by_and_rejects_ai_ingestion_ban():
    source = OpenTextbookSource(
        source_id="test-book",
        course_ids=("course-1",),
        title="中文开放教材",
        landing_url="https://example.edu/book/",
        publisher="示例大学",
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        allowed_hosts=("example.edu",),
    )

    validate_open_textbook_license(
        source,
        '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>',
    )

    prohibited = "This book may not be ingested into large language models or generative AI offerings."
    try:
        validate_open_textbook_license(source, prohibited)
    except ValueError as exc:
        assert "generative AI" in str(exc)
    else:
        raise AssertionError("AI-ingestion prohibition must reject the source")


def test_internal_noncommercial_source_is_explicit_and_native_chinese():
    source = resolve_open_textbook_source("computational-thinking")

    assert source.source_id == "hello-algo-zh"
    assert source.source_language == "zh-CN"
    assert "非商业" in source.usage_restriction
    validate_open_textbook_license(source, "CC BY-NC-SA 4.0")


def test_parse_hello_algo_mkdocs_navigation():
    parts = _parse_mkdocs_nav(
        """
site_name: Hello 算法
nav:
  - 第 1 章 &nbsp; 初识算法:
    - chapter_introduction/index.md
    - 1.1 &nbsp; 算法无处不在: chapter_introduction/algorithms_are_everywhere.md
  - 第 2 章 &nbsp; 复杂度分析:
    - chapter_computational_complexity/index.md
"""
    )

    assert [part["title"] for part in parts] == ["第 1 章 初识算法", "第 2 章 复杂度分析"]
    assert parts[0]["files"] == [
        "chapter_introduction/index",
        "chapter_introduction/algorithms_are_everywhere",
    ]


def test_supplement_audit_only_accepts_reviewed_sources_and_weak_content():
    weak = _material_quality("只有一句简短定义。", "算法定义")
    strong = _material_quality(("这是完整的中文解释、推导步骤和示例。" * 80) + "\n```python\nprint('ok')\n```", "算法定义")

    assert weak["needs_supplement"] is True
    assert strong["needs_supplement"] is False
    assert _supplement_policy("https://oi-wiki.org/basic/complexity/")["language"] == "zh-CN"
    assert _supplement_policy("https://docs.python.org/3/tutorial/") is None
    assert _supplement_policy("https://blog.csdn.net/example") is None


def test_build_graph_uses_real_page_and_section_titles_with_provenance():
    source = OpenTextbookSource(
        source_id="test-book",
        course_ids=("course-1",),
        title="中文开放教材",
        landing_url="https://example.edu/book/",
        publisher="示例大学",
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        allowed_hosts=("example.edu",),
    )
    pages = [
        {
            "url": "https://example.edu/book/algorithms.html",
            "title": "算法",
            "intro": "算法如何解决问题。",
            "sections": [
                {"title": "查找", "content": "线性查找与二分查找。"},
                {"title": "排序", "content": "插入排序与归并排序。"},
            ],
        }
    ]

    graph, materials = build_graph_from_textbook_pages(source=source, pages=pages)

    chapter = graph["children"][0]
    assert chapter["label"] == "算法"
    assert chapter["data"]["source_url"].endswith("algorithms.html")
    assert chapter["data"]["source_license"] == "CC BY 4.0"
    assert [node["label"] for node in chapter["children"]] == ["查找", "排序"]
    assert [item["scope_id"] for item in materials] == [
        "chapter-1-section-1",
        "chapter-1-section-2",
    ]
    assert all(item["source_url"].startswith("https://example.edu/") for item in materials)


def test_native_chinese_mkdocs_source_keeps_chapter_hierarchy_and_scope_ids():
    source = resolve_open_textbook_source("computational-thinking")
    pages = [
        {"part_title": "第 1 章 初识算法", "title": "算法是什么", "url": "https://example/a", "sections": []},
        {"part_title": "第 1 章 初识算法", "title": "算法应用", "url": "https://example/b", "sections": []},
    ]

    graph, materials = build_graph_from_textbook_pages(source=source, pages=pages)

    assert len(graph["children"]) == 1
    assert graph["children"][0]["label"] == "初识算法"
    assert [node["id"] for node in graph["children"][0]["children"]] == ["chapter-1", "chapter-2"]
    assert [item["scope_id"] for item in materials] == ["chapter-1", "chapter-2"]


def test_graph_excludes_book_front_and_back_matter_but_preserves_original_scope_ids():
    source = resolve_open_textbook_source("computational-thinking")
    pages = [
        {"part_title": "序", "title": "序", "url": "https://example/preface", "sections": []},
        {"part_title": "第 1 章 初识算法", "title": "算法是什么", "url": "https://example/a", "sections": []},
        {"part_title": "参考文献", "title": "参考文献", "url": "https://example/references", "sections": []},
        {"part_title": "纸质书", "title": "购买链接", "url": "https://example/paper", "sections": []},
    ]

    graph, materials = build_graph_from_textbook_pages(source=source, pages=pages)

    assert [group["label"] for group in graph["children"]] == ["初识算法"]
    assert [node["id"] for node in graph["children"][0]["children"]] == ["chapter-2"]
    assert [item["scope_id"] for item in materials] == ["chapter-2"]


def test_build_course_knowledge_base_persists_only_chinese_node_materials(
    tmp_path: Path,
    monkeypatch,
):
    manager = CourseStorageManager(root_path=str(tmp_path / "course_data"))
    _create_course(manager, "computational-thinking")

    monkeypatch.setattr(
        "app.services.course_knowledge_builder.fetch_open_textbook_pages",
        lambda source, max_pages: (
            [
                {
                    "part_title": "Part 1",
                    "file_stem": "algorithms",
                    "url": "https://thinkcompute.github.io/algorithms.html",
                    "content": "# 算法\n\n## 查找\n\n线性查找。",
                }
            ],
            "revision-1",
        ),
    )

    class FakeRag:
        def delete_document(self, path, **kwargs):
            return {"deleted": 0}

        def import_document(self, path, **kwargs):
            assert Path(path).read_text(encoding="utf-8").find("线性查找") >= 0
            return {"status": "success", "chunk_count": 2}

    result = build_course_knowledge_base(
        manager=manager,
        rag_system=FakeRag(),
        course_id="computational-thinking",
        owner_user_id="teacher",
        translator=lambda text: (_ for _ in ()).throw(AssertionError("原生中文教材不应调用翻译模型")),
    )

    graph = manager.get_knowledge_graph("computational-thinking")
    assert graph["label"] == "计算思维课程知识图谱"
    assert graph["children"][0]["label"] == "Part 1"
    assert graph["children"][0]["children"][0]["label"] == "算法"
    assert graph["children"][0]["children"][0]["children"][0]["label"] == "查找"
    index = manager.get_knowledge_base_index("computational-thinking")
    assert len(index) == 1
    assert index[0]["content_language"] == "zh-CN"
    assert index[0]["translation_notice"].startswith("原生中文")
    assert index[0]["source_license"] == "CC BY-NC-SA 4.0"
    assert "非商业" in index[0]["usage_restriction"]
    assert result["node_document_count"] == 1
