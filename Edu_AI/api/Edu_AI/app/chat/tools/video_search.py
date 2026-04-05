from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import Config
from local_video_ingestion import LocalVideoRAGIngester


def should_use_video_search(
    *,
    question: str,
    llm: Any,
    prompt: str,
) -> Tuple[bool, str, str]:
    text = str(question or "").strip()
    if not text:
        return False, "empty_question", "fallback"

    if not llm:
        return False, "llm_unavailable", "fallback"

    try:
        resp = llm.invoke([
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ])
        raw = str(getattr(resp, "content", "") or "").strip()
        payload = json.loads(raw)
        if isinstance(payload, dict):
            use_video = bool(payload.get("use_video_search", False))
            reason = str(payload.get("reason") or "llm_decision")
            return use_video, reason, "llm"
        return False, "invalid_payload", "fallback"
    except Exception as exc:
        return False, f"llm_error:{exc}", "fallback"


def search_video_segments_for_chat(
    *,
    query: str,
    owner: Optional[str],
    course_id: Optional[str],
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    username = owner or "anonymous"
    query_chunk_dir = Config.VIDEO_CHUNKS_ROOT / username / "_query_tmp"
    query_chunk_dir.mkdir(parents=True, exist_ok=True)

    embedding_api_base = os.getenv("EMBEDDING_API_BASE") or Config.EMBEDDING_API_BASE
    embedding_api_key = os.getenv("EMBEDDING_API_KEY") or Config.OPENROUTER_API_KEY
    embedding_model = os.getenv("EMBEDDING_MODEL") or Config.EMBEDDING_MODEL
    embedding_backend = os.getenv("EMBEDDING_BACKEND") or Config.EMBEDDING_BACKEND

    if not embedding_api_base or not embedding_api_key:
        return []

    ingester = LocalVideoRAGIngester(
        embedding_api_base=embedding_api_base,
        embedding_api_key=embedding_api_key,
        embedding_model=embedding_model,
        embedding_backend=embedding_backend,
        chroma_persist_dir=Config.VECTOR_DB_PATH,
        collection_name="course_videos",
        temp_dir=query_chunk_dir,
        window_seconds=30,
        stride_seconds=20,
        embedding_timeout_sec=Config.EMBEDDING_TIMEOUT_SEC,
        embedding_max_retries=Config.EMBEDDING_MAX_RETRIES,
        gemini_dimensions=Config.GEMINI_EMBEDDING_DIMENSIONS,
    )

    query_vector = ingester._post_text_query_embedding(query)
    where: Optional[Dict[str, Any]] = {"modality": "video"}
    if course_id:
        where = {"$and": [{"modality": "video"}, {"course_id": course_id}]}

    raw = ingester.collection.query(
        query_embeddings=[query_vector],
        n_results=max(1, min(int(top_k), 5)),
        where=where,
    )

    ids = raw.get("ids", [[]])[0] if raw.get("ids") else []
    docs = raw.get("documents", [[]])[0] if raw.get("documents") else []
    metas = raw.get("metadatas", [[]])[0] if raw.get("metadatas") else []
    dists = raw.get("distances", [[]])[0] if raw.get("distances") else []

    hits: List[Dict[str, Any]] = []
    for i, _id in enumerate(ids):
        md = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
        hits.append(
            {
                "id": str(_id),
                "score": float(dists[i]) if i < len(dists) else 0.0,
                "transcript": str(docs[i]) if i < len(docs) else "",
                "course_id": md.get("course_id"),
                "source_chunk_path": md.get("source_chunk_path"),
                "start_time": md.get("start_time"),
                "end_time": md.get("end_time"),
            }
        )
    return hits
