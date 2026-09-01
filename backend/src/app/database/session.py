from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


class DatabaseNotConfigured(RuntimeError):
    pass


@contextmanager
def database_session(
    *,
    engine: Engine | None = None,
    database_url: str | None = None,
) -> Iterator[Session]:
    owns_engine = engine is None
    if engine is None:
        normalized_url = str(
            database_url
            if database_url is not None
            else os.getenv("DATABASE_URL", "")
        ).strip()
        if not normalized_url:
            raise DatabaseNotConfigured("DATABASE_URL is not configured")
        engine = create_engine(normalized_url, pool_pre_ping=True)

    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        if owns_engine:
            engine.dispose()
