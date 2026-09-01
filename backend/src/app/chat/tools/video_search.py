from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import Config
from local_video_ingestion import LocalVideoRAGIngester

VIDEO_QUERY_HINTS = (
    "视频",
    "片段",
    "画面",
    "镜头",
    "播放",
    "讲解视频",
    "这段视频",
)


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


def should_query_video_for_runtime(question: str) -> bool:
    text = str(question or "").strip().lower()
    if not text:
        return False
    return any(hint in text for hint in VIDEO_QUERY_HINTS)


def video_search_tool(
    *,
    query: str,
    top_k: int = 5,
    selected_doc_ids: Optional[List[str]] = None,
    owner: Optional[str] = None,
    course_id: Optional[str] = None,
) -> Dict[str, Any]:
    del selected_doc_ids

    if not should_query_video_for_runtime(query):
        return {"ok": True, "payload": {"summary": "", "sources": []}}

    hits = search_video_segments_for_chat(
        query=query,
        owner=owner,
        course_id=course_id,
        top_k=top_k,
    )

    sources: List[Dict[str, Any]] = []
    summary_lines: List[str] = []
    for index, hit in enumerate(hits, start=1):
        start_time = hit.get("start_time")
        end_time = hit.get("end_time")
        transcript = str(hit.get("transcript") or "").strip()
        stream_url = str(hit.get("playback_url") or hit.get("stream_url") or "").strip()
        title = Path(str(hit.get("source_original_path") or hit.get("source_chunk_path") or f"视频片段 {index}")).name

        if transcript:
            summary_lines.append(
                f"{index}. [{start_time}-{end_time}] {transcript[:180]}"
            )

        sources.append(
            {
                "source": title,
                "content": transcript,
                "modality": "video",
                "video_url": stream_url,
                "start_time": start_time,
                "end_time": end_time,
                "source_path": hit.get("source_original_path") or hit.get("source_chunk_path"),
                "metadata": {
                    "modality": "video",
                    "video_url": stream_url,
                    "stream_url": str(hit.get("stream_url") or "").strip(),
                    "playback_url": str(hit.get("playback_url") or "").strip(),
                    "title": title,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            }
        )

    return {
        "ok": True,
        "payload": {
            "summary": "\n".join(summary_lines),
            "sources": sources,
        },
    }
