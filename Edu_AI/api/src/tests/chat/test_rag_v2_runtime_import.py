import inspect
import io
import json
import sys
import uuid
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from fastapi.responses import StreamingResponse

API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from modules.rag_v2.rag_main import api as runtime_api
from modules.rag_v2.rag_main import system as runtime_system
from modules.rag_v2.rag_main.system import RAGSystem


def _make_workspace_tmp(name: str) -> Path:
    base_dir = Path(__file__).resolve().parents[5] / "_runtime_import_test_tmp_root"
    base_dir.mkdir(parents=True, exist_ok=True)
    test_dir = base_dir / f"{name}_{uuid.uuid4().hex}"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


def test_rag_v2_runtime_package_can_be_imported():
    assert runtime_api.router.prefix == "/api/rag"
    assert RAGSystem is not None
    assert runtime_api.get_current_user.__module__ == "app.auth"
    assert runtime_api.Config.BASE_DIR == Path(__file__).resolve().parents[2]


def test_check_mineru_available_reflects_provider_config(monkeypatch):
    """迁移后（SPEC-03）：MinerU 可用性 = 直连 MinerU Cloud provider 是否配置了
    API key，不再依赖本地 mineru CLI。"""
    import app.integrations.pdf as pdf_pkg

    class _ConfiguredParser:
        def is_configured(self):
            return True

    class _UnconfiguredParser:
        def is_configured(self):
            return False

    monkeypatch.setattr(pdf_pkg, "get_pdf_parser", lambda: _ConfiguredParser())
    assert runtime_system._check_mineru_available() is True

    monkeypatch.setattr(pdf_pkg, "get_pdf_parser", lambda: _UnconfiguredParser())
    assert runtime_system._check_mineru_available() is False


