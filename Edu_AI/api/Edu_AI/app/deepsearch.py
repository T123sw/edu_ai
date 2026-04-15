"""
深度搜索和爬取API路由
集成EduAgent的深度搜索功能
"""
import sys
import re
import hashlib
import importlib.util
import time
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.deepsearch_loader import load_eduagent_capabilities
from core import Config
from rag_v2.api import get_rag_system
from rag_v2.document_resolver import resolve_rag_document

# 添加EduAgent到Python路径
# 从 D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\deepsearch.py 到 D:\Edu_AI_1\EduAgent
# 可能路径：D:\Edu_AI_1\EduAgent 或 D:\Edu_AI_1\Edu_AI\EduAgent
base_dir = Path(__file__).resolve().parent
candidate_paths = [
    base_dir.parent.parent.parent.parent.parent / "EduAgent",
    base_dir.parent.parent.parent.parent / "EduAgent",
]
EDU_AGENT_PATH = next((p for p in candidate_paths if p.exists()), candidate_paths[0])
if str(EDU_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(EDU_AGENT_PATH))
    print(f"[DeepSearch] 已添加EduAgent路径: {EDU_AGENT_PATH}")

# 导入EduAgent的服务
try:
    try:
        crawler_module = importlib.import_module("services.crawler_service")
        cleaner_module = importlib.import_module("services.content_cleaner")
        storage_module = importlib.import_module("services.storage_service")
        get_crawler_service = getattr(crawler_module, "get_crawler_service", None)
        ContentCleaner = getattr(cleaner_module, "ContentCleaner", None)
        get_storage_service = getattr(storage_module, "get_storage_service", None)
    except Exception:
        get_crawler_service = None
        ContentCleaner = None
        get_storage_service = None

    if get_crawler_service is None or ContentCleaner is None or get_storage_service is None:
        services_path = EDU_AGENT_PATH / "services"
        if services_path.exists() and str(services_path) not in sys.path:
            sys.path.insert(0, str(services_path))
        try:
            crawler_module = importlib.import_module("crawler_service")
            cleaner_module = importlib.import_module("content_cleaner")
            storage_module = importlib.import_module("storage_service")
            get_crawler_service = getattr(crawler_module, "get_crawler_service", None)
            ContentCleaner = getattr(cleaner_module, "ContentCleaner", None)
            get_storage_service = getattr(storage_module, "get_storage_service", None)
        except Exception:
            pass

    if get_crawler_service is None or ContentCleaner is None or get_storage_service is None:
        raise ImportError("EduAgent services not found")

    try:
        from deepsearch import deepsearch_large_llm
    except Exception:
        deepsearch_large_llm = None

    if deepsearch_large_llm is None:
        deepsearch_path = EDU_AGENT_PATH / "deepsearch.py"
        if deepsearch_path.exists():
            spec = importlib.util.spec_from_file_location("edu_agent_deepsearch", deepsearch_path)
            module = importlib.util.module_from_spec(spec) if spec else None
            if spec and module:
                spec.loader.exec_module(module)
                deepsearch_large_llm = getattr(module, "deepsearch_large_llm", None)

    if deepsearch_large_llm is None:
        raise ImportError("EduAgent deepsearch_large_llm not found")
except ImportError as e:
    print(f"警告: 无法导入EduAgent模块: {e}")
    print(f"EduAgent路径: {EDU_AGENT_PATH}")
    print(f"Python路径: {sys.path[:3]}")
    # 创建占位函数，避免启动失败
    def deepsearch_large_llm(query: str):
        raise NotImplementedError("EduAgent模块未找到")
    def get_crawler_service():
        raise NotImplementedError("EduAgent模块未找到")
    def ContentCleaner():
        raise NotImplementedError("EduAgent模块未找到")
    def get_storage_service():
        raise NotImplementedError("EduAgent模块未找到")

router = APIRouter(prefix="/agent", tags=["深度搜索"])


_capabilities = load_eduagent_capabilities(__file__)
EDU_AGENT_PATH = _capabilities.edu_agent_path


def _missing_capability(message: str):
    def _raise(*args, **kwargs):
        raise NotImplementedError(message)

    return _raise


print(f"[DeepSearch] 已添加EduAgent路径: {EDU_AGENT_PATH}")

if _capabilities.deepsearch_error:
    print(f"警告: 无法导入EduAgent深度搜索模块: {_capabilities.deepsearch_error}")
    deepsearch_large_llm = _missing_capability(
        f"EduAgent deepsearch 未配置: {_capabilities.deepsearch_error}"
    )
else:
    deepsearch_large_llm = _capabilities.deepsearch_large_llm

