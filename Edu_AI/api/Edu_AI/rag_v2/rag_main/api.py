"""
新的 RAG v2 API 路由
提供知识库增量导入和RAG问答功能
"""
import os
import time
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, status, Query, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from urllib.parse import quote, unquote

from .system import RAGSystem
from .core.config import Config
from app.auth import get_current_user

import base64
import mimetypes
import requests
import subprocess
import tempfile
import shutil
import hashlib
from datetime import datetime

# 加载.env文件
try:
    from dotenv import load_dotenv

    env_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "config_openai.env"),
        ".env",
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
            break
except ImportError:
    pass
except Exception as e:
    print(f"[WARNING] Failed to load .env file: {e}")


router = APIRouter(prefix="/api/rag", tags=["RAG"])

# 全局RAG系统实例（延迟初始化）
_rag_system: Optional[RAGSystem] = None
_import_jobs: Dict[str, Dict[str, Any]] = {}
_video_index: Dict[str, Dict[str, Any]] = {}
_image_index: Dict[str, Dict[str, Any]] = {}


def _normalize_owner(owner: Optional[str]) -> str:
    normalized_owner = (owner or "anonymous").strip()
    if not normalized_owner or normalized_owner in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效用户名")
    if ".." in normalized_owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效用户名")
    if "/" in normalized_owner or "\\" in normalized_owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效用户名")
    if normalized_owner.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", normalized_owner):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效用户名")
    return normalized_owner


def _sanitize_upload_filename(filename: Optional[str]) -> str:
    safe_name = Path(filename or "").name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效文件名")
    return safe_name


def _is_path_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _get_user_temp_dir(username: Optional[str]) -> Path:
    return Config.TEMP_DIR / _normalize_owner(username)


def _get_user_media_dir(media_kind: str, username: Optional[str]) -> Path:
    return Config.STORAGE_ROOT / media_kind / _normalize_owner(username)


def _set_import_job(job_id: str, owner: Optional[str], **updates: Any) -> Dict[str, Any]:
    normalized_owner = _normalize_owner(owner)
    existing = _import_jobs.get(job_id)
    if existing and existing.get("owner") not in {None, normalized_owner}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该导入任务")

    job = dict(existing or {})
    job.update(updates)
    job["job_id"] = job_id
    job["owner"] = normalized_owner
    _import_jobs[job_id] = job
    return job


def _get_owned_import_job(job_id: str, owner: Optional[str]) -> Dict[str, Any]:
    job = _import_jobs.get(job_id)
    if not job or job.get("owner") != _normalize_owner(owner):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应导入任务")
    return job


