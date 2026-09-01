"""Video ingestion and search business services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.services.job_store import (
    EduJob,
    JobKind,
    JobStatus,
    create_job,
    get_job,
    update_job,
)
from app.services.runtime_config_resolver import runtime_config_resolver
from core.config import Config
from local_video_ingestion import LocalVideoRAGIngester


def make_ingester(
    window_seconds: int,
    stride_seconds: int,
    chunk_dir: Path,
    *,
    owner_user_id: str | None = None,
    config_snapshot: dict[str, str] | None = None,
) -> LocalVideoRAGIngester:
    """Build an ingester from the request/job's resolved provider revision."""
    runtime_embedding = runtime_config_resolver.resolve(
        "embedding",
        owner_user_id=owner_user_id,
        snapshot=config_snapshot,
    )
    embedding_api_base = str(runtime_embedding.get("base_url") or "").strip()
    embedding_api_key = str(runtime_embedding.get("api_key") or "").strip()
    embedding_model = str(
        runtime_embedding.get("model") or Config.EMBEDDING_MODEL
    ).strip()

    if not embedding_api_base:
        raise RuntimeError("未配置 EMBEDDING_API_BASE，无法执行视频向量化")
    if not embedding_api_key:
        raise RuntimeError("未配置 EMBEDDING_API_KEY，无法执行视频向量化")

    return LocalVideoRAGIngester(
        embedding_api_base=embedding_api_base,
        embedding_api_key=embedding_api_key,
        embedding_model=embedding_model,
        embedding_backend=Config.EMBEDDING_BACKEND,
        chroma_persist_dir=Config.VECTOR_DB_PATH,
        collection_name="course_videos",
        temp_dir=chunk_dir,
        window_seconds=window_seconds,
        stride_seconds=stride_seconds,
        embedding_timeout_sec=int(
            runtime_embedding.get("timeout_seconds") or Config.EMBEDDING_TIMEOUT_SEC
        ),
        embedding_max_retries=Config.EMBEDDING_MAX_RETRIES,
        gemini_dimensions=int(
            runtime_embedding.get("dimensions")
            or Config.GEMINI_EMBEDDING_DIMENSIONS
        ),
    )


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


def iter_file_range(
    path: Path, start: int, end: int, chunk_size: int = 1024 * 512
):
    with open(path, "rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = handle.read(read_size)
            if not data:
                break
            remaining -= len(data)
            yield data


def create_video_ingestion_job(
    *,
    video_path: Path,
    course_id: str,
    owner: str,
    original_filename: str,
    window_seconds: int,
    stride_seconds: int,
    config_snapshot: dict[str, str] | None = None,
    existing_job: EduJob | None = None,
) -> EduJob:
    """Persist a sanitized, retryable video-ingestion command."""
    if existing_job is not None:
        return existing_job
    user_root = (Config.VIDEOS_ROOT / owner).resolve()
    resolved_path = video_path.resolve()
    if user_root not in resolved_path.parents:
        raise PermissionError("视频文件不属于当前用户")
    video_rel_path = str(resolved_path.relative_to(user_root)).replace("\\", "/")
    job = create_job(
        kind=JobKind.INGEST_VIDEO,
        owner_user_id=owner,
        course_id=course_id,
        input_summary={
            "title": original_filename,
            "video_rel_path": video_rel_path,
            "window_seconds": window_seconds,
            "stride_seconds": stride_seconds,
            "config_snapshot": dict(config_snapshot or {}),
        },
    )
    from app.services.platform_task_handlers import enqueue_platform_task

    return enqueue_platform_task(
        job=job,
        workflow_type="video_ingest",
        command={
            "course_id": course_id,
            "video_rel_path": video_rel_path,
            "window_seconds": window_seconds,
            "stride_seconds": stride_seconds,
        },
        runtime_config_snapshot=dict(config_snapshot or {}),
    )


def run_video_ingestion_job(job_id: str) -> None:
    """Run one durable job. Re-reading the ledger makes cancel/restart safe."""
    job = get_job(job_id)
    if job is None or job.kind != JobKind.INGEST_VIDEO:
        return
    if job.status in {JobStatus.CANCELED, JobStatus.CANCEL_REQUESTED}:
        if job.status == JobStatus.CANCEL_REQUESTED:
            update_job(
                job_id,
                status=JobStatus.CANCELED,
                step="canceled",
                progress=100,
                message="视频入库任务已取消",
            )
        return

    summary = dict(job.input_summary or {})
    owner = job.owner_user_id
    course_id = str(job.course_id or "").strip()
    video_rel_path = str(summary.get("video_rel_path") or "").strip()
    window_seconds = int(summary.get("window_seconds") or 30)
    stride_seconds = int(summary.get("stride_seconds") or 20)
    config_snapshot = dict(summary.get("config_snapshot") or {})
    user_root = (Config.VIDEOS_ROOT / owner).resolve()
    video_path = (user_root / video_rel_path).resolve()
    if user_root not in video_path.parents or not video_path.is_file():
        update_job(
            job_id,
            status=JobStatus.FAILED,
            step="source_missing",
            progress=100,
            message="视频源文件不存在或不可访问",
            error_message="视频源文件不存在或不可访问",
            error_code="VIDEO_SOURCE_MISSING",
        )
        return

    update_job(
        job_id,
        status=JobStatus.RUNNING,
        step="ingesting",
        progress=10,
        message="正在切片并建立视频索引",
    )
    try:
        chunk_dir = Config.VIDEO_CHUNKS_ROOT / owner / course_id / video_path.stem
        chunk_dir.mkdir(parents=True, exist_ok=True)
        ingester = make_ingester(
            window_seconds=window_seconds,
            stride_seconds=stride_seconds,
            chunk_dir=chunk_dir,
            owner_user_id=owner,
            config_snapshot=config_snapshot,
        )
        result = ingester.ingest(video_path=str(video_path), course_id=course_id)
        update_job(
            job_id,
            status=JobStatus.SUCCEEDED,
            step="completed",
            progress=100,
            message="视频入库完成",
            result_ref={
                "resource_type": "video_document",
                "course_id": course_id,
                "video_rel_path": video_rel_path,
                **(result if isinstance(result, dict) else {}),
            },
        )
    except Exception as exc:
        update_job(
            job_id,
            status=JobStatus.FAILED,
            step="failed",
            progress=100,
            message=f"视频入库失败: {exc}",
            error_message=str(exc),
            error_code="VIDEO_INGESTION_FAILED",
        )


def as_legacy_video_job(job: EduJob) -> dict[str, Any]:
    """Keep the old status route compatible while the UI uses /api/jobs."""
    status_map = {
        JobStatus.SUCCEEDED: "completed",
        JobStatus.CANCELED: "failed",
        JobStatus.CANCEL_REQUESTED: "running",
    }
    return {
        "job_id": job.edu_job_id,
        "status": status_map.get(job.status, job.status.value),
        "stage": job.step,
        "progress": job.progress,
        "message": job.message,
        "result": job.result_ref,
        "owner": job.owner_user_id,
    }
