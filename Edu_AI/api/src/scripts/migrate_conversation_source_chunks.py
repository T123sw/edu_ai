from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _display_content(value: Any) -> str:
    normalized = re.sub(r"\r\n?", "\n", str(value or "")).strip()
    return re.sub(
        r"^【章节上下文】\s*[:：]\s*[^\n]*\n+",
        "",
        normalized,
        count=1,
    ).strip()


def migrate_payload(payload: dict, chunk_records: dict[str, dict]) -> int:
    changed = 0
    for conversation in payload.get("conversations") or []:
        for message in conversation.get("messages") or []:
            for source in message.get("sources") or []:
                if not isinstance(source, dict):
                    continue
                chunk_id = str(source.get("chunk_id") or "").strip()
                record = chunk_records.get(chunk_id)
                if not record:
                    continue
                content = _display_content(record.get("content"))
                if not content or content == str(source.get("content") or "").strip():
                    continue
                metadata = dict(record.get("metadata") or {})
                source["content"] = content
                source["source_start_line"] = metadata.get("source_start_line")
                source["source_end_line"] = metadata.get("source_end_line")
                changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    from chromadb import PersistentClient
    from chromadb.config import Settings
    from modules.rag_v2.rag_main.core.config import Config

    conversations_path = Path(Config.CONVERSATIONS_FILE)
    payload = json.loads(conversations_path.read_text(encoding="utf-8"))
    chunk_ids = sorted(
        {
            str(source.get("chunk_id") or "").strip()
            for conversation in payload.get("conversations") or []
            for message in conversation.get("messages") or []
            for source in message.get("sources") or []
            if isinstance(source, dict) and source.get("chunk_id")
        }
    )

    collection = PersistentClient(
        path=str(Config.VECTOR_DB_PATH),
        settings=Settings(anonymized_telemetry=False),
    ).get_collection("documents")
    result = collection.get(ids=chunk_ids, include=["documents", "metadatas"])
    chunk_records = {
        chunk_id: {
            "content": (result.get("documents") or [])[index],
            "metadata": (result.get("metadatas") or [])[index],
        }
        for index, chunk_id in enumerate(result.get("ids") or [])
    }
    changed = migrate_payload(payload, chunk_records)

    if args.apply and changed:
        conversations_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"matched_chunks": len(chunk_records), "changed_sources": changed, "applied": args.apply}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
