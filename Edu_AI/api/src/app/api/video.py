"""Video API routes — HTTP layer only.

Delegates business logic to app.services.video_service.
"""

from __future__ import annotations

import mimetypes
import shutil
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from app.auth import get_current_user
from app.schemas.video import (
    VideoJobStatusResponse,
    VideoSearchHit,
    VideoSearchRequest,
    VideoSearchResponse,
    VideoUploadResponse,
)
from app.services import video_service as _svc
from app.services.job_store import JobKind, get_job
from app.services.runtime_config_resolver import runtime_config_resolver
from core.config import Config

router = APIRouter(prefix="/api/video", tags=["Video Ingestion"])


@router.get("/stream", summary="本地视频流播放（支持 Range/206）")
async def stream_video(
    rel_path: str = Query(..., description="相对当前用户视频根目录的路径，如 physics_1/abc.mp4"),
    range_header: str | None = Header(default=None, alias="Range"),
    current_user: dict = Depends(get_current_user),
):
    try:
        video_path = _svc.resolve_user_video_path(current_user, rel_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="视频文件不存在")
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权访问该视频")

    file_size = video_path.stat().st_size
    media_type, _ = mimetypes.guess_type(str(video_path))
    media_type = media_type or "application/octet-stream"

    common_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache",
    }

    if not range_header:
        headers = {**common_headers, "Content-Length": str(file_size)}
        return StreamingResponse(_svc.iter_file_range(video_path, 0, file_size - 1), media_type=media_type, headers=headers)

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
        _svc.iter_file_range(video_path, start, end),
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存视频失败: {exc}") from exc

    job = _svc.create_video_ingestion_job(
        video_path=save_path,
        course_id=course_id,
        owner=username,
        original_filename=file.filename or save_name,
        window_seconds=window_seconds,
        stride_seconds=stride_seconds,
        config_snapshot=runtime_config_resolver.capture_snapshot(username),
    )

    bg.add_task(
        _svc.run_video_ingestion_job,
        job.edu_job_id,
    )

    return VideoUploadResponse(
        job_id=job.edu_job_id,
        status="queued",
        message="上传成功，已提交后台入库任务",
        saved_video_path=str(
            save_path.relative_to(Config.VIDEOS_ROOT / username)
        ).replace("\\", "/"),
    )


@router.get("/jobs/{job_id}", response_model=VideoJobStatusResponse, summary="查询视频入库任务状态")
async def get_video_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    job = get_job(job_id)
    if not job or job.kind != JobKind.INGEST_VIDEO:
        raise HTTPException(status_code=404, detail="任务不存在")

    username = current_user.get("username") or "anonymous"
    if job.owner_user_id != username:
        raise HTTPException(status_code=403, detail="无权查看该任务")

    return VideoJobStatusResponse(**_svc.as_legacy_video_job(job))


@router.post("/search", response_model=VideoSearchResponse, summary="视频片段语义检索")
async def search_video_segments(request: VideoSearchRequest, current_user: dict = Depends(get_current_user)):
    try:
        query_chunk_dir = Config.VIDEO_CHUNKS_ROOT / (current_user.get("username") or "anonymous") / "_query_tmp"
        query_chunk_dir.mkdir(parents=True, exist_ok=True)
        ingester = _svc.make_ingester(window_seconds=30, stride_seconds=20, chunk_dir=query_chunk_dir)
        query_vector = ingester._post_text_query_embedding(request.query)

        where: dict | None = {"modality": "video"}
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

            stream_url: str | None = None
            playback_url: str | None = None
            if chunk_path:
                rel_path = _svc.to_user_relative_path(current_user, str(chunk_path))
            elif source_path:
                rel_path = _svc.to_user_relative_path(current_user, str(source_path))
            else:
                rel_path = None

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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"视频检索失败: {exc}") from exc
