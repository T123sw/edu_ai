from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260812_0015_knowledge_build_drafts.py"
)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("knowledge_build_drafts", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Inspector:
    def __init__(self, *, columns: set[str], indexes: set[str]) -> None:
        self._columns = columns
        self._indexes = indexes

    def get_columns(self, _table_name: str):
        return [{"name": name} for name in sorted(self._columns)]

    def get_indexes(self, _table_name: str):
        return [{"name": name} for name in sorted(self._indexes)]


class _Operations:
    def __init__(self) -> None:
        self.added_columns: list[str] = []
        self.created_indexes: list[tuple[str, str, list[str]]] = []

    @staticmethod
    def get_bind():
        return object()

    @staticmethod
    def f(name: str) -> str:
        return name

    def add_column(self, _table_name: str, column) -> None:
        self.added_columns.append(column.name)

    def create_index(self, name: str, table_name: str, columns: list[str]) -> None:
        self.created_indexes.append((name, table_name, columns))


def test_upgrade_adds_missing_graph_confirmation_schema(monkeypatch) -> None:
    migration = _load_migration()
    operations = _Operations()
    inspector = _Inspector(columns={"build_id"}, indexes=set())
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: inspector)

    migration.upgrade()

    assert operations.added_columns == [
        "revision",
        "graph_confirmed_at",
        "confirmed_graph_revision",
        "confirmed_by",
    ]
    assert operations.created_indexes == [
        (
            "ix_knowledge_builds_confirmed_by",
            "knowledge_builds",
            ["confirmed_by"],
        )
    ]


def test_upgrade_is_noop_when_merged_branch_schema_already_exists(monkeypatch) -> None:
    migration = _load_migration()
    operations = _Operations()
    inspector = _Inspector(
        columns={
            "build_id",
            "revision",
            "graph_confirmed_at",
            "confirmed_graph_revision",
            "confirmed_by",
        },
        indexes={"ix_knowledge_builds_confirmed_by"},
    )
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: inspector)

    migration.upgrade()

    assert operations.added_columns == []
    assert operations.created_indexes == []


def test_downgrade_preserves_reconciled_graph_confirmation_schema(monkeypatch) -> None:
    migration = _load_migration()
    operations = _Operations()
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()
