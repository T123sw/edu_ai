from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.database import AppStateRecord, database_session


class PostgresAppStateRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def put(
        self,
        namespace: str,
        record_key: str,
        payload: Mapping[str, Any],
        *,
        owner_user_id: str | None = None,
    ) -> None:
        key = (str(namespace).strip(), str(record_key).strip())
        if not all(key):
            raise ValueError("namespace and record_key are required")
        value = dict(payload)
        with database_session(engine=self._engine) as session:
            record = session.get(AppStateRecord, key)
            if record is None:
                record = AppStateRecord(namespace=key[0], record_key=key[1])
                session.add(record)
            record.owner_user_id = (
                str(owner_user_id or value.get("owner_user_id") or value.get("owner") or "").strip()
                or None
            )
            record.payload = value

    def get(self, namespace: str, record_key: str) -> dict[str, Any] | None:
        with database_session(engine=self._engine) as session:
            record = session.get(AppStateRecord, (namespace, record_key))
            return dict(record.payload or {}) if record is not None else None

    def list(self, namespace: str) -> list[dict[str, Any]]:
        with database_session(engine=self._engine) as session:
            records = session.scalars(
                select(AppStateRecord)
                .where(AppStateRecord.namespace == namespace)
                .order_by(AppStateRecord.updated_at.desc(), AppStateRecord.record_key)
            ).all()
            return [dict(record.payload or {}) for record in records]

    def delete(self, namespace: str, record_key: str) -> bool:
        with database_session(engine=self._engine) as session:
            record = session.get(AppStateRecord, (namespace, record_key))
            if record is None:
                return False
            session.delete(record)
            return True