def _normalize_storage_relative_path(file_path: str | Path) -> Path:
    storage_root = Config.STORAGE_ROOT.resolve()
    candidate = Path(str(file_path))

    if candidate.is_absolute():
        resolved = candidate.resolve()
        try:
            return resolved.relative_to(storage_root)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid media path") from exc

    normalized = Path(str(file_path).replace("\\", "/"))
    if normalized.parts and normalized.parts[0] == "storage":
        normalized = Path(*normalized.parts[1:])

    resolved = (storage_root / normalized).resolve()
    try:
        resolved.relative_to(storage_root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid media path") from exc
    return resolved.relative_to(storage_root)


def _resolve_guarded_storage_path(path: str) -> tuple[Path, Path]:
    storage_root = Config.STORAGE_ROOT.resolve()
    decoded_path = unquote(path).strip()
    if not decoded_path:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该媒体文件")
    if Path(decoded_path).is_absolute() or decoded_path.startswith(("~", "/")) or re.match(r"^[A-Za-z]:", decoded_path):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该媒体文件")

    relative_path = _normalize_storage_relative_path(decoded_path)
    file_path = (storage_root / relative_path).resolve()
    return file_path, relative_path


def _build_guarded_media_url(server_url: str, file_path: str | Path, endpoint: str) -> str:
    relative_path = _normalize_storage_relative_path(file_path)
    encoded_path = quote(relative_path.as_posix(), safe="")
    return f"{server_url.rstrip('/')}/api/rag/{endpoint}?path={encoded_path}"


def _get_server_url() -> str:
    return os.getenv("SERVER_URL", "").rstrip("/")


def _scrub_response_metadata(metadata: Optional[Dict[str, Any]], server_url: str) -> Dict[str, Any]:
    scrubbed = dict(metadata or {})

    image_path = scrubbed.pop("image_path", None)
    if image_path:
        scrubbed["image_url"] = _build_guarded_media_url(server_url, image_path, "image")

    video_path = scrubbed.pop("video_path", None)
    if video_path:
        scrubbed["video_url"] = _build_guarded_media_url(server_url, video_path, "media")

    for key in list(scrubbed.keys()):
        if key.endswith("_path"):
            scrubbed.pop(key, None)

    return scrubbed


def _scrub_response_sources(sources: Optional[List[Dict[str, Any]]], server_url: str) -> List[Dict[str, Any]]:
    safe_sources: List[Dict[str, Any]] = []
    for source in sources or []:
        safe_source = dict(source or {})
        safe_source["metadata"] = _scrub_response_metadata(safe_source.get("metadata"), server_url)
        safe_sources.append(safe_source)
    return safe_sources


def _normalize_owner_for_media(owner: Optional[str]) -> str:
    if not owner:
        return ""
    try:
        return _normalize_owner(owner)
    except HTTPException:
        return ""


def _guarded_storage_file_response(path: str, current_user: dict) -> FileResponse:
    file_path, relative_path = _resolve_guarded_storage_path(path)
    owner = _normalize_owner(current_user.get("username"))

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体文件不存在")

    path_parts = relative_path.parts
    if len(path_parts) == 2:
        media_root = path_parts[0]
        if media_root not in {"images", "videos"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid media path")
        return FileResponse(str(file_path))
    if len(path_parts) < 3:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该媒体文件")

    media_root, media_owner = path_parts[0], path_parts[1]
    if media_root not in {"images", "videos"} or media_owner != owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该媒体文件")

    return FileResponse(str(file_path))


def _public_document_key(rag_system: RAGSystem, file_path: Optional[str], owner: Optional[str]) -> Optional[str]:
    if not file_path:
        return file_path
    try:
        return rag_system._make_index_key(file_path, owner)
    except Exception:
        return str(file_path)


def _public_temp_file_path(file_path: str | Path) -> str:
    temp_root = Config.TEMP_DIR.resolve()
    resolved = Path(file_path).resolve()
    try:
        return resolved.relative_to(temp_root).as_posix()
    except ValueError:
        return Path(file_path).name


def _scrub_document_detail_payload(details: Dict[str, Any], server_url: str) -> Dict[str, Any]:
    safe_details = dict(details or {})
    scrubbed_samples = []
    for sample in safe_details.get("samples") or []:
        safe_sample = dict(sample or {})
        image_path = safe_sample.pop("image_path", None)
        if image_path:
            safe_sample["image_url"] = _build_guarded_media_url(server_url, image_path, "image")
        scrubbed_samples.append(safe_sample)
    safe_details["samples"] = scrubbed_samples
    return safe_details


def _image_index_entry_to_document_info(
    index_key: str,
    record: Dict[str, Any],
    *,
    owner: Optional[str],
    server_url: str = "",
) -> Optional[Dict[str, Any]]:
    if owner is not None and record.get("owner") != owner:
        return None
    if bool(record.get("hidden_in_list")):
        return None

    image_path = record.get("file_path") or record.get("image_path")
    if not image_path:
        return None

    return {
        "file_path": index_key,
        "file_name": record.get("file_name") or Path(str(image_path)).name,
        "include_in_search": bool(record.get("include_in_search", True)),
        "chunk_count": int(record.get("chunk_count", 1) or 1),
        "image_chunk_count": 1,
        "imported_at": record.get("imported_at"),
        "summary": record.get("summary"),
        "summary_updated_at": record.get("summary_updated_at"),
        "file_size": record.get("file_size"),
        "page_count": 1,
        "hash": record.get("hash"),
        "owner": record.get("owner"),
        "doc_kind": record.get("doc_kind") or "image",
        "modality": "image",
        "image_url": _build_guarded_media_url(server_url, image_path, "image"),
    }


def _list_owner_image_documents(owner: Optional[str], server_url: str = "") -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []
    for index_key, record in _image_index.items():
        if not isinstance(record, dict):
            continue
        document = _image_index_entry_to_document_info(
            str(index_key),
            record,
            owner=owner,
            server_url=server_url,
        )
        if document is not None:
            documents.append(document)
    return documents


def _copy_local_image_into_owner_dir(
    source_path: str | Path,
    *,
    owner: str,
    preferred_name: Optional[str] = None,
) -> Path:
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(str(source))

    user_dir = _get_user_media_dir("images", owner)
    user_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize_upload_filename(preferred_name or source.name)
    destination = user_dir / safe_name
    if destination.resolve() != source.resolve():
        if destination.exists():
            suffix = hashlib.md5(str(source).encode("utf-8")).hexdigest()[:8]
            destination = user_dir / f"{destination.stem}_{suffix}{destination.suffix}"
        shutil.copy2(source, destination)
    return destination


def _index_owner_image_file(
    file_path: str | Path,
    *,
    owner: str,
    include_in_search: bool = True,
    hidden_in_list: bool = False,
    doc_kind: str = "image",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    target_path = Path(file_path)
    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(str(target_path))

    mime_type, _ = mimetypes.guess_type(str(target_path))
    mime_type = mime_type or "image/jpeg"
    with open(target_path, "rb") as img_file:
        encoded_string = base64.b64encode(img_file.read()).decode("utf-8")
    base64_data = f"data:{mime_type};base64,{encoded_string}"

    rag_system = get_rag_system()
    api_key = os.getenv("EMBEDDING_API_KEY")
    api_base = os.getenv("EMBEDDING_API_BASE")
    if api_base and not api_base.endswith("/v1"):
        api_base = f"{api_base}/v1"

    embed_model = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")
    url = f"{api_base.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": embed_model,
        "input": [base64_data],
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise Exception(f"大模型 API 响应异常: {resp.text}")

    try:
        embedding = resp.json()["data"][0]["embedding"]
    except Exception as exc:
        raise Exception(f"向量数据解析失败，模型可能不支持多模态。原始返回: {resp.text[:100]}") from exc

    with open(target_path, "rb") as image_file:
        file_hash = hashlib.md5(image_file.read()).hexdigest()

    index_key = rag_system._make_index_key(str(target_path), owner)
    existing_record = _image_index.get(index_key)
    if isinstance(existing_record, dict) and existing_record.get("hash") == file_hash:
        return {
            "status": "success",
            "message": f"图片 {target_path.name} 已存在，复用已有索引",
            "file": index_key,
            "file_path": index_key,
            "image_path": str(target_path),
            "image_url": _build_guarded_media_url("", target_path, "image"),
            "doc_kind": existing_record.get("doc_kind") or doc_kind or "image",
        }

    source_key = rag_system._make_source_key(str(target_path), owner)
    image_id = f"image_{target_path.stem}_{file_hash[:8]}"
    image_metadata = {
        "image_path": str(target_path),
        "modality": "image",
        "source": source_key,
        "owner": owner,
        "owner_username": owner,
        "file_name": target_path.name,
        "file_size": target_path.stat().st_size,
        "hash": file_hash,
    }
    if extra_metadata:
        image_metadata.update(extra_metadata)

    rag_system.vector_store.collection.add(
        embeddings=[embedding],
        documents=["[多模态图片节点]"],
        metadatas=[image_metadata],
        ids=[image_id],
    )

    index_record = {
        "file_path": str(target_path),
        "file_name": target_path.name,
        "include_in_search": bool(include_in_search),
        "imported_at": datetime.now().isoformat(),
        "file_size": int(target_path.stat().st_size),
        "hash": file_hash,
        "owner": owner,
        "modality": "image",
        "doc_kind": doc_kind or "image",
        "chunk_count": 1,
        "embedding_dim": len(embedding),
        "hidden_in_list": bool(hidden_in_list),
    }
    if extra_metadata:
        index_record.update(extra_metadata)
    _image_index[index_key] = index_record
    _save_image_index()

    return {
        "status": "success",
        "message": f"图片 {target_path.name} 已成功向量化并入库",
        "file": index_key,
        "file_path": index_key,
        "image_path": str(target_path),
        "image_url": _build_guarded_media_url("", target_path, "image"),
        "doc_kind": doc_kind or "image",
    }


def import_local_image_file(
    source_path: str | Path,
    *,
    owner: str,
    preferred_name: Optional[str] = None,
    include_in_search: bool = False,
    hidden_in_list: bool = True,
    doc_kind: str = "image",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_owner = _normalize_owner(owner)
    stored_path = _copy_local_image_into_owner_dir(
        source_path,
        owner=normalized_owner,
        preferred_name=preferred_name,
    )
    return _index_owner_image_file(
        stored_path,
        owner=normalized_owner,
        include_in_search=include_in_search,
        hidden_in_list=hidden_in_list,
        doc_kind=doc_kind,
        extra_metadata=extra_metadata,
    )


def _resolve_image_index_record(
    rag_system: RAGSystem,
    file_path: str,
    owner: Optional[str],
) -> tuple[str, Dict[str, Any]] | None:
    candidate_keys = [str(file_path or "")]
    try:
        candidate_keys.append(rag_system._make_index_key(file_path, owner))
    except Exception:
        pass

    for candidate in candidate_keys:
        record = _image_index.get(candidate)
        if isinstance(record, dict) and (owner is None or record.get("owner") == owner):
            return candidate, record

    requested = str(file_path or "").replace("\\", "/").lower().strip()
    for index_key, record in _image_index.items():
        if not isinstance(record, dict) or (owner is not None and record.get("owner") != owner):
            continue
        image_path = str(record.get("file_path") or record.get("image_path") or "")
        if requested == image_path.replace("\\", "/").lower().strip():
            return str(index_key), record

    return None


def _build_allowed_sources_for_owner(rag_system: RAGSystem, owner: Optional[str]) -> List[str]:
    if not owner:
        return []

    allowed_sources: List[str] = []
    seen: set[str] = set()
    for doc in rag_system.list_documents(owner=owner):
        if not doc.get("include_in_search", True):
            continue

        file_path = doc.get("file_path")
        if not file_path:
            continue

        for source in (
            rag_system._make_index_key(file_path, owner),
            rag_system._make_source_key(file_path, owner),
        ):
            if source and source not in seen:
                seen.add(source)
                allowed_sources.append(source)

    return allowed_sources


def _load_video_index() -> Dict[str, Dict[str, Any]]:
    """加载视频索引"""
    if Config.VIDEO_INDEX_PATH.exists():
        with open(Config.VIDEO_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_video_index():
    """保存视频索引"""
    Config.VIDEO_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(Config.VIDEO_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(_video_index, f, ensure_ascii=False, indent=2)


def _load_image_index() -> Dict[str, Dict[str, Any]]:
    """加载图片索引"""
    if Config.IMAGE_INDEX_PATH.exists():
        with open(Config.IMAGE_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_image_index():
    """保存图片索引"""
    Config.IMAGE_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(Config.IMAGE_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(_image_index, f, ensure_ascii=False, indent=2)


def split_video_into_chunks(video_path: str, chunk_duration: int = 80, temp_dir: str = None) -> List[str]:
    """
    使用 ffmpeg 将视频按指定时长分割成多个片段

    Args:
        video_path: 视频文件路径
        chunk_duration: 每个片段的时长（秒），默认 80 秒
        temp_dir: 临时目录路径，如果不指定则自动创建

    Returns:
        分割后的视频文件路径列表
    """
    # 获取视频总时长
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]

    try:
        result = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='ignore'
        )

        if result.returncode != 0:
            raise Exception(f"ffprobe 执行失败: {result.stderr}")

        duration_str = result.stdout.strip()
        if not duration_str:
            raise Exception("无法获取视频时长")

        total_seconds = float(duration_str)
        print(f"[视频分割] 视频总时长: {total_seconds:.2f}秒")

        # 如果视频时长小于等于 chunk_duration，不需要分割
        if total_seconds <= chunk_duration:
            print(f"[视频分割] 视频时长 <= {chunk_duration}秒，无需分割")
            return [video_path]

        # 创建临时目录存放分割后的视频
        if temp_dir is None:
            temp_dir = tempfile.mkdtemp(prefix="video_chunks_")
        else:
            os.makedirs(temp_dir, exist_ok=True)
            temp_dir = tempfile.mkdtemp(prefix="video_chunks_", dir=temp_dir)

        chunk_paths = []

        # 计算需要分割的片段数
        num_chunks = int(total_seconds / chunk_duration) + (1 if total_seconds % chunk_duration > 0 else 0)
        print(f"[视频分割] 将分割为 {num_chunks} 个片段")

        # 分割视频
        for i in range(num_chunks):
            start_time = i * chunk_duration
            chunk_path = os.path.join(temp_dir, f"chunk_{i:03d}.mp4")

            split_cmd = [
                "ffmpeg", "-i", video_path,
                "-ss", str(start_time),
                "-t", str(chunk_duration),
                "-c", "copy",  # 使用流复制，不重新编码，速度快
                "-avoid_negative_ts", "1",
                chunk_path,
                "-y",  # 覆盖已存在的文件
                "-loglevel", "error"
            ]

            result = subprocess.run(
                split_cmd,
                capture_output=True,
                timeout=120,
                encoding='utf-8',
                errors='ignore'
            )

            if result.returncode != 0:
                raise Exception(f"ffmpeg 分割失败: {result.stderr}")

            chunk_paths.append(chunk_path)
            print(f"[视频分割] 已生成片段 {i+1}/{num_chunks}: {chunk_path}")

        return chunk_paths

    except subprocess.TimeoutExpired:
        raise Exception("ffmpeg 执行超时")
    except Exception as e:
        raise Exception(f"视频分割失败: {str(e)}")


def get_rag_system() -> RAGSystem:
    """获取或创建RAG系统实例"""
    global _rag_system, _video_index, _image_index
    if _rag_system is None:
        # LLM 与 Embedding 允许使用不同网关/密钥。
        # RAGSystem 的 api_base/api_key 主要用于 LLM；EmbeddingClient 会优先读取 EMBEDDING_* 环境变量。
        llm_api_base = (
            os.getenv("QWEN_BASE_URL")
            or os.getenv("REMOTE_MODEL_API_BASE")
            or os.getenv("DEEPSEEK_BASE_URL")
            or Config.REMOTE_MODEL_API_BASE
            or Config.DEEPSEEK_BASE_URL
            or Config.OLLAMA_BASE_URL
        )
        api_base = llm_api_base

        llm_api_key = (
            os.getenv("QWEN_API_KEY")
            or os.getenv("REMOTE_MODEL_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or Config.REMOTE_MODEL_API_KEY
            or Config.DEEPSEEK_API_KEY
        )
        api_key = llm_api_key

        embedding_model = os.getenv("EMBEDDING_MODEL") or Config.EMBEDDING_MODEL
        llm_model = os.getenv("VISION_MODEL_ID") or os.getenv("LLM_MODEL_DEEP") or os.getenv("LLM_MODEL") or Config.LLM_MODEL_DEEP
        vector_db_path = Config.VECTOR_DB_PATH
        document_index_path = Config.DOCUMENT_INDEX_PATH

        if not api_base:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="未配置 EMBEDDING_API_BASE 或 DEEPSEEK_BASE_URL 或 OLLAMA_BASE_URL",
            )

        _rag_system = RAGSystem(
            api_base=api_base,
            api_key=api_key,
            embedding_model=embedding_model,
            llm_model=llm_model,
            vector_db_path=vector_db_path,
            document_index_path=document_index_path,
        )

        # 加载视频和图片索引
        _video_index = _load_video_index()
        _image_index = _load_image_index()

    return _rag_system


class QueryRequest(BaseModel):
    """RAG 问答请求模型"""

    question: str = Field(..., description="问题")
    top_k: int = Field(default=5, ge=1, le=20, description="检索的文档数量")
    use_enhanced_retrieval: bool = Field(default=False, description="是否使用增强检索（HyDE + 多路召回 + RRF）")
    hyde_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="HyDE 权重（0-1）")
    use_rrf: bool = Field(default=True, description="是否使用 RRF 融合")
    conversation_history: Optional[List[Dict[str, str]]] = Field(None, description="对话历史记录")


class QueryResponse(BaseModel):
    """RAG 问答响应模型"""

    question: str
    answer: str
    sources: list
    retrieval_metrics: Optional[Dict[str, Any]] = None  # 新增：检索质量指标


class ImportResponse(BaseModel):
    """文档导入响应模型"""

    status: str
    message: str
    file: Optional[str] = None
    chunk_count: Optional[int] = None


class StatsResponse(BaseModel):
    """统计信息响应模型"""

    document_count: int
    indexed_files: int
    indexed_files_list: list


class DocumentInfo(BaseModel):
    file_path: str
    file_name: str
    include_in_search: bool
    chunk_count: int
    image_chunk_count: int = 0
    imported_at: Optional[str] = None
    summary: Optional[str] = None
    summary_updated_at: Optional[str] = None
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    hash: Optional[str] = None
    owner: Optional[str] = None
    # 可选：网页来源信息（深度研究/爬取入库时写入 document_index）
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    source_domain: Optional[str] = None
    doc_kind: Optional[str] = None
    modality: Optional[str] = None
    image_url: Optional[str] = None
    source_icon_url: Optional[str] = None


class DocumentParticipationRequest(BaseModel):
    file_path: str = Field(..., description="文档路径（绝对路径）")
    include_in_search: bool = Field(..., description="是否参与检索")


class DocumentDetailResponse(DocumentInfo):
    text_chunk_count: Optional[int] = None
    image_chunk_count: Optional[int] = None
    samples: List[Dict[str, Any]]


class DocumentSummaryRequest(BaseModel):
    file_path: str = Field(..., description="文档路径")
    force_refresh: bool = Field(False, description="是否强制重新生成摘要")


class DocumentSummaryResponse(BaseModel):
    file_path: str
    summary: str
    summary_updated_at: Optional[str] = None


class ImportFromPathRequest(BaseModel):
    file_path: str = Field(..., description="文件路径（相对于项目根目录或绝对路径）")
    force_reimport: bool = Field(False, description="是否强制重新导入")
    job_id: Optional[str] = Field(None, description="进度跟踪的任务ID")


class UploadTempResponse(BaseModel):
    job_id: str
    temp_file_path: str
    filename: str


class ImportProgressResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    stage: str
    message: Optional[str] = None
    file: Optional[str] = None


class RenameDocumentRequest(BaseModel):
    file_path: str = Field(..., description="文档路径（绝对路径，前端传 file_path）")
    new_name: str = Field(..., description="新名称（仅文件名，不含路径）")


@router.post(
    "/upload_temp",
    response_model=UploadTempResponse,
    summary="上传文件到临时目录（不解析，仅用于进度展示的第一步）",
)
async def upload_temp(
    file: UploadFile = File(..., description="支持的文件类型：PDF、Word（.doc/.docx）、文本（.txt/.md）"),
    current_user: dict = Depends(get_current_user),
):
    # 支持的文件类型
    filename = _sanitize_upload_filename(file.filename)
    allowed_extensions = [".pdf", ".doc", ".docx", ".txt", ".md", ".markdown"]
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file_ext}，支持的类型: {', '.join(allowed_extensions)}",
        )

    import shutil
    import uuid

    username = current_user.get("username")
    temp_dir = _get_user_temp_dir(username)
    temp_dir.mkdir(parents=True, exist_ok=True)

    job_id = uuid.uuid4().hex
    temp_file_path = temp_dir / f"{job_id}_{filename}"
    public_temp_path = _public_temp_file_path(temp_file_path)

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        _set_import_job(
            job_id,
            username,
            status="uploaded",
            progress=0,
            stage="uploaded",
            file=public_temp_path,
        )

        return UploadTempResponse(
            job_id=job_id,
            temp_file_path=public_temp_path,
            filename=filename,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传临时文件失败: {e}",
        )


@router.post("/query", response_model=QueryResponse, summary="RAG 问答")
async def rag_query(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        rag_system = get_rag_system()
        result = rag_system.query(
            request.question,
            top_k=request.top_k,
            conversation_history=request.conversation_history,  # 传递对话历史
            use_enhanced_retrieval=request.use_enhanced_retrieval,
            hyde_weight=request.hyde_weight,
            use_rrf=request.use_rrf,
            owner=current_user.get("username"),
        )
        server_url = _get_server_url()
        result["sources"] = _scrub_response_sources(result.get("sources"), server_url)
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG 问答失败：{str(e)}",
        )


@router.post("/query_stream", summary="RAG 问答（流式输出）")
async def rag_query_stream(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """流式 RAG 问答接口，支持实时返回 LLM 生成内容"""
    try:
        rag_system = get_rag_system()

        # 先进行检索，获取相关文档
        from .system import RAGSystem

        # 复用 query 方法的检索逻辑，但不调用 LLM
        # 我们需要手动执行检索部分
        retrieval_query = rag_system._rewrite_query(request.question, request.conversation_history)
        query_embedding = rag_system.embedding_client.embed_query(retrieval_query)
        owner = current_user.get("username")
        allowed_sources = _build_allowed_sources_for_owner(rag_system, owner)

        # 执行检索
        if owner and not allowed_sources:
            retrieved_docs = []
        elif request.use_enhanced_retrieval:
            retrieved_docs = rag_system.vector_store.enhanced_hybrid_search_with_hyde(
                query=retrieval_query,
                query_embedding=query_embedding,
                top_k=request.top_k,
                distance_threshold=1.5,
                keyword_weight=0.4,
                vector_weight=0.6,
                use_hyde=True,
                hyde_weight=request.hyde_weight,
                use_rrf=request.use_rrf,
                allowed_sources=allowed_sources or None,
                rerank_enabled=True,
                rag_system=rag_system,
            )
        else:
            retrieved_docs = rag_system.vector_store.hybrid_search(
                query=retrieval_query,
                query_embedding=query_embedding,
                top_k=request.top_k,
                distance_threshold=1.5,
                keyword_weight=0.4,
                vector_weight=0.6,
                allowed_sources=allowed_sources or None
            )

        # 构建上下文（包含多模态资源路径）
        context_parts = []
        sources = []
        has_images = False
        has_videos = False

        # 获取服务器地址（用于构建完整 URL）
        server_url = _get_server_url()

        for i, doc in enumerate(retrieved_docs[:request.top_k], 1):
            content = doc.get("content", "")
            raw_metadata = dict(doc.get("metadata", {}) or {})
            metadata = _scrub_response_metadata(raw_metadata, server_url)
            source = raw_metadata.get("source", "未知来源")
            modality = raw_metadata.get("modality", "text")
            media_owner = _normalize_owner_for_media(
                raw_metadata.get("owner") or raw_metadata.get("owner_username") or owner
            )

            # 获取分数
            rerank_score = doc.get("rerank_score")
            combined_score = doc.get("combined_score", 0.0)
            score = rerank_score if rerank_score is not None else combined_score

            # 修复文档内容中的相对路径图片/视频引用
            import re
            from urllib.parse import quote

            # 根据文档的 owner 构建正确的图片路径
            # 替换 ![xxx](images/xxx.jpg) -> ![xxx](http://localhost:8000/storage/images/admin/xxx.jpg)
            if media_owner:
                # 图片替换
                def replace_image(match):
                    alt_text = match.group(1)
                    filename = match.group(2)
                    image_path = Config.STORAGE_ROOT / "images" / media_owner / filename
                    return f"![{alt_text}]({_build_guarded_media_url(server_url, image_path, 'image')})"

                content = re.sub(
                    r'!\[([^\]]*)\]\(images/([^)]+)\)',
                    replace_image,
                    content
                )

                # 视频替换（Markdown 格式）
                def replace_video_markdown(match):
                    alt_text = match.group(1)
                    filename = match.group(2)
                    video_path = Config.STORAGE_ROOT / "videos" / media_owner / filename
                    video_url = _build_guarded_media_url(server_url, video_path, "media")
                    return f'<video src="{video_url}" controls style="max-width: 100%; width: 800px; height: auto;"></video>'

                content = re.sub(
                    r'!\[([^\]]*)\]\(videos/([^)]+)\)',
                    replace_video_markdown,
                    content
                )

                # 视频替换（已有的 video 标签）
                def replace_video_tag(match):
                    filename = match.group(1)
                    video_path = Config.STORAGE_ROOT / "videos" / media_owner / filename
                    video_url = _build_guarded_media_url(server_url, video_path, "media")
                    return f'<video src="{video_url}" controls style="max-width: 100%; width: 800px; height: auto;">'

                content = re.sub(
                    r'<video\s+src="videos/([^"]+)"[^>]*>',
                    replace_video_tag,
                    content
                )
            else:
                # 兼容没有 owner 的旧数据
                def replace_image_no_owner(match):
                    alt_text = match.group(1)
                    filename = match.group(2)
                    image_path = Config.STORAGE_ROOT / "images" / filename
                    return f"![{alt_text}]({_build_guarded_media_url(server_url, image_path, 'image')})"

                content = re.sub(
                    r'!\[([^\]]*)\]\(images/([^)]+)\)',
                    replace_image_no_owner,
                    content
                )

                def replace_video_markdown_no_owner(match):
                    alt_text = match.group(1)
                    filename = match.group(2)
                    video_path = Config.STORAGE_ROOT / "videos" / filename
                    video_url = _build_guarded_media_url(server_url, video_path, "media")
                    return f'<video src="{video_url}" controls style="max-width: 100%; width: 800px; height: auto;"></video>'

                content = re.sub(
                    r'!\[([^\]]*)\]\(videos/([^)]+)\)',
                    replace_video_markdown_no_owner,
                    content
                )

                def replace_video_tag_no_owner(match):
                    filename = match.group(1)
                    video_path = Config.STORAGE_ROOT / "videos" / filename
                    video_url = _build_guarded_media_url(server_url, video_path, "media")
                    return f'<video src="{video_url}" controls style="max-width: 100%; width: 800px; height: auto;">'

                content = re.sub(
                    r'<video\s+src="videos/([^"]+)"[^>]*>',
                    replace_video_tag_no_owner,
                    content
                )

            # 根据模态类型构建上下文
            if modality == "image":
                image_path = raw_metadata.get("image_path", "")
                # 转换为 HTTP URL
                if image_path:
                    # 将本地路径转换为 URL（./storage/images/xxx.jpg -> http://localhost:8000/storage/images/xxx.jpg）
                    relative_path = str(image_path).replace("\\", "/").replace("./", "")
                    # 如果路径不是以 storage/ 开头，补全它
                    if not relative_path.startswith("storage/"):
                        if relative_path.startswith("images/"):
                            relative_path = f"storage/{relative_path}"
                        else:
                            relative_path = f"storage/images/{relative_path}"
                    image_url = _build_guarded_media_url(server_url, image_path, "image")
                    context_parts.append(f"[资料 {i}] 类型: 图片\n来源: {source}\n图片URL: {image_url}\n描述: {content}\n")
                    has_images = True
            elif modality == "video":
                video_path = raw_metadata.get("video_path", "")
                # 转换为 HTTP URL
                if video_path:
                    from urllib.parse import quote
                    relative_path = str(video_path).replace("\\", "/").replace("./", "")

                    # 如果路径不是以 storage/ 开头，补全它
                    if not relative_path.startswith("storage/"):
                        if relative_path.startswith("videos/"):
                            relative_path = f"storage/{relative_path}"
                        else:
                            relative_path = f"storage/videos/{relative_path}"

                    # 检查路径格式，如果缺少 owner 子目录则补全
                    # 格式1: storage/videos/admin/xxx.mp4 (正确)
                    # 格式2: storage/videos/xxx.mp4 (缺少owner，需要补全)
                    path_parts = relative_path.split('/')
                    if len(path_parts) == 3 and path_parts[0] == 'storage' and path_parts[1] == 'videos':
                        # 缺少 owner 子目录，补全它
                        if owner:
                            relative_path = f"storage/videos/{owner}/{path_parts[2]}"

                    # URL 编码文件名（保留路径分隔符）
                    path_parts = relative_path.split('/')
                    encoded_parts = [quote(part, safe='') for part in path_parts]
                    encoded_path = '/'.join(encoded_parts)
                    video_url = _build_guarded_media_url(server_url, video_path, "media")
                    context_parts.append(f"[资料 {i}] 类型: 视频\n来源: {source}\n视频URL: {video_url}\n描述: {content}\n")
                    has_videos = True
            else:
                context_parts.append(f"[文档 {i}] 来源: {source}\n内容: {content}\n")

            sources.append({
                "source": source,
                "content": content,
                "combined_score": combined_score,
                "rerank_score": rerank_score,
                "metadata": metadata
            })

        context = "\n".join(context_parts) if context_parts else "未找到相关参考资料"

        # 构建系统提示词（根据是否有多模态内容调整）
        system_prompt = """你是一名专业的教育知识助手。请基于【参考资料】回答用户问题。

【核心原则】
1. **优先使用参考资料**：有资料时优先基于资料回答
2. **降级使用通用知识**：资料不足时使用内部知识，并说明"*知识库中未找到特定记录...*"
3. **混合使用**：可以结合资料和专业知识

【引用规范】
使用 <cite source="文件名" score="0.85">简短概括</cite> 标注引用来源。
"""

        # 检查参考资料中是否包含图片或视频链接
        has_media_in_content = bool(re.search(r'!\[.*?\]\(http[s]?://.*?\.(jpg|jpeg|png|gif|webp)\)', context)) or \
                              bool(re.search(r'<video\s+src="http[s]?://.*?"', context))

        # 如果有图片或视频，添加多模态输出指令
        if has_images or has_videos or has_media_in_content:
            system_prompt += """
【多模态内容输出规范】（极其重要！必须严格遵守！）

**关键规则**：参考资料中如果包含图片 Markdown 语法或视频标签，你**必须原样复制**到回答中！

**图片格式**：
参考资料包含：![二叉树结构图](http://localhost:8000/api/rag/image?path=%2Fstorage%2Fimages%2Fadmin%2Fabc123.jpg)
你的回答：直接原样复制该行

**视频格式**：
参考资料包含：<video src="http://localhost:8000/api/rag/media?path=%2Fstorage%2Fvideos%2Fadmin%2Fxxx.mp4" controls style="max-width: 100%; width: 800px; height: auto;"></video>
你的回答：直接原样复制该行（包括所有 HTML 属性）

**正确示例**：
```
队列是一种先进先出的数据结构，相关视频讲解如下：

<video src="http://localhost:8000/api/rag/media?path=%2Fstorage%2Fvideos%2Fadmin%2F%E9%98%9F%E5%88%97%E8%AE%B2%E8%A7%A3.mp4" controls style="max-width: 100%; width: 800px; height: auto;"></video>

从视频中可以看到队列的基本操作...
```

**错误示例**（禁止）：
❌ 视频链接：http://...
❌ [观看视频](http://...)
❌ 修改 video 标签的任何属性

**核心要求**：
1. 图片/视频标签必须原样复制，包括所有 HTML 属性
2. 不要把标签转换成纯文本链接
3. 不要修改 URL 或样式属性
"""

        # 构建消息
        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        # 添加对话历史
        if request.conversation_history:
            for msg in request.conversation_history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        # 添加当前问题
        user_message = f"【参考资料】\n{context}\n\n【用户问题】\n{request.question}"
        messages.append({"role": "user", "content": user_message})

        # 流式生成函数
        def generate():
            # 先发送元数据（sources）
            safe_sources = _scrub_response_sources(sources, server_url)
            metadata = {
                "type": "metadata",
                "sources": safe_sources,
                "retrieval_metrics": {
                    "doc_count": len(safe_sources),
                    "max_score": max([s.get("rerank_score") or s.get("combined_score", 0) for s in safe_sources]) if safe_sources else 0,
                    "avg_score": sum([s.get("rerank_score") or s.get("combined_score", 0) for s in safe_sources]) / len(safe_sources) if safe_sources else 0,
                }
            }
            yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"

            # 流式调用 LLM
            stream_generator = rag_system._call_llm(messages=messages, stream=True)
            for chunk in stream_generator:
                data = {"type": "content", "content": chunk}
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            # 发送结束标记
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG 流式问答失败：{str(e)}",
        )


@router.post("/import", response_model=ImportResponse, summary="增量导入文档")
async def import_document(
    file: UploadFile = File(..., description="支持的文件类型：PDF、Word（.doc/.docx）、文本（.txt/.md）"),
    force_reimport: bool = False,
    current_user: dict = Depends(get_current_user),
):
    # 支持的文件类型
    filename = _sanitize_upload_filename(file.filename)
    allowed_extensions = [".pdf", ".doc", ".docx", ".txt", ".md", ".markdown"]
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file_ext}，支持的类型: {', '.join(allowed_extensions)}",
        )

    import shutil

    # 先写入临时目录
    temp_dir = Config.TEMP_DIR
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = temp_dir / filename

    # 永久目录：storage/documents/<username>/
    user_dir = Config.DOCUMENTS_ROOT / _normalize_owner(current_user.get("username"))
    user_dir.mkdir(parents=True, exist_ok=True)
    permanent_path = user_dir / filename

    try:
        # 🚀 终极方案：直接写入目标路径，彻底避开临时文件占用问题
        with open(permanent_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 显式关闭 FastAPI 文件对象
        await file.close()

        rag_system = get_rag_system()
        result = rag_system.import_document(
            str(permanent_path),
            force_reimport=force_reimport,
            owner=current_user.get("username"),
        )
        result["file"] = _public_document_key(rag_system, result.get("file"), current_user.get("username"))
        return ImportResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        import traceback

        err_type = type(e).__name__
        err_msg = str(e)
        err_trace = traceback.format_exc()
        print(f"[RAG导入][ERROR][/import/path] type={err_type} msg={err_msg}")
        print(f"[RAG导入][TRACE][/import/path]\n{err_trace}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入文档失败: [{err_type}] {err_msg}",
        )


@router.post("/import/path", response_model=ImportResponse, summary="从路径导入文档")
async def import_document_from_path(
    request: ImportFromPathRequest,
    current_user: dict = Depends(get_current_user),
):
    """从文件路径导入文档到知识库（用于 temp 上传后的第二步）"""
    try:
        file_path = request.file_path
        force_reimport = request.force_reimport
        job_id = request.job_id
        username = current_user.get("username")

        # import/path 传进来的是 temp 文件路径，这里也需要转存到永久目录
        requested_path = Path(file_path)
        if requested_path.is_absolute():
            src_path = requested_path.expanduser().resolve()
        else:
            src_path = (user_temp_dir / requested_path).resolve()
        user_temp_dir = _get_user_temp_dir(username).resolve()
        user_temp_dir.mkdir(parents=True, exist_ok=True)

        if not src_path.exists():
            raise FileNotFoundError(f"文件不存在: {src_path}")
        if not _is_path_within_root(src_path, user_temp_dir):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅允许导入当前用户临时目录中的文件")

        user_dir = Config.DOCUMENTS_ROOT / _normalize_owner(username)
        user_dir.mkdir(parents=True, exist_ok=True)
        permanent_path = user_dir / src_path.name

        # move to permanent
        import shutil
        try:
            shutil.move(str(src_path), str(permanent_path))
        except Exception:
            # 如果 move 失败（跨盘/权限），退化为 copy+delete
            shutil.copy2(str(src_path), str(permanent_path))
            try:
                src_path.unlink()
            except Exception:
                pass

        rag_system = get_rag_system()

        def progress_cb(progress: int, stage: str):
            if not job_id:
                return
            _set_import_job(
                job_id,
                username,
                status="running",
                progress=max(0, min(100, int(progress))),
                stage=stage,
            )

        if job_id:
            _set_import_job(
                job_id,
                username,
                status="running",
                progress=0,
                stage="starting",
                file=_public_document_key(rag_system, str(permanent_path), username),
            )

        try:
            result = await run_in_threadpool(
                rag_system.import_document,
                str(permanent_path),
                force_reimport,
                progress_cb,
                username,
            )
        except Exception:
            if job_id:
                _set_import_job(job_id, username, status="failed")
            raise

        if job_id:
            _set_import_job(
                job_id,
                username,
                status="completed",
                progress=100,
                stage="completed",
                file=_public_document_key(rag_system, result.get("file"), username),
                message=result.get("message"),
            )

        result["file"] = _public_document_key(rag_system, result.get("file"), username)
        return ImportResponse(**result)
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        import traceback

        err_type = type(e).__name__
        err_msg = str(e)
        err_trace = traceback.format_exc()
        print(f"[RAG导入][ERROR][/import/path] type={err_type} msg={err_msg}")
        print(f"[RAG导入][TRACE][/import/path]\n{err_trace}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入文档失败: [{err_type}] {err_msg}",
        )


@router.get("/stats", response_model=StatsResponse, summary="获取统计信息")
async def get_stats(current_user: dict = Depends(get_current_user)):
    try:
        rag_system = get_rag_system()
        owner = current_user.get("username")
        documents = rag_system.list_documents(owner=owner)
        indexed_files_list = [doc.get("file_path") for doc in documents if doc.get("file_path")]
        stats = {
            "document_count": len(indexed_files_list),
            "indexed_files": len(indexed_files_list),
            "indexed_files_list": indexed_files_list,
        }
        return StatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {str(e)}",
        )


@router.get(
    "/import/progress",
    response_model=ImportProgressResponse,
    summary="查询文档导入进度",
)
async def get_import_progress(
    job_id: str = Query(..., description="导入任务ID"),
    current_user: dict = Depends(get_current_user),
):
    job = _get_owned_import_job(job_id, current_user.get("username"))
    return ImportProgressResponse(**job)


@router.delete("/document/{file_path:path}", summary="删除文档")
async def delete_document(
    file_path: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        rag_system = get_rag_system()
        normalized_index_key = rag_system._make_index_key(file_path, current_user.get("username"))
        record = rag_system.document_index.get(normalized_index_key)

        physical_path = (record or {}).get("physical_path") or (
            file_path.split(":", 1)[1] if str(file_path).startswith("user_") and ":" in str(file_path) else file_path
        )
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定文档")
        if record.get("owner") != current_user.get("username"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该文档")

        rag_system.delete_document(physical_path, owner=current_user.get("username"))
        public_file_path = _public_document_key(rag_system, physical_path, current_user.get("username"))
        return {"status": "success", "message": f"已删除文档: {public_file_path}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档失败: {str(e)}",
        )


@router.post("/document/rename", response_model=DocumentInfo, summary="重命名文档")
async def rename_document(
    request: RenameDocumentRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        rag_system = get_rag_system()
        index_key = rag_system._make_index_key(request.file_path, current_user.get("username"))
        record = rag_system.document_index.get(index_key)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定文档")
        if record.get("owner") != current_user.get("username"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权重命名该文档")

        new_name = (request.new_name or "").strip()
        if not new_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新名称不能为空")
        if "/" in new_name or "\\" in new_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新名称不能包含路径分隔符")

        record["file_name"] = new_name
        rag_system._save_index()

        return {
            "file_path": _public_document_key(
                rag_system,
                record.get("physical_path") or request.file_path,
                current_user.get("username"),
            ),
            "file_name": record.get("file_name") or Path(request.file_path).name,
            "include_in_search": record.get("include_in_search", True),
            "chunk_count": record.get("chunk_count", 0),
            "imported_at": record.get("imported_at"),
            "summary": record.get("summary"),
            "summary_updated_at": record.get("summary_updated_at"),
            "file_size": record.get("file_size"),
            "page_count": record.get("page_count"),
            "hash": record.get("hash"),
            "owner": record.get("owner"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重命名文档失败: {str(e)}",
        )


@router.get("/documents", response_model=List[DocumentInfo], summary="列出已导入文档")
async def list_documents(current_user: dict = Depends(get_current_user)):
    try:
        rag_system = get_rag_system()
        owner = current_user.get("username")
        server_url = _get_server_url()
        raw_documents = list(rag_system.list_documents(owner=owner) or [])
        raw_documents.extend(_list_owner_image_documents(owner))
        scrubbed_documents = []
        for document in raw_documents:
            safe_document = dict(document or {})
            source_icon_path = safe_document.pop("source_icon_path", None)
            if source_icon_path:
                safe_document["source_icon_url"] = _build_guarded_media_url(server_url, source_icon_path, "image")
            scrubbed_documents.append(safe_document)
        return [
            document if isinstance(document, DocumentInfo) else DocumentInfo.model_validate(document)
            for document in scrubbed_documents
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {str(e)}",
        )


@router.get("/image", summary="读取RAG图片上下文")
async def get_rag_image(path: str = Query(..., description="图片绝对路径"), current_user: dict = Depends(get_current_user)):
    try:
        return _guarded_storage_file_response(path, current_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"读取图片失败: {str(e)}",
        )


@router.get("/media", summary="读取RAG媒体上下文")
async def get_rag_media(path: str = Query(..., description="媒体绝对路径"), current_user: dict = Depends(get_current_user)):
    try:
        return _guarded_storage_file_response(path, current_user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"读取媒体失败: {str(e)}",
        )


@router.patch(
    "/document/participation",
    response_model=DocumentInfo,
    summary="设置文档是否参与检索",
)
async def update_document_participation(
    request: DocumentParticipationRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        rag_system = get_rag_system()
        index_key = rag_system._make_index_key(request.file_path, current_user.get("username"))
        record = rag_system.document_index.get(index_key)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定文档")
        if record.get("owner") != current_user.get("username"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该文档")

        # 传入 index_key 和 owner，确保正确更新
        rag_system.update_document_participation(
            index_key,  # 使用 index_key 而不是 physical_path
            request.include_in_search,
            owner=current_user.get("username")
        )
        all_docs = rag_system.list_documents(owner=current_user.get("username"))
        for doc in all_docs:
            if doc["file_path"] == index_key:
                return doc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定文档")
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新文档状态失败: {str(e)}",
        )


@router.get(
    "/document/details",
    response_model=DocumentDetailResponse,
    summary="查看文档详情",
)
async def get_document_details(
    file_path: str = Query(..., description="文档路径"),
    current_user: dict = Depends(get_current_user),
):
    try:
        rag_system = get_rag_system()
        index_key = rag_system._make_index_key(file_path, current_user.get("username"))
        record = rag_system.document_index.get(index_key)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定文档")
        if record.get("owner") != current_user.get("username"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该文档")

        server_url = _get_server_url()
        details = dict(rag_system.get_document_details(index_key))
        details["file_path"] = index_key
        details["samples"] = [
            _scrub_response_metadata(sample, server_url)
            for sample in details.get("samples", [])
        ]
        return details
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档详情失败: {str(e)}",
        )


@router.post(
    "/document/summary",
    response_model=DocumentSummaryResponse,
    summary="查看或生成文档摘要",
)
async def get_document_summary(
    request: DocumentSummaryRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        rag_system = get_rag_system()
        username = current_user.get("username")
        
        # 前端传入的 file_path 可能是物理路径，也可能是 index_key（user_owner:path）
        # list_documents 返回的是 index_key 格式（user_owner:physical_path）
        # 使用 _make_index_key 统一处理，它会识别已经是 index_key 格式的路径
        index_key = rag_system._make_index_key(request.file_path, username)
        record = rag_system.document_index.get(index_key)
        
        if not record:
            # 如果没找到，尝试直接使用传入的路径作为 index_key（兼容性处理）
            if not str(request.file_path).startswith("user_"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"未找到指定文档: {request.file_path}",
                )
            # 如果传入的路径已经是 index_key 格式，直接使用
            index_key = str(request.file_path)
            record = rag_system.document_index.get(index_key)
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"未找到指定文档: {request.file_path}",
                )
        
        # 权限检查
        if record.get("owner") != username:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该文档摘要")

        # summarize_document 内部会处理 index_key 格式，直接传入即可
        # 传入 index_key 确保后端能正确查找文档
        summary = rag_system.summarize_document(
            index_key,  # 使用处理后的 index_key，确保一致性
            force_refresh=request.force_refresh,
            owner=username,
        )
        return summary
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        import traceback

        err_type = type(e).__name__
        err_msg = str(e)
        err_trace = traceback.format_exc()
        print(f"[RAG摘要][ERROR][/document/summary] type={err_type} msg={err_msg}")
        print(f"[RAG摘要][TRACE][/document/summary]\n{err_trace}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档摘要失败: [{err_type}] {err_msg}",
        )


class DocumentContentResponse(BaseModel):
    file_path: str
    file_name: str
    content: str
    chunks: List[Dict[str, Any]]
    total_chunks: int


@router.get(
    "/document/content",
    response_model=DocumentContentResponse,
    summary="获取文档完整内容",
)
async def get_document_content(
    file_path: str = Query(..., description="文档路径"),
    current_user: dict = Depends(get_current_user),
):
    try:
        rag_system = get_rag_system()
        username = current_user.get("username")
        index_key = rag_system._make_index_key(file_path, username)
        record = rag_system.document_index.get(index_key)
        if not record:
            image_record = _resolve_image_index_record(rag_system, file_path, username)
            if image_record is not None:
                image_index_key, image_info = image_record
                image_doc = _image_index_entry_to_document_info(
                    image_index_key,
                    image_info,
                    owner=username,
                )
                if image_doc is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
                content = f"![{image_doc['file_name']}]({image_doc['image_url']})"
                return DocumentContentResponse(
                    file_path=image_index_key,
                    file_name=image_doc["file_name"],
                    content=content,
                    chunks=[
                        {
                            "id": 0,
                            "content": content,
                            "page": 1,
                            "metadata": {
                                "modality": "image",
                                "image_url": image_doc["image_url"],
                                "image_name": image_doc["file_name"],
                            },
                        }
                    ],
                    total_chunks=1,
                )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
        if record.get("owner") != username:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该文档内容")

        physical_path = record.get("physical_path") or (
            file_path.split(":", 1)[1] if str(file_path).startswith("user_") and ":" in str(file_path) else file_path
        )

        # chunks 按 source_key 取
        source_key = record.get("source_key") or rag_system._make_source_key(physical_path, username)
        documents = rag_system.vector_store.get_documents_by_source(source_key)
        documents.sort(key=lambda x: int(x["metadata"].get("page", 0)))
        server_url = _get_server_url()
        
        content_parts = []
        chunks_info = []
        for idx, doc in enumerate(documents):
            chunk_content = doc["content"]
            page = doc["metadata"].get("page", 0)
            content_parts.append(chunk_content)
            chunks_info.append(
                {
                    "id": idx,
                    "content": chunk_content,
                    "page": page,
                    "metadata": _scrub_response_metadata(doc["metadata"], server_url),
                }
            )

        seen_linked_images = {
            str(chunk.get("metadata", {}).get("image_url") or "").strip()
            for chunk in chunks_info
            if str(chunk.get("metadata", {}).get("modality") or "").lower() == "image"
        }
        next_chunk_id = len(chunks_info)
        for linked_image in record.get("linked_images") or []:
            image_path = linked_image.get("image_path")
            if not image_path:
                continue
            image_url = linked_image.get("image_url") or _build_guarded_media_url(server_url, image_path, "image")
            if image_url in seen_linked_images:
                continue

            image_name = linked_image.get("image_name") or Path(str(image_path)).name
            chunk_content = f"![{image_name}]({image_url})"
            content_parts.append(chunk_content)
            chunks_info.append(
                {
                    "id": next_chunk_id,
                    "content": chunk_content,
                    "page": linked_image.get("page", 1),
                    "metadata": {
                        "modality": "image",
                        "image_url": image_url,
                        "image_name": image_name,
                        "image_alt": linked_image.get("image_alt"),
                        "source": linked_image.get("source"),
                    },
                }
            )
            seen_linked_images.add(image_url)
            next_chunk_id += 1

        full_content = "\n\n".join(content_parts)
        
        return DocumentContentResponse(
            file_path=index_key,
            file_name=record.get("file_name", Path(physical_path).name),
            content=full_content,
            chunks=chunks_info,
            total_chunks=len(chunks_info),
        )
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档内容失败: {str(e)}",
        )


@router.post(
    "/import_image",
    summary="导入单张图片到向量数据库",
    tags=["RAG多模态"]
)
async def import_image_to_db(
        file: UploadFile = File(..., description="请选择一张本地图片 (jpg/png)"),
        current_user: dict = Depends(get_current_user),
):
    try:
        filename = _sanitize_upload_filename(file.filename)
        # 1. 保存到永久目录 storage/images/<username>/
        user_dir = _get_user_media_dir("images", current_user.get("username"))
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / filename

        # 2. 将网页上传的图片持久化到本地硬盘
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # 3. 将图片转为 Base64 编码 (用于大模型传输)
        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "image/jpeg"
        with open(file_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
        base64_data = f"data:{mime_type};base64,{encoded_string}"

        # 4. 获取系统环境变量和 RAG 实例
        rag_system = get_rag_system()
        api_key = os.getenv("EMBEDDING_API_KEY")
        api_base = os.getenv("EMBEDDING_API_BASE")
        # 自动补全 /v1 容错机制
        if api_base and not api_base.endswith("/v1"):
            api_base = f"{api_base}/v1"

        # 优先读取环境变量中的模型名，兜底使用 gemini-embedding-2-preview
        embed_model = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")

        # 5. 调用大模型提取多模态图片向量
        url = f"{api_base.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": embed_model,
            "input": [base64_data]
        }

        # ================== 核心网络请求区 ==================
        print(f"[RAG导入] 开始处理多模态图片: {filename}")
        print(f"[Embedding] backend=multimodal_api model={embed_model} size={len(base64_data) / 1024:.2f}KB")

        # 加上 timeout=15 防止请求阻塞
        resp = requests.post(url, json=payload, headers=headers, timeout=15)

        if resp.status_code != 200:
            raise Exception(f"大模型 API 响应异常: {resp.text}")

        try:
            embedding = resp.json()["data"][0]["embedding"]
        except Exception as e:
            raise Exception(f"向量数据解析失败，模型可能不支持多模态。原始返回: {resp.text[:100]}")
        # =======================================================

        # 6. 计算文件哈希值
        file_hash = hashlib.md5(open(file_path, "rb").read()).hexdigest()

        # 7. 存入底层的 ChromaDB 向量数据库
        owner = current_user.get("username")
        source_key = rag_system._make_source_key(str(file_path), owner)
        image_id = f"image_{Path(filename).stem}_{file_hash[:8]}"

        image_metadata = {
            "image_path": str(file_path),
            "modality": "image",
            "source": source_key,
            "owner": owner,
            "owner_username": owner,
            "file_name": filename,
            "file_size": file_path.stat().st_size,
            "hash": file_hash,
        }

        rag_system.vector_store.collection.add(
            embeddings=[embedding],
            documents=["[多模态图片节点]"],
            metadatas=[image_metadata],
            ids=[image_id]
        )

        print(f"[RAG导入][Stage] image_index_save_done id={image_id}")

        # 8. 更新 image_index（记录图片元信息）
        index_key = rag_system._make_index_key(str(file_path), owner)
        _image_index[index_key] = {
            "file_path": str(file_path),
            "file_name": filename,
            "include_in_search": True,
            "imported_at": datetime.now().isoformat(),
            "file_size": int(file_path.stat().st_size),
            "hash": file_hash,
            "owner": owner,
            "modality": "image",
            "doc_kind": "image",
            "chunk_count": 1,
            "embedding_dim": len(embedding),
        }
        _save_image_index()
        print(f"[RAG导入] 图片元信息已保存到 image_index.json")

        return {
            "status": "success",
            "message": f"图片 {filename} 已成功转换为 {len(embedding)} 维向量并入库！",
            "file": index_key,
            "file_path": index_key,
            "image_url": _build_guarded_media_url("", file_path, "image"),
        }

    except Exception as e:
        print(f"[RAG导入] 图片入库失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"图片入库失败: {str(e)}")


@router.post(
    "/import_video",
    summary="导入单个视频到向量数据库",
    tags=["RAG多模态"]
)
async def import_video_to_db(
        file: UploadFile = File(..., description="请选择一个本地视频 (mp4/avi/mov/mkv)"),
        current_user: dict = Depends(get_current_user),
):
    chunk_paths = []
    temp_dir = None

    try:
        filename = _sanitize_upload_filename(file.filename)
        # 1. 保存到永久目录 storage/videos/<username>/
        user_dir = _get_user_media_dir("videos", current_user.get("username"))
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / filename

        # 2. 将网页上传的视频持久化到本地硬盘
        with open(file_path, "wb") as f:
            f.write(await file.read())

        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"[RAG导入] 视频文件: {filename}, 大小: {file_size_mb:.2f}MB")

        # 3. 使用 ffmpeg 将视频分割成 80 秒的片段（临时文件放在 temp/videos）
        chunk_duration = int(os.getenv("VIDEO_CHUNK_DURATION", "80"))
        print(f"[视频分割] 开始分割视频，每段 {chunk_duration} 秒")

        # 创建临时目录用于存放分割片段
        temp_videos_dir = _get_user_temp_dir(current_user.get("username")) / "videos"
        temp_videos_dir.mkdir(parents=True, exist_ok=True)

        chunk_paths = await run_in_threadpool(
            split_video_into_chunks,
            str(file_path),
            chunk_duration,
            str(temp_videos_dir)
        )

        if chunk_paths[0] != str(file_path):
            temp_dir = os.path.dirname(chunk_paths[0])

        print(f"[视频分割] 共生成 {len(chunk_paths)} 个片段")

        # 4. 获取系统环境变量和 RAG 实例
        rag_system = get_rag_system()
        api_key = os.getenv("EMBEDDING_API_KEY")
        api_base = os.getenv("EMBEDDING_API_BASE")
        if api_base and not api_base.endswith("/v1"):
            api_base = f"{api_base}/v1"

        embed_model = os.getenv("EMBEDDING_MODEL", "gemini-embedding-preview")
        url = f"{api_base.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # 5. 对每个视频片段进行 embedding
        embeddings_data = []
        failed_chunks = []

        for idx, chunk_path in enumerate(chunk_paths):
            print(f"[Embedding] 处理片段 {idx+1}/{len(chunk_paths)}: {os.path.basename(chunk_path)}")

            try:
                # 转为 Base64
                mime_type, _ = mimetypes.guess_type(chunk_path)
                if not mime_type or not mime_type.startswith("video/"):
                    mime_type = "video/mp4"

                with open(chunk_path, "rb") as video_file:
                    encoded_string = base64.b64encode(video_file.read()).decode('utf-8')
                base64_data = f"data:{mime_type};base64,{encoded_string}"

                chunk_size_kb = len(base64_data) / 1024
                print(f"[Embedding] 片段大小: {chunk_size_kb:.2f}KB")

                # 调用 API
                payload = {
                    "model": embed_model,
                    "input": [base64_data]
                }

                timeout_sec = int(os.getenv("VIDEO_EMBEDDING_TIMEOUT", "120"))
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout_sec)

                if resp.status_code != 200:
                    error_msg = f"片段 {idx+1} embedding 失败: {resp.text}"
                    print(f"[Embedding错误] {error_msg}")
                    failed_chunks.append({"index": idx, "error": resp.text})
                    continue

                embedding = resp.json()["data"][0]["embedding"]
                embeddings_data.append({
                    "embedding": embedding,
                    "chunk_index": idx,
                    "chunk_path": chunk_path
                })
                print(f"[Embedding] 片段 {idx+1} 完成，向量维度: {len(embedding)}")

            except Exception as e:
                error_msg = f"片段 {idx+1} 处理失败: {str(e)}"
                print(f"[Embedding错误] {error_msg}")
                failed_chunks.append({"index": idx, "error": str(e)})
                continue

        # 检查是否有成功的片段
        if not embeddings_data:
            raise Exception(f"所有视频片段 embedding 均失败。请检查 EMBEDDING_MODEL 配置是否支持视频/多模态内容。失败详情: {failed_chunks[:3]}")

        # 6. 计算文件哈希值（用于增量导入判断）
        file_hash = hashlib.md5(open(file_path, "rb").read()).hexdigest()

        # 7. 将所有片段的 embedding 存入向量数据库
        owner = current_user.get("username")
        source_key = rag_system._make_source_key(str(file_path), owner)

        for data in embeddings_data:
            chunk_id = f"video_{Path(filename).stem}_{file_hash[:8]}_chunk_{data['chunk_index']:03d}"

            rag_system.vector_store.collection.add(
                embeddings=[data["embedding"]],
                documents=[f"[多模态视频节点 - 片段 {data['chunk_index']+1}/{len(chunk_paths)}]"],
                metadatas={
                    "video_path": str(file_path),
                    "chunk_index": data['chunk_index'],
                    "total_chunks": len(chunk_paths),
                    "chunk_duration": chunk_duration,
                    "modality": "video",
                    "source": source_key,
                    "owner": owner,
                    "owner_username": owner,
                    "file_name": filename,
                    "file_size": file_size_mb,
                    "hash": file_hash,
                },
                ids=[chunk_id]
            )
            print(f"[RAG导入] 片段 {data['chunk_index']+1} 已入库，ID: {chunk_id}")

        # 8. 更新 video_index（记录视频元信息）
        index_key = rag_system._make_index_key(str(file_path), owner)
        _video_index[index_key] = {
            "file_path": str(file_path),
            "file_name": filename,
            "include_in_search": True,
            "chunk_count": len(embeddings_data),  # 成功入库的片段数
            "total_chunks": len(chunk_paths),  # 总片段数
            "failed_chunks": len(failed_chunks),  # 失败的片段数
            "imported_at": datetime.now().isoformat(),
            "file_size": int(file_path.stat().st_size),
            "hash": file_hash,
            "owner": owner,
            "modality": "video",
            "chunk_duration": chunk_duration,
        }
        _save_video_index()
        print(f"[RAG导入] 视频元信息已保存到 video_index.json")

        # 9. 清理临时文件
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"[清理] 已删除临时目录: {temp_dir}")

        success_msg = f"视频 {filename} 已分割为 {len(chunk_paths)} 个片段，成功入库 {len(embeddings_data)} 个片段"
        if failed_chunks:
            success_msg += f"，{len(failed_chunks)} 个片段失败"

        return {
            "status": "success" if not failed_chunks else "partial_success",
            "message": success_msg,
            "file_path": str(file_path),
            "chunk_count": len(embeddings_data),
            "total_chunks": len(chunk_paths),
            "failed_chunks": len(failed_chunks),
            "chunk_duration": chunk_duration
        }

    except Exception as e:
        # 清理临时文件
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

        print(f"[RAG导入] 视频入库失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"视频入库失败: {str(e)}")
