from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base


@pytest.fixture
def engine(tmp_path: Path):
    value = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'jobs.db').as_posix()}")
    Base.metadata.create_all(value)
    try:
        yield value
    finally:
        value.dispose()


def _job_payload(version: int = 1, status: str = "queued"):
    return {
        "schema_version": 2,
        "version": version,
        "edu_job_id": "job-1",
        "kind": "generate_report",
        "status": status,
        "step": status,
        "progress": 0 if status == "queued" else 100,
        "message": "",
        "owner_user_id": "teacher",
        "owner": "teacher",
        "course_id": "course-1",
        "scope_type": "course",
        "scope_id": None,
        "input_summary": {"topic": "AI"},
        "result_ref": None,
        "retryable": False,
        "cancelable": status == "queued",
        "created_at": "2026-08-10T10:00:00+00:00",
        "updated_at": "2026-08-10T10:00:00+00:00",
    }


def test_job_repository_round_trip_and_version_events(engine):
    from app.database import JobEvent
    from app.persistence.postgres_job_repository import PostgresJobRepository

    repository = PostgresJobRepository(engine)
    repository.upsert(_job_payload())
    repository.upsert(_job_payload(version=2, status="succeeded"))

    assert repository.get("job-1")["status"] == "succeeded"
    assert repository.list()[0]["version"] == 2
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(JobEvent)) == 2


def test_job_store_uses_database_without_job_json(
    engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from app.services import job_store

    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("JOB_PERSISTENCE_MODE", "postgres")
    monkeypatch.setattr(job_store.Config, "STORAGE_ROOT", tmp_path / "storage")

    created = job_store.create_job(
        kind=job_store.JobKind.GENERATE_REPORT,
        edu_job_id="job-db",
        owner_user_id="teacher",
    )
    updated = job_store.update_job(
        created.edu_job_id, status=job_store.JobStatus.SUCCEEDED
    )

    assert updated.status is job_store.JobStatus.SUCCEEDED
    assert job_store.get_job("job-db").version == 2
    assert job_store.list_jobs(limit=10)[0].edu_job_id == "job-db"
    assert not (tmp_path / "storage" / "jobs" / "job-db.json").exists()
