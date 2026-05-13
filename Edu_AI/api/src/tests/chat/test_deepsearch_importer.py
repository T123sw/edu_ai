import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.deepsearch_importer import (
    import_crawl_results_to_rag,
    persist_imported_documents_to_course_kb,
)
from core.course_storage import CourseStorageManager
from modules.rag_v2.rag_main.system import RAGSystem


def _make_workspace_tmp(name: str) -> Path:
    base_dir = Path(__file__).resolve().parents[5] / "_deepsearch_import_test_tmp_root"
    base_dir.mkdir(parents=True, exist_ok=True)
    test_dir = base_dir / f"{name}_{uuid.uuid4().hex}"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


def test_import_crawl_results_to_rag_rewrites_inline_images_and_site_icon(monkeypatch):
    workspace = _make_workspace_tmp("deepsearch_import")
    documents_root = workspace / "documents"
    crawl_root = workspace / "crawl"
    crawl_root.mkdir(parents=True, exist_ok=True)

    text_file = crawl_root / "example.txt"
    text_file.write_text("web page content " * 120, encoding="utf-8")

    page_image = crawl_root / "example_001.png"
    page_image.write_bytes(b"page-image")
    site_icon = crawl_root / "site-icon.png"
    site_icon.write_bytes(b"site-icon")

    source_image_url = "https://example.com/static/example_001.png"
    page_markdown = ("web page content " * 60) + f"\n\n![diagram]({source_image_url})\n\n" + ("web page content " * 60)

    result = SimpleNamespace(
        url="https://example.com/article",
        title="Example Article",
        content=page_markdown,
        content_type="text",
        file_path=str(text_file),
        status="success",
        metadata={
            "image_assets": [
                {
                    "file_path": str(page_image),
                    "source_url": source_image_url,
                }
            ],
            "site_icon_path": str(site_icon),
        },
    )

    class FakeRAGSystem:
        def __init__(self):
            self.imported = []
            self.saved = False

        def import_document(self, file_path, force_reimport=False, owner=None):
            self.imported.append((file_path, force_reimport, owner))
            return {"status": "success", "file_path": file_path}

        def _save_index(self):
            self.saved = True

    rag_system = FakeRAGSystem()
    record = {}

    monkeypatch.setattr(
        "app.deepsearch_importer.resolve_rag_document",
        lambda *_args, **_kwargs: SimpleNamespace(
            index_key="user_teacher:/tmp/example.md",
            source_key="user_teacher:/tmp/example.md",
            record=record,
        ),
    )

    imported_images = []

    def fake_image_importer(image_path, **kwargs):
        imported_images.append((Path(image_path).name, kwargs))
        return {
            "file_path": f"user_teacher:{image_path}",
            "image_path": image_path,
            "image_url": f"/api/rag/image?path=images%2Fteacher%2F{Path(image_path).name}",
        }

    imported = import_crawl_results_to_rag(
        results=[result],
        owner="teacher",
        rag_system=rag_system,
        documents_root=documents_root,
        image_importer=fake_image_importer,
        min_content_length=10,
    )

    assert len(imported) == 1
    assert rag_system.saved is True
    assert rag_system.imported == [
        (imported[0]["file_path"], False, "teacher"),
        (imported[0]["file_path"], True, "teacher"),
    ]
    assert [name for name, _ in imported_images] == ["example_001.png", "site-icon.png"]
    assert record["doc_kind"] == "web"
    assert record["source_domain"] == "example.com"
    assert record["source_icon_url"].endswith("site-icon.png")
    assert len(record["linked_images"]) == 1
    assert record["linked_images"][0]["image_url"].endswith("example_001.png")

    markdown_path = Path(imported[0]["file_path"])
    markdown_content = markdown_path.read_text(encoding="utf-8")
    assert source_image_url not in markdown_content
    assert "/api/rag/image?path=images%2Fteacher%2Fexample_001.png" in markdown_content


