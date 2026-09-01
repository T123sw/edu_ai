"""Dry-run/apply repair for course document IDs and RAG index links."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from core.course_storage import COURSE_STORAGE_ROOT, CourseStorageManager
from modules.rag_v2.document_resolver import (
    find_rag_record_for_legacy_identifiers,
)


@dataclass(frozen=True)
class CourseDocumentMigrationReport:
    scanned_count: int
    repairable_count: int
    changed_count: int
    applied: bool
    issues: tuple[dict[str, Any], ...]


def _stable_public_id(course_id: str, legacy_path: str) -> str:
    normalized_path = str(legacy_path or "").replace("\\", "/").strip().casefold()
    value = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"edu-ai/course-document/{course_id}/{normalized_path}",
    )
    return f"doc-{value.hex}"


def _load_indexes(
    manager: CourseStorageManager,
) -> list[tuple[str, Path, list[dict[str, Any]]]]:
    loaded = []
    if not manager.courses_dir.exists():
        return loaded
    for course_dir in sorted(manager.courses_dir.iterdir()):
        index_path = course_dir / "knowledge_base" / "index.json"
        if not course_dir.is_dir() or not index_path.exists():
            continue
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, list):
            loaded.append(
                (
                    course_dir.name,
                    index_path,
                    [dict(item) for item in payload if isinstance(item, dict)],
                )
            )
    return loaded


def migrate_course_documents(
    root_path: str | Path,
    *,
    apply: bool,
    rag_document_index: Mapping[str, Any] | None = None,
) -> CourseDocumentMigrationReport:
    resolved_root = Path(root_path)
    if not (resolved_root / "courses").exists():
        return CourseDocumentMigrationReport(
            scanned_count=0,
            repairable_count=0,
            changed_count=0,
            applied=apply,
            issues=(),
        )
    manager = CourseStorageManager(root_path=str(resolved_root))
    loaded = _load_indexes(manager)
    rag_index = dict(rag_document_index or {})
    id_counts: dict[str, int] = {}
    for _course_id, _path, records in loaded:
        for record in records:
            document_id = str(record.get("id") or "").strip()
            if document_id:
                id_counts[document_id] = id_counts.get(document_id, 0) + 1

    scanned = repairable = changed = 0
    issues: list[dict[str, Any]] = []
    for course_id, index_path, records in loaded:
        next_records: list[dict[str, Any]] = []
        course_changed = False
        for position, source_record in enumerate(records):
            scanned += 1
            record = dict(source_record)
            changes: list[str] = []
            document_id = str(record.get("id") or "").strip()
            relative_path = str(
                record.get("path")
                or record.get("filename")
                or f"legacy-{position}"
            )
            if not document_id or id_counts.get(document_id, 0) > 1:
                record["id"] = _stable_public_id(course_id, relative_path)
                changes.append(
                    "repair_duplicate_public_id"
                    if document_id
                    else "assign_public_id"
                )

            rag_index_key = str(record.get("rag_index_key") or "").strip()
            rag_record = rag_index.get(rag_index_key) if rag_index_key else None
            resolved_key = rag_index_key if isinstance(rag_record, Mapping) else ""
            if not resolved_key:
                legacy_match = find_rag_record_for_legacy_identifiers(
                    rag_index,
                    [record.get("path"), record.get("filename")],
                    owner=record.get("owner_user_id"),
                )
                if legacy_match is not None:
                    resolved_key, rag_record = legacy_match
            if resolved_key and isinstance(rag_record, Mapping):
                if rag_index_key != resolved_key:
                    changes.append("repair_rag_index_key")
                record["rag_index_key"] = resolved_key
                next_chunk_count = max(0, int(rag_record.get("chunk_count") or 0))
                if int(record.get("chunk_count") or 0) != next_chunk_count:
                    record["chunk_count"] = next_chunk_count
                    if "repair_rag_index_key" not in changes:
                        changes.append("refresh_chunk_count")
                if record.get("status") != "ready":
                    record["status"] = "ready"
                    changes.append("restore_ready_status")
                record["error_code"] = None
                record["error_message"] = None
            else:
                missing_state = (
                    record.get("rag_index_key") is not None
                    or record.get("status") != "failed"
                    or record.get("error_code") != "RAG_INDEX_MISSING"
                    or int(record.get("chunk_count") or 0) != 0
                )
                record["rag_index_key"] = None
                record["chunk_count"] = 0
                record["status"] = "failed"
                record["error_code"] = "RAG_INDEX_MISSING"
                record["error_message"] = "RAG index record is missing; reindex this document."
                if missing_state:
                    changes.append("mark_missing_rag_index")

            if changes:
                repairable += 1
                issues.append(
                    {
                        "course_id": course_id,
                        "document_id": record["id"],
                        "changes": changes,
                    }
                )
                course_changed = True
            next_records.append(record)
        if apply and course_changed:
            manager._write_json(index_path, next_records)
            changed += sum(
                1 for issue in issues if issue["course_id"] == course_id
            )
    return CourseDocumentMigrationReport(
        scanned_count=scanned,
        repairable_count=repairable,
        changed_count=changed,
        applied=apply,
        issues=tuple(issues),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--root",
        default=os.getenv("COURSE_STORAGE_ROOT") or str(COURSE_STORAGE_ROOT),
    )
    args = parser.parse_args()
    from modules.rag_v2.api import get_rag_system

    report = migrate_course_documents(
        args.root,
        apply=bool(args.apply),
        rag_document_index=getattr(get_rag_system(), "document_index", {}),
    )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
