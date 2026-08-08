from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document


def main() -> int:
    parser = argparse.ArgumentParser(description="离线审计统一结构化分块器")
    parser.add_argument("--owner", default="teacher")
    parser.add_argument("--source-path-contains", default="course_data")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    load_dotenv(Path.cwd() / ".env", override=False)
    from modules.rag_v2.api import get_rag_system

    rag = get_rag_system()
    processor = rag.document_processor
    entries = []
    for index_key, metadata in rag.document_index.items():
        path = Path(str(metadata.get("physical_path") or ""))
        if args.owner and metadata.get("owner") != args.owner:
            continue
        if args.source_path_contains.lower() not in str(path).lower():
            continue
        entries.append((index_key, metadata, path))

    supported = {".md", ".markdown", ".txt", ".html", ".htm", ".docx"}
    report = {
        "document_count": len(entries),
        "audited_document_count": 0,
        "skipped_documents": [],
        "errors": [],
        "chunk_count": 0,
        "token_min": None,
        "token_max": 0,
        "token_average": 0.0,
        "unexplained_tiny_chunks": 0,
        "broken_code_fences": 0,
        "broken_display_math": 0,
        "empty_chunks": 0,
        "unstable_chunk_ids": 0,
        "chunk_kinds": {},
    }
    token_counts: list[int] = []
    kind_counts: Counter[str] = Counter()
    for _, metadata, path in entries:
        if not path.exists() or path.suffix.lower() not in supported:
            report["skipped_documents"].append(str(path))
            continue
        try:
            if path.suffix.lower() == ".docx":
                source_docs = processor.load_doc(str(path))
            else:
                text = processor._fallback_read(str(path))
                source_docs = [
                    Document(
                        page_content=text,
                        metadata={"source": str(path), "document_name": path.name, "page": 0},
                    )
                ]
            first = processor.split_documents(source_docs)
            second = processor.split_documents(source_docs)
            first_ids = [str((doc.metadata or {}).get("chunk_id") or "") for doc in first]
            second_ids = [str((doc.metadata or {}).get("chunk_id") or "") for doc in second]
            if first_ids != second_ids:
                report["unstable_chunk_ids"] += 1
            report["audited_document_count"] += 1
            report["chunk_count"] += len(first)
            for chunk in first:
                content = str(chunk.page_content or "")
                chunk_metadata = chunk.metadata or {}
                token_count = int(chunk_metadata.get("token_count") or 0)
                kind = str(chunk_metadata.get("chunk_kind") or "text")
                token_counts.append(token_count)
                kind_counts[kind] += 1
                if not content.strip():
                    report["empty_chunks"] += 1
                if content.count("```") % 2:
                    report["broken_code_fences"] += 1
                if content.count("$$") % 2:
                    report["broken_display_math"] += 1
                if token_count < 120 and not chunk_metadata.get("small_chunk_reason"):
                    report["unexplained_tiny_chunks"] += 1
        except Exception as exc:
            report["errors"].append({"file": str(path), "error": str(exc)})

    if token_counts:
        report["token_min"] = min(token_counts)
        report["token_max"] = max(token_counts)
        report["token_average"] = round(sum(token_counts) / len(token_counts), 2)
    report["chunk_kinds"] = dict(sorted(kind_counts.items()))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
