from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

from core.config import Config
from modules.rag_v2.rag_main.system import RAGSystem


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".next")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _validate_gates(manifest: dict, evaluation: dict) -> None:
    metrics = evaluation.get("metrics") or {}
    failures = []
    if manifest.get("status") != "ready" or int(manifest.get("node_count") or 0) != 49:
        failures.append("reviewed corpus is incomplete")
    if int(manifest.get("document_count") or 0) != 147:
        failures.append("reviewed corpus must contain exactly three documents for each of 49 nodes")
    if float(metrics.get("recall_at_10") or 0) < 0.90:
        failures.append("Recall@10 is below 0.90")
    if float(metrics.get("node_hit_at_5") or 0) < 0.85:
        failures.append("node hit@5 is below 0.85")
    if int(metrics.get("scope_leakage_count") or 0) != 0:
        failures.append("retrieval scope leakage is non-zero")
    visual = metrics.get("visual_hit_at_10")
    if visual is None or float(visual) < 0.75:
        failures.append("visual hit@10 is below 0.75")
    if failures:
        raise RuntimeError("promotion gates failed: " + "; ".join(failures))


def _copy_markdown_assets(source_path: Path, destination_path: Path, destination_root: Path) -> None:
    if source_path.suffix.lower() not in {".md", ".markdown"}:
        return
    content = source_path.read_text(encoding="utf-8")
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", content):
        target = unquote(match.group(1).strip().split("#", 1)[0].split("?", 1)[0])
        if not target or target.startswith(("http://", "https://", "data:")):
            continue
        source_asset = (source_path.parent / target).resolve()
        if not source_asset.is_file() or source_path.parent.resolve() not in source_asset.parents:
            raise RuntimeError(f"invalid or missing Markdown asset: {source_asset}")
        destination_asset = (destination_path.parent / target).resolve()
        if destination_root != destination_asset and destination_root not in destination_asset.parents:
            raise RuntimeError(f"resolved asset destination escaped course corpus: {destination_asset}")
        destination_asset.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_asset, destination_asset)