def test_import_crawl_results_to_rag_generates_summary_title_and_renames_web_doc(monkeypatch):
    workspace = _make_workspace_tmp("deepsearch_import_summary")
    documents_root = workspace / "documents"
    crawl_root = workspace / "crawl"
    crawl_root.mkdir(parents=True, exist_ok=True)

    text_file = crawl_root / "example.txt"
    text_file.write_text("algorithm lesson content " * 120, encoding="utf-8")

    result = SimpleNamespace(
        url="https://example.edu/lesson",
        title="A very long crawler page title",
        content="algorithm lesson content " * 120,
        content_type="text",
        file_path=str(text_file),
        status="success",
        metadata={"site_name": "Example EDU"},
    )

    class FakeRAGSystem:
        def __init__(self):
            self.summary_calls = []
            self.saved = False

        def import_document(self, file_path, force_reimport=False, owner=None):
            return {"status": "success", "file_path": file_path}

        def summarize_document_for_import(self, file_path, owner=None):
            self.summary_calls.append((file_path, owner))
            return {
                "summary": "This document explains classroom algorithm ideas.",
                "summary_title": "Algorithm Lesson",
            }

        def _save_index(self):
            self.saved = True

    rag_system = FakeRAGSystem()
    record = {}

    monkeypatch.setattr(
        "app.deepsearch_importer.resolve_rag_document",
        lambda *_args, **_kwargs: SimpleNamespace(
            index_key="user_teacher:/tmp/example.md",
            source_key="user_teacher:/tmp/example.md",
            record=record,
        ),
    )

    imported = import_crawl_results_to_rag(
        results=[result],
        owner="teacher",
        rag_system=rag_system,
        documents_root=documents_root,
        min_content_length=10,
    )

    assert len(imported) == 1
    assert rag_system.summary_calls == [(imported[0]["file_path"], "teacher")]
    assert record["summary"] == "This document explains classroom algorithm ideas."
    assert record["summary_title"] == "Algorithm Lesson"
    assert record["source_site_name"] == "Example EDU"
    assert record["file_name"] == "Example EDU｜Algorithm Lesson"


def test_rag_system_summarize_document_for_import_parses_short_title(monkeypatch):
    index_key = "user_teacher:/tmp/web.md"
    source_key = "user_teacher:/tmp/web.md"
    saved = {"called": False}

    rag_system = RAGSystem.__new__(RAGSystem)
    rag_system.summary_model = "summary-model"
    rag_system.document_index = {
        index_key: {
            "file_name": "web_example.md",
            "owner": "teacher",
            "physical_path": "/tmp/web.md",
            "source_key": source_key,
        }
    }
    rag_system.vector_store = SimpleNamespace(
        get_documents_by_source=lambda key: [
            {"content": "Algorithms help students reason about procedures.", "metadata": {"page": 0}}
        ]
    )
    rag_system._make_index_key = lambda file_path, owner=None: index_key
    rag_system._make_source_key = lambda file_path, owner=None: source_key
    rag_system._save_index = lambda: saved.update(called=True)
    rag_system._call_llm = lambda *args, **kwargs: (
        '{"summary":"A concise summary for teachers.","summary_title":"Algorithm Reasoning"}'
    )

    monkeypatch.setattr(
        "rag_v2.rag_main.system.Config.get_deep_model",
        lambda: {"model_name": "summary-model"},
    )

    result = rag_system.summarize_document_for_import("/tmp/web.md", owner="teacher")

    assert result["summary"] == "A concise summary for teachers."
    assert result["summary_title"] == "Algorithm Reasoning"
    assert rag_system.document_index[index_key]["summary_title"] == "Algorithm Reasoning"
    assert saved["called"] is True


def test_persist_imported_documents_to_course_kb_writes_personal_scoped_entries_and_hides_rag_docs():
    workspace = _make_workspace_tmp("deepsearch_course_kb")
    course_root = workspace / "courses"
    manager = CourseStorageManager(root_path=str(course_root))
    manager.create_course_structure("course-1")
    manager.save_course_info("course-1", {"id": "course-1", "title": "course"})

    imported_file = workspace / "documents" / "web" / "teacher-a" / "lesson.md"
    imported_file.parent.mkdir(parents=True, exist_ok=True)
    imported_file.write_text("# lesson", encoding="utf-8")

    class FakeRAGSystem:
        def __init__(self):
            self.document_index = {
                "user_teacher-a:/tmp/lesson.md": {
                    "physical_path": str(imported_file),
                    "file_name": "lesson.md",
                    "owner": "teacher-a",
                    "hidden_in_list": False,
                }
            }
            self.saved = False

        def _save_index(self):
            self.saved = True

    rag_system = FakeRAGSystem()

    persisted = persist_imported_documents_to_course_kb(
        imported_docs=[
            {
                "file_path": str(imported_file),
                "index_key": "user_teacher-a:/tmp/lesson.md",
                "file_name": "lesson.md",
                "url": "https://example.com/lesson",
            }
        ],
        owner="teacher-a",
        course_id="course-1",
        scope_type="knowledge_point",
        scope_id="variables",
        storage_manager=manager,
        rag_system=rag_system,
    )

    assert len(persisted) == 1
    latest = manager.get_knowledge_base_index("course-1")[-1]
    assert latest["library_type"] == "personal"
    assert latest["owner_user_id"] == "teacher-a"
    assert latest["scope_type"] == "knowledge_point"
    assert latest["scope_id"] == "variables"
    assert latest["promoted_from_document_id"] == "user_teacher-a:/tmp/lesson.md"
    assert latest["source_url"] == "https://example.com/lesson"
    assert latest["doc_kind"] == "web"
    assert rag_system.document_index["user_teacher-a:/tmp/lesson.md"]["hidden_in_list"] is True
    assert rag_system.saved is True
