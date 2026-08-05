"""Plan or apply the explicit migration of legacy course resources.

Dry-run is the default. Use ``--apply`` only after reviewing the JSON report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_SRC = PROJECT_ROOT / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from core.course_storage import CourseStorageManager  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply legacy course resource migration."
    )
    parser.add_argument("course_id", help="Course identifier to inspect.")
    parser.add_argument(
        "--owner",
        dest="owner_user_id",
        help="Explicitly assign unowned legacy records to this user.",
    )
    parser.add_argument(
        "--storage-root",
        help="Override the course storage root for this invocation.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the reviewed migration plan. Omit for a side-effect-free dry run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manager = CourseStorageManager(root_path=args.storage_root)
    report = manager.migrate_legacy_generated_materials(
        args.course_id,
        owner_user_id=args.owner_user_id,
        dry_run=not args.apply,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["legacy_partial"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
