import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from app.database import Base
from tests.self_learning.test_session_repository import repository
from app.self_learning.progress_repository import TABLES, ProgressRepository
from tests.self_learning.test_progress_repository import event


def test_progress_migration_upgrade_use_downgrade(repository):
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/20260917_0024_learning_progress.py'
    spec = importlib.util.spec_from_file_location('learning_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = list(TABLES)
    with repository.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection, opts={'target_metadata': Base.metadata})):
            module.upgrade()
        inspector = inspect(connection)
        for name in names:
            expected = Base.metadata.tables[name]
            assert {c['name'] for c in inspector.get_columns(name)} == set(expected.columns.keys())
            assert {c['name'] for c in inspector.get_check_constraints(name)} == {
                c.name for c in expected.constraints if c.__class__.__name__ == 'CheckConstraint'}
            assert len(inspector.get_foreign_keys(name)) == len(expected.foreign_key_constraints)
    assert ProgressRepository(repository.engine).record('alice', 'course', 'a', event())['applied']
    with repository.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()
        assert not set(names) & set(inspect(connection).get_table_names())
        assert 'conversation_messages' in inspect(connection).get_table_names()
