from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import create_engine, select

from app.database import MigrationQuarantine, database_session
from app.persistence.postgres_app_state_repository import PostgresAppStateRepository
from core.config import Config


EXCLUDED_STORAGE = {
    "users.json", "course_memberships.json", "conversations.json",
    "document_index.json", "image_index.json", "video_index.json",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import remaining JSON state into PostgreSQL.")
    parser.add_argument("--storage-root", type=Path, default=Config.STORAGE_ROOT)
    parser.add_argument("--courses-root", type=Path, default=Config.COURSE_STORAGE_ROOT / "courses")
    parser.add_argument(
        "--agent-runs-db",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "data" / "agent_runs.db",
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--apply", action="store_true")
    return parser


def _record(namespace: str, key: str, value: Any, source_path: str):
    payload = dict(value) if isinstance(value, dict) else {"value": value}
    payload.setdefault("legacy_source_path", source_path)
    return namespace, key[:300], payload


def _scan(storage_root: Path, courses_root: Path, agent_runs_db: Path | None = None):
    records: list[tuple[str, str, dict[str, Any]]] = []
    invalid: list[dict[str, str]] = []
    if storage_root.exists():
        for path in sorted(storage_root.rglob("*.json")):
            relative = path.relative_to(storage_root).as_posix()
            parts = Path(relative).parts
            if relative in EXCLUDED_STORAGE or (parts and parts[0] == "jobs"):
                continue
            try:
                raw = path.read_text(encoding="utf-8")
                value = json.loads(raw)
                if relative == "lesson_plans.json" and isinstance(value, dict):
                    records.extend(
                        _record("lesson_plans", str(item.get("id")), item, relative)
                        for item in value.get("plans", []) if item.get("id")
                    )
                elif relative == "user_profiles.json" and isinstance(value, dict):
                    records.extend(
                        _record("user_profiles", str(item.get("user_id")), item, relative)
                        for item in value.get("profiles", []) if item.get("user_id")
                    )
                elif parts and parts[0] in {"crawl_batches", "blog_tasks", "tasks"}:
                    namespace = {"tasks": "pipeline_tasks"}.get(parts[0], parts[0])
                    records.append(_record(namespace, path.stem, value, relative))
                elif parts and parts[0] == "runtime_config":
                    records.append(_record("runtime_config", ":".join(parts[1:]).removesuffix(".json"), value, relative))
                elif parts and parts[0] == "searched_images":
                    records.append(_record("searched_images", hashlib.sha256(relative.encode()).hexdigest(), value, relative))
                else:
                    records.append(_record("legacy_json", hashlib.sha256(relative.encode()).hexdigest(), value, relative))
            except Exception as exc:
                raw = path.read_text(encoding="utf-8", errors="replace")
                invalid.append({
                    "source_path": f"storage/{relative}",
                    "content_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "error_message": str(exc),
                    "raw_content": raw,
                })
    if courses_root.exists():
        for course_dir in sorted(path for path in courses_root.iterdir() if path.is_dir()):
            metadata = course_dir / "metadata.json"
            if metadata.exists():
                value = json.loads(metadata.read_text(encoding="utf-8"))
                records.append(_record("course_metadata", course_dir.name, value, str(metadata)))
    if agent_runs_db and agent_runs_db.exists():
        connection = sqlite3.connect(agent_runs_db)
        connection.row_factory = sqlite3.Row
        try:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_runs'"
            ).fetchone()
            if exists:
                for row in connection.execute("SELECT * FROM agent_runs"):
                    records.append(_record(
                        "agent_runs",
                        str(row["conversation_id"]),
                        {
                            "conversation_id": row["conversation_id"],
                            "owner_user_id": row["owner_user_id"],
                            "course_id": row["course_id"],
                            "state": json.loads(row["state_json"] or "{}"),
                            "updated_at": row["updated_at"],
                        },
                        str(agent_runs_db),
                    ))
        finally:
            connection.close()
    return records, invalid


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    records, invalid = _scan(args.storage_root, args.courses_root, args.agent_runs_db)
    if args.apply:
        database_url = str(args.database_url or "").strip()
        if not database_url:
            raise ValueError("--database-url is required with --apply")
        engine = create_engine(database_url, pool_pre_ping=True)
        repository = PostgresAppStateRepository(engine)
        for namespace, key, payload in records:
            repository.put(namespace, key, payload)
        with database_session(engine=engine) as session:
            for item in invalid:
                record = session.scalar(select(MigrationQuarantine).where(
                    MigrationQuarantine.domain == "app_state",
                    MigrationQuarantine.source_path == item["source_path"],
                ))
                if record is None:
                    record = MigrationQuarantine(domain="app_state", source_path=item["source_path"])
                    session.add(record)
                record.content_hash = item["content_hash"]
                record.error_message = item["error_message"]
                record.raw_content = item["raw_content"]
    print(json.dumps({
        "mode": "applied" if args.apply else "preview",
        "records": len(records),
        "quarantined": [item["source_path"] for item in invalid],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
