from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import create_engine

from app.persistence.postgres_conversation_repository import (
    PostgresConversationRepository,
)
from core.config import Config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or import legacy JSON conversations into PostgreSQL."
    )
    parser.add_argument(
        "--source", type=Path, default=Path(Config.CONVERSATIONS_FILE)
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--apply", action="store_true")
    return parser


def _read(source: Path) -> list[dict[str, Any]]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    records = payload.get("conversations", []) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("conversations must be a list")
    return [dict(item) for item in records]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    conversations = _read(args.source)
    summary = {
        "mode": "applied" if args.apply else "preview",
        "conversations": len(conversations),
        "messages": sum(len(item.get("messages") or []) for item in conversations),
    }
    if args.apply:
        database_url = str(args.database_url or "").strip()
        if not database_url:
            raise ValueError("--database-url is required with --apply")
        repository = PostgresConversationRepository(
            create_engine(database_url, pool_pre_ping=True)
        )
        for conversation in conversations:
            repository.upsert(conversation)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