def test_rag_v2_runtime_system_uses_host_storage_and_host_auth(monkeypatch):
    monkeypatch.delenv("QWEN_BASE_URL", raising=False)
    monkeypatch.delenv("REMOTE_MODEL_API_BASE", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("REMOTE_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    runtime_api._rag_system = None
    runtime_api.Config.REMOTE_MODEL_API_BASE = "https://config.example/v1"
    runtime_api.Config.REMOTE_MODEL_API_KEY = "config-key"

    captured = {}

    class FakeRAGSystem:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    original_rag_system = runtime_api.RAGSystem
    runtime_api.RAGSystem = FakeRAGSystem
    try:
        runtime_api.get_rag_system()
    finally:
        runtime_api.RAGSystem = original_rag_system
        runtime_api._rag_system = None

    assert captured["api_base"] == "https://config.example/v1"
    assert captured["vector_db_path"] == runtime_api.Config.VECTOR_DB_PATH
    assert captured["document_index_path"] == runtime_api.Config.DOCUMENT_INDEX_PATH
    assert runtime_api.Config.STORAGE_ROOT == Path(__file__).resolve().parents[2] / "storage"
    assert runtime_api.Config.VIDEO_INDEX_PATH.parent == runtime_api.Config.STORAGE_ROOT
    assert runtime_api.Config.IMAGE_INDEX_PATH.parent == runtime_api.Config.STORAGE_ROOT


def test_runtime_media_dirs_follow_config_storage_root():
    image_dir = runtime_api._get_user_media_dir("images", "alice")
    video_dir = runtime_api._get_user_media_dir("videos", "alice")

    assert image_dir == runtime_api.Config.STORAGE_ROOT / "images" / "alice"
    assert video_dir == runtime_api.Config.STORAGE_ROOT / "videos" / "alice"


def test_document_processor_extracts_docx_text_without_zip_gibberish(monkeypatch):
    docx_path = _make_workspace_tmp("docx_extract") / "lesson.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>变量定义与使用</w:t></w:r></w:p>
    <w:p><w:r><w:t>变量用于记住和处理信息。</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with zipfile.ZipFile(docx_path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", document_xml)

    processor = runtime_system.DocumentProcessor(chunk_size=2000, chunk_overlap=0)
    documents = processor.process_file(str(docx_path))
    full_text = "\n\n".join(str(document.page_content or "") for document in documents)

    assert "变量定义与使用" in full_text
    assert "变量用于记住和处理信息" in full_text
    assert "PK" not in full_text
    assert "[Content_Types]" not in full_text


def test_active_runtime_has_no_legacy_pdf_parser_residue():
    repo_root = Path(__file__).resolve().parents[5]
    checked_paths = [
        repo_root / "Edu_AI" / "api" / "src" / "config.py",
        repo_root / "Edu_AI" / "api" / "src" / "requirements.txt",
        repo_root / "Edu_AI" / "api" / "src" / "requirements-lock.txt",
        repo_root / "Edu_AI" / "api" / "src" / "modules" / "rag_v2" / "rag_main" / "system.py",
        repo_root / "EduAgent" / "chunks.py",
        repo_root / "EduAgent" / "services" / "content_cleaner.py",
        repo_root / "EduAgent" / "requirements.txt",
        repo_root / "EduAgent" / "install_deps.ps1",
    ]
    forbidden = [
        "doc" + "ling",
        "PyMu" + "PDF",
        "pymu" + "pdf",
        "fit" + "z",
        "PyMu" + "PDFLoader",
        "RAG_USE_DOC" + "LING",
        "DOC" + "LING_AVAILABLE",
    ]

    offenders = []
    for path in checked_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        for token in forbidden:
            if token.lower() in lowered:
                offenders.append(f"{path.relative_to(repo_root)} contains {token}")

    assert offenders == []


def test_document_processor_pdf_fails_when_mineru_fails_without_local_parser_fallback(monkeypatch):
    pdf_path = _make_workspace_tmp("mineru_failure") / "lesson.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test")

    monkeypatch.setattr(runtime_system, "MINERU_AVAILABLE", True)
    processor = runtime_system.DocumentProcessor(chunk_size=2000, chunk_overlap=0)

    def fail_mineru(**_kwargs):
        return {
            "success": False,
            "error": "MinerU test failure",
            "markdown_text": "",
            "images": [],
            "temp_dirs_to_cleanup": [],
        }

    monkeypatch.setattr(processor, "_parse_pdf_with_mineru", fail_mineru)

    with pytest.raises(ValueError, match="MinerU test failure"):
        processor.process_file(str(pdf_path), owner="alice", doc_id="doc-1")


def test_document_processor_mineru_images_are_registered_as_linked_images(monkeypatch):
    workspace = _make_workspace_tmp("mineru_linked_images")
    pdf_path = workspace / "lesson.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test")
    source_image = workspace / "hash.jpg"
    source_image.write_bytes(b"fake image")
    images_root = workspace / "storage" / "images"

    monkeypatch.setattr(runtime_system, "MINERU_AVAILABLE", True)
    processor = runtime_system.DocumentProcessor(chunk_size=2000, chunk_overlap=0)

    def parse_with_image(**_kwargs):
        return {
            "success": True,
            "error": "",
            "markdown_text": "正文\n\n![图 1](images/hash.jpg)",
            "images": [{"path": str(source_image), "name": "hash.jpg", "page_offset": 1}],
            "temp_dirs_to_cleanup": [],
        }

    monkeypatch.setattr(processor, "_parse_pdf_with_mineru", parse_with_image)
    documents = processor.process_file(
        str(pdf_path),
        owner="alice",
        doc_id="doc-1",
        images_root=images_root,
    )

    text_documents = [
        document
        for document in documents
        if str((document.metadata or {}).get("modality", "text")).lower() != "image"
    ]
    assert text_documents
    linked_images = text_documents[0].metadata.get("linked_images")
    assert linked_images == [
        {
            "image_path": str(images_root / "alice" / "doc-1" / "hash.jpg"),
            "image_name": "hash.jpg",
            "image_alt": "MinerU 解析的插图",
            "page": 1,
            "source": "mineru",
        }
    ]
    assert (images_root / "alice" / "doc-1" / "hash.jpg").exists()


def test_normalize_owner_rejects_pathlike_values():
    assert runtime_api._normalize_owner("alice") == "alice"

    for owner in ("..", "../alice", "alice/bob", "alice\\bob", "C:\\temp", "/tmp/alice", "alice.."):
        with pytest.raises(runtime_api.HTTPException) as exc_info:
            runtime_api._normalize_owner(owner)
        assert exc_info.value.status_code == 400


def test_guarded_storage_requires_expected_owner_layout(monkeypatch):
    storage_root = _make_workspace_tmp("guarded_storage") / "storage"
    monkeypatch.setattr(runtime_api.Config, "STORAGE_ROOT", storage_root)

    good_file = storage_root / "images" / "alice" / "pic.png"
    good_file.parent.mkdir(parents=True, exist_ok=True)
    good_file.write_bytes(b"image")

    wrong_owner = storage_root / "videos" / "bob" / "clip.mp4"
    wrong_owner.parent.mkdir(parents=True, exist_ok=True)
    wrong_owner.write_bytes(b"video")

    wrong_layout = storage_root / "misc" / "alice" / "note.txt"
    wrong_layout.parent.mkdir(parents=True, exist_ok=True)
    wrong_layout.write_text("nope", encoding="utf-8")

    legacy_file = storage_root / "images" / "legacy.png"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_bytes(b"legacy")

    response = runtime_api._guarded_storage_file_response("images/alice/pic.png", {"username": "alice"})
    assert response.path == str(good_file)

    legacy_response = runtime_api._guarded_storage_file_response("images/legacy.png", {"username": "alice"})
    assert legacy_response.path == str(legacy_file)

    with pytest.raises(runtime_api.HTTPException) as exc_info:
        runtime_api._guarded_storage_file_response("images/alice/pic.png", {"username": "Alice"})
    assert exc_info.value.status_code == 403

    for candidate in (wrong_owner, wrong_layout):
        with pytest.raises(runtime_api.HTTPException) as exc_info:
            relative_candidate = candidate.relative_to(storage_root).as_posix()
            runtime_api._guarded_storage_file_response(relative_candidate, {"username": "alice"})
        assert exc_info.value.status_code == 403

    with pytest.raises(runtime_api.HTTPException) as exc_info:
        runtime_api._guarded_storage_file_response(str(good_file), {"username": "alice"})
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_query_routes_require_auth_and_pass_owner_scope(monkeypatch):
    query_signature = inspect.signature(runtime_api.rag_query)
    stream_signature = inspect.signature(runtime_api.rag_query_stream)

    assert "current_user" in query_signature.parameters
    assert "current_user" in stream_signature.parameters

    captured = {}

    class FakeRAGSystem:
        def query(self, question, **kwargs):
            captured["question"] = question
            captured.update(kwargs)
            return {"question": question, "answer": "ok", "sources": []}

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.rag_query(
        runtime_api.QueryRequest(question="owner scoped"),
        current_user={"username": "alice"},
    )

    assert response.answer == "ok"
    assert captured["owner"] == "alice"


@pytest.mark.anyio
async def test_query_stream_scopes_sources_and_emits_guarded_media_urls(monkeypatch):
    captured = {}
    leaked_windows_path = r"C:\secret\alice\diagram.png"

    class FakeEmbeddingClient:
        def embed_query(self, query):
            captured["retrieval_query"] = query
            return [0.1]

    class FakeVectorStore:
        def hybrid_search(self, **kwargs):
            captured["allowed_sources"] = kwargs["allowed_sources"]
            return [
                {
                    "content": "![img](images/pic.png)",
                    "combined_score": 0.9,
                    "metadata": {
                        "source": "user_alice:doc1",
                        "owner": "alice",
                        "modality": "image",
                        "image_path": str(runtime_api.Config.STORAGE_ROOT / "images" / "alice" / "pic.png"),
                        "source_path": leaked_windows_path,
                    },
                },
                {
                    "content": '<video src="videos/clip.mp4" controls></video>',
                    "combined_score": 0.8,
                    "metadata": {
                        "source": "user_alice:doc2",
                        "owner": "alice",
                        "modality": "video",
                        "video_path": str(runtime_api.Config.STORAGE_ROOT / "videos" / "alice" / "clip.mp4"),
                        "source_path": leaked_windows_path,
                    },
                },
            ]

    class FakeRAGSystem:
        embedding_client = FakeEmbeddingClient()
        vector_store = FakeVectorStore()

        def _rewrite_query(self, question, conversation_history):
            return question

        def _call_llm(self, messages, stream):
            return iter(["chunk"])

        def list_documents(self, owner=None):
            captured["owner"] = owner
            return [
                {
                    "file_path": str(runtime_api.Config.DOCUMENTS_ROOT / owner / "doc1.md"),
                    "include_in_search": True,
                    "owner": owner,
                },
                {
                    "file_path": str(runtime_api.Config.DOCUMENTS_ROOT / owner / "doc2.md"),
                    "include_in_search": True,
                    "owner": owner,
                },
            ]

        def _make_index_key(self, file_path, owner):
            return f"user_{owner}:{file_path}"

        def _make_source_key(self, file_path, owner):
            return f"user_{owner}:{file_path}"

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())
    response = await runtime_api.rag_query_stream(
        runtime_api.QueryRequest(question="show media"),
        current_user={"username": "alice"},
    )

    assert isinstance(response, StreamingResponse)

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))

    metadata_payload = json.loads(chunks[0].removeprefix("data: ").strip())

    assert captured["owner"] == "alice"
    assert captured["allowed_sources"]
    assert all(source.startswith("user_alice:") for source in captured["allowed_sources"])
    rendered = json.dumps(metadata_payload, ensure_ascii=False)
    assert "/storage/" not in rendered
    assert "\\storage\\" not in rendered
    assert str(runtime_api.Config.STORAGE_ROOT) not in rendered
    assert leaked_windows_path not in rendered
    assert "image_path" not in rendered
    assert "video_path" not in rendered
    assert "source_path" not in rendered
    assert "/api/rag/image?path=" in rendered
    assert "/api/rag/media?path=" in rendered

    image_url = metadata_payload["sources"][0]["metadata"]["image_url"]
    image_ref = unquote(parse_qs(urlsplit(image_url).query)["path"][0])
    assert image_ref == "images/alice/pic.png"
    assert str(runtime_api.Config.STORAGE_ROOT) not in image_ref
    assert ":" not in image_ref

    video_url = metadata_payload["sources"][1]["metadata"]["video_url"]
    video_ref = unquote(parse_qs(urlsplit(video_url).query)["path"][0])
    assert video_ref == "videos/alice/clip.mp4"
    assert str(runtime_api.Config.STORAGE_ROOT) not in video_ref
    assert ":" not in video_ref


