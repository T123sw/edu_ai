"""Video ingestion and search service — embedding, chunking, ChromaDB indexing.

Does NOT depend on HTTP or FastAPI.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from core.config import Config
from local_video_ingestion import LocalVideoRAGIngester

# ---------------------------------------------------------------------------
# in-memory job store
# ---------------------------------------------------------------------------

_video_jobs: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# ingester factory
# ---------------------------------------------------------------------------


def make_ingester(window_seconds: int, stride_seconds: int, chunk_dir: Path) -> LocalVideoRAGIngester:
    embedding_api_base = os.getenv("EMBEDDING_API_BASE") or Config.EMBEDDING_API_BASE
    embedding_api_key = os.getenv("EMBEDDING_API_KEY") or Config.OPENROUTER_API_KEY
    embedding_model = os.getenv("EMBEDDING_MODEL") or Config.EMBEDDING_MODEL
    embedding_backend = os.getenv("EMBEDDING_BACKEND") or Config.EMBEDDING_BACKEND

    if not embedding_api_base:
        raise RuntimeError("未配置 EMBEDDING_API_BASE，无法执行视频向量化")
    if not embedding_api_key:
        raise RuntimeError("未配置 EMBEDDING_API_KEY/OPENROUTER_API_KEY，无法执行视频向量化")

    return LocalVideoRAGIngester(
        embedding_api_base=embedding_api_base,
        embedding_api_key=embedding_api_key,
        embedding_model=embedding_model,
        embedding_backend=embedding_backend,
        chroma_persist_dir=Config.VECTOR_DB_PATH,
        collection_name="course_videos",
        temp_dir=chunk_dir,
        window_seconds=window_seconds,
        stride_seconds=stride_seconds,
        embedding_timeout_sec=Config.EMBEDDING_TIMEOUT_SEC,
        embedding_max_retries=Config.EMBEDDING_MAX_RETRIES,
        gemini_dimensions=Config.GEMINI_EMBEDDING_DIMENSIONS,
    )


# ---------------------------------------------------------------------------
# user path helpers
# ---------------------------------------------------------------------------


def get_user_root(current_user: dict) -> Path:
    username = current_user.get("username") or "anonymous"
    return (Config.VIDEOS_ROOT / username).resolve()


def resolve_user_video_path(current_user: dict, rel_path: str) -> Path:
    user_root = get_user_root(current_user)
    candidate = (user_root / rel_path).resolve()
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError("视频文件不存在")
    if user_root not in candidate.parents and candidate != user_root:
        raise PermissionError("无权访问该视频")
    return candidate


def to_user_relative_path(current_user: dict, full_path: str) -> Optional[str]:
    try:
        user_root = get_user_root(current_user)
        path_obj = Path(full_path).resolve()
        return str(path_obj.relative_to(user_root)).replace("\\", "/")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# file streaming
# ---------------------------------------------------------------------------


def iter_file_range(path: Path, start: int, end: int, chunk_size: int = 1024 * 512):
    with open(path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = f.read(read_size)
            if not data:
                break
            remaining -= len(data)
            yield data


# ---------------------------------------------------------------------------
# background ingestion job
# ---------------------------------------------------------------------------


def run_video_ingestion_job(
    job_id: str,
    *,
    video_path: str,
    course_id: str,
    owner: str,
    window_seconds: int,
    stride_seconds: int,
) -> None:
    _video_jobs[job_id].update({"status": "running", "stage": "ingesting", "progress": 10})
    try:
        chunk_dir = Config.VIDEO_CHUNKS_ROOT / owner / course_id / Path(video_path).stem
        chunk_dir.mkdir(parents=True, exist_ok=True)
        ingester = make_ingester(
            window_seconds=window_seconds,
            stride_seconds=stride_seconds,
            chunk_dir=chunk_dir,
        )
        result = ingester.ingest(video_path=video_path, course_id=course_id)
        _video_jobs[job_id].update(
            {
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "message": "视频入库完成",
                "result": result,
            }
        )
    except Exception as exc:
        _video_jobs[job_id].update(
            {
                "status": "failed",
                "stage": "failed",
                "progress": 100,
                "message": f"视频入库失败: {exc}",
            }
        )


def create_job(video_path: str, course_id: str, owner: str) -> str:
    job_id = uuid.uuid4().hex
    _video_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "stage": "uploaded",
        "progress": 0,
        "message": "视频上传成功，等待入库",
        "video_path": video_path,
        "course_id": course_id,
        "owner": owner,
    }
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    return _video_jobs.get(job_id)
