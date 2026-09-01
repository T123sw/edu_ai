from pathlib import Path
from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine

from app.database import Base


@pytest.fixture
def engine(tmp_path: Path):
    value = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'state.db').as_posix()}")
    Base.metadata.create_all(value)
    try:
        yield value
    finally:
        value.dispose()


def test_app_state_repository_crud_and_namespace_listing(engine):
    from app.persistence.postgres_app_state_repository import PostgresAppStateRepository

    repository = PostgresAppStateRepository(engine)
    repository.put("crawl_batches", "batch-1", {"batch_id": "batch-1"})
    repository.put("crawl_batches", "batch-2", {"batch_id": "batch-2"})

    assert repository.get("crawl_batches", "batch-1") == {"batch_id": "batch-1"}
    assert len(repository.list("crawl_batches")) == 2
    assert repository.delete("crawl_batches", "batch-1") is True


def test_crawl_batch_store_uses_database_without_json(
    engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from app.services import crawl_batch_store

    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("APP_STATE_PERSISTENCE_MODE", "postgres")
    monkeypatch.setattr(crawl_batch_store.Config, "STORAGE_ROOT", tmp_path / "storage")
    @dataclass
    class Batch:
        batch_id: str
        query: str
        created_at: str

    batch = Batch(batch_id="batch-db", query="database", created_at="2026-08-10")

    crawl_batch_store.save_crawl_batch(batch, owner="teacher")

    assert crawl_batch_store.load_crawl_batch("batch-db", owner="teacher")["query"] == "database"
    assert crawl_batch_store.list_batches(owner="teacher")[0]["batch_id"] == "batch-db"
    assert not (tmp_path / "storage" / "crawl_batches" / "batch-db.json").exists()
