from __future__ import annotations

import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.auth import get_current_user
from core.config import Config
from local_video_ingestion import LocalVideoRAGIngester


router = APIRouter(prefix="/api/video", tags=["Video Ingestion"])

_video_jobs: Dict[str, Dict[str, Any]] = {}


class VideoUploadResponse(BaseModel):
    job_id: str
    status: str
    message: str
    saved_video_path: str


class VideoJobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress: int
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class VideoSearchRequest(BaseModel):
    query: str = Field(..., description="查询文本")
    top_k: int = Field(default=5, ge=1, le=20)
    course_id: Optional[str] = Field(default=None, description="按课程过滤")


class VideoSearchHit(BaseModel):
    id: str
    score: float
    transcript: str
    course_id: Optional[str] = None
    source_original_path: Optional[str] = None
    source_chunk_path: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    stream_url: Optional[str] = None
    playback_url: Optional[str] = None


class VideoSearchResponse(BaseModel):
    query: str
    hits: list[VideoSearchHit]


def _make_ingester(window_seconds: int, stride_seconds: int, chunk_dir: Path) -> LocalVideoRAGIngester:
    import os

    embedding_api_base = os.getenv("EMBEDDING_API_BASE") or Config.EMBEDDING_API_BASE
    embedding_api_key = os.getenv("EMBEDDING_API_KEY") or Config.OPENROUTER_API_KEY
    embedding_model = os.getenv("EMBEDDING_MODEL") or Config.EMBEDDING_MODEL
    embedding_backend = os.getenv("EMBEDDING_BACKEND") or Config.EMBEDDING_BACKEND

    if not embedding_api_base:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="未配置 EMBEDDING_API_BASE，无法执行视频向量化",
        )
    if not embedding_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="未配置 EMBEDDING_API_KEY/OPENROUTER_API_KEY，无法执行视频向量化",
        )

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


def _get_user_root(current_user: dict) -> Path:
    username = current_user.get("username") or "anonymous"
    return (Config.VIDEOS_ROOT / username).resolve()


def _resolve_user_video_path(current_user: dict, rel_path: str) -> Path:
    user_root = _get_user_root(current_user)
    candidate = (user_root / rel_path).resolve()
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="视频文件不存在")

    if user_root not in candidate.parents and candidate != user_root:
        raise HTTPException(status_code=403, detail="无权访问该视频")

    return candidate


def _to_user_relative_path(current_user: dict, full_path: str) -> Optional[str]:
    try:
        user_root = _get_user_root(current_user)
        path_obj = Path(full_path).resolve()
        return str(path_obj.relative_to(user_root)).replace("\\", "/")
    except Exception:  # noqa: BLE001
        return None


def _iter_file_range(path: Path, start: int, end: int, chunk_size: int = 1024 * 512):
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


def _run_video_ingestion_job(
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
        ingester = _make_ingester(
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
    except Exception as exc:  # noqa: BLE001
        _video_jobs[job_id].update(
            {
                "status": "failed",
                "stage": "failed",
                "progress": 100,
                "message": f"视频入库失败: {exc}",
            }
        )


@router.get("/stream", summary="本地视频流播放（支持 Range/206）")
async def stream_video(
    rel_path: str = Query(..., description="相对当前用户视频根目录的路径，如 physics_1/abc.mp4"),
    range_header: Optional[str] = Header(default=None, alias="Range"),
    current_user: dict = Depends(get_current_user),
):
    video_path = _resolve_user_video_path(current_user, rel_path)
    file_size = video_path.stat().st_size
    media_type, _ = mimetypes.guess_type(str(video_path))
    media_type = media_type or "application/octet-stream"

    common_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache",
    }

    if not range_header:
        headers = {**common_headers, "Content-Length": str(file_size)}
        return StreamingResponse(_iter_file_range(video_path, 0, file_size - 1), media_type=media_type, headers=headers)

    if not range_header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="不合法的 Range 头")

    byte_range = range_header.replace("bytes=", "").strip()
    start_str, end_str = byte_range.split("-", 1)
    start = int(start_str) if start_str else 0
    end = int(end_str) if end_str else file_size - 1

    if start < 0 or end < 0 or start > end or start >= file_size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    end = min(end, file_size - 1)
    content_length = end - start + 1
    headers = {
        **common_headers,
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(content_length),
    }

    return StreamingResponse(
        _iter_file_range(video_path, start, end),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


@router.post("/upload", response_model=VideoUploadResponse, summary="上传视频并异步入库")
async def upload_video(
    bg: BackgroundTasks,
    file: UploadFile = File(..., description="视频文件，建议 .mp4"),
    course_id: str = Query(..., description="课程ID"),
    window_seconds: int = Query(30, ge=10, le=120),
    stride_seconds: int = Query(20, ge=5, le=120),
    current_user: dict = Depends(get_current_user),
):
    if stride_seconds > window_seconds:
        raise HTTPException(status_code=400, detail="stride_seconds 不能大于 window_seconds")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
        raise HTTPException(status_code=400, detail=f"不支持的视频类型: {ext}")

    username = current_user.get("username") or "anonymous"
    user_video_dir = Config.VIDEOS_ROOT / username / course_id
    user_video_dir.mkdir(parents=True, exist_ok=True)

    save_name = f"{uuid.uuid4().hex}{ext}"
    save_path = (user_video_dir / save_name).resolve()

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"保存视频失败: {exc}") from exc

    job_id = uuid.uuid4().hex
    _video_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "stage": "uploaded",
        "progress": 0,
        "message": "视频上传成功，等待入库",
        "video_path": str(save_path),
        "course_id": course_id,
        "owner": username,
    }

    bg.add_task(
        _run_video_ingestion_job,
        job_id,
        video_path=str(save_path),
        course_id=course_id,
        owner=username,
        window_seconds=window_seconds,
        stride_seconds=stride_seconds,
    )

    return VideoUploadResponse(
        job_id=job_id,
        status="queued",
        message="上传成功，已开始后台入库",
        saved_video_path=str(save_path),
    )