def main() -> int:
    parser = argparse.ArgumentParser(description="Atomically promote the reviewed course shadow corpus")
    parser.add_argument("--course-id", default="computational-thinking")
    parser.add_argument("--owner", default="teacher")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evaluation/shadow/computational-thinking-v2/selected-manifest.json"),
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=Path("evaluation/candidates/computational-thinking-knowledge-graph-v2.json"),
    )
    parser.add_argument(
        "--evaluation",
        type=Path,
        default=Path("evaluation/reports/2026-08-08-shadow-index-retrieval.json"),
    )
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env", override=False)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
    _validate_gates(manifest, evaluation)
    if not args.apply:
        print(json.dumps({"status": "validated", "apply": False}, ensure_ascii=False, indent=2))
        return 0

    course_root = (Config.COURSE_STORAGE_ROOT / "courses" / args.course_id).resolve()
    knowledge_root = (course_root / "knowledge_base").resolve()
    destination_root = (knowledge_root / "documents-v2").resolve()
    if course_root not in destination_root.parents:
        raise RuntimeError("resolved destination escaped course root")
    destination_root.mkdir(parents=True, exist_ok=True)

    rag = RAGSystem(
        api_base=Config.DEEP_MODEL_API_BASE or Config.REMOTE_MODEL_API_BASE or Config.OLLAMA_BASE_URL,
        api_key=Config.DEEP_MODEL_API_KEY or Config.REMOTE_MODEL_API_KEY,
        embedding_model=Config.EMBEDDING_MODEL,
        llm_model=Config.LLM_MODEL_DEEP,
        vector_db_path=Config.VECTOR_DB_PATH,
        document_index_path=Config.DOCUMENT_INDEX_PATH,
        storage_root=Config.STORAGE_ROOT,
    )

    version = "course-kb-v2-" + hashlib.sha256(
        args.manifest.read_bytes() + args.graph.read_bytes()
    ).hexdigest()[:12]
    prepared: list[dict] = []
    for ordinal, material in enumerate(manifest.get("documents") or [], start=1):
        source_path = Path(str(material.get("path") or "")).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        destination_path = destination_root / source_path.name
        shutil.copy2(source_path, destination_path)
        _copy_markdown_assets(source_path, destination_path, destination_root)

        material_id = str(material.get("material_id") or source_path.stem)
        document_id = "doc-v2-" + hashlib.sha256(material_id.encode("utf-8")).hexdigest()[:24]
        prepared.append(
            {
                "ordinal": ordinal,
                "material": material,
                "destination_path": destination_path,
                "document_id": document_id,
            }
        )

    def import_one(item: dict) -> tuple[int, dict, dict]:
        material = item["material"]
        destination_path = item["destination_path"]
        document_id = item["document_id"]
        result = rag.import_document(
            str(destination_path),
            owner=args.owner,
            metadata_overrides={
                "course_id": args.course_id,
                "library_type": "course",
                "scope_type": "knowledge_point",
                "scope_id": str(material.get("scope_id") or ""),
                "knowledge_node_id": str(material.get("scope_id") or ""),
                "course_document_id": document_id,
                "content_language": str(material.get("language") or ""),
                "authority_tier": str(material.get("authority_tier") or ""),
            },
        )
        return int(item["ordinal"]), item, result

    imported_paths: list[str] = []
    imported_results: dict[int, tuple[dict, dict]] = {}
    import_failures: list[dict] = []
    worker_count = max(1, min(int(args.workers), 4, len(prepared) or 1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_items = {executor.submit(import_one, item): item for item in prepared}
        for future in concurrent.futures.as_completed(future_items):
            item = future_items[future]
            try:
                ordinal, completed_item, result = future.result()
                imported_results[ordinal] = (completed_item, result)
                imported_paths.append(str(completed_item["destination_path"].resolve()))
            except Exception as exc:
                import_failures.append(
                    {
                        "scope_id": (item.get("material") or {}).get("scope_id"),
                        "path": str(item.get("destination_path")),
                        "error": str(exc),
                    }
                )

    if import_failures or len(imported_results) != len(prepared):
        # These sources are not referenced by the active course index yet, so
        # keep successful imports as resumable staging data. A subsequent run
        # skips their matching hashes and retries only transient failures.
        pending_report = {
            "status": "pending",
            "course_id": args.course_id,
            "staged_document_count": len(imported_results),
            "failed_document_count": len(import_failures),
            "failures": import_failures,
            "active_course_index_unchanged": True,
        }
        _atomic_json(knowledge_root / "promotion-pending-report.json", pending_report)
        raise RuntimeError(
            "active index import failed: "
            + json.dumps(import_failures, ensure_ascii=False)
        )

    records = []
    for ordinal in sorted(imported_results):
        item, result = imported_results[ordinal]
        material = item["material"]
        destination_path = item["destination_path"]
        document_id = item["document_id"]
        try:
            source_url = str(material.get("source_url") or "")
        except Exception:
            raise
        records.append(
            {
                "id": document_id,
                "filename": destination_path.name,
                "path": str(destination_path.relative_to(course_root)).replace("\\", "/"),
                "size": destination_path.stat().st_size,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "course_id": args.course_id,
                "scope_type": "knowledge_point",
                "scope_id": str(material.get("scope_id") or ""),
                "library_type": "course",
                "owner_user_id": None,
                "source_url": source_url or None,
                "source_title": str(material.get("title") or destination_path.stem),
                "source_domain": urlparse(source_url).netloc if source_url else None,
                "source_site_name": str(material.get("source_group") or "reviewed-course-corpus"),
                "source_language": str(material.get("language") or ""),
                "content_language": str(material.get("language") or ""),
                "authority_tier": str(material.get("authority_tier") or "reviewed_material"),
                "doc_kind": str(material.get("doc_kind") or "document"),
                "generated_by": version,
                "status": "ready",
                "chunk_count": int(result.get("chunk_count") or 0),
                "rag_index_key": rag._make_index_key(str(destination_path.resolve()), args.owner),
                "active_index_version": version,
                "pending_index_version": None,
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    index_path = knowledge_root / "index.json"
    graph_path = course_root / "knowledge_graph.json"
    previous_index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = knowledge_root / "backups" / stamp
    backup_root.mkdir(parents=True, exist_ok=True)
    if index_path.exists():
        shutil.copy2(index_path, backup_root / "index.json")
    if graph_path.exists():
        shutil.copy2(graph_path, backup_root / "knowledge_graph.json")

    graph["status"] = "active"
    graph.setdefault("data", {})["activated_at"] = datetime.now(timezone.utc).isoformat()
    graph["data"]["corpus_version"] = version
    _atomic_json(index_path, records)
    _atomic_json(graph_path, graph)

    cleanup_failures = []
    for old in previous_index:
        relative = str(old.get("path") or "")
        if not relative or relative.startswith("knowledge_base/documents-v2/"):
            continue
        old_path = (course_root / relative).resolve()
        try:
            rag.delete_document(str(old_path), owner=args.owner)
        except Exception as exc:
            cleanup_failures.append({"path": str(old_path), "error": str(exc)})

    old_documents = (knowledge_root / "documents").resolve()
    if old_documents.is_dir() and old_documents != destination_root:
        archived_documents = backup_root / "documents"
        shutil.move(str(old_documents), str(archived_documents))

    report = {
        "status": "active",
        "course_id": args.course_id,
        "version": version,
        "document_count": len(records),
        "node_count": int(manifest.get("node_count") or 0),
        "backup_root": str(backup_root),
        "cleanup_failures": cleanup_failures,
        "imported_paths": imported_paths,
    }
    _atomic_json(knowledge_root / "promotion-report.json", report)
    pending_report_path = knowledge_root / "promotion-pending-report.json"
    if pending_report_path.exists():
        pending_report_path.unlink()
    print(json.dumps({**report, "imported_paths": "omitted"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
