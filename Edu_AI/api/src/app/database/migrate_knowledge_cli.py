from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import create_engine

from app.persistence.postgres_knowledge_repository import PostgresKnowledgeRepository
from core.config import Config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or import knowledge metadata into PostgreSQL."
    )
    parser.add_argument("--courses-root", type=Path, default=Config.COURSE_STORAGE_ROOT / "courses")
    parser.add_argument("--document-index", type=Path, default=Config.STORAGE_ROOT / "document_index.json")
    parser.add_argument("--image-index", type=Path, default=Config.STORAGE_ROOT / "image_index.json")
    parser.add_argument("--video-index", type=Path, default=Config.STORAGE_ROOT / "video_index.json")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--apply", action="store_true")
    return parser


def _json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    course_documents: dict[str, list[dict[str, Any]]] = {}
    graphs: dict[str, dict[str, Any]] = {}
    if args.courses_root.exists():
        for course_dir in sorted(path for path in args.courses_root.iterdir() if path.is_dir()):
            entries = _json(course_dir / "knowledge_base" / "index.json", [])
            if not isinstance(entries, list):
                raise ValueError(f"knowledge index must be a list: {course_dir.name}")
            course_documents[course_dir.name] = [dict(item) for item in entries]
            graph = _json(course_dir / "knowledge_graph.json", None)
            if isinstance(graph, dict):
                graphs[course_dir.name] = graph
    runtime_indexes = {
        "document": _json(args.document_index, {}),
        "image": _json(args.image_index, {}),
        "video": _json(args.video_index, {}),
    }
    for name, entries in runtime_indexes.items():
        if not isinstance(entries, dict):
            raise ValueError(f"{name} index must be an object")

    if args.apply:
        database_url = str(args.database_url or "").strip()
        if not database_url:
            raise ValueError("--database-url is required with --apply")
        repository = PostgresKnowledgeRepository(
            create_engine(database_url, pool_pre_ping=True)
        )
        for course_id, documents in course_documents.items():
            repository.replace_documents(course_id, documents)
        for course_id, graph in graphs.items():
            repository.upsert_graph(course_id, graph)
        for name, entries in runtime_indexes.items():
            repository.replace_runtime_index(name, entries)

    summary = {
        "mode": "applied" if args.apply else "preview",
        "libraries": len(course_documents),
        "course_documents": sum(len(items) for items in course_documents.values()),
        "graphs": len(graphs),
        "runtime_document_entries": len(runtime_indexes["document"]),
        "runtime_image_entries": len(runtime_indexes["image"]),
        "runtime_video_entries": len(runtime_indexes["video"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