if _capabilities.service_error:
    print(f"警告: EduAgent 爬取服务未完全可用: {_capabilities.service_error}")
    get_crawler_service = _missing_capability(
        f"EduAgent crawler_service 未配置: {_capabilities.service_error}"
    )
    ContentCleaner = _missing_capability(
        f"EduAgent content_cleaner 未配置: {_capabilities.service_error}"
    )
    get_storage_service = _missing_capability(
        f"EduAgent storage_service 未配置: {_capabilities.service_error}"
    )
else:
    get_crawler_service = _capabilities.get_crawler_service
    ContentCleaner = _capabilities.ContentCleaner
    get_storage_service = _capabilities.get_storage_service

class DeepSearchAndCrawlRequest(BaseModel):
    """深度搜索并爬取请求"""
    query: str = Field(..., description="搜索关键词")
    max_urls: Optional[int] = Field(10, description="最多爬取的URL数量")
    crawl_timeout: Optional[int] = Field(30, description="单个URL爬取超时（秒）")
    save_to_kb: Optional[bool] = Field(True, description="是否将爬取结果永久保存到知识库并加入RAG索引")


def _safe_slug(text: str, max_len: int = 60) -> str:
    s = (text or "").strip()
    if not s:
        return "untitled"
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s[:max_len].strip()
    return s or "untitled"


def _url_hash(url: str) -> str:
    return hashlib.md5((url or "").encode("utf-8", errors="ignore")).hexdigest()[:12]


