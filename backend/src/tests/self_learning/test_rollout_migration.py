import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from app.database import Base
from app.self_learning.migration_models import TABLES
from tests.self_learning.test_session_repository import repository

def test_rollout_migration_matches_models_and_reverses(repository):
    path=Path(__file__).resolve().parents[2]/'alembic/versions/20260917_0029_learning_rollout.py'
    spec=importlib.util.spec_from_file_location('learning_rollout_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with repository.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):module.upgrade()
        for name in TABLES:
            assert {c['name'] for c in inspect(connection).get_columns(name)}==set(Base.metadata.tables[name].columns.keys())
        with Operations.context(MigrationContext.configure(connection)):module.downgrade()
        assert not set(TABLES)&set(inspect(connection).get_table_names())
