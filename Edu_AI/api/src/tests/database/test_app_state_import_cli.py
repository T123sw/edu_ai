import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import AppStateRecord, Base


def test_app_state_import_cli_imports_long_tail_json(tmp_path: Path, capsys):
    from app.database.migrate_app_state_cli import main

    storage = tmp_path / "storage"
    batches = storage / "crawl_batches"
    batches.mkdir(parents=True)
    (batches / "batch-1.json").write_text(
        json.dumps({"batch_id": "batch-1", "owner_user_id": "teacher"}),
        encoding="utf-8",
    )
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'target.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    assert main([
        "--storage-root", str(storage),
        "--courses-root", str(tmp_path / "courses"),
        "--agent-runs-db", str(tmp_path / "missing-agent-runs.db"),
        "--database-url", database_url,
        "--apply",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(AppStateRecord)) == 1
