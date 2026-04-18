import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.deepsearch_importer import import_crawl_results_to_rag


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
