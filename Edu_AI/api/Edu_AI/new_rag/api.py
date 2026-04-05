"""
新的RAG API路由（new_rag.api）
提供知识库增量导入和RAG问答功能
"""
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, status, Query, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from urllib.parse import unquote

from .system import RAGSystem
from core.config import Config
from app.auth import get_current_user

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


def get_rag_system() -> RAGSystem:
    """获取或创建RAG系统实例"""
    global _rag_system
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
    return _rag_system


class QueryRequest(BaseModel):
    """RAG问答请求模型"""

    question: str = Field(..., description="问题")
    top_k: int = Field(default=5, ge=1, le=20, description="检索的文档数量")


class QueryResponse(BaseModel):
    """RAG问答响应模型"""

    question: str
    answer: str
    sources: list


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
    allowed_extensions = [".pdf", ".doc", ".docx", ".txt", ".md", ".markdown"]
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file_ext}，支持的类型: {', '.join(allowed_extensions)}",
        )

    import shutil
    import uuid

    temp_dir = Config.TEMP_DIR
    temp_dir.mkdir(parents=True, exist_ok=True)

    job_id = uuid.uuid4().hex
    temp_file_path = temp_dir / f"{job_id}_{file.filename}"

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        _import_jobs[job_id] = {
            "job_id": job_id,
            "status": "uploaded",
            "progress": 0,
            "stage": "uploaded",
            "file": str(temp_file_path),
        }

        return UploadTempResponse(
            job_id=job_id,
            temp_file_path=str(temp_file_path),
            filename=file.filename,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传临时文件失败: {e}",
        )


@router.post("/query", response_model=QueryResponse, summary="RAG问答")
async def rag_query(request: QueryRequest):
    try:
        rag_system = get_rag_system()
        result = rag_system.query(request.question, top_k=request.top_k)
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG问答失败: {str(e)}",
        )


@router.post("/import", response_model=ImportResponse, summary="增量导入文档")
async def import_document(
    file: UploadFile = File(..., description="支持的文件类型：PDF、Word（.doc/.docx）、文本（.txt/.md）"),
    force_reimport: bool = False,
    current_user: dict = Depends(get_current_user),
):
    # 支持的文件类型
    allowed_extensions = [".pdf", ".doc", ".docx", ".txt", ".md", ".markdown"]
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file_ext}，支持的类型: {', '.join(allowed_extensions)}",
        )

    import shutil

    # 先写入临时目录
    temp_dir = Config.TEMP_DIR
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = temp_dir / file.filename

    # 永久目录：storage/documents/<username>/
    user_dir = Config.DOCUMENTS_ROOT / (current_user.get("username") or "anonymous")
    user_dir.mkdir(parents=True, exist_ok=True)
    permanent_path = user_dir / file.filename

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 将原文件移动到永久目录（覆盖同名文件）
        shutil.move(str(temp_file_path), str(permanent_path))

        rag_system = get_rag_system()
        result = rag_system.import_document(
            str(permanent_path),
            force_reimport=force_reimport,
            owner=current_user.get("username"),
        )

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
    finally:
        # 确保临时文件被清理（永久文件不删）
        if temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception:
                pass


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

        # import/path 传进来的是 temp 文件路径，这里也需要转存到永久目录
        src_path = Path(file_path).absolute()
        if not src_path.exists():
            raise FileNotFoundError(f"文件不存在: {src_path}")

        user_dir = Config.DOCUMENTS_ROOT / (current_user.get("username") or "anonymous")
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
            _import_jobs.setdefault(job_id, {})
            _import_jobs[job_id].update(
                {
                    "job_id": job_id,
                    "status": "running",
                    "progress": max(0, min(100, int(progress))),
                    "stage": stage,
                }
            )

        if job_id:
            _import_jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "progress": 0,
                "stage": "starting",
                "file": str(permanent_path),
            }

        try:
            result = await run_in_threadpool(
                rag_system.import_document,
                str(permanent_path),
                force_reimport,
                progress_cb,
                current_user.get("username"),
            )
        except Exception:
            if job_id and job_id in _import_jobs:
                _import_jobs[job_id]["status"] = "failed"
            raise

        if job_id:
            _import_jobs[job_id].update(
                {
                    "status": "completed",
                    "progress": 100,
                    "stage": "completed",
                    "file": result.get("file"),
                    "message": result.get("message"),
                }
            )

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


@router.get("/stats", response_model=StatsResponse, summary="获取统计信息")
async def get_stats():
    try:
        rag_system = get_rag_system()
        stats = rag_system.get_stats()
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
async def get_import_progress(job_id: str = Query(..., description="导入任务ID")):
    job = _import_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到对应导入任务")
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
        return {"status": "success", "message": f"已删除文档: {physical_path}"}
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
            "file_path": record.get("physical_path") or request.file_path,
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
        return rag_system.list_documents(owner=current_user.get("username"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {str(e)}",
        )


@router.get("/image", summary="读取RAG图片上下文")
async def get_rag_image(path: str = Query(..., description="图片绝对路径"), current_user: dict = Depends(get_current_user)):
    try:
        decoded_path = unquote(path)
        file_path = Path(decoded_path).resolve()
        storage_root = Config.STORAGE_ROOT.resolve()

        try:
            file_path.relative_to(storage_root)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该图片")

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")

        owner = current_user.get("username") or ""
        parts = [p.lower() for p in file_path.parts]
        if owner and owner.lower() not in parts:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该图片")

        return FileResponse(str(file_path))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"读取图片失败: {str(e)}",
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
            if doc["file_path"] == (record.get("physical_path") or request.file_path):
                return doc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到指定文档")
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

        details = rag_system.get_document_details(record.get("physical_path") or file_path)
        return details
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
        index_key = rag_system._make_index_key(file_path, current_user.get("username"))
        record = rag_system.document_index.get(index_key)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
        if record.get("owner") != current_user.get("username"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该文档内容")

        physical_path = record.get("physical_path") or (
            file_path.split(":", 1)[1] if str(file_path).startswith("user_") and ":" in str(file_path) else file_path
        )

        # chunks 按 source_key 取
        source_key = record.get("source_key") or rag_system._make_source_key(physical_path, current_user.get("username"))
        documents = rag_system.vector_store.get_documents_by_source(source_key)
        documents.sort(key=lambda x: int(x["metadata"].get("page", 0)))
        
        content_parts = []
        chunks_info = []
        for idx, doc in enumerate(documents):
            chunk_content = doc["content"]
            page = doc["metadata"].get("page", 0)
            content_parts.append(chunk_content)
            chunks_info.append({"id": idx, "content": chunk_content, "page": page, "metadata": doc["metadata"]})
        
        full_content = "\n\n".join(content_parts)
        
        return DocumentContentResponse(
            file_path=physical_path,
            file_name=record.get("file_name", Path(physical_path).name),
            content=full_content,
            chunks=chunks_info,
            total_chunks=len(documents),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档内容失败: {str(e)}",
        )
