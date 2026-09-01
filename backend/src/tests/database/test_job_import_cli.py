import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base, JobEvent, JobRecord


def test_job_import_cli_applies_directory_idempotently(tmp_path: Path, capsys):
    from app.database.migrate_jobs_cli import main

    source = tmp_path / "jobs"
    source.mkdir()
    payload = {
        "schema_version": 2,
        "version": 1,
        "edu_job_id": "job-import",
        "kind": "rag_import",
        "status": "succeeded",
        "step": "done",
        "progress": 100,
        "message": "",
        "owner_user_id": "teacher",
        "course_id": "course-1",
        "scope_type": "course",
        "input_summary": {},
        "retryable": False,
        "cancelable": False,
        "created_at": "2026-08-10T10:00:00+00:00",
        "updated_at": "2026-08-10T10:01:00+00:00",
    }
    (source / "job-import.json").write_text(json.dumps(payload), encoding="utf-8")
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'target.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    for _ in range(2):
        assert main([
            "--source", str(source), "--database-url", database_url, "--apply"
        ]) == 0
        assert json.loads(capsys.readouterr().out)["jobs"] == 1

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(JobRecord)) == 1
        assert session.scalar(select(func.count()).select_from(JobEvent)) == 1
