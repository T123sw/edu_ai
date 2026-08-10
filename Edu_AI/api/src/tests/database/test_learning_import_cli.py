import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base, LearningTaskModel


def test_learning_import_cli_imports_sqlite_tasks(tmp_path: Path, capsys):
    from app.database.migrate_learning_cli import main

    source = tmp_path / "learning.db"
    connection = sqlite3.connect(source)
    connection.execute("""CREATE TABLE learning_tasks (
        task_id TEXT PRIMARY KEY, course_id TEXT, title TEXT, instructions TEXT,
        created_by TEXT, resource_refs_json TEXT, knowledge_point_ids_json TEXT,
        status TEXT, created_at TEXT, published_at TEXT, published_by TEXT)""")
    connection.execute(
        "INSERT INTO learning_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("task-1", "course-1", "Task", "Learn", "teacher", "[]", "[]", "draft", "2026-08-10T10:00:00+00:00", None, None),
    )
    connection.commit()
    connection.close()
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'target.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    assert main(["--source", str(source), "--database-url", database_url, "--apply"]) == 0
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(LearningTaskModel)) == 1
