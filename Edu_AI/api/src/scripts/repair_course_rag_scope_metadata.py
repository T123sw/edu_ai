from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


API_ROOT = Path(__file__).resolve().parents[2]
COURSES_ROOT = API_ROOT / "course_data" / "courses"
RAG_INDEX_PATH = API_ROOT / "src" / "storage" / "document_index.json"

CATALOG_FIELDS = (
    "course_id",
    "library_type",
    "scope_type",
    "scope_id",
    "content_language",
    "authority_tier",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".next")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _path_key(value: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(value)))


def reconcile(*, check_only: bool) -> dict[str, Any]:
    rag_index = _load_json(RAG_INDEX_PATH)
    if not isinstance(rag_index, dict):
        raise RuntimeError(f"RAG index must be an object: {RAG_INDEX_PATH}")

    rag_by_path: dict[str, tuple[str, dict[str, Any]]] = {}
    for index_key, entry in rag_index.items():
        if not isinstance(entry, dict):
            continue
        physical_path = entry.get("physical_path")
        if physical_path:
            rag_by_path[_path_key(str(physical_path))] = (index_key, entry)

    matched = 0
    mismatched = 0
    repaired = 0
    missing_from_rag: list[str] = []
    course_records = 0
    personal_records = 0

    for course_index_path in sorted(COURSES_ROOT.glob("*/knowledge_base/index.json")):
        course_dir = course_index_path.parents[1]
        course_index = _load_json(course_index_path)
        if not isinstance(course_index, list):
            raise RuntimeError(f"course index must be an array: {course_index_path}")
        for document in course_index:
            if not isinstance(document, dict) or not document.get("path"):
                continue
            library_type = str(document.get("library_type") or "course").strip().lower()
            if library_type == "course":
                course_records += 1
            else:
                personal_records += 1

            physical_path = (course_dir / str(document["path"])).resolve()
            rag_match = rag_by_path.get(_path_key(physical_path))
            if rag_match is None:
                missing_from_rag.append(str(physical_path))
                continue
            _, rag_entry = rag_match
            matched += 1

            expected = {
                field: document.get(field)
                for field in CATALOG_FIELDS
                if document.get(field) is not None
            }
            expected["course_id"] = str(document.get("course_id") or course_dir.name)
            expected["library_type"] = library_type
            expected["knowledge_node_id"] = document.get("scope_id")
            expected["course_document_id"] = document.get("id")
            expected = {key: value for key, value in expected.items() if value is not None}

            if any(rag_entry.get(key) != value for key, value in expected.items()):
                mismatched += 1
                if not check_only:
                    rag_entry.update(expected)
                    repaired += 1

    if repaired:
        _atomic_json(RAG_INDEX_PATH, rag_index)

    return {
        "status": "clean" if mismatched == 0 else ("needs_repair" if check_only else "repaired"),
        "rag_index": str(RAG_INDEX_PATH),
        "course_records": course_records,
        "personal_records": personal_records,
        "matched_rag_records": matched,
        "metadata_mismatches": mismatched,
        "repaired_records": repaired,
        "missing_from_rag_count": len(missing_from_rag),
        "missing_from_rag": missing_from_rag,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile course knowledge-base records into the global RAG catalog."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Audit only; do not modify document_index.json.",
    )
    args = parser.parse_args()
    result = reconcile(check_only=args.check)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.check and (
        result["metadata_mismatches"] or result["missing_from_rag_count"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
