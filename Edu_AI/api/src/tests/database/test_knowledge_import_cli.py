import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base, KnowledgeDocument, RuntimeIndexEntry


def test_knowledge_import_cli_imports_course_and_runtime_indexes(tmp_path: Path, capsys):
    from app.database.migrate_knowledge_cli import main

    courses = tmp_path / "courses"
    kb = courses / "course-1" / "knowledge_base"
    kb.mkdir(parents=True)
    (kb / "index.json").write_text(
        json.dumps([{"id": "doc-1", "filename": "book.pdf", "path": "book.pdf"}]),
        encoding="utf-8",
    )
    document_index = tmp_path / "document_index.json"
    document_index.write_text(json.dumps({"source": {"hash": "abc"}}), encoding="utf-8")
    personal_root = tmp_path / "personal"
    personal_index = personal_root / "owner-hash" / "knowledge_base" / "index.json"
    personal_index.parent.mkdir(parents=True)
    personal_index.write_text(json.dumps([{
        "id": "personal-doc", "filename": "notes.md", "path": "notes.md",
        "library_type": "personal", "owner_user_id": "teacher",
        "course_id": "personal:teacher",
    }]), encoding="utf-8")
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'target.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    assert main([
        "--courses-root", str(courses),
        "--document-index", str(document_index),
        "--image-index", str(tmp_path / "missing-image-index.json"),
        "--video-index", str(tmp_path / "missing-video-index.json"),
        "--personal-root", str(personal_root),
        "--database-url", database_url,
        "--apply",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["knowledge_documents"] == 2
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(KnowledgeDocument)) == 2
        assert session.scalar(select(func.count()).select_from(RuntimeIndexEntry)) == 1
