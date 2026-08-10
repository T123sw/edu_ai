from __future__ import annotations

import argparse
import json
import os
from typing import Sequence

from sqlalchemy import create_engine, inspect, text

from app.persistence.retirement import validate_retired_legacy_storage


EXPECTED_REVISION = "20260810_0008"
BUSINESS_TABLES = (
    "users", "courses", "course_objectives", "course_memberships",
    "conversations", "conversation_messages", "jobs", "job_events",
    "materials", "material_versions", "artifact_files",
    "migration_quarantine", "knowledge_libraries", "knowledge_documents",
    "knowledge_graph_versions", "runtime_index_entries", "app_state_records",
    "learning_tasks", "learning_events", "learning_progress", "durable_tasks",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the PostgreSQL-only persistence cutover."
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    database_url = str(args.database_url or "").strip()
    if not database_url:
        raise ValueError("--database-url or DATABASE_URL is required")
    validate_retired_legacy_storage()
    engine = create_engine(database_url, pool_pre_ping=True)
    table_names = set(inspect(engine).get_table_names())
    missing = sorted(set(BUSINESS_TABLES) - table_names)
    if missing:
        raise RuntimeError("Missing PostgreSQL business tables: " + ", ".join(missing))
    counts: dict[str, int] = {}
    with engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != EXPECTED_REVISION:
            raise RuntimeError(
                f"Alembic revision mismatch: expected {EXPECTED_REVISION}, got {revision}"
            )
        for table in BUSINESS_TABLES:
            counts[table] = int(
                connection.scalar(text(f'SELECT count(*) FROM "{table}"')) or 0
            )
    report = {
        "status": "passed",
        "persistence_profile": "database",
        "alembic_revision": revision,
        "business_table_count": len(BUSINESS_TABLES),
        "record_counts": counts,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