@pytest.mark.anyio
async def test_upload_temp_uses_user_temp_dir_and_progress_is_owner_scoped(monkeypatch):
    monkeypatch.setattr(runtime_api.Config, "TEMP_DIR", _make_workspace_tmp("upload_temp") / "temp")
    runtime_api._import_jobs.clear()

    upload = runtime_api.UploadFile(filename="../notes.md", file=io.BytesIO(b"hello"))
    response = await runtime_api.upload_temp(file=upload, current_user={"username": "alice"})

    temp_path = runtime_api.Config.TEMP_DIR / response.temp_file_path
    assert response.filename == "notes.md"
    assert temp_path.parent == runtime_api.Config.TEMP_DIR / "alice"
    assert temp_path.exists()
    assert str(runtime_api.Config.TEMP_DIR) not in response.temp_file_path
    assert runtime_api._import_jobs[response.job_id]["owner"] == "alice"
    assert runtime_api._import_jobs[response.job_id]["file"] == response.temp_file_path

    progress = await runtime_api.get_import_progress(response.job_id, current_user={"username": "alice"})
    assert progress.job_id == response.job_id

    with pytest.raises(runtime_api.HTTPException) as exc_info:
        await runtime_api.get_import_progress(response.job_id, current_user={"username": "bob"})
    assert exc_info.value.status_code in {403, 404}


