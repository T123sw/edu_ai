"""Isolated contract databases; never read the application's DATABASE_URL."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.database import Base, User
from app.course_preparation import runtime_models


@pytest.fixture(params=['sqlite', 'postgresql'])
def db_engine(request, tmp_path):
    schema = 'preparation_test_' + uuid4().hex
    if request.param == 'postgresql':
        url = os.getenv('PREPARATION_TEST_DATABASE_URL')
        if not url:
            pytest.skip('set PREPARATION_TEST_DATABASE_URL to an isolated PostgreSQL test database')
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
        engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    else:
        admin = None
        engine = create_engine(f'sqlite:///{tmp_path / "preparation.db"}')

        @event.listens_for(engine, 'connect')
        def enable_foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA synchronous=OFF')
            connection.execute('PRAGMA journal_mode=MEMORY')
    try:
        tables = [Base.metadata.tables[name] for name in (
            'users', 'course_research_runs', 'course_preparations', 'course_preparation_attempts', 'course_preparation_events',
        )]
        Base.metadata.create_all(engine, tables=tables)
        with Session(engine) as session:
            for owner in ('alice', 'bob'):
                session.add(User(user_id=owner, username=owner, password_hash='test-only', role='student'))
            session.commit()
        yield engine
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            admin.dispose()


@pytest.fixture
def runtime_engine(db_engine):
    names = ('preparation_budgets', 'preparation_executions', 'preparation_actions')
    Base.metadata.create_all(db_engine, tables=[Base.metadata.tables[name] for name in names])
    return db_engine
