from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import create_engine, select

from app.database import MigrationQuarantine, database_session
from app.persistence.postgres_material_repository import PostgresMaterialRepository
from core.config import Config
from core.course_storage import DIR_TO_TYPE, FORMAL_MATERIAL_TYPES


def _artifact_paths(
    payload: dict[str, Any], course_dir: Path, manifest_path: Path
) -> list[str]:
    discovered = {
        str(item).replace("\\", "/")
        for item in list(payload.get("artifact_paths") or [])
        if str(item).strip()
    }
    if payload.get("file_path"):
        discovered.add(str(payload["file_path"]).replace("\\", "/"))

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            candidate = value.strip().replace("\\", "/")
            if candidate and (course_dir / candidate).is_file():
                discovered.add(candidate)

    visit(payload)
    for sibling in manifest_path.parent.glob(f"{manifest_path.stem}.*"):
        if sibling != manifest_path and sibling.is_file():
            discovered.add(sibling.relative_to(course_dir).as_posix())
    media_root = manifest_path.parent / f"{manifest_path.stem}_media"
    if media_root.exists():
        for media_file in media_root.rglob("*"):
            if media_file.is_file():
                discovered.add(media_file.relative_to(course_dir).as_posix())
    return sorted(discovered)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or import generated material manifests into PostgreSQL."
    )
    parser.add_argument(
        "--courses-root", type=Path, default=Config.COURSE_STORAGE_ROOT / "courses"
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--apply", action="store_true")
    return parser


def _records(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    for course_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        generated_root = course_dir / "generated_materials"
        if not generated_root.exists():
            continue
        for path in sorted(generated_root.glob("*/*.json")):
            raw_content = path.read_text(encoding="utf-8")
            try:
                payload = json.loads(raw_content)
                material_type = str(
                    payload.get("material_type") or DIR_TO_TYPE.get(path.parent.name) or ""
                ).strip()
                if material_type not in FORMAL_MATERIAL_TYPES:
                    raise ValueError("unsupported material type")
                now = datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).isoformat()
                payload.update(
                    {
                        "course_id": str(payload.get("course_id") or course_dir.name),
                        "material_type": material_type,
                        "material_id": str(
                            payload.get("material_id") or payload.get("id") or path.stem
                        ),
                        "version": int(payload.get("version") or 1),
                        "created_at": str(payload.get("created_at") or now),
                        "updated_at": str(payload.get("updated_at") or now),
                        "status": str(payload.get("status") or "ready"),
                        "visibility": str(payload.get("visibility") or "course"),
                        "scope_type": str(payload.get("scope_type") or "course"),
                    }
                )
                payload["artifact_paths"] = _artifact_paths(
                    payload, course_dir, path
                )
                payload.setdefault(
                    "content_hash", hashlib.sha256(path.read_bytes()).hexdigest()
                )
                records.append(payload)
            except Exception as exc:
                invalid.append(
                    {
                        "source_path": str(path.relative_to(root)),
                        "content_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "error_message": str(exc),
                        "raw_content": raw_content,
                    }
                )
    return records, invalid


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    materials, invalid = _records(args.courses_root)
    if args.apply:
        database_url = str(args.database_url or "").strip()
        if not database_url:
            raise ValueError("--database-url is required with --apply")
        engine = create_engine(database_url, pool_pre_ping=True)
        repository = PostgresMaterialRepository(engine)
        for material in materials:
            repository.upsert(material)
        with database_session(engine=engine) as session:
            for item in invalid:
                record = session.scalar(
                    select(MigrationQuarantine).where(
                        MigrationQuarantine.domain == "materials",
                        MigrationQuarantine.source_path == item["source_path"],
                    )
                )
                if record is None:
                    record = MigrationQuarantine(
                        domain="materials", source_path=item["source_path"]
                    )
                    session.add(record)
                record.content_hash = item["content_hash"]
                record.error_message = item["error_message"]
                record.raw_content = item["raw_content"]
    print(
        json.dumps(
            {
                "mode": "applied" if args.apply else "preview",
                "materials": len(materials),
                "quarantined": [item["source_path"] for item in invalid],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
