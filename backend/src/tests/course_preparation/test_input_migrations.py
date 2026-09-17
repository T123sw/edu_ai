import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from app.database import Base


def test_memory_and_document_migration_roundtrip(db_engine):
    modules=[]
    for filename in ('20260917_0028_memory_lifecycle.py','20260917_0029_preparation_documents.py'):
        path=Path(__file__).resolve().parents[2]/'alembic/versions'/filename
        spec=importlib.util.spec_from_file_location(filename,path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        modules.append(module)
    names=['agent_memory_epochs','agent_memory_suppressions','agent_memory_dependencies','agent_memory_changes','preparation_document_versions']
    with db_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for module in modules: module.upgrade()
        inspector=inspect(connection)
        for name in names:
            assert {c['name'] for c in inspector.get_columns(name)}==set(Base.metadata.tables[name].columns.keys())
        with Operations.context(MigrationContext.configure(connection)):
            for module in reversed(modules): module.downgrade()
        assert not set(names).intersection(inspect(connection).get_table_names())
