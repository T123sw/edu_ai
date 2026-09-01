from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from app.services.retrieval_evaluation import RetrievalCase, evaluate_retrieval


def _load_cases(path: Path) -> list[RetrievalCase]:
    cases: list[RetrievalCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        payload = json.loads(value)
        try:
            cases.append(
                RetrievalCase(
                    case_id=str(payload["case_id"]),
                    query=str(payload["query"]),
                    expected_source_contains=tuple(payload.get("expected_source_contains") or ()),
                    expected_chunk_ids=tuple(payload.get("expected_chunk_ids") or ()),
                    expected_node_ids=tuple(payload.get("expected_node_ids") or ()),
                    requires_visual=bool(payload.get("requires_visual", False)),
                )
            )
        except KeyError as exc:
            raise ValueError(f"评测集第 {line_number} 行缺少字段: {exc}") from exc
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="运行生产同链路 RAG 离线评测")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--owner", default="teacher")
    parser.add_argument("--source-path-contains", default="course_data")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--vector-db-path", type=Path)
    parser.add_argument("--document-index-path", type=Path)
    parser.add_argument("--storage-root", type=Path)
    args = parser.parse_args()

    load_dotenv(Path.cwd() / ".env", override=False)
    if args.vector_db_path or args.document_index_path:
        if not args.vector_db_path or not args.document_index_path:
            raise ValueError("--vector-db-path and --document-index-path must be supplied together")
        from core.config import Config
        from modules.rag_v2.rag_main.system import RAGSystem

        rag_system = RAGSystem(
            api_base=Config.DEEP_MODEL_API_BASE or Config.REMOTE_MODEL_API_BASE or Config.OLLAMA_BASE_URL,
            api_key=Config.DEEP_MODEL_API_KEY or Config.REMOTE_MODEL_API_KEY,
            embedding_model=Config.EMBEDDING_MODEL,
            llm_model=Config.LLM_MODEL_DEEP,
            vector_db_path=args.vector_db_path,
            document_index_path=args.document_index_path,
            storage_root=args.storage_root,
        )
    else:
        from modules.rag_v2.api import get_rag_system

        rag_system = get_rag_system()
    allowed_sources: list[str] = []
    for index_key, metadata in rag_system.document_index.items():
        physical_path = str(metadata.get("physical_path") or "")
        if args.owner and metadata.get("owner") != args.owner:
            continue
        if args.source_path_contains and args.source_path_contains.lower() not in physical_path.lower():
            continue
        allowed_sources.append(str(metadata.get("source_key") or index_key))
    if not allowed_sources:
        raise RuntimeError("没有找到符合评测范围的活动索引")

    report = evaluate_retrieval(
        rag_system,
        _load_cases(args.dataset),
        allowed_sources=allowed_sources,
        top_k=args.top_k,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
