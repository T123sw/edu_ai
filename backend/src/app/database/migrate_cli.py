from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from core.config import Config

from .legacy_importer import apply_legacy_core_snapshot, build_legacy_core_snapshot
from .session import database_session


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or import legacy JSON identity/course data into PostgreSQL."
    )
    parser.add_argument(
        "--users-json",
        type=Path,
        default=Config.STORAGE_ROOT / "users.json",
    )
    parser.add_argument(
        "--courses-root",
        type=Path,
        default=Config.COURSE_STORAGE_ROOT / "courses",
    )
    parser.add_argument(
        "--memberships-json",
        type=Path,
        default=Config.COURSE_MEMBERSHIPS_FILE,
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="SQLAlchemy database URL; required only with --apply.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the validated snapshot. Without this flag the command is read-only.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    snapshot = build_legacy_core_snapshot(
        users_path=args.users_json,
        courses_root=args.courses_root,
        memberships_path=args.memberships_json,
    )
    summary = snapshot.summary()
    if args.apply:
        with database_session(database_url=args.database_url) as session:
            summary = apply_legacy_core_snapshot(session, snapshot)
    print(
        json.dumps(
            {"mode": "applied" if args.apply else "preview", **summary},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
