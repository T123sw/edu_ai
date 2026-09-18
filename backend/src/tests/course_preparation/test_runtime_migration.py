import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from app.database import Base
from tests.course_preparation.test_runtime_foundation import repo, request


def test_runtime_migration_roundtrip(db_engine):
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/20260917_0030_preparation_runtime.py'
    spec = importlib.util.spec_from_file_location('runtime_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = ['preparation_executions', 'preparation_budgets', 'preparation_actions']
    with db_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection, opts={'target_metadata': Base.metadata})):
            module.upgrade()
        inspector = inspect(connection)
        for name in names:
            expected = Base.metadata.tables[name]
            assert {c['name'] for c in inspector.get_columns(name)} == set(expected.columns.keys())
            assert {c['name'] for c in inspector.get_check_constraints(name)} == {
                c.name for c in expected.constraints if c.__class__.__name__ == 'CheckConstraint'}
    service = repo(db_engine)
    value = service.submit('alice', request())
    assert service.claim('migration-worker').preparation_id == value['preparation_id']
    with db_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()
        assert not set(names).intersection(inspect(connection).get_table_names())