@pytest.mark.anyio
async def test_import_route_sanitizes_uploaded_filename(monkeypatch):
    monkeypatch.setattr(runtime_api.Config, "DOCUMENTS_ROOT", _make_workspace_tmp("import_route") / "documents")

    captured = {}

    class FakeRAGSystem:
        def import_document(self, file_path, force_reimport=False, owner=None):
            captured["file_path"] = file_path
            captured["owner"] = owner
            return {
                "status": "success",
                "message": "ok",
                "file": file_path,
                "chunk_count": 1,
            }

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    upload = runtime_api.UploadFile(filename="nested/lesson.md", file=io.BytesIO(b"lesson"))
    response = await runtime_api.import_document(file=upload, current_user={"username": "alice"})

    assert response.status == "success"
    assert Path(captured["file_path"]) == runtime_api.Config.DOCUMENTS_ROOT / "alice" / "lesson.md"
    assert captured["owner"] == "alice"


@pytest.mark.anyio
async def test_import_path_is_confined_to_user_temp_files(monkeypatch):
    tmp_root = _make_workspace_tmp("import_path")
    monkeypatch.setattr(runtime_api.Config, "TEMP_DIR", tmp_root / "temp")
    monkeypatch.setattr(runtime_api.Config, "DOCUMENTS_ROOT", tmp_root / "documents")
    runtime_api._import_jobs.clear()

    user_temp_dir = runtime_api.Config.TEMP_DIR / "alice"
    user_temp_dir.mkdir(parents=True, exist_ok=True)
    safe_file = user_temp_dir / "upload.md"
    safe_file.write_text("safe", encoding="utf-8")

    unsafe_file = tmp_root / "outside.md"
    unsafe_file.write_text("unsafe", encoding="utf-8")

    captured = {}

    class FakeRAGSystem:
        def import_document(self, file_path, force_reimport=False, progress_callback=None, owner=None):
            captured["file_path"] = file_path
            captured["owner"] = owner
            if progress_callback is not None:
                progress_callback(50, "indexing")
            return {
                "status": "success",
                "message": "ok",
                "file": file_path,
                "chunk_count": 1,
            }

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.import_document_from_path(
        runtime_api.ImportFromPathRequest(file_path=str(safe_file), job_id="job-safe"),
        current_user={"username": "alice"},
    )

    assert response.status == "success"
    assert Path(captured["file_path"]) == runtime_api.Config.DOCUMENTS_ROOT / "alice" / safe_file.name
    assert captured["owner"] == "alice"
    assert runtime_api._import_jobs["job-safe"]["owner"] == "alice"
    assert not safe_file.exists()

    with pytest.raises(runtime_api.HTTPException) as exc_info:
        await runtime_api.import_document_from_path(
            runtime_api.ImportFromPathRequest(file_path=str(unsafe_file)),
            current_user={"username": "alice"},
        )
    assert exc_info.value.status_code in {400, 403}


