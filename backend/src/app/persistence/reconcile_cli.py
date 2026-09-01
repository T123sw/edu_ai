from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from app.database import database_session
from app.database.legacy_importer import build_legacy_core_snapshot
from core.config import Config

from .reconciliation import reconcile_core_snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare core JSON records with the PostgreSQL shadow copy."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
    )
    parser.add_argument(
        "--users-json",
        type=Path,
        default=Path(Config.STORAGE_ROOT) / "users.json",
    )
    parser.add_argument(
        "--courses-root",
        type=Path,
        default=Path(Config.COURSE_STORAGE_ROOT) / "courses",
    )
    parser.add_argument(
        "--memberships-json",
        type=Path,
        default=Path(Config.COURSE_MEMBERSHIPS_FILE),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    snapshot = build_legacy_core_snapshot(
        users_path=args.users_json,
        courses_root=args.courses_root,
        memberships_path=args.memberships_json,
    )
    with database_session(database_url=args.database_url) as session:
        report = reconcile_core_snapshot(session, snapshot)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