@router.get("/jobs/{job_id}", response_model=VideoJobStatusResponse, summary="查询视频入库任务状态")
async def get_video_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    job = _video_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    username = current_user.get("username") or "anonymous"
    if job.get("owner") != username:
        raise HTTPException(status_code=403, detail="无权查看该任务")

    return VideoJobStatusResponse(**{k: job.get(k) for k in ["job_id", "status", "stage", "progress", "message", "result"]})


@router.post("/search", response_model=VideoSearchResponse, summary="视频片段语义检索")
async def search_video_segments(request: VideoSearchRequest, current_user: dict = Depends(get_current_user)):
    try:
        query_chunk_dir = Config.VIDEO_CHUNKS_ROOT / (current_user.get("username") or "anonymous") / "_query_tmp"
        query_chunk_dir.mkdir(parents=True, exist_ok=True)
        ingester = _make_ingester(window_seconds=30, stride_seconds=20, chunk_dir=query_chunk_dir)
        query_vector = ingester._post_text_query_embedding(request.query)

        where: Optional[Dict[str, Any]] = {"modality": "video"}
        if request.course_id:
            where = {"$and": [{"modality": "video"}, {"course_id": request.course_id}]}

        raw = ingester.collection.query(
            query_embeddings=[query_vector],
            n_results=request.top_k,
            where=where,
        )

        ids = raw.get("ids", [[]])[0] if raw.get("ids") else []
        docs = raw.get("documents", [[]])[0] if raw.get("documents") else []
        metas = raw.get("metadatas", [[]])[0] if raw.get("metadatas") else []
        dists = raw.get("distances", [[]])[0] if raw.get("distances") else []

        hits: list[VideoSearchHit] = []
        for i, _id in enumerate(ids):
            md = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            start_time = float(md.get("start_time")) if md.get("start_time") is not None else None
            end_time = float(md.get("end_time")) if md.get("end_time") is not None else None
            source_path = md.get("source_original_path")
            chunk_path = md.get("source_chunk_path")

            stream_url: Optional[str] = None
            playback_url: Optional[str] = None
            if chunk_path:
                rel_path = _to_user_relative_path(current_user, str(chunk_path))
            elif source_path:
                rel_path = _to_user_relative_path(current_user, str(source_path))
            else:
                rel_path = None

            if rel_path:
                if rel_path:
                    stream_url = f"/api/video/stream?rel_path={quote(rel_path, safe='')}"
                    if start_time is not None:
                        playback_url = f"{stream_url}#t={start_time}"
                    else:
                        playback_url = stream_url

            hits.append(
                VideoSearchHit(
                    id=str(_id),
                    score=float(dists[i]) if i < len(dists) else 0.0,
                    transcript=str(docs[i]) if i < len(docs) else "",
                    course_id=md.get("course_id"),
                    source_original_path=source_path,
                    source_chunk_path=str(chunk_path) if chunk_path else None,
                    start_time=start_time,
                    end_time=end_time,
                    stream_url=stream_url,
                    playback_url=playback_url,
                )
            )

        return VideoSearchResponse(query=request.query, hits=hits)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"视频检索失败: {exc}") from exc
