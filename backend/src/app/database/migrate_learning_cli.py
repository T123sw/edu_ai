from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Sequence

from sqlalchemy import create_engine

from app.database import (
    LearningEventModel,
    LearningProgressModel,
    LearningTaskModel,
    database_session,
)
from app.persistence.postgres_repositories import _timestamp
from core.config import Config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import learning SQLite data into PostgreSQL.")
    parser.add_argument("--source", type=Path, default=Config.LEARNING_DB_PATH)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--apply", action="store_true")
    return parser


def _rows(connection: sqlite3.Connection, table: str):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return connection.execute(f"SELECT * FROM {table}").fetchall() if exists else []


def _value(row: sqlite3.Row, name: str, default=None):
    return row[name] if name in row.keys() else default


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.source.exists():
        tasks = events = progress = []
    else:
        source = sqlite3.connect(args.source)
        source.row_factory = sqlite3.Row
        try:
            tasks = _rows(source, "learning_tasks")
            events = _rows(source, "learning_events")
            progress = _rows(source, "task_progress")
        finally:
            source.close()
    if args.apply:
        database_url = str(args.database_url or "").strip()
        if not database_url:
            raise ValueError("--database-url is required with --apply")
        engine = create_engine(database_url, pool_pre_ping=True)
        with database_session(engine=engine) as session:
            for row in tasks:
                record = session.get(LearningTaskModel, row["task_id"])
                if record is None:
                    record = LearningTaskModel(task_id=row["task_id"])
                    session.add(record)
                record.course_id = row["course_id"]
                record.title = row["title"]
                record.instructions = row["instructions"]
                record.created_by = row["created_by"]
                record.resource_refs = json.loads(row["resource_refs_json"] or "[]")
                record.knowledge_point_ids = json.loads(row["knowledge_point_ids_json"] or "[]")
                record.status = row["status"]
                record.created_at = _timestamp(row["created_at"])
                record.published_at = _timestamp(row["published_at"]) if row["published_at"] else None
                record.published_by = row["published_by"]
            session.flush()
            for row in events:
                record = session.get(LearningEventModel, row["event_id"])
                if record is None:
                    session.add(LearningEventModel(
                        event_id=row["event_id"], course_id=row["course_id"],
                        task_id=row["task_id"], student_id=row["student_id"],
                        event_type=row["event_type"], progress_percent=row["progress_percent"],
                        resource_ref=json.loads(row["resource_ref_json"]) if row["resource_ref_json"] else None,
                        evidence=(
                            json.loads(_value(row, "evidence_json"))
                            if _value(row, "evidence_json")
                            else None
                        ),
                        occurred_at=_timestamp(row["occurred_at"]),
                    ))
            for row in progress:
                key = (row["task_id"], row["student_id"])
                record = session.get(LearningProgressModel, key)
                if record is None:
                    record = LearningProgressModel(task_id=key[0], student_id=key[1])
                    session.add(record)
                record.course_id = row["course_id"]
                record.status = row["status"]
                record.progress_percent = row["progress_percent"]
                record.completion_basis = _value(
                    row,
                    "completion_basis",
                    "self_reported" if row["status"] == "completed" else "none",
                )
                record.evidence_count = int(_value(row, "evidence_count", 0) or 0)
                last_activity_at = _value(row, "last_activity_at")
                record.last_activity_at = _timestamp(last_activity_at) if last_activity_at else None
                record.started_at = _timestamp(row["started_at"]) if row["started_at"] else None
                record.completed_at = _timestamp(row["completed_at"]) if row["completed_at"] else None
                record.updated_at = _timestamp(row["updated_at"])
    print(json.dumps({
        "mode": "applied" if args.apply else "preview",
        "tasks": len(tasks), "events": len(events), "progress": len(progress),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
