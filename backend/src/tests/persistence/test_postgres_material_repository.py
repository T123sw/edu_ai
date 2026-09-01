from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base


@pytest.fixture
def engine(tmp_path: Path):
    value = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'materials.db').as_posix()}")
    Base.metadata.create_all(value)
    try:
        yield value
    finally:
        value.dispose()


def _manifest(version: int = 1):
    return {
        "schema_version": 2,
        "version": version,
        "course_id": "course-1",
        "material_type": "report",
        "material_id": "report-1",
        "title": "Report",
        "status": "ready",
        "visibility": "course",
        "scope_type": "course",
        "scope_id": None,
        "artifact_paths": ["generated_materials/reports/report-1.md"],
        "content_hash": "abc",
        "created_at": "2026-08-10T10:00:00+00:00",
        "updated_at": "2026-08-10T10:00:00+00:00",
    }


def test_material_repository_tracks_versions_and_artifact_references(engine):
    from app.database import ArtifactFile, MaterialVersion
    from app.persistence.postgres_material_repository import PostgresMaterialRepository

    repository = PostgresMaterialRepository(engine)
    repository.upsert(_manifest())
    repository.upsert(_manifest(version=2))

    loaded = repository.get("course-1", "report", "report-1")
    assert loaded["version"] == 2
    assert repository.list("course-1", "report") == [loaded]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(MaterialVersion)) == 2
        assert session.scalar(select(func.count()).select_from(ArtifactFile)) == 1


def test_material_repository_preserves_standard_review_metadata_and_version(engine):
    from app.persistence.postgres_material_repository import PostgresMaterialRepository

    repository = PostgresMaterialRepository(engine)
    manifest = {
        **_manifest(),
        "material_id": "standard-leaf-1-study_guide",
        "origin_type": "standard",
        "standard_kind": "study_guide",
        "generation_batch_id": "batch-1",
        "current_review_status": "pending",
        "approved_version": None,
        "content": "pending content",
    }
    repository.upsert(manifest)

    loaded = repository.get("course-1", "report", manifest["material_id"])
    assert loaded["origin_type"] == "standard"
    assert loaded["standard_kind"] == "study_guide"
    assert loaded["current_review_status"] == "pending"
    version = repository.get_version("course-1", "report", manifest["material_id"], 1)
    assert version is not None
    assert version["generation_batch_id"] == "batch-1"
    assert version["review_status"] == "pending"


def test_course_storage_keeps_artifact_file_but_not_manifest_json_in_postgres_mode(
    engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from core.course_storage import CourseStorageManager

    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("MATERIAL_PERSISTENCE_MODE", "postgres")
    manager = CourseStorageManager(str(tmp_path / "course-data"))
    manager.create_course_structure("course-1")

    assert manager.save_generated_material(
        "course-1",
        "report",
        "report-1",
        {"title": "Database manifest", "file_extension": ".md"},
        file_data=b"report body",
    )

    manifest = manager.get_generated_material("course-1", "report", "report-1")
    assert manifest["title"] == "Database manifest"
    assert manager.list_generated_materials("course-1", "report") == [manifest]
    material_dir = (
        tmp_path / "course-data" / "courses" / "course-1" / "generated_materials" / "reports"
    )
    assert (material_dir / "report-1.md").exists()
    assert not (material_dir / "report-1.json").exists()
