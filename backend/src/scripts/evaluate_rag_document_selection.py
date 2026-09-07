"""Real-model smoke test using synthetic filenames; never opens the document index.

Run from backend/src: python scripts/evaluate_rag_document_selection.py --output /tmp/selection.json
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.rag_v2.document_selector import select_documents
from modules.rag_v2.rag_main.system import RAGSystem
from modules.rag_v2.rag_main.core.config import Config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rag = RAGSystem.__new__(RAGSystem)
    rag.api_base = (os.getenv("QWEN_BASE_URL") or os.getenv("REMOTE_MODEL_API_BASE")
                    or os.getenv("DEEPSEEK_BASE_URL") or Config.REMOTE_MODEL_API_BASE
                    or Config.DEEPSEEK_BASE_URL or Config.OLLAMA_BASE_URL)
    rag.api_key = (os.getenv("QWEN_API_KEY") or os.getenv("REMOTE_MODEL_API_KEY")
                   or os.getenv("DEEPSEEK_API_KEY") or Config.REMOTE_MODEL_API_KEY
                   or Config.DEEPSEEK_API_KEY)
    rag.llm_model = os.getenv("LLM_MODEL") or Config.LLM_MODEL
    candidates = {"D1": {"file_name": "树与二叉树.pdf"}, "D2": {"file_name": "排序算法.pdf"},
                  "D3": {"file_name": "数据库事务.pdf"}, "D4": {"file_name": "课程资料.pdf"}}
    rows = []
    for question, expected in [("解释二叉树的中序遍历", ["D1"]),
                               ("生成排序算法练习题", ["D2"]),
                               ("对比二叉树遍历与排序算法", ["D1", "D2"])]:
        keys, trace = select_documents(question, candidates, lambda messages: rag._call_llm(
            messages=messages, llm_config={"timeout_seconds": Config.RAG_DOCUMENT_SELECTION_TIMEOUT}))
        rows.append({"question": question, "expected": expected, "selected_ids": keys,
                     "passed": set(keys) == set(expected) and trace["fallback_reason"] is None,
                     "trace": trace})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"kind": "real model, synthetic filenames; not browser E2E",
                                      "results": rows}, ensure_ascii=False, indent=2))
    print(f"{sum(row['passed'] for row in rows)}/{len(rows)} filename selection cases passed; evidence: {args.output}")
    return 0 if all(row["passed"] for row in rows) else 1

if __name__ == "__main__":
    raise SystemExit(main())