@pytest.mark.anyio
async def test_stats_require_auth_and_are_owner_scoped(monkeypatch):
    stats_signature = inspect.signature(runtime_api.get_stats)
    assert "current_user" in stats_signature.parameters

    captured = {}

    class FakeRAGSystem:
        def get_stats(self):
            return {
                "document_count": 99,
                "indexed_files": 99,
                "indexed_files_list": ["global"],
            }

        def list_documents(self, owner=None):
            captured["owner"] = owner
            return [
                {"file_path": "user_alice:/docs/a.md"},
                {"file_path": "user_alice:/docs/b.md"},
            ]

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.get_stats(current_user={"username": "alice"})

    assert captured["owner"] == "alice"
    assert response.document_count == 2
    assert response.indexed_files == 2
    assert response.indexed_files_list == ["user_alice:/docs/a.md", "user_alice:/docs/b.md"]


@pytest.mark.anyio
async def test_list_documents_includes_owner_scoped_image_entries(monkeypatch):
    image_path = runtime_api.Config.STORAGE_ROOT / "images" / "alice" / "diagram.png"
    index_key = f"user_alice:{image_path}"

    class FakeRAGSystem:
        def list_documents(self, owner=None):
            return []

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())
    monkeypatch.setattr(
        runtime_api,
        "_image_index",
        {
            index_key: {
                "file_path": str(image_path),
                "file_name": "diagram.png",
                "include_in_search": True,
                "imported_at": "2026-04-15T00:00:00",
                "file_size": 123,
                "hash": "hash-1",
                "owner": "alice",
                "modality": "image",
            },
            "user_bob:/tmp/secret.png": {
                "file_path": "/tmp/secret.png",
                "file_name": "secret.png",
                "owner": "bob",
                "modality": "image",
            },
        },
    )

    response = await runtime_api.list_documents(current_user={"username": "alice"})

    assert len(response) == 1
    image_doc = response[0]
    assert image_doc.file_path == index_key
    assert image_doc.file_name == "diagram.png"
    assert image_doc.modality == "image"
    assert image_doc.image_url == "/api/rag/image?path=images%2Falice%2Fdiagram.png"


@pytest.mark.anyio
async def test_list_documents_exposes_source_icon_url_for_web_documents(monkeypatch):
    icon_path = runtime_api.Config.STORAGE_ROOT / "images" / "alice" / "site-icon.png"
    index_key = "user_alice:D:/docs/alice/web.md"

    class FakeRAGSystem:
        def list_documents(self, owner=None):
            assert owner == "alice"
            return [
                {
                    "file_path": index_key,
                    "file_name": "Example Site",
                    "include_in_search": True,
                    "chunk_count": 3,
                    "owner": owner,
                    "doc_kind": "web",
                    "source_url": "https://example.com/article",
                    "source_domain": "example.com",
                    "source_title": "Example Site",
                    "source_icon_path": str(icon_path),
                }
            ]

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.list_documents(current_user={"username": "alice"})

    assert len(response) == 1
    assert response[0].file_path == index_key
    assert response[0].doc_kind == "web"
    assert response[0].source_icon_url == "/api/rag/image?path=images%2Falice%2Fsite-icon.png"


