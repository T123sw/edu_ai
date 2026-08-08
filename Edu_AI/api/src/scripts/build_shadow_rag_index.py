from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path

from dotenv import load_dotenv

from core.config import Config
from modules.rag_v2.rag_main.system import RAGSystem


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an isolated RAG index from the reviewed course corpus")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evaluation/shadow/computational-thinking-v2/selected-manifest.json"),
    )
    parser.add_argument(
        "--index-root",
        type=Path,
        default=Path("evaluation/shadow/computational-thinking-v2/rag-index-v1"),
    )
    parser.add_argument("--max-documents", type=int, default=0)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent document parsing/embedding workers; vector/index commits stay serialized",
    )
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env", override=False)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("status") != "ready":
        raise RuntimeError("reviewed corpus manifest is incomplete; refusing to build a partial index")
    documents = list(manifest.get("documents") or [])
    if args.max_documents > 0:
        documents = documents[: args.max_documents]

    args.index_root.mkdir(parents=True, exist_ok=True)
    rag = RAGSystem(
        api_base=Config.DEEP_MODEL_API_BASE or Config.REMOTE_MODEL_API_BASE or Config.OLLAMA_BASE_URL,
        api_key=Config.DEEP_MODEL_API_KEY or Config.REMOTE_MODEL_API_KEY,
        embedding_model=Config.EMBEDDING_MODEL,
        llm_model=Config.LLM_MODEL_DEEP,
        vector_db_path=args.index_root / "chroma",
        document_index_path=args.index_root / "document-index.json",
        storage_root=args.index_root / "storage",
    )

    def import_one(index: int, material: dict) -> tuple[str, dict | None]:
        path = Path(str(material.get("path") or "")).resolve()
        print(f"[ShadowIndex] {index}/{len(documents)} {material.get('scope_id')} {path.name}")
        try:
            result = rag.import_document(
                str(path),
                owner="course-shadow-v2",
                metadata_overrides={
                    "course_id": "computational-thinking",
                    "library_type": "course",
                    "scope_type": "knowledge_point",
                    "scope_id": str(material.get("scope_id") or ""),
                    "knowledge_node_id": str(material.get("scope_id") or ""),
                    "course_material_id": str(material.get("material_id") or ""),
                    "content_language": str(material.get("language") or ""),
                    "authority_tier": str(material.get("authority_tier") or ""),
                },
            )
            if result.get("status") == "skipped":
                return "skipped", None
            return "imported", None
        except Exception as exc:
            return "failed", {
                "scope_id": material.get("scope_id"),
                "material_id": material.get("material_id"),
                "path": str(path),
                "error": str(exc),
            }

    imported = 0
    skipped = 0
    failed: list[dict] = []
    worker_count = max(1, min(int(args.workers), 8, len(documents) or 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(import_one, index, material)
            for index, material in enumerate(documents, start=1)
        ]
        for future in concurrent.futures.as_completed(futures):
            status, failure = future.result()
            if status == "imported":
                imported += 1
            elif status == "skipped":
                skipped += 1
            elif failure:
                failed.append(failure)

    expected_index_keys = {
        rag._make_index_key(str(Path(str(material.get("path") or "")).resolve()), "course-shadow-v2")
        for material in documents
    }
    registered_index_keys = expected_index_keys.intersection(rag.document_index.keys())
    missing_index_keys = sorted(expected_index_keys - registered_index_keys)
    try:
        vector_chunk_count = int(rag.vector_store.collection.count())
        vector_store_error = None
    except Exception as exc:
        vector_chunk_count = 0
        vector_store_error = str(exc)

    build_ready = (
        not failed
        and imported + skipped == len(documents)
        and not missing_index_keys
        and vector_chunk_count > 0
        and vector_store_error is None
    )
    report = {
        "status": "ready" if build_ready else "failed",
        "requested_document_count": len(documents),
        "imported_document_count": imported,
        "skipped_document_count": skipped,
        "failed_document_count": len(failed),
        "failures": failed,
        "registered_document_count": len(registered_index_keys),
        "missing_registry_count": len(missing_index_keys),
        "missing_registry_keys": missing_index_keys,
        "vector_chunk_count": vector_chunk_count,
        "vector_store_error": vector_store_error,
        "vector_db_path": str((args.index_root / "chroma").resolve()),
        "document_index_path": str((args.index_root / "document-index.json").resolve()),
    }
    report_path = args.index_root / "build-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
