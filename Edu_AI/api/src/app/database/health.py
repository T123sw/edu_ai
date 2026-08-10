from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


def probe_database(
    *,
    database_url: str | None = None,
    engine: Engine | None = None,
) -> dict[str, Any]:
    owns_engine = engine is None
    if engine is None:
        normalized_url = str(database_url or "").strip()
        if not normalized_url:
            return {
                "configured": False,
                "status": "disabled",
                "message": "database is not configured",
            }
        engine = create_engine(normalized_url, pool_pre_ping=True)

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "configured": True,
            "status": "ready",
            "message": "database connection ready",
        }
    except SQLAlchemyError:
        return {
            "configured": True,
            "status": "unavailable",
            "message": "database connection unavailable",
        }
    finally:
        if owns_engine:
            engine.dispose()
