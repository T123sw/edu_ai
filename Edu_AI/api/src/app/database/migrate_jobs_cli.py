from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from sqlalchemy import create_engine

from app.persistence.postgres_job_repository import PostgresJobRepository
from app.services.job_store import EduJob
from core.config import Config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or import legacy JSON job records into PostgreSQL."
    )
    parser.add_argument("--source", type=Path, default=Config.STORAGE_ROOT / "jobs")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    jobs: list[EduJob] = []
    invalid: list[str] = []
    for path in sorted(args.source.glob("*.json")):
        try:
            jobs.append(EduJob.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:
            invalid.append(path.name)
    if args.apply:
        database_url = str(args.database_url or "").strip()
        if not database_url:
            raise ValueError("--database-url is required with --apply")
        repository = PostgresJobRepository(
            create_engine(database_url, pool_pre_ping=True)
        )
        for job in jobs:
            repository.upsert(job.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "mode": "applied" if args.apply else "preview",
                "jobs": len(jobs),
                "invalid": invalid,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not invalid else 2


if __name__ == "__main__":
    raise SystemExit(main())