@pytest.mark.anyio
async def test_image_document_content_returns_preview_metadata(monkeypatch):
    image_path = runtime_api.Config.STORAGE_ROOT / "images" / "alice" / "diagram.png"
    index_key = f"user_alice:{image_path}"

    class FakeRAGSystem:
        document_index = {}

        def _make_index_key(self, file_path, owner):
            return index_key

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())
    monkeypatch.setattr(
        runtime_api,
        "_image_index",
        {
            index_key: {
                "file_path": str(image_path),
                "file_name": "diagram.png",
                "include_in_search": True,
                "imported_at": "2026-04-15T00:00:00",
                "file_size": 123,
                "hash": "hash-1",
                "owner": "alice",
                "modality": "image",
            }
        },
    )

    response = await runtime_api.get_document_content(
        file_path=index_key,
        current_user={"username": "alice"},
    )

    assert response.file_path == index_key
    assert response.file_name == "diagram.png"
    assert response.total_chunks == 1
    assert response.chunks[0]["metadata"]["modality"] == "image"
    assert response.chunks[0]["metadata"]["image_url"] == "/api/rag/image?path=images%2Falice%2Fdiagram.png"


@pytest.mark.anyio
async def test_document_content_scrubs_embedded_image_chunks_to_relative_urls(monkeypatch):
    physical_path = str(Path("D:/docs/alice/lesson.pdf"))
    index_key = f"user_alice:{physical_path}"
    image_path = runtime_api.Config.STORAGE_ROOT / "images" / "alice" / "page1_0000.png"

    class FakeVectorStore:
        def get_documents_by_source(self, source_key):
            assert source_key == index_key
            return [
                {
                    "content": "正文段落",
                    "metadata": {"page": 1, "modality": "text"},
                },
                {
                    "content": "[IMAGE_CHUNK] 文件名: page1_0000.png",
                    "metadata": {
                        "page": 1,
                        "modality": "image",
                        "image_path": str(image_path),
                        "image_name": "page1_0000.png",
                    },
                },
            ]

    class FakeRAGSystem:
        def __init__(self):
            self.document_index = {
                index_key: {
                    "physical_path": physical_path,
                    "file_name": "lesson.pdf",
                    "owner": "alice",
                    "source_key": index_key,
                }
            }
            self.vector_store = FakeVectorStore()

        def _make_index_key(self, file_path, owner):
            return index_key

        def _make_source_key(self, file_path, owner):
            return index_key

    monkeypatch.delenv("SERVER_URL", raising=False)
    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.get_document_content(
        file_path=index_key,
        current_user={"username": "alice"},
    )

    image_chunks = [chunk for chunk in response.chunks if chunk["metadata"].get("modality") == "image"]
    assert len(image_chunks) == 1
    assert image_chunks[0]["metadata"]["image_url"] == "/api/rag/image?path=images%2Falice%2Fpage1_0000.png"


@pytest.mark.anyio
async def test_document_content_appends_linked_web_images(monkeypatch):
    physical_path = str(Path("D:/docs/alice/example.md"))
    index_key = f"user_alice:{physical_path}"
    linked_image_path = runtime_api.Config.STORAGE_ROOT / "images" / "alice" / "example_001.png"

    class FakeVectorStore:
        def get_documents_by_source(self, source_key):
            assert source_key == index_key
            return [
                {
                    "content": "网页正文",
                    "metadata": {"page": 1, "modality": "text"},
                }
            ]

    class FakeRAGSystem:
        def __init__(self):
            self.document_index = {
                index_key: {
                    "physical_path": physical_path,
                    "file_name": "example.md",
                    "owner": "alice",
                    "source_key": index_key,
                    "linked_images": [
                        {
                            "image_path": str(linked_image_path),
                            "image_name": "网页配图 1",
                            "source": "crawl",
                        }
                    ],
                }
            }
            self.vector_store = FakeVectorStore()

        def _make_index_key(self, file_path, owner):
            return index_key

        def _make_source_key(self, file_path, owner):
            return index_key

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.get_document_content(
        file_path=index_key,
        current_user={"username": "alice"},
    )

    image_chunks = [chunk for chunk in response.chunks if chunk["metadata"].get("modality") == "image"]
    assert len(image_chunks) == 1
    assert image_chunks[0]["metadata"]["image_url"] == "/api/rag/image?path=images%2Falice%2Fexample_001.png"
    assert image_chunks[0]["metadata"]["image_name"] == "网页配图 1"


