from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import create_engine

from app.database import DurableTaskModel, database_session


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import the legacy SQLite task queue into PostgreSQL."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "data" / "tasks.db",
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--apply", action="store_true")
    return parser


def _json(value: Any) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    decoded = json.loads(str(value))
    return dict(decoded) if isinstance(decoded, dict) else {"value": decoded}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    rows: list[sqlite3.Row] = []
    if args.source.exists():
        source = sqlite3.connect(args.source)
        source.row_factory = sqlite3.Row
        try:
            exists = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tasks'"
            ).fetchone()
            if exists:
                rows = list(source.execute("SELECT * FROM tasks ORDER BY task_id"))
        finally:
            source.close()
    if args.apply:
        database_url = str(args.database_url or "").strip()
        if not database_url:
            raise ValueError("--database-url is required with --apply")
        engine = create_engine(database_url, pool_pre_ping=True)
        with database_session(engine=engine) as session:
            for row in rows:
                record = session.get(DurableTaskModel, str(row["task_id"]))
                if record is None:
                    record = DurableTaskModel(task_id=str(row["task_id"]))
                    session.add(record)
                record.workflow_type = str(row["workflow_type"] or "")
                record.handler_version = int(row["handler_version"] or 1)
                record.owner_user_id = str(row["owner_user_id"] or "")
                record.course_id = str(row["course_id"] or "").strip() or None
                record.scope_type = str(row["scope_type"] or "course")
                record.scope_id = str(row["scope_id"] or "").strip() or None
                record.command = _json(row["command_json"])
                record.config_snapshot_id = str(row["config_snapshot_id"] or "").strip() or None
                record.idempotency_key = str(row["idempotency_key"] or "").strip() or None
                record.status = str(row["status"] or "pending")
                record.attempt_count = int(row["attempt_count"] or 0)
                record.max_attempts = int(row["max_attempts"] or 3)
                record.available_at = float(row["available_at"] or 0)
                record.lease_owner = str(row["lease_owner"] or "").strip() or None
                record.lease_expires_at = row["lease_expires_at"]
                record.heartbeat_at = row["heartbeat_at"]
                record.deadline_at = row["deadline_at"]
                record.cancel_requested = bool(row["cancel_requested"])
                record.progress = _json(row["progress_json"])
                record.result = _json(row["result_json"])
                record.result_ref = _json(row["result_ref_json"])
                record.error_code = str(row["error_code"] or "").strip() or None
                record.error = row["error"]
                record.created_at = str(row["created_at"])
                record.started_at = row["started_at"]
                record.finished_at = row["finished_at"]
                record.updated_at = float(row["updated_at"] or 0)
    print(json.dumps({
        "mode": "applied" if args.apply else "preview",
        "tasks": len(rows),
        "source": str(args.source),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
