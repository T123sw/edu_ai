import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from app.database import Base
from tests.self_learning.test_session_repository import repository


def test_enrichment_migration_upgrade_use_downgrade(repository):
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/20260917_0027_learning_enrichment.py'
    spec = importlib.util.spec_from_file_location('learning_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from app.self_learning.enrichment_models import TABLES
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
    assert repository.ensure_session('alice', 'course', 'a', '导学')['message_count'] == 1
    with repository.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()
        assert not set(names) & set(inspect(connection).get_table_names())
        assert 'conversation_messages' in inspect(connection).get_table_names()
