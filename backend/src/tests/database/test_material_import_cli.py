import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import ArtifactFile, Base, Material


def test_material_import_cli_imports_course_manifests(tmp_path: Path, capsys):
    from app.database.migrate_materials_cli import main

    courses = tmp_path / "courses"
    source = courses / "course-1" / "generated_materials" / "reports"
    source.mkdir(parents=True)
    (source / "report-1.json").write_text(
        json.dumps(
            {
                "version": 1,
                "material_id": "report-1",
                "material_type": "report",
                "title": "Imported report",
                "created_at": "2026-08-10T10:00:00+00:00",
                "updated_at": "2026-08-10T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (source / "report-1.md").write_text("report", encoding="utf-8")
    media = source / "report-1_media" / "audio"
    media.mkdir(parents=True)
    (media / "narration.wav").write_bytes(b"audio")
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'target.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    assert main([
        "--courses-root", str(courses), "--database-url", database_url, "--apply"
    ]) == 0
    assert json.loads(capsys.readouterr().out)["materials"] == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Material)) == 1
        assert session.scalar(select(func.count()).select_from(ArtifactFile)) == 2
