from sqlalchemy import create_engine, text

from app.database.cutover_report_cli import main
from app.database.models import Base


def test_cutover_report_accepts_current_schema(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'database.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        connection.execute(
            text("INSERT INTO alembic_version(version_num) VALUES ('20260810_0008')")
        )
    monkeypatch.setenv("PERSISTENCE_PROFILE", "database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    for variable in (
        "USER_PERSISTENCE_MODE", "COURSE_PERSISTENCE_MODE",
        "COURSE_MEMBERSHIP_PERSISTENCE_MODE", "CONVERSATION_PERSISTENCE_MODE",
        "JOB_PERSISTENCE_MODE", "MATERIAL_PERSISTENCE_MODE",
        "KNOWLEDGE_PERSISTENCE_MODE", "APP_STATE_PERSISTENCE_MODE",
        "LEARNING_PERSISTENCE_MODE", "TASK_PERSISTENCE_MODE",
    ):
        monkeypatch.setenv(variable, "postgres")

    assert main(["--database-url", database_url]) == 0