@pytest.mark.anyio
async def test_document_content_rewrites_mineru_markdown_images_to_guarded_doc_storage(monkeypatch):
    physical_path = str(Path("D:/docs/alice/mineru.pdf"))
    index_key = f"user_alice:{physical_path}"

    class FakeVectorStore:
        def get_documents_by_source(self, source_key):
            assert source_key == index_key
            return [
                {
                    "content": "正文\n\n![图 1](images/hash.jpg)",
                    "metadata": {"page": 1, "modality": "text"},
                }
            ]

    class FakeRAGSystem:
        def __init__(self):
            self.document_index = {
                index_key: {
                    "physical_path": physical_path,
                    "file_name": "mineru.pdf",
                    "owner": "alice",
                    "source_key": index_key,
                    "image_doc_id": "doc-mineru",
                }
            }
            self.vector_store = FakeVectorStore()

        def _make_index_key(self, file_path, owner):
            return index_key

        def _make_source_key(self, file_path, owner):
            return index_key

    monkeypatch.delenv("SERVER_URL", raising=False)
    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.get_document_content(
        file_path=index_key,
        current_user={"username": "alice"},
    )

    assert "images/hash.jpg" not in response.content
    assert str(runtime_api.Config.STORAGE_ROOT) not in response.content
    assert (
        "/api/rag/image?path=images%2Falice%2Fdoc-mineru%2Fhash.jpg"
        in response.content
    )
    assert (
        "/api/rag/image?path=images%2Falice%2Fdoc-mineru%2Fhash.jpg"
        in response.chunks[0]["content"]
    )


@pytest.mark.anyio
async def test_document_content_resolves_public_course_relative_path_without_record_path(monkeypatch):
    physical_path = str(Path("D:/course/shared/legacy-lesson.md"))
    index_key = physical_path

    class FakeVectorStore:
        def get_documents_by_source(self, source_key):
            assert source_key == index_key
            return [
                {
                    "content": "public course content",
                    "metadata": {"page": 1, "source": index_key, "modality": "text"},
                }
            ]

    class FakeRAGSystem:
        def __init__(self):
            self.document_index = {
                index_key: {
                    "physical_path": physical_path,
                    "file_name": "legacy-lesson.md",
                    "owner": None,
                    "source_key": index_key,
                }
            }
            self.vector_store = FakeVectorStore()

        def _make_index_key(self, file_path, owner):
            return f"user_{owner}:{file_path}" if owner else str(file_path)

        def _make_source_key(self, file_path, owner):
            return f"user_{owner}:{file_path}" if owner else str(file_path)

        def list_documents(self, owner=None):
            return [
                {
                    "file_path": index_key,
                    "file_name": "legacy-lesson.md",
                    "owner": None,
                }
            ]

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.get_document_content(
        file_path="knowledge_base/documents/legacy-lesson.md",
        current_user={"username": "alice"},
    )

    assert response.file_path == index_key
    assert response.file_name == "legacy-lesson.md"
    assert response.content == "public course content"
    assert response.total_chunks == 1


@pytest.mark.anyio
async def test_document_summary_resolves_public_course_relative_path_without_record_path(monkeypatch):
    physical_path = str(Path("D:/course/shared/legacy-lesson.md"))
    index_key = physical_path
    summarize_calls = []

    class FakeRAGSystem:
        def __init__(self):
            self.document_index = {
                index_key: {
                    "physical_path": physical_path,
                    "file_name": "legacy-lesson.md",
                    "owner": None,
                    "source_key": index_key,
                }
            }

        def _make_index_key(self, file_path, owner):
            return f"user_{owner}:{file_path}" if owner else str(file_path)

        def _make_source_key(self, file_path, owner):
            return f"user_{owner}:{file_path}" if owner else str(file_path)

        def list_documents(self, owner=None):
            return [
                {
                    "file_path": index_key,
                    "file_name": "legacy-lesson.md",
                    "owner": None,
                }
            ]

        def summarize_document(self, file_path, force_refresh=False, owner=None):
            summarize_calls.append(
                {
                    "file_path": file_path,
                    "force_refresh": force_refresh,
                    "owner": owner,
                }
            )
            return {
                "file_path": file_path,
                "summary": "public course summary",
                "summary_updated_at": "2026-04-20T00:00:00",
            }

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.get_document_summary(
        runtime_api.DocumentSummaryRequest(file_path="knowledge_base/documents/legacy-lesson.md"),
        current_user={"username": "alice"},
    )

    assert response["summary"] == "public course summary"
    assert summarize_calls == [
        {
            "file_path": index_key,
            "force_refresh": False,
            "owner": None,
        }
    ]


