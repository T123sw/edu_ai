import importlib.util
from io import StringIO
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from app.database import Base
from app.course_preparation.repository import PreparationRepository
from app.course_preparation.schemas import PreparationRequest


def migration():
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/20260917_0022_course_preparation_intake.py'
    spec = importlib.util.spec_from_file_location('preparation_intake_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AllowFixture:
    def authorize(self, owner_user_id, request):
        assert owner_user_id == 'alice'


def test_migration_roundtrip_and_intake(db_engine):
    module = migration()
    names = ['course_preparation_events', 'course_preparation_attempts', 'course_preparations']
    with db_engine.begin() as connection:
        for name in names:
            Base.metadata.tables[name].drop(connection)
        with Operations.context(MigrationContext.configure(connection, opts={'target_metadata': Base.metadata})):
            module.upgrade()
        inspector = inspect(connection)
        for name in names:
            expected = Base.metadata.tables[name]
            actual = {c['name']: c for c in inspector.get_columns(name)}
            assert set(actual) == set(expected.columns.keys())
            assert {c['name'] for c in inspector.get_check_constraints(name)} == {
                c.name for c in expected.constraints if c.__class__.__name__ == 'CheckConstraint'
            }
            assert {tuple(c['column_names']) for c in inspector.get_unique_constraints(name)} == {
                tuple(c.columns.keys()) for c in expected.constraints if c.__class__.__name__ == 'UniqueConstraint'
            }
            assert len(inspector.get_foreign_keys(name)) == len(expected.foreign_key_constraints)
    repo = PreparationRepository(db_engine, authorizer=AllowFixture())
    accepted = repo.accept(owner_user_id='alice', request=PreparationRequest.model_validate({
        'request_id': str(uuid4()), 'operation': 'create_course', 'goal': '学习图论',
    }))
    assert repo.get(owner_user_id='alice', preparation_id=accepted.preparation_id) == accepted
    with db_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()
        tables = inspect(connection).get_table_names()
        assert 'users' in tables
        assert not set(names).intersection(tables)


def test_postgresql_offline_ddl():
    output = StringIO()
    context = MigrationContext.configure(dialect_name='postgresql', opts={
        'as_sql': True, 'output_buffer': output, 'target_metadata': Base.metadata,
    })
    with Operations.context(context):
        migration().upgrade()
    sql = output.getvalue()
    assert sql.count('CREATE TABLE') == 3
    assert 'JSONB' in sql and 'TIMESTAMP WITH TIME ZONE' in sql
    assert 'uq_course_preparation_request' in sql