@router.post("/deepsearch-and-crawl")
async def deepsearch_and_crawl(
    request: DeepSearchAndCrawlRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    深度搜索并爬取URL内容
    
    流程：
    1. 使用深度搜索获取相关URL
    2. 使用爬虫模块爬取URL内容
    3. 清洗和格式化内容
    4. 保存结果并返回
    
    注意：此操作可能需要较长时间（5-10分钟），请耐心等待
    """
    start_time = time.time()
    username = current_user.get("username", "unknown")
    
    try:
        print(f"[API] [深度搜索] 收到请求 - 用户: {username}, query={request.query}, max_urls={request.max_urls}")
        
        # 步骤1: 深度搜索获取URL
        print(f"[API] 步骤1/4: 开始深度搜索...")
        search_start = time.time()
        search_result = deepsearch_large_llm(request.query)
        search_time = time.time() - search_start
        print(f"[API] 深度搜索完成，耗时: {search_time:.2f}秒")
        
        if not search_result or not search_result.get('links'):
            return JSONResponse(
                status_code=200,
                content={
                    "ok": False,
                    "message": "深度搜索未找到相关链接",
                    "query": request.query
                }
            )
        
        urls = search_result['links']
        
        # 限制URL数量
        if request.max_urls:
            urls = urls[:request.max_urls]
        
        # 步骤2: 爬取URL内容
        print(f"[API] 步骤2/4: 开始爬取 {len(urls)} 个URL...")
        crawl_start = time.time()
        crawler_service = get_crawler_service()
        try:
            crawl_batch = crawler_service.crawl_urls(
                urls=urls,
                query=request.query,
                max_urls=request.max_urls,
                timeout_per_url=request.crawl_timeout
            )
        except Exception as exc:
            print(f"[API] [深度搜索] 爬取失败: {exc}")
            return JSONResponse(
                status_code=200,
                content={
                    "ok": False,
                    "message": f"爬虫启动失败: {exc}",
                    "query": request.query,
                    "links": urls,
                },
            )
        crawl_time = time.time() - crawl_start
        print(f"[API] 爬取完成，耗时: {crawl_time:.2f}秒，成功: {crawl_batch.success_count}, 失败: {crawl_batch.failed_count}")
        
        # 步骤3: 清洗内容
        print(f"[API] 步骤3/4: 开始清洗内容...")
        clean_start = time.time()
        content_cleaner = ContentCleaner()
        cleaned_results = []
        
        for idx, result in enumerate(crawl_batch.results, 1):
            print(f"[API] [清洗] 处理第 {idx}/{len(crawl_batch.results)} 个结果: {result.url}")
            print(f"[API] [清洗] 状态: {result.status}, 文件路径: {result.file_path}")
            print(f"[API] [清洗] result.content原始长度: {len(result.content) if result.content else 0} 字符")
            
            if result.status == "success" and result.file_path:
                if result.content_type == "pdf":
                    # 清洗PDF内容
                    print(f"[API] [清洗] 开始清洗PDF: {result.file_path}")
                    cleaned = content_cleaner.clean_pdf_content(result.file_path)
                else:
                    # 清洗文本内容
                    print(f"[API] [清洗] 开始清洗文本: {result.file_path}")
                    cleaned = content_cleaner.clean_text_content(
                        result.content or "",
                        result.file_path
                    )
                
                # 更新结果
                if "cleaned_content" in cleaned:
                    cleaned_content = cleaned.get("cleaned_content", "")
                    cleaned_length = len(cleaned_content)
                    print(f"[API] [清洗] cleaned_content长度: {cleaned_length} 字符")
                    result.content = cleaned_content
                    result.metadata.update(cleaned.get("metadata", {}))
                    print(f"[API] [清洗] 更新后result.content长度: {len(result.content)} 字符")
                else:
                    print(f"[API] [清洗] 警告: cleaned结果中没有cleaned_content字段")
                    print(f"[API] [清洗] cleaned keys: {list(cleaned.keys())}")
            else:
                print(f"[API] [清洗] 跳过（状态: {result.status}, 文件路径: {result.file_path}）")
            
            cleaned_results.append({
                "url": result.url,
                "title": result.title,
                "content": result.content[:2000] if result.content else None,  # 限制返回长度
                "content_type": result.content_type,
                "status": result.status,
                "error_message": result.error_message,
                "metadata": result.metadata,
                "file_path": result.file_path
            })
        
        clean_time = time.time() - clean_start
        print(f"[API] 内容清洗完成，耗时: {clean_time:.2f}秒")
        
        # 步骤4: 保存结果
        print(f"[API] 步骤4/4: 保存结果...")
        storage_service = get_storage_service()
        batch_id = storage_service.save_crawl_batch(crawl_batch)

        # 额外步骤：将结果永久保存为“文档”并加入 RAG 索引，便于前端知识库展示与勾选检索
        imported_docs = []
        if request.save_to_kb:
            try:
                print(f"[API] [深度搜索] 开始入库到知识库（RAG）... user={username}")
                rag_system = get_rag_system()
                dest_dir = (Config.DOCUMENTS_ROOT / "web" / username)
                dest_dir.mkdir(parents=True, exist_ok=True)

                for r in crawl_batch.results:
                    if r.status != "success":
                        continue

                    url = r.url or ""
                    if not url:
                        continue

                    title = (r.title or "").strip() or url
                    domain = ""
                    try:
                        domain = (urlparse(url).netloc or "").replace(":", "_")
                    except Exception:
                        domain = ""
                    h = _url_hash(url)

                    # PDF：复制原文件；Text：生成 markdown
                    if r.content_type == "pdf" and r.file_path and Path(r.file_path).exists():
                        filename = f"web_{domain or 'pdf'}_{_safe_slug(title, 30)}_{h}.pdf"
                        dst = dest_dir / filename
                        if not dst.exists():
                            dst.write_bytes(Path(r.file_path).read_bytes())
                        import_path = str(dst.absolute())
                    else:
                        filename = f"web_{domain or 'page'}_{_safe_slug(title, 30)}_{h}.md"
                        dst = dest_dir / filename
                        
                        # 获取完整内容（优先使用清洗后的内容，否则从文件读取）
                        full_content = ""
                        if r.content:
                            full_content = r.content
                            print(f"[API] [入库] 使用result.content，长度: {len(full_content)} 字符")
                        elif r.file_path and Path(r.file_path).exists():
                            try:
                                with open(r.file_path, 'r', encoding='utf-8') as f:
                                    full_content = f.read()
                                    print(f"[API] [入库] 从文件读取，长度: {len(full_content)} 字符")
                            except Exception as e:
                                print(f"[API] [入库] 读取文件失败: {e}")
                                full_content = r.content or ""
                        
                        if not full_content:
                            print(f"[API] [入库] 警告: URL {url} 没有内容，跳过")
                            continue
                        
                        print(f"[API] [入库] 准备写入文件: {dst}")
                        print(f"[API] [入库] 写入内容长度: {len(full_content)} 字符")
                        print(f"[API] [入库] 内容前200字符预览: {full_content[:200]}...")
                        
                        if not dst.exists():
                            md = (
                                f"# {title}\n\n"
                                f"- 来源: {url}\n"
                                f"- 抓取方式: deepsearch+crawl\n\n"
                                f"## 正文\n\n{full_content}\n"
                            )
                            md_length = len(md)
                            print(f"[API] [入库] Markdown总长度: {md_length} 字符（正文: {len(full_content)} 字符）")
                            dst.write_text(md, encoding="utf-8")
                            written_size = dst.stat().st_size
                            print(f"[API] [入库] 文件已写入，大小: {written_size} 字节")
                        else:
                            print(f"[API] [入库] 文件已存在，跳过写入: {dst}")
                        import_path = str(dst.absolute())

                    # 导入到 RAG（owner隔离）
                    print(f"[API] [入库] 准备导入文档到RAG: {import_path}")
                    
                    # 验证文件存在且大小合理
                    if not Path(import_path).exists():
                        print(f"[API] [入库] 错误: 文件不存在: {import_path}")
                        continue
                    
                    file_size_before_import = Path(import_path).stat().st_size
                    print(f"[API] [入库] 导入前文件大小: {file_size_before_import} 字节")
                    
                    # 读取文件内容验证
                    try:
                        with open(import_path, 'r', encoding='utf-8') as f:
                            verify_content = f.read()
                            verify_length = len(verify_content)
                            print(f"[API] [入库] 文件内容验证长度: {verify_length} 字符")
                            print(f"[API] [入库] 文件内容前200字符: {verify_content[:200]}...")
                    except Exception as e:
                        print(f"[API] [入库] 文件验证失败: {e}")
                    
                    import_result = rag_system.import_document(import_path, force_reimport=False, owner=username)
                    print(f"[API] [入库] 导入结果: {import_result}")
                    print(f"[API] [入库] 状态: {import_result.get('status')}, chunk_count: {import_result.get('chunk_count', 0)}")

                    # 回写 document_index 的展示信息：让前端列表显示更友好
                    resolved_document = None
                    try:
                        resolved_document = resolve_rag_document(rag_system, import_path, owner=username)
                        rec = resolved_document.record if resolved_document is not None else None
                        if isinstance(rec, dict):
                            pretty_name = f"{title}"
                            if domain and domain not in pretty_name:
                                pretty_name = f"{pretty_name} - {domain}"
                            rec["file_name"] = _safe_slug(pretty_name, 120)
                            rec["source_url"] = url
                            rec["source_title"] = title
                            rec["source_domain"] = domain
                            rec["doc_kind"] = "web"
                            rec["source_key"] = rec.get("source_key") or resolved_document.source_key
                    except Exception as _e:
                        print(f"[API] [深度搜索] 写入document_index元数据失败: {type(_e).__name__}: {_e}")
                    imported_docs.append({
                        "file_path": import_path,
                        "index_key": resolved_document.index_key if resolved_document is not None else None,
                        "file_name": Path(import_path).name,
                        "url": url,
                    })

                # 保存 index（无论导入多少，统一保存一次）
                try:
                    rag_system._save_index()
                except Exception as _e:
                    print(f"[API] [深度搜索] 保存document_index失败: {type(_e).__name__}: {_e}")
                print(f"[API] [深度搜索] 入库完成 imported={len(imported_docs)}")
            except Exception as e:
                # 入库失败不影响主流程：仅记录并返回提示
                print(f"[API] [深度搜索] 入库失败: {type(e).__name__}: {e}")
        
        total_time = time.time() - start_time
        print(f"[API] 全部完成! 总耗时: {total_time:.2f}秒")
        
        # 返回格式与前端期望一致
        return {
            "ok": True,
            "query": request.query,
            "batch_id": batch_id,
            "total_urls": crawl_batch.total_urls,
            "success_count": crawl_batch.success_count,
            "failed_count": crawl_batch.failed_count,
            "links": urls,  # 搜索到的链接列表
            "created_at": crawl_batch.created_at.isoformat() if hasattr(crawl_batch.created_at, 'isoformat') else None,
            # 同时返回详细结果（可选，前端可以选择使用）
            "results": cleaned_results,
            # 知识库入库结果（用于前端提示/刷新）
            "saved_to_kb": bool(request.save_to_kb),
            "imported_documents": imported_docs,
        }
    
    except NotImplementedError as e:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "message": f"深度搜索功能未配置: {str(e)}",
                "query": request.query
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": f"处理失败: {str(e)}",
                "query": request.query
            }
        )


@router.get("/crawl-results/{batch_id}")
async def get_crawl_results(
    batch_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取爬取结果"""
    try:
        storage_service = get_storage_service()
        batch_result = storage_service.load_crawl_batch(batch_id)
        
        if not batch_result:
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "message": "批次不存在"
                }
            )
        
        return {
            "ok": True,
            "batch_id": batch_id,
            "query": batch_result.query,
            "total_urls": batch_result.total_urls,
            "success_count": batch_result.success_count,
            "failed_count": batch_result.failed_count,
            "created_at": batch_result.created_at.isoformat(),
            "results": [
                {
                    "url": r.url,
                    "title": r.title,
                    "content": r.content[:2000] if r.content else None,
                    "content_type": r.content_type,
                    "status": r.status,
                    "error_message": r.error_message,
                    "metadata": r.metadata,
                    "file_path": r.file_path
                }
                for r in batch_result.results
            ]
        }
    except NotImplementedError as e:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "message": f"深度搜索功能未配置: {str(e)}"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": f"获取结果失败: {str(e)}"
            }
        )


@router.get("/crawl-history")
async def get_crawl_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """获取爬取历史"""
    try:
        storage_service = get_storage_service()
        batches = storage_service.list_batches(limit=limit)
        
        return {
            "ok": True,
            "batches": batches
        }
    except NotImplementedError as e:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "message": f"深度搜索功能未配置: {str(e)}"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": f"获取历史失败: {str(e)}"
            }
        )