@pytest.mark.anyio
async def test_document_participation_returns_updated_index_key_record(monkeypatch):
    physical_path = str(Path("D:/docs/alice/lesson.md"))
    index_key = f"user_alice:{physical_path}"

    class FakeRAGSystem:
        def __init__(self):
            self.document_index = {
                index_key: {
                    "physical_path": physical_path,
                    "file_name": "lesson.md",
                    "include_in_search": True,
                    "chunk_count": 2,
                    "owner": "alice",
                }
            }

        def _make_index_key(self, file_path, owner):
            return index_key

        def update_document_participation(self, file_path, include, owner=None):
            self.document_index[file_path]["include_in_search"] = include
            return {"file_path": file_path, "include_in_search": include}

        def list_documents(self, owner=None):
            return [
                {
                    "file_path": index_key,
                    "file_name": "lesson.md",
                    "include_in_search": self.document_index[index_key]["include_in_search"],
                    "chunk_count": 2,
                    "owner": owner,
                }
            ]

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.update_document_participation(
        runtime_api.DocumentParticipationRequest(file_path=physical_path, include_in_search=False),
        current_user={"username": "alice"},
    )

    assert response["file_path"] == index_key
    assert response["include_in_search"] is False


@pytest.mark.anyio
async def test_document_details_uses_index_key_for_lookup(monkeypatch):
    physical_path = str(Path("D:/docs/alice/lesson.md"))
    index_key = f"user_alice:{physical_path}"
    captured = {}
    leaked_image_path = str(runtime_api.Config.STORAGE_ROOT / "images" / "alice" / "lesson.png")

    class FakeRAGSystem:
        document_index = {
            index_key: {
                "physical_path": physical_path,
                "file_name": "lesson.md",
                "include_in_search": True,
                "chunk_count": 3,
                "owner": "alice",
            }
        }

        def _make_index_key(self, file_path, owner):
            return index_key

        def get_document_details(self, file_path, sample_limit=5):
            captured["file_path"] = file_path
            if file_path != index_key:
                raise FileNotFoundError(file_path)
            return {
                "file_path": physical_path,
                "file_name": "lesson.md",
                "include_in_search": True,
                "chunk_count": 3,
                "text_chunk_count": 2,
                "image_chunk_count": 1,
                "samples": [
                    {
                        "content": "image chunk",
                        "page": 1,
                        "id": "chunk-1",
                        "modality": "image",
                        "image_path": leaked_image_path,
                    }
                ],
            }

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    response = await runtime_api.get_document_details(
        file_path=physical_path,
        current_user={"username": "alice"},
    )

    assert captured["file_path"] == index_key
    assert response["file_path"] == index_key
    assert response["samples"][0]["modality"] == "image"
    assert "image_path" not in response["samples"][0]
    assert response["samples"][0]["image_url"].endswith("path=images%2Falice%2Flesson.png")


@pytest.mark.anyio
async def test_document_management_routes_preserve_http_exceptions(monkeypatch):
    physical_path = str(Path("D:/docs/alice/lesson.md"))
    index_key = f"user_alice:{physical_path}"

    class FakeVectorStore:
        def get_documents_by_source(self, source_key):
            return []

    class FakeRAGSystem:
        vector_store = FakeVectorStore()
        document_index = {
            index_key: {
                "physical_path": physical_path,
                "file_name": "lesson.md",
                "include_in_search": True,
                "chunk_count": 1,
                "owner": "bob",
            }
        }

        def _make_index_key(self, file_path, owner):
            return index_key

        def _make_source_key(self, file_path, owner):
            return f"user_{owner}:{file_path}"

        def delete_document(self, file_path, owner=None):
            raise AssertionError("delete_document should not be called")

        def summarize_document(self, file_path, force_refresh=False, owner=None):
            raise AssertionError("summarize_document should not be called")

    monkeypatch.setattr(runtime_api, "get_rag_system", lambda: FakeRAGSystem())

    with pytest.raises(runtime_api.HTTPException) as delete_exc:
        await runtime_api.delete_document(file_path=physical_path, current_user={"username": "alice"})
    assert delete_exc.value.status_code == 403

    with pytest.raises(runtime_api.HTTPException) as summary_exc:
        await runtime_api.get_document_summary(
            runtime_api.DocumentSummaryRequest(file_path=physical_path),
            current_user={"username": "alice"},
        )
    assert summary_exc.value.status_code == 403

    with pytest.raises(runtime_api.HTTPException) as content_exc:
        await runtime_api.get_document_content(file_path=physical_path, current_user={"username": "alice"})
    assert content_exc.value.status_code == 403
