"""
新的RAG模块
使用requests进行模型调用，支持知识库增量导入和RAG问答
支持混合检索：向量检索 + 关键词检索（BM25）
"""
import os
import sys
import json
import hashlib
import base64
import mimetypes
import shutil
import subprocess
import tempfile
import glob
import requests
import re
import time
import concurrent.futures
from urllib.parse import unquote, quote
from typing import List, Dict, Optional, Any, Union, Callable
from pathlib import Path
from datetime import datetime
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
import chromadb
from chromadb.config import Settings
from .core.config import Config

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except Exception:
    fitz = None  # type: ignore
    PYMUPDF_AVAILABLE = False
    print("[WARNING] PyMuPDF 未安装，PDF 解析将不可用。安装: pip install PyMuPDF")

# MinerU 命令解析与可用性检测（可选）
def _resolve_mineru_command() -> List[str]:
    """优先使用项目目录下的 MinerU CLI，其次回退到系统 PATH。"""
    base_dir = Path(Config.BASE_DIR)
    bundled_runtime_dir = base_dir / "rag_v2" / "rag-main"

    if os.name == "nt":
        candidates = [
            base_dir / ".venv" / "Scripts" / "mineru.cmd",
            base_dir / ".venv" / "Scripts" / "mineru.exe",
            bundled_runtime_dir / ".venv" / "Scripts" / "mineru.cmd",
            bundled_runtime_dir / ".venv" / "Scripts" / "mineru.exe",
        ]
    else:
        candidates = [
            base_dir / ".venv" / "bin" / "mineru",
            bundled_runtime_dir / ".venv" / "bin" / "mineru",
        ]

    for candidate in candidates:
        if candidate.exists():
            return [str(candidate)]

    resolved = shutil.which("mineru")
    if resolved:
        return [resolved]

    return ["mineru"]


def _resolve_mineru_cwd(command: List[str]) -> Optional[str]:
    if not command:
        return None

    executable = str(command[0] or "").strip().strip('"')
    if not executable:
        return None

    candidate = Path(executable).expanduser()
    if candidate.exists():
        return str(candidate.resolve().parent)

    resolved = shutil.which(executable)
    if resolved:
        return str(Path(resolved).resolve().parent)

    return None


def _check_mineru_available() -> bool:
    """检查 MinerU CLI 是否可用"""
    try:
        command = _resolve_mineru_command()
        result = subprocess.run(
            command + ["--version"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=_resolve_mineru_cwd(command)
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

MINERU_AVAILABLE = _check_mineru_available()
if MINERU_AVAILABLE:
    print("[MinerU] 检测到 MinerU CLI 已安装，将用于 PDF 解析")
else:
    print("[WARNING] MinerU CLI 未检测到，将使用 PyMuPDF 作为备选方案")

# 关键词检索支持（可选导入）
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("[WARNING] rank-bm25 未安装，关键词检索功能将不可用。安装: pip install rank-bm25")

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("[WARNING] jieba 未安装，中文分词功能将不可用。安装: pip install jieba")

# 尝试导入 Docling
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    try:
        from docling.datamodel.pipeline_options import RapidOcrOptions  # type: ignore
    except Exception:
        RapidOcrOptions = None  # type: ignore
    try:
        from docling.datamodel.pipeline_options import TableFormerMode  # type: ignore
    except Exception:
        TableFormerMode = None  # type: ignore
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    RapidOcrOptions = None  # type: ignore
    TableFormerMode = None  # type: ignore
    print("[WARNING] docling 未安装，强烈建议安装以获得最佳文档解析效果: pip install docling")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[WARNING] Pillow 未安装，图片尺寸读取功能将降级。安装: pip install pillow")



class EmbeddingClient:
    """使用 requests 调用 OpenAI-compatible embedding（默认 Gemini Embedding 2）"""

    def __init__(
        self,
        api_base: str,
        api_key: Optional[str] = None,
        model: str = "gemini-embedding-2-preview",
        backend: Optional[str] = None,
    ):
        self.backend = (backend or os.getenv("EMBEDDING_BACKEND", "gemini")).lower()
        if self.backend not in {"gemini", "openai"}:
            raise ValueError(f"当前仅支持 EMBEDDING_BACKEND=gemini/openai，收到: {self.backend}")

        base = (
            os.getenv("EMBEDDING_API_BASE")
            or api_base
            or getattr(Config, "EMBEDDING_API_BASE", "")
            or getattr(Config, "OPENROUTER_BASE_URL", "")
        ).rstrip("/")
        if base and not base.endswith("/v1"):
            base = f"{base}/v1"

        self.api_base = base
        # embedding 优先使用独立密钥，默认回落到 OpenRouter key
        self.api_key = os.getenv("EMBEDDING_API_KEY") or api_key or getattr(Config, "OPENROUTER_API_KEY", "") or "dummy-key"
        self.model = model or os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")

        self.timeout_sec = int(os.getenv("EMBEDDING_TIMEOUT_SEC", str(getattr(Config, "EMBEDDING_TIMEOUT_SEC", 120))))
        self.max_retries = int(os.getenv("EMBEDDING_MAX_RETRIES", str(getattr(Config, "EMBEDDING_MAX_RETRIES", 3))))
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", str(getattr(Config, "EMBEDDING_BATCH_SIZE", 64))))
        self.max_workers = int(os.getenv("EMBEDDING_MAX_WORKERS", str(getattr(Config, "EMBEDDING_MAX_WORKERS", 4))))
        self.gemini_dimensions = int(
            os.getenv("GEMINI_EMBEDDING_DIMENSIONS", str(getattr(Config, "GEMINI_EMBEDDING_DIMENSIONS", 0)))
        )

    def _post_embeddings_batch(self, batch_texts: List[str]) -> List[List[float]]:
        """调用 OpenAI-compatible /embeddings，支持重试与退避。"""
        if not self.api_base:
            raise ValueError("EMBEDDING_API_BASE 未配置")

        # 防空输入 + 防超长输入（Gemini embedding 对上下文长度较敏感）
        safe_texts: List[str] = []
        empty_count = 0
        for t in batch_texts:
            s = str(t or "").strip()
            if not s:
                empty_count += 1
                s = "[EMPTY_CHUNK]"
            safe_texts.append(s[:1500])
        if empty_count:
            print(f"[Embedding][Sanitize] empty_inputs={empty_count} replaced_with_placeholder")

        url = f"{self.api_base}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "dummy-key":
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: Dict[str, Any] = {
            "model": self.model,
            "input": safe_texts,
        }
        if self.backend == "gemini" and self.gemini_dimensions > 0:
            payload["dimensions"] = self.gemini_dimensions

        last_error: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=self.timeout_sec)
                if response.status_code == 200:
                    data = response.json() or {}
                    vectors = [item.get("embedding") for item in (data.get("data") or [])]
                    valid_vectors = [vec for vec in vectors if isinstance(vec, list) and len(vec) > 0]
                    if len(valid_vectors) != len(batch_texts):
                        raise Exception(f"返回数量异常: 期望={len(batch_texts)} 实际={len(valid_vectors)}")
                    return valid_vectors

                # 仅对限流/服务器错误重试；400 等请求错误直接抛出，避免把渠道打挂
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    wait_sec = min(8, 0.5 * (2 ** attempt))
                    print(
                        f"[Embedding][Retry] stage=waiting_retry attempt={attempt + 1}/{self.max_retries} "
                        f"status={response.status_code} wait={wait_sec}s"
                    )
                    time.sleep(wait_sec)
                    continue

                raise Exception(f"Embedding API错误: HTTP {response.status_code} - {response.text}")
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    wait_sec = min(8, 0.5 * (2 ** attempt))
                    print(
                        f"[Embedding][Retry] stage=waiting_retry attempt={attempt + 1}/{self.max_retries} "
                        f"reason=network wait={wait_sec}s err={last_error}"
                    )
                    time.sleep(wait_sec)
                    continue
                raise Exception(f"网络请求异常: {str(e)}")
            except Exception as e:
                # 非网络异常（尤其 400）直接失败，不重试
                raise e

        raise Exception(f"Embedding调用失败: {last_error or 'unknown error'}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """对文档列表进行 embedding（OpenAI-compatible 并发批处理）。"""
        if not texts:
            return []

        batches = [texts[i:i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        max_workers = max(1, min(self.max_workers, len(batches)))

        print(f"[Embedding] backend={self.backend} model={self.model} chunks={len(texts)} batches={len(batches)} workers={max_workers}")

        results: List[Optional[List[List[float]]]] = [None] * len(batches)

        def run_batch(batch_idx: int, batch_texts: List[str]):
            return batch_idx, self._post_embeddings_batch(batch_texts)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures_with_idx = [
                executor.submit(run_batch, batch_idx, batch_texts)
                for batch_idx, batch_texts in enumerate(batches)
            ]
            for future in concurrent.futures.as_completed(futures_with_idx):
                batch_idx, vectors = future.result()
                results[batch_idx] = vectors

        all_embeddings: List[List[float]] = []
        for batch_vectors in results:
            if not batch_vectors:
                raise Exception("部分 batch embedding 失败，未返回结果")
            all_embeddings.extend(batch_vectors)

        if len(all_embeddings) != len(texts):
            raise Exception(f"Embedding 结果总数异常，期望={len(texts)} 实际={len(all_embeddings)}")

        return all_embeddings

    def _guess_mime_type(self, image_path: str) -> str:
        mime, _ = mimetypes.guess_type(image_path)
        return mime or "image/png"

    def _encode_image_to_data_url(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            raw = f.read()
        mime = self._guess_mime_type(image_path)
        b64 = base64.b64encode(raw).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def _post_image_embedding_single(self, image_path: str, hint_text: Optional[str] = None) -> List[float]:
        """真实图片 embedding：向中转站发送 Base64 data-url 字符串。"""
        _ = hint_text  # 预留参数，保持调用兼容
        if not self.api_base:
            raise ValueError("EMBEDDING_API_BASE 未配置")

        data_url = self._encode_image_to_data_url(image_path)
        url = f"{self.api_base}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "dummy-key":
            headers["Authorization"] = f"Bearer {self.api_key}"

        # 中转站 /v1/embeddings 兼容模式：input 直接传字符串数组
        payload: Dict[str, Any] = {
            "model": self.model,
            "input": [data_url],
        }
        if self.backend == "gemini" and self.gemini_dimensions > 0:
            payload["dimensions"] = self.gemini_dimensions

        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout_sec)

                if resp.status_code == 200:
                    data = resp.json() or {}
                    item = (data.get("data") or [{}])[0]
                    emb = item.get("embedding") if isinstance(item, dict) else None
                    if isinstance(emb, list) and emb:
                        return emb
                    raise Exception("响应中未返回有效 embedding")

                # 仅对限流/服务器错误重试；400 等请求错误直接失败防止渠道被禁用
                if resp.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    wait_sec = min(8, 0.5 * (2 ** attempt))
                    print(f"[ImageEmbedding][Retry] HTTP {resp.status_code}，等待 {wait_sec}s 后重试")
                    time.sleep(wait_sec)
                    continue

                raise Exception(f"HTTP {resp.status_code}: {resp.text}")

            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    wait_sec = min(8, 0.5 * (2 ** attempt))
                    time.sleep(wait_sec)
                    continue
                raise Exception(f"网络请求异常: {str(e)}")

        raise Exception("图片 embedding 调用失败，超过最大重试次数")

    def embed_images(self, image_paths: List[str], hint_texts: Optional[List[Optional[str]]] = None) -> List[List[float]]:
        if not image_paths:
            return []

        results: List[Optional[List[float]]] = [None] * len(image_paths)

        def run_one(i: int, path: str, hint: Optional[str]):
            return i, self._post_image_embedding_single(path, hint_text=hint)

        max_workers = max(1, min(self.max_workers, len(image_paths)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(run_one, idx, path, (hint_texts[idx] if hint_texts and idx < len(hint_texts) else None))
                for idx, path in enumerate(image_paths)
            ]
            for future in concurrent.futures.as_completed(futures):
                idx, emb = future.result()
                results[idx] = emb

        if any(r is None for r in results):
            raise Exception("部分图片 embedding 失败")
        return [r for r in results if r is not None]

    def embed_query(self, text: str) -> List[float]:
        q = str(text or "").strip()
        if not q:
            q = "[EMPTY_QUERY]"
            print("[Embedding][Sanitize] empty_query replaced_with_placeholder")
        embeddings = self.embed_documents([q])
        return embeddings[0] if embeddings else []


class RerankerClient:
    """Reranker 客户端（可选启用，失败自动降级）"""

    def __init__(self):
        self.enabled = os.getenv("RAG_ENABLE_RERANKER", "0").strip().lower() in {"1", "true", "yes"}
        self.api_base = (
            os.getenv("RERANKER_API_BASE")
            or os.getenv("EMBEDDING_API_BASE")
            or getattr(Config, "EMBEDDING_API_BASE", "")
        ).rstrip("/")
        self.api_key = os.getenv("RERANKER_API_KEY") or os.getenv("EMBEDDING_API_KEY") or getattr(Config, "OPENROUTER_API_KEY", "") or ""
        self.model = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        self.timeout = int(os.getenv("RERANKER_TIMEOUT", "30"))

    def is_ready(self) -> bool:
        return self.enabled and bool(self.api_base)

    def rerank(self, query: str, documents: List[str], top_n: int) -> List[Dict[str, Any]]:
        if not self.is_ready() or not query or not documents:
            return []

        url = f"{self.api_base}/rerank"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": min(max(top_n, 1), len(documents)),
        }

        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        if response.status_code != 200:
            raise Exception(f"Reranker API错误: {response.status_code} - {response.text}")

        data = response.json() or {}

        # 兼容多种返回格式：
        # 1) {"results": [{"index": 0, "relevance_score": 0.9}, ...]}
        # 2) {"data": [{"index": 0, "score": 0.9}, ...]}
        # 3) OpenAI 风格扩展字段（部分服务）
        results = data.get("results") or data.get("data") or []

        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(results):
            if not isinstance(item, dict):
                continue

            item_index = item.get("index")
            if item_index is None:
                item_index = item.get("document_index")
            if item_index is None:
                item_index = item.get("id")

            score = item.get("relevance_score")
            if score is None:
                score = item.get("score")
            if score is None:
                score = item.get("similarity")
            if score is None:
                score = 0.0

            # 某些服务把 index 返回成字符串
            if isinstance(item_index, str) and item_index.isdigit():
                item_index = int(item_index)

            # fallback：如果服务未返回 index，按返回顺序兜底
            if item_index is None:
                item_index = idx

            if isinstance(item_index, int):
                normalized.append({"index": item_index, "score": float(score or 0.0)})

        normalized.sort(key=lambda x: x["score"], reverse=True)
        return normalized


class VectorStore:
    """向量数据库管理类（支持混合检索：向量检索 + 关键词检索）"""
    
    def __init__(
        self,
        persist_directory: Union[str, Path] = Config.VECTOR_DB_PATH,
        collection_name: str = "documents",
        embedding_client: Optional[Any] = None  # 新增：用于 HyDE 生成 embedding
    ):
        """
        初始化向量数据库
        
        Args:
            persist_directory: 持久化目录
            collection_name: 集合名称
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 创建或获取集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # BM25 索引（用于关键词检索，延迟初始化）
        self._bm25_index: Optional[Any] = None
        self._bm25_documents: List[Dict] = []  # 存储文档内容用于 BM25 检索
        self._bm25_initialized = False
        self._bm25_loaded_once = False
        self._bm25_dirty = False
        self._bm25_last_rebuild_ts = 0.0
        self._bm25_rebuild_interval_sec = float(os.getenv("BM25_REBUILD_INTERVAL_SEC", "2"))
        self._bm25_max_docs = int(os.getenv("BM25_MAX_DOCS", "120000"))
                
        # Embedding 客户端（用于 HyDE）
        self.embedding_client = embedding_client

        # Reranker（可选）
        self.reranker = RerankerClient()
        
        # 初始化BM25索引（如果可用）
        if BM25_AVAILABLE:
            self._update_bm25_index(force_full_reload=True)
    
    def add_documents( # 这里头的embedding和document是单独的参数，这个数据库的添加并不做对文档的embedding处理
        self,
        documents: List[Document],
        embeddings: List[List[float]],
        ids: Optional[List[str]] = None
    ):
        """
        添加文档到向量数据库
        
        Args:
            documents: 文档列表
            embeddings: embedding向量列表
            ids: 文档ID列表（可选，会自动生成）
        """
        if not documents or not embeddings:
            return
        
        if len(documents) != len(embeddings):
            raise ValueError("文档数量和embedding数量不匹配")
        
        # 生成ID
        if not ids:
            ids = [self._generate_doc_id(doc, idx) for idx, doc in enumerate(documents)]
        
        # 准备数据
        texts = [doc.page_content for doc in documents]
        metadatas = [self._extract_metadata(doc) for doc in documents]
        
        # 写入集合（若已存在则更新，避免 DuplicateIDError）
        self.collection.upsert(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
    
        # 标记 BM25 需要重建（延迟到查询时按需执行）
        if BM25_AVAILABLE:
            self._bm25_dirty = True
    
    def search(
        self, 
        query_embedding: List[float], 
        top_k: int = 5, 
        distance_threshold: float = 1.5,
        allowed_sources: Optional[List[str]] = None  # 允许检索的文档源列表（如果提供，只检索这些文档）
    ) -> List[Dict]:
        """
        搜索相似文档（自动去重、动态过滤）
        
        Args:
            query_embedding: 查询embedding向量
            top_k: 最大返回结果数（实际返回数可能更少，取决于相似度）
            distance_threshold: 距离阈值（L2距离，越小越相似，通常0-2之间，超过阈值的结果会被过滤）
            allowed_sources: 允许检索的文档源列表（如果提供，只检索这些文档的chunks）
            
        Returns:
            搜索结果列表（按相似度排序，已去重，只包含高质量结果）
        """
        # 如果指定了 allowed_sources，使用 where 条件过滤
        if allowed_sources and len(allowed_sources) > 0:
            # 使用 where 条件只检索指定文档的chunks
            # ChromaDB 的 where 条件支持 $in 操作符（用于多个值）
            print(f"[VectorSearch] 限制检索范围：只检索 {len(allowed_sources)} 个文档源")
            print(f"[VectorSearch] allowed_sources: {allowed_sources[:3]}...")
            
            # 去重 allowed_sources
            unique_sources = list(set(allowed_sources))
            print(f"[VectorSearch] 去重后的 unique_sources: {unique_sources[:3]}...")
            
            if len(unique_sources) == 1:
                # 单个源：直接使用 where
                where_condition = {"source": unique_sources[0]}
                print(f"[VectorSearch] 使用单个源 where 条件: {where_condition}")
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k * 5, 100),
                    where=where_condition
                )
                print(f"[VectorSearch] 查询结果数量: {len(results.get('documents', [[]])[0]) if results.get('documents') else 0}")
            else:
                # 多个源：使用 $in 操作符（如果支持）或分别查询
                try:
                    # 尝试使用 $in 操作符
                    where_condition = {"source": {"$in": unique_sources}}
                    print("[VectorSearch] 尝试使用 $in 操作符")
                    results = self.collection.query(
                        query_embeddings=[query_embedding],
                        n_results=min(top_k * 5, 100),
                        where=where_condition
                    )
                    print(f"[VectorSearch] $in 查询成功，结果数量: {len(results.get('documents', [[]])[0]) if results.get('documents') else 0}")
                except Exception as e:
                    # 如果不支持 $in，分别查询然后合并
                    print(f"[VectorSearch] $in 操作符不支持，使用分别查询方式: {e}")
                    all_results = {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
                    for source in unique_sources:
                        try:
                            where_condition = {"source": source}
                            print(f"[VectorSearch] 查询源: {source}")
                            source_results = self.collection.query(
                                query_embeddings=[query_embedding],
                                n_results=min(top_k * 5, 100),
                                where=where_condition
                            )
                            # 合并结果
                            if source_results.get("documents") and source_results["documents"][0]:
                                print(f"[VectorSearch] 源 {source} 返回 {len(source_results['documents'][0])} 个结果")
                                all_results["documents"][0].extend(source_results["documents"][0])
                                if source_results.get("metadatas"):
                                    all_results["metadatas"][0].extend(source_results["metadatas"][0])
                                if source_results.get("distances"):
                                    all_results["distances"][0].extend(source_results["distances"][0])
                                if source_results.get("ids"):
                                    all_results["ids"][0].extend(source_results["ids"][0])
                        except Exception as e2:
                            print(f"[VectorSearch] 查询源 {source} 失败: {e2}")
                            import traceback
                            traceback.print_exc()
                    results = all_results
                    print(f"[VectorSearch] 分别查询完成，总结果数量: {len(all_results.get('documents', [[]])[0])}")
        else:
            # 没有指定 allowed_sources，检索所有文档
            print(f"[VectorSearch] 未限制检索范围，检索所有文档")
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k * 5, 100)  # 检索更多候选，确保有足够的选择
            )
            print(f"[VectorSearch] 查询结果数量: {len(results.get('documents', [[]])[0]) if results.get('documents') else 0}")
        
        # 格式化结果并过滤
        documents: List[Dict] = []
        if results.get("documents") and len(results["documents"]) > 0:
            print(f"[VectorSearch] 开始格式化 {len(results['documents'][0])} 个检索结果")
            for i in range(len(results["documents"][0])):
                distance = results["distances"][0][i] if results.get("distances") else None
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                doc_source = metadata.get("source", "unknown")
                
                # 如果指定了 allowed_sources，检查 source 是否匹配（双重保险）
                if allowed_sources and len(allowed_sources) > 0:
                    if doc_source not in allowed_sources:
                        print(f"[VectorSearch] 过滤文档（source 不匹配）: {doc_source} 不在 allowed_sources 中")
                        continue
                
                # 过滤：只保留相似度足够高的结果
                # ChromaDB 使用 L2 距离，距离越小越相似
                # 对于大多数 embedding 模型，距离 < 1.0 表示非常相似，< 1.5 表示相关
                if distance is not None and distance > distance_threshold:
                    print(f"[VectorSearch] 过滤文档（距离过大）: {doc_source}, distance={distance:.3f} > {distance_threshold}")
                    continue
                
                doc = {
                    "content": results["documents"][0][i],
                    "metadata": metadata,
                    "distance": distance,
                    "id": results["ids"][0][i] if results.get("ids") else None
                }
                documents.append(doc)
        
        # 按距离排序（距离越小越相似）
        documents.sort(key=lambda x: x.get("distance", float('inf')))
        
        # 去重策略：多层去重确保结果多样性
        # 1. 按来源去重：相同来源只保留最相似的一个
        # 2. 按内容相似度去重：如果两个块的内容高度相似（重叠度>80%），只保留更相似的一个
        seen_sources = set()
        unique_documents = []
        seen_content_hashes = set()
        
        for doc in documents:
            source = doc.get("metadata", {}).get("source", "")
            content = doc.get("content", "")
            
            # 计算内容哈希（用于快速去重）
            # 使用前100个字符的哈希，快速检测内容重复
            content_preview = content[:100] if len(content) > 100 else content
            content_hash = hash(content_preview)
            
            # 检查来源是否已存在
            if source and source in seen_sources:
                continue
            
            # 检查内容是否高度相似（简单重叠检测）
            is_duplicate = False
            if content_hash in seen_content_hashes:
                # 如果哈希相同，进一步检查内容重叠度
                for existing_doc in unique_documents:
                    existing_content = existing_doc.get("content", "")
                    # 计算重叠度（简单方法：检查较短的文本有多少包含在较长的文本中）
                    shorter = min(len(content), len(existing_content))
                    if shorter > 0:
                        # 如果较短文本的大部分（>80%）都出现在较长文本中，认为是重复
                        overlap = sum(1 for i in range(min(100, shorter)) 
                                     if i < len(content) and i < len(existing_content) 
                                     and content[i] == existing_content[i])
                        if overlap / min(100, shorter) > 0.8:
                            is_duplicate = True
                            break
            
            if not is_duplicate:
                if source:
                    seen_sources.add(source)
                seen_content_hashes.add(content_hash)
                unique_documents.append(doc)
            elif not source:
                # 如果没有 source，按 id 去重
                doc_id = doc.get("id", "")
                if doc_id and doc_id not in seen_sources:
                    seen_sources.add(doc_id)
                    seen_content_hashes.add(content_hash)
                    unique_documents.append(doc)
        
        # 动态调整：根据相似度自动确定返回数量
        # 如果最相似的结果距离很小（< 0.8），说明非常相关，可以返回更多
        # 如果最相似的结果距离较大（> 1.2），说明相关性一般，只返回最相关的几个
        if unique_documents:
            best_distance = unique_documents[0].get("distance", float('inf'))
            if best_distance < 0.8:
                # 非常相关，返回更多结果（但不超过 top_k）
                return unique_documents[:min(top_k, len(unique_documents))]
            elif best_distance < 1.2:
                # 中等相关，返回中等数量
                return unique_documents[:min(max(3, top_k // 2), len(unique_documents))]
            else:
                # 相关性一般，只返回最相关的1-2个
                return unique_documents[:min(2, len(unique_documents))]
        
        return unique_documents
    
    def delete_by_source(self, source: str):
        """
        根据源文件删除文档
        
        Args:
            source: 源文件路径
        """
        # 获取所有文档
        all_data = self.collection.get()
        
        # 找到匹配的ID
        ids_to_delete: List[str] = []
        if all_data.get("metadatas"):
            for i, metadata in enumerate(all_data["metadatas"]):
                if metadata.get("source") == source:
                    ids_to_delete.append(all_data["ids"][i])
        
        # 删除
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)
            # 标记 BM25 脏数据，延迟到查询时再重建
            if BM25_AVAILABLE:
                self._bm25_dirty = True
        return len(ids_to_delete)
    
    def _tokenize_text(self, text: str) -> List[str]:
        """分词函数（支持中英文）"""
        if not text:
            return []
        
        # 如果jieba可用，使用jieba进行中文分词
        if JIEBA_AVAILABLE:
            # 混合分词：中文用jieba，英文保留单词
            tokens = []
            # 先提取英文单词
            english_words = re.findall(r'\b[a-zA-Z]+\b', text)
            tokens.extend([w.lower() for w in english_words])
            # 中文分词
            chinese_tokens = jieba.cut(text)
            tokens.extend([t.strip() for t in chinese_tokens if t.strip() and len(t.strip()) > 1])
            return tokens
        else:
            # 简单的分词：按空格和标点分割
            tokens = re.findall(r'\b\w+\b', text.lower())
            return tokens
    
    def _update_bm25_index(self, force_full_reload: bool = False):
        """更新BM25索引（按需重建，避免高频全量重建）"""
        if not BM25_AVAILABLE:
            return

        now = time.time()
        if (
            not force_full_reload
            and self._bm25_loaded_once
            and not self._bm25_dirty
            and self._bm25_initialized
        ):
            return

        if (
            not force_full_reload
            and (now - self._bm25_last_rebuild_ts) < self._bm25_rebuild_interval_sec
            and self._bm25_initialized
        ):
            self._bm25_dirty = True
            return
        
        try:
            # 从向量库获取所有文档（按需触发，而非每次增删都拉全量）
            all_data = self.collection.get()
            docs = all_data.get("documents") or []
            if not docs:
                self._bm25_documents = []
                self._bm25_index = None
                self._bm25_initialized = False
                self._bm25_loaded_once = True
                self._bm25_dirty = False
                self._bm25_last_rebuild_ts = now
                return

            if len(docs) > self._bm25_max_docs:
                print(
                    f"[BM25] 文档量 {len(docs)} 超过阈值 {self._bm25_max_docs}，"
                    "暂不重建内存 BM25（建议迁移到外部倒排引擎）"
                )
                self._bm25_initialized = False
                self._bm25_loaded_once = True
                self._bm25_dirty = True
                self._bm25_last_rebuild_ts = now
                return
            
            metadatas = all_data.get("metadatas", [])
            ids = all_data.get("ids", [])
            
            self._bm25_documents = []
            tokenized_corpus = []
            
            for i, doc_text in enumerate(docs):
                metadata = metadatas[i] if i < len(metadatas) else {}
                doc_id = ids[i] if i < len(ids) else None

                # 多模态：图片 chunk 不进入 BM25，避免关键词污染
                modality = str((metadata or {}).get("modality", "text")).lower()
                if modality == "image":
                    continue

                self._bm25_documents.append({
                    "content": doc_text,
                    "metadata": metadata,
                    "id": doc_id
                })

                tokens = self._tokenize_text(doc_text)
                tokenized_corpus.append(tokens)
            
            if tokenized_corpus:
                self._bm25_index = BM25Okapi(tokenized_corpus)
                self._bm25_initialized = True
                self._bm25_loaded_once = True
                self._bm25_dirty = False
                self._bm25_last_rebuild_ts = now
                print(f"[BM25] 索引已更新，包含 {len(tokenized_corpus)} 个文档")
            else:
                self._bm25_index = None
                self._bm25_initialized = False
                self._bm25_loaded_once = True
                self._bm25_dirty = False
                self._bm25_last_rebuild_ts = now
        except Exception as e:
            print(f"[BM25] 更新索引失败: {e}")
            self._bm25_initialized = False
    
    def keyword_search(
        self, 
        query: str, 
        top_k: int = 5,
        allowed_sources: Optional[List[str]] = None  # 允许检索的文档源列表（如果提供，只检索这些文档）
    ) -> List[Dict]:
        """
        关键词检索（BM25）
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            allowed_sources: 允许检索的文档源列表（如果提供，只检索这些文档的chunks）
            
        Returns:
            搜索结果列表（按BM25分数排序）
        """
        if not BM25_AVAILABLE:
            print(f"[BM25] 关键词检索不可用：rank-bm25 未安装")
            return []
        
        if not self._bm25_initialized:
            print(f"[BM25] 索引未初始化，尝试初始化...")
            self._update_bm25_index()
            if not self._bm25_initialized:
                print(f"[BM25] 索引初始化失败，关键词检索不可用")
                return []
        
        try:
            # 分词查询
            query_tokens = self._tokenize_text(query)
            if not query_tokens:
                return []
            
            # BM25检索
            scores = self._bm25_index.get_scores(query_tokens)
            
            # 获取top_k结果
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k * 2]  # 多取一些用于后续过滤
            
            results = []
            for idx in top_indices:
                if scores[idx] > 0:  # 只返回有分数的结果
                    doc = self._bm25_documents[idx].copy()
                    doc_source = doc.get("metadata", {}).get("source", "")
                    
                    # 如果指定了 allowed_sources，只返回匹配的文档
                    if allowed_sources and len(allowed_sources) > 0:
                        if doc_source not in allowed_sources:
                            continue
                    
                    doc["bm25_score"] = scores[idx]
                    results.append(doc)
            
            if allowed_sources and len(allowed_sources) > 0:
                print(f"[BM25] 关键词检索完成，限制在 {len(allowed_sources)} 个源中，返回 {len(results)} 个结果")
            else:
                print(f"[BM25] 关键词检索完成，返回 {len(results)} 个结果")
            
            return results
        except Exception as e:
            print(f"[BM25] 关键词检索失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def hybrid_search(
        self, 
        query: str,
        query_embedding: List[float],
        top_k: int = 5,
        distance_threshold: float = 1.5,
        keyword_weight: float = 0.4,  # 关键词检索权重（0-1），默认40%
        vector_weight: float = 0.6,    # 向量检索权重（0-1），默认60%
        allowed_sources: Optional[List[str]] = None  # 允许检索的文档源列表（如果提供，只检索这些文档）
    ) -> List[Dict]:
        """
        混合检索：结合向量检索和关键词检索
        
        Args:
            query: 查询文本（用于关键词检索）
            query_embedding: 查询embedding向量（用于向量检索）
            top_k: 返回结果数量
            distance_threshold: 向量检索距离阈值
            keyword_weight: 关键词检索权重（0-1），默认0.4（40%）
            vector_weight: 向量检索权重（0-1），默认0.6（60%）
            allowed_sources: 允许检索的文档源列表（如果提供，只检索这些文档的chunks）
            
        Returns:
            融合后的搜索结果列表
        """
        # 1. 向量检索（如果指定了 allowed_sources，只检索这些文档）
        vector_results = self.search(
            query_embedding, 
            top_k=top_k * 3, 
            distance_threshold=distance_threshold,
            allowed_sources=allowed_sources
        )
        
        # 2. 关键词检索（如果可用，也只检索 allowed_sources 中的文档）
        keyword_results = self.keyword_search(
            query, 
            top_k=top_k * 3,
            allowed_sources=allowed_sources
        ) if BM25_AVAILABLE else []
        
        # 如果关键词检索不可用，直接返回向量检索结果
        if not keyword_results:
            print(f"[Hybrid] 关键词检索不可用，仅使用向量检索: {len(vector_results)} 个结果")
            return vector_results
        
        # 3. 融合结果
        # 构建文档ID到结果的映射
        doc_scores: Dict[str, Dict] = {}
        
        # 处理向量检索结果
        max_vector_score = 1.0
        if vector_results:
            # 将距离转换为相似度分数（距离越小，分数越高）
            min_distance = min(doc.get("distance", 1.5) for doc in vector_results)
            max_distance = max(doc.get("distance", 0.0) for doc in vector_results)
            score_range = max_distance - min_distance if max_distance > min_distance else 1.0
            
            for doc in vector_results:
                doc_id = doc.get("id") or doc.get("metadata", {}).get("source", "")
                distance = doc.get("distance", 1.5)
                # 将距离转换为相似度分数（0-1）
                if score_range > 0:
                    similarity_score = 1.0 - ((distance - min_distance) / score_range)
                else:
                    similarity_score = 1.0 - distance / 1.5  # 归一化
                similarity_score = max(0.0, min(1.0, similarity_score))
                
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "doc": doc,
                        "vector_score": 0.0,
                        "keyword_score": 0.0,
                        "combined_score": 0.0
                    }
                doc_scores[doc_id]["vector_score"] = similarity_score
                max_vector_score = max(max_vector_score, similarity_score)
        
        # 处理关键词检索结果
        max_keyword_score = 1.0
        if keyword_results:
            max_keyword_score = max(doc.get("bm25_score", 0.0) for doc in keyword_results)
            if max_keyword_score == 0:
                max_keyword_score = 1.0
            
            for doc in keyword_results:
                doc_id = doc.get("id") or doc.get("metadata", {}).get("source", "")
                bm25_score = doc.get("bm25_score", 0.0)
                # 归一化BM25分数（0-1）
                normalized_score = bm25_score / max_keyword_score if max_keyword_score > 0 else 0.0
                
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "doc": doc,
                        "vector_score": 0.0,
                        "keyword_score": 0.0,
                        "combined_score": 0.0
                    }
                doc_scores[doc_id]["keyword_score"] = normalized_score
        
        # 计算融合分数
        for doc_id, scores in doc_scores.items():
            vector_s = scores["vector_score"]
            keyword_s = scores["keyword_score"]
            # 加权融合
            combined = (vector_s * vector_weight) + (keyword_s * keyword_weight)
            scores["combined_score"] = combined
        
        # 按融合分数排序
        sorted_results = sorted(
            doc_scores.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        # 返回top_k结果（先按融合分数粗排）
        final_results = []
        for item in sorted_results[: max(top_k * 4, top_k)]:
            doc = item["doc"].copy()
            doc["combined_score"] = item["combined_score"]
            doc["vector_score"] = item["vector_score"]
            doc["keyword_score"] = item["keyword_score"]
            final_results.append(doc)

        # 可选第二阶段：Reranker 精排
        if self.reranker.is_ready() and final_results:
            print(f"[Reranker] 开始重排... 输入文档数={len(final_results)}, top_n={min(top_k, len(final_results))}")
            rerank_start = time.time()
            try:
                rerank_input = [doc.get("content", "") for doc in final_results]
                rerank_top_n = min(top_k, len(rerank_input))
                hybrid_top_before = []
                for doc in final_results[:top_k]:
                    src = str(doc.get("metadata", {}).get("source", ""))
                    hybrid_top_before.append(src)
        
                print(f"[Reranker] 调用 API...")
                reranked = self.reranker.rerank(query=query, documents=rerank_input, top_n=rerank_top_n)
                print(f"[Reranker] API 返回结果数={len(reranked) if reranked else 0}")
                
                if reranked:
                    reranked_docs: List[Dict] = []
                    for item in reranked:
                        idx = item.get("index")
                        score = item.get("score", 0.0)
                        print(f"[Reranker] 文档索引={idx}, 分数={score:.4f}")
                        if isinstance(idx, int) and 0 <= idx < len(final_results):
                            doc = final_results[idx].copy()
                            doc["rerank_score"] = score
                            reranked_docs.append(doc)
                    if reranked_docs:
                        final_results = reranked_docs[:top_k]
                                
                        # ========== 任务一：检索质量量化（Retrieval Confidence Metric） ==========
                        # 计算检索置信度指标
                        rerank_scores = [doc.get("rerank_score", 0.0) for doc in final_results]
                        if rerank_scores:
                            max_score = max(rerank_scores)
                            avg_score = sum(rerank_scores) / len(rerank_scores)
                                    
                            # 根据最高分给出置信度评级
                            if max_score > 0.7:
                                confidence_level = "High"
                            elif max_score >= 0.4:
                                confidence_level = "Medium"
                            else:
                                confidence_level = "Low"
                                    
                            # 将指标存储到第一个文档的 metadata 中（后续会提取到返回结果）
                            retrieval_metrics = {
                                "max_score": round(max_score, 4),
                                "avg_score": round(avg_score, 4),
                                "confidence_level": confidence_level,
                                "doc_count": len(final_results),
                                "rerank_enabled": True
                            }
                            # 存储在第一个文档中，便于后续提取
                            if final_results:
                                final_results[0]["retrieval_metrics"] = retrieval_metrics
                        # =========================================================================
                                
                        rerank_ms = int((time.time() - rerank_start) * 1000)
                        hybrid_top1 = hybrid_top_before[0] if hybrid_top_before else ""
                        rerank_top1 = str(final_results[0].get("metadata", {}).get("source", "")) if final_results else ""
                        top1_changed = bool(hybrid_top1 and rerank_top1 and hybrid_top1 != rerank_top1)
                        print(
                            f"[RerankerMetrics] enabled=1 success=1 latency_ms={rerank_ms} "
                            f"input={len(rerank_input)} output={len(final_results)} top1_changed={int(top1_changed)}"
                        )
                        print(f"[Reranker] 重排成功，输入：{len(rerank_input)}，输出：{len(final_results)}")
                    else:
                        final_results = final_results[:top_k]
                        rerank_ms = int((time.time() - rerank_start) * 1000)
                        print(
                            f"[RerankerMetrics] enabled=1 success=0 latency_ms={rerank_ms} "
                            f"input={len(rerank_input)} output={len(final_results)} reason=empty_indexed_result"
                        )
                        print("[Reranker] 返回为空索引结果，降级使用 Hybrid 结果")
                else:
                    final_results = final_results[:top_k]
                    rerank_ms = int((time.time() - rerank_start) * 1000)
                    print(
                        f"[RerankerMetrics] enabled=1 success=0 latency_ms={rerank_ms} "
                        f"input={len(rerank_input)} output={len(final_results)} reason=empty_result"
                    )
                    print("[Reranker] 返回空结果，降级使用 Hybrid 结果")
            except Exception as e:
                final_results = final_results[:top_k]
                rerank_ms = int((time.time() - rerank_start) * 1000)
                print(
                    f"[RerankerMetrics] enabled=1 success=0 latency_ms={rerank_ms} "
                    f"input={len(final_results)} output={len(final_results)} reason=exception"
                )
                print(f"[Reranker] 重排失败，降级使用 Hybrid 结果：{e}")
        else:
            final_results = final_results[:top_k]
            if not self.reranker.is_ready():
                print("[RerankerMetrics] enabled=0 reason=not_ready")
            
            # ========== 任务一（降级方案）：未开启 Rerank 时使用向量检索得分 ==========
            # 如果未开启 Rerank，使用向量检索的相似度得分计算置信度
            vector_scores = [doc.get("vector_score", 0.0) for doc in final_results]
            if vector_scores:
                max_score = max(vector_scores)
                avg_score = sum(vector_scores) / len(vector_scores) if vector_scores else 0.0
                
                # 根据最高分给出置信度评级
                if max_score > 0.7:
                    confidence_level = "High"
                elif max_score >= 0.4:
                    confidence_level = "Medium"
                else:
                    confidence_level = "Low"
                
                retrieval_metrics = {
                    "max_score": round(max_score, 4),
                    "avg_score": round(avg_score, 4),
                    "confidence_level": confidence_level,
                    "doc_count": len(final_results),
                    "rerank_enabled": False
                }
                if final_results:
                    final_results[0]["retrieval_metrics"] = retrieval_metrics
            # =========================================================================

        print(f"[Hybrid] 向量检索：{len(vector_results)} 个结果，关键词检索：{len(keyword_results)} 个结果，融合后：{len(final_results)} 个结果")
        
        return final_results
    
    def enhanced_hybrid_search_with_hyde(
        self,
        query: str,
        query_embedding: List[float],
        top_k: int = 5,
        distance_threshold: float = 1.5,
        keyword_weight: float = 0.4,
        vector_weight: float = 0.6,
        use_hyde: bool = True,
        hyde_weight: float = 0.5,
        use_rrf: bool = True,
        rrf_k: int = 60,
        allowed_sources: Optional[List[str]] = None,
        rerank_enabled: bool = True,
        rag_system: Optional[Any] = None,  # 新增：传入 RAGSystem 实例用于调用 LLM
    ) -> List[Dict]:
        """
        增强版混合检索：HyDE + 多路召回 + RRF 融合 + Rerank 精排
        
        Args:
            query: 查询文本
            query_embedding: 原问题的 embedding 向量
            top_k: 返回结果数量
            distance_threshold: 向量检索距离阈值
            keyword_weight: 关键词检索权重（传统混合检索使用）
            vector_weight: 向量检索权重（传统混合检索使用）
            use_hyde: 是否启用 HyDE 策略
            hyde_weight: HyDE 结果权重（RRF 融合时使用）
            use_rrf: 是否使用 RRF 融合（否则使用加权融合）
            rrf_k: RRF 公式中的 k 值（默认 60）
            allowed_sources: 允许检索的文档源列表
            rerank_enabled: 是否启用 Rerank 精排
            rag_system: RAGSystem 实例（用于调用 _call_llm 生成 HyDE 答案）
            
        Returns:
            融合后的搜索结果列表
        """
        recall_results: Dict[str, List[Dict]] = {}
        
        # ===== 第一路：原问题向量检索 =====
        vector_results = self.search(
            query_embedding,
            top_k=top_k * 5,
            distance_threshold=distance_threshold,
            allowed_sources=allowed_sources
        )
        recall_results["original_vector"] = vector_results
        print(f"[EnhancedHybrid] 原问题向量检索：{len(vector_results)} 个结果")
        
        # ===== 第二路：HyDE 假设性答案向量检索 =====
        if use_hyde and rag_system:
            # 使用 RAGSystem 的 LLM 能力生成假设性答案
            hypothetical_doc = rag_system._generate_hypothetical_answer(query)
            if hypothetical_doc:
                hyde_embedding = self.embedding_client.embed_query(hypothetical_doc)
                hyde_results = self.search(
                    hyde_embedding,
                    top_k=top_k * 5,
                    distance_threshold=distance_threshold,
                    allowed_sources=allowed_sources
                )
                recall_results["hyde_vector"] = hyde_results
                print(f"[EnhancedHybrid] HyDE 假设性答案检索：{len(hyde_results)} 个结果")
            else:
                print("[EnhancedHybrid] HyDE 生成失败，跳过此路召回")
        elif use_hyde:
            print("[EnhancedHybrid] 未提供 rag_system，无法使用 HyDE")
        
        # ===== 第三路：BM25 关键词检索 =====
        if BM25_AVAILABLE:
            keyword_results = self.keyword_search(
                query,
                top_k=top_k * 5,
                allowed_sources=allowed_sources
            )
            recall_results["bm25"] = keyword_results
            print(f"[EnhancedHybrid] BM25 关键词检索：{len(keyword_results)} 个结果")
        else:
            print("[EnhancedHybrid] BM25 不可用，跳过关键词检索")
        
        
        # ===== 结果融合 =====
        if use_rrf:
            # RRF（Reciprocal Rank Fusion）融合
            # 为不同路设置不同权重
            weights = {
                "original_vector": 1.0,  # 原问题向量
                "hyde_vector": hyde_weight if use_hyde else 0.0,  # HyDE 向量
                "bm25": 1.0 if BM25_AVAILABLE else 0.0,  # BM25
            }
            
            merged_docs = self._weighted_reciprocal_rank_fusion(
                recall_results,
                weights=weights,
                k=rrf_k
            )
            print(f"[EnhancedHybrid] RRF 融合后：{len(merged_docs)} 个结果")
        else:
            # 传统加权融合（兼容旧模式）
            merged_docs = self._traditional_weighted_fusion(
                vector_results,
                recall_results.get("bm25", []),
                top_k=top_k * 4,
                keyword_weight=keyword_weight,
                vector_weight=vector_weight
            )
            print(f"[EnhancedHybrid] 加权融合后：{len(merged_docs)} 个结果")
        
        # ===== Rerank 精排 =====
        final_results = merged_docs
        if rerank_enabled and self.reranker.is_ready() and merged_docs:
            rerank_start = time.time()
            try:
                rerank_input = [doc.get("content", "") for doc in merged_docs]
                rerank_top_n = min(top_k, len(rerank_input))
                
                reranked = self.reranker.rerank(
                    query=query,
                    documents=rerank_input,
                    top_n=rerank_top_n
                )
                
                if reranked:
                    # 将 rerank 结果映射回原始文档
                    reranked_docs: List[Dict] = []
                    for item in reranked:
                        idx = item.get("index")
                        if isinstance(idx, int) and 0 <= idx < len(merged_docs):
                            doc = merged_docs[idx].copy()
                            doc["rerank_score"] = item.get("score", 0.0)
                            reranked_docs.append(doc)
                    
                    if reranked_docs:
                        final_results = reranked_docs[:top_k]
                        rerank_ms = int((time.time() - rerank_start) * 1000)
                        print(f"[Reranker] HyDE 增强检索 + 重排成功，输入:{len(rerank_input)}, 输出:{len(final_results)}, 耗时:{rerank_ms}ms")
                    else:
                        final_results = merged_docs[:top_k]
                        print("[Reranker] Rerank 返回空结果，降级使用融合结果")
                else:
                    final_results = merged_docs[:top_k]
                    print("[Reranker] Rerank 返回空列表，降级使用融合结果")
            except Exception as e:
                final_results = merged_docs[:top_k]
                print(f"[Reranker] Rerank 异常，降级使用融合结果：{e}")
        else:
            final_results = merged_docs[:top_k]
            if not self.reranker.is_ready():
                print("[EnhancedHybrid] Reranker 未启用，直接返回 Top-K")
        
        # 截取最终的 top_k
        return final_results[:top_k]
    
    def _weighted_reciprocal_rank_fusion(
        self,
        recall_results: Dict[str, List[Dict]],
        weights: Dict[str, float] = None,
        k: int = 60
    ) -> List[Dict]:
        """
        加权 RRF（Weighted Reciprocal Rank Fusion）
        
        公式：score(d) = Σ w_i / (k + rank_i(d))
        其中 w_i 是第 i 路召回的权重
        
        Args:
            recall_results: 各路召回结果 {strategy_name: [docs]}
            weights: 各路权重 {strategy_name: weight}
            k: RRF 公式中的常数（默认 60）
            
        Returns:
            融合后的结果列表
        """
        if not weights:
            weights = {name: 1.0 for name in recall_results.keys()}
        
        doc_scores: Dict[str, Dict] = {}
        
        # 为每个召回结果计算加权 RRF 分数
        for strategy_name, docs in recall_results.items():
            weight = weights.get(strategy_name, 1.0)
            if weight <= 0:
                continue  # 权重为 0 的路径不参与融合
            
            for rank, doc in enumerate(docs):
                doc_id = doc.get("id") or doc.get("metadata", {}).get("source", "")
                
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "doc": doc,
                        "rrf_score": 0.0,
                        "strategies": set(),
                        "strategy_scores": {}
                    }
                
                # 加权 RRF 公式
                rrf_score = weight / (k + rank + 1)  # rank 从 0 开始
                doc_scores[doc_id]["rrf_score"] += rrf_score
                doc_scores[doc_id]["strategies"].add(strategy_name)
                doc_scores[doc_id]["strategy_scores"][strategy_name] = 1.0 / (k + rank + 1)
        
        # 按加权 RRF 分数排序
        sorted_docs = sorted(
            doc_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )
        
        # 返回融合后的结果
        final_results = []
        for item in sorted_docs:
            doc = item["doc"].copy()
            doc["rrf_score"] = item["rrf_score"]
            doc["recall_strategies"] = list(item["strategies"])
            doc["strategy_scores"] = item["strategy_scores"]
            final_results.append(doc)
        
        return final_results
    
    def _traditional_weighted_fusion(
        self,
        vector_results: List[Dict],
        keyword_results: List[Dict],
        top_k: int,
        keyword_weight: float = 0.4,
        vector_weight: float = 0.6
    ) -> List[Dict]:
        """
        传统加权融合（兼容旧的 hybrid_search 逻辑）
        """
        doc_scores: Dict[str, Dict] = {}
        
        # 处理向量检索结果
        max_vector_score = 1.0
        if vector_results:
            min_distance = min(doc.get("distance", 1.5) for doc in vector_results)
            max_distance = max(doc.get("distance", 0.0) for doc in vector_results)
            score_range = max_distance - min_distance if max_distance > min_distance else 1.0
            
            for doc in vector_results:
                doc_id = doc.get("id") or doc.get("metadata", {}).get("source", "")
                distance = doc.get("distance", 1.5)
                
                if score_range > 0:
                    similarity_score = 1.0 - ((distance - min_distance) / score_range)
                else:
                    similarity_score = 1.0 - distance / 1.5
                similarity_score = max(0.0, min(1.0, similarity_score))
                
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "doc": doc,
                        "vector_score": 0.0,
                        "keyword_score": 0.0,
                        "combined_score": 0.0
                    }
                doc_scores[doc_id]["vector_score"] = similarity_score
                max_vector_score = max(max_vector_score, similarity_score)
        
        # 处理关键词检索结果
        max_keyword_score = 1.0
        if keyword_results:
            max_keyword_score = max(doc.get("bm25_score", 0.0) for doc in keyword_results)
            if max_keyword_score == 0:
                max_keyword_score = 1.0
            
            for doc in keyword_results:
                doc_id = doc.get("id") or doc.get("metadata", {}).get("source", "")
                bm25_score = doc.get("bm25_score", 0.0)
                normalized_score = bm25_score / max_keyword_score if max_keyword_score > 0 else 0.0
                
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "doc": doc,
                        "vector_score": 0.0,
                        "keyword_score": 0.0,
                        "combined_score": 0.0
                    }
                doc_scores[doc_id]["keyword_score"] = normalized_score
        
        # 计算融合分数
        for doc_id, scores in doc_scores.items():
            vector_s = scores["vector_score"]
            keyword_s = scores["keyword_score"]
            combined = (vector_s * vector_weight) + (keyword_s * keyword_weight)
            scores["combined_score"] = combined
        
        # 按融合分数排序
        sorted_results = sorted(
            doc_scores.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        # 返回 top_k 结果
        final_results = []
        for item in sorted_results[:max(top_k, 1)]:
            doc = item["doc"].copy()
            doc["combined_score"] = item["combined_score"]
            doc["vector_score"] = item["vector_score"]
            doc["keyword_score"] = item["keyword_score"]
            final_results.append(doc)
        
        return final_results
    
    def get_documents_by_source(self, source: str) -> List[Dict]:
        """按源文件获取所有文档块"""
        records = self.collection.get(where={"source": source})
        documents: List[Dict] = []
        if not records or not records.get("documents"):
            return documents

        for idx, content in enumerate(records["documents"]):
            metadata = {}
            if records.get("metadatas"):
                metadata = records["metadatas"][idx]
            doc_id = None
            if records.get("ids"):
                doc_id = records["ids"][idx]

            documents.append(
                {
                    "content": content,
                    "metadata": metadata,
                    "id": doc_id,
                }
            )
        return documents

    def get_document_count(self) -> int:
        """获取文档总数"""
        return self.collection.count()
    
    def _generate_doc_id(self, doc: Document, index: int = 0) -> str:
        """生成文档ID"""
        content_hash = hashlib.md5(doc.page_content.encode()).hexdigest()[:8]
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", 0)
        return f"{source}_{page}_{index}_{content_hash}"
    
    def _extract_metadata(self, doc: Document) -> Dict:
        """提取文档元数据"""
        metadata = doc.metadata.copy()
        # 确保所有值都是字符串（ChromaDB要求）
        return {k: str(v) for k, v in metadata.items()}


class DocumentProcessor:
    """升级版文档处理类：基于 Docling 解析 + Markdown AST 结构化切分"""

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        embedding_client: Optional[Any] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_client = embedding_client
        
        # 1. 第一道防线：结构化切分器（基于 Markdown 标题 AST）
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
        ]
        self.md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False,
        )

        # 2. 第二道防线：长度兜底切分器（防止某个结构块过长撑爆 LLM）
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        )
        
        use_docling = os.getenv("RAG_USE_DOCLING", "0").strip().lower() in {"1", "true", "yes"}
        if DOCLING_AVAILABLE and use_docling:
            # 防止极复杂 PDF 导致 AST 递归栈溢出
            try:
                sys.setrecursionlimit(max(5000, sys.getrecursionlimit()))
            except Exception:
                pass

            pipeline_options = PdfPipelineOptions()
            pipeline_options.generate_picture_images = True
            pipeline_options.generate_page_images = False

            # OCR 策略：默认开启，但优先混合解析（非全页 OCR）
            low_memory_ocr = os.getenv("RAG_LOW_MEMORY_OCR", "1").strip().lower() in {"1", "true", "yes"}
            enable_ocr = os.getenv("RAG_ENABLE_OCR", "1").strip().lower() in {"1", "true", "yes"}
            if hasattr(pipeline_options, "do_ocr"):
                pipeline_options.do_ocr = enable_ocr

            # 显式绑定 RapidOCR（若当前版本可用）
            if RapidOcrOptions is not None:
                try:
                    ocr_opts = RapidOcrOptions()
                    if hasattr(ocr_opts, "force_full_page_ocr"):
                        # 稳定优先：默认不做全页 OCR，仅在必要时触发
                        force_full_page = os.getenv("RAG_OCR_FORCE_FULL_PAGE", "0").strip().lower() in {"1", "true", "yes"}
                        ocr_opts.force_full_page_ocr = force_full_page
                    pipeline_options.ocr_options = ocr_opts
                except Exception as e:
                    print(f"[Docling] RapidOcrOptions 配置失败，回退默认 OCR 选项: {e}")

            # 表格结构：稳定优先，低内存模式下默认关闭（可通过环境变量强制开启）
            if hasattr(pipeline_options, "do_table_structure"):
                default_table = "0" if low_memory_ocr else "1"
                pipeline_options.do_table_structure = os.getenv("RAG_ENABLE_TABLE_STRUCTURE", default_table).strip().lower() in {"1", "true", "yes"}
            tso = getattr(pipeline_options, "table_structure_options", None)
            if tso is not None and TableFormerMode is not None and hasattr(tso, "mode"):
                try:
                    tso.mode = TableFormerMode.FAST
                except Exception:
                    pass

            # 并发限制（稳定优先：低内存模式默认单线程）
            if hasattr(pipeline_options, "num_threads"):
                try:
                    default_threads = "1" if low_memory_ocr else "2"
                    pipeline_options.num_threads = int(os.getenv("DOCLING_NUM_THREADS", default_threads))
                except Exception:
                    pipeline_options.num_threads = 1 if low_memory_ocr else 2

            if low_memory_ocr:
                # 降低图像尺度，显著降低 OCR 峰值内存（稳定优先默认 0.6）
                if hasattr(pipeline_options, "images_scale"):
                    try:
                        pipeline_options.images_scale = float(os.getenv("RAG_OCR_IMAGE_SCALE", "0.6"))
                    except Exception:
                        pipeline_options.images_scale = 0.6

                # 尝试压低各类批量参数（不同 docling 版本字段名可能不同）
                ocr_opts = getattr(pipeline_options, "ocr_options", None)
                if ocr_opts is not None:
                    for name, value in {
                        "batch_size": 1,
                        "det_batch_size": 1,
                        "rec_batch_size": 1,
                        "cls_batch_size": 1,
                        "max_batch_size": 1,
                    }.items():
                        if hasattr(ocr_opts, name):
                            try:
                                setattr(ocr_opts, name, int(os.getenv(f"RAG_OCR_{name.upper()}", str(value))))
                            except Exception:
                                setattr(ocr_opts, name, value)

            print(
                "[DoclingConfig] "
                f"ocr={getattr(pipeline_options, 'do_ocr', 'n/a')} "
                f"threads={getattr(pipeline_options, 'num_threads', 'n/a')} "
                f"images_scale={getattr(pipeline_options, 'images_scale', 'n/a')} "
                f"table={getattr(pipeline_options, 'do_table_structure', 'n/a')} "
                f"low_memory={low_memory_ocr}"
            )

            self.converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                }
            )

        self.image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

    def _split_pdf_by_pages(self, file_path: str, pages_per_chunk: int = 20) -> List[str]:
        """
        将 PDF 文件按页数切割成多个小 PDF。
        
        Args:
            file_path: 原始 PDF 文件路径
            pages_per_chunk: 每个分片的页数（默认 20 页）
            
        Returns:
            分片 PDF 文件路径列表
        """
        if not PYMUPDF_AVAILABLE:
            raise RuntimeError("PyMuPDF 未安装，无法切割 PDF")
        
        try:
            pdf_document = fitz.open(file_path)
            total_pages = len(pdf_document)
            pdf_document.close()
            
            if total_pages <= pages_per_chunk:
                # 不需要切割
                return [file_path]
            
            # 创建临时目录存放分片
            temp_dir = tempfile.mkdtemp(prefix="pdf_split_")
            base_name = Path(file_path).stem
            
            chunk_files = []
            for start_page in range(0, total_pages, pages_per_chunk):
                end_page = min(start_page + pages_per_chunk, total_pages)
                
                # 创建新的 PDF 文档
                new_pdf = fitz.open()
                original_pdf = fitz.open(file_path)
                
                # 复制指定页面
                for page_num in range(start_page, end_page):
                    new_pdf.insert_pdf(original_pdf, from_page=page_num, to_page=page_num)
                
                # 保存分片
                chunk_filename = f"{base_name}_pages_{start_page+1}-{end_page}.pdf"
                chunk_path = os.path.join(temp_dir, chunk_filename)
                new_pdf.save(chunk_path)
                new_pdf.close()
                original_pdf.close()
                
                chunk_files.append(chunk_path)
                print(f"[PDF切割] 生成分片: {chunk_filename} (第 {start_page+1}-{end_page} 页)")
            
            print(f"[PDF切割] 共生成 {len(chunk_files)} 个分片文件")
            return chunk_files
            
        except Exception as e:
            raise RuntimeError(f"PDF 切割失败: {str(e)}")
    
    def _parse_single_pdf_with_mineru(
        self, 
        pdf_path: str, 
        output_dir: str,
        page_offset: int = 0
    ) -> Dict[str, Any]:
        """
        使用 MinerU CLI 解析单个 PDF 文件。
        
        Args:
            pdf_path: PDF 文件路径
            output_dir: MinerU 输出目录（会自动创建 {pdf_name}/ 子目录）
            page_offset: 页码偏移量（用于分片合并时计算真实页码）
            
        Returns:
            包含文本和图片信息的字典：
            {
                'markdown_text': str,  # Markdown 文本
                'images': List[Dict],  # 图片信息列表
                'success': bool,       # 是否成功
                'error': str           # 错误信息（如果有）
            }
        """
        result = {
            'markdown_text': '',
            'images': [],
            'success': False,
            'error': ''
        }
        
        try:
            print(f"[MinerU] 开始解析: {Path(pdf_path).name}")
            
            # 构建 MinerU CLI 命令
            cmd = _resolve_mineru_command() + [
                "-p", pdf_path,
                "-o", output_dir
            ]
            
            # 执行命令
            exec_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                cwd=_resolve_mineru_cwd(cmd) or str(Path(pdf_path).parent)
            )
            
            # 🔍 透视眼：打印 MinerU 的真实输出
            print("\n" + "="*20 + " MinerU 终端输出 (STDOUT) " + "="*20)
            print(exec_result.stdout)
            print("="*20 + " MinerU 错误信息 (STDERR) " + "="*20)
            print(exec_result.stderr)
            print("="*66 + "\n")
            
            # 检查执行结果
            if exec_result.returncode != 0:
                error_msg = exec_result.stderr.strip() if exec_result.stderr else "未知错误"
                result['error'] = f"MinerU 执行失败: {error_msg}"
                return result
            
            # MinerU 会在 output_dir 下创建以 PDF 文件名命名的子目录
            pdf_name = Path(pdf_path).stem
            mineru_output_dir = os.path.join(output_dir, pdf_name)
            
            if not os.path.exists(mineru_output_dir):
                result['error'] = f"MinerU 未生成输出目录: {mineru_output_dir}"
                return result
            
            # 🔍 查找 Markdown 文件（可能在子目录中）
            md_file_path = None
            
            # 方案 1：直接在 pdf_name 目录下
            direct_md = os.path.join(mineru_output_dir, f"{pdf_name}.md")
            if os.path.exists(direct_md):
                md_file_path = direct_md
            else:
                # 方案 2：在子目录中（如 hybrid_auto/）
                for root, dirs, files in os.walk(mineru_output_dir):
                    for file in files:
                        if file == f"{pdf_name}.md":
                            md_file_path = os.path.join(root, file)
                            break
                    if md_file_path:
                        break
            
            if not md_file_path:
                result['error'] = f"未找到 Markdown 文件，请在 {mineru_output_dir} 中查找 {pdf_name}.md"
                return result
            
            with open(md_file_path, 'r', encoding='utf-8') as f:
                markdown_text = f.read()
            
            if not markdown_text.strip():
                result['error'] = "MinerU 生成的 .md 文件为空"
                return result
            
            result['markdown_text'] = markdown_text
            
            # 🔍 查找 images 目录（可能在子目录中）
            images_dir = None
            
            # 方案 1：直接在 pdf_name/images/
            direct_images = os.path.join(mineru_output_dir, "images")
            if os.path.exists(direct_images) and os.path.isdir(direct_images):
                images_dir = direct_images
            else:
                # 方案 2：在子目录中（如 hybrid_auto/images/）
                for root, dirs, files in os.walk(mineru_output_dir):
                    if "images" in dirs:
                        images_dir = os.path.join(root, "images")
                        break
            
            if images_dir and os.path.isdir(images_dir):
                image_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
                for filename in sorted(os.listdir(images_dir)):  # 排序保证顺序一致
                    file_ext = Path(filename).suffix.lower()
                    if file_ext in image_extensions:
                        image_path = os.path.join(images_dir, filename)
                        # 获取图片尺寸
                        width, height = 0, 0
                        if PIL_AVAILABLE:
                            try:
                                with Image.open(image_path) as img:
                                    width, height = img.size
                            except Exception:
                                pass
                        
                        result['images'].append({
                            'path': image_path,
                            'name': filename,
                            'width': width,
                            'height': height,
                            'size': os.path.getsize(image_path),
                            'page_offset': page_offset
                        })
            
            result['success'] = True
            print(f"[MinerU] 解析成功！文本: {len(markdown_text)} 字符, 图片: {len(result['images'])} 张")
            
        except subprocess.TimeoutExpired:
            result['error'] = "MinerU 执行超时（超过 5 分钟）"
        except Exception as e:
            result['error'] = f"MinerU 解析失败: {str(e)}"
        
        return result
    
    def _parse_pdf_with_mineru(
        self, 
        file_path: str,
        pages_per_chunk: int = 20,
        max_workers: int = 4
    ) -> Dict[str, Any]:
        """
        使用 MinerU CLI 解析 PDF 文件（支持大文件分页切割和并行处理）。
        
        Args:
            file_path: PDF 文件的绝对路径
            pages_per_chunk: 每个分片的页数（默认 20 页，范围 10-30）
            max_workers: 最大并行工作线程数（默认 4）
            
        Returns:
            包含文本和图片信息的字典：
            {
                'markdown_text': str,      # 合并后的 Markdown 文本
                'images': List[Dict],      # 所有图片信息列表
                'success': bool,           # 是否成功
                'error': str               # 错误信息（如果有）
            }
        """
        if not MINERU_AVAILABLE:
            return {
                'markdown_text': '',
                'images': [],
                'success': False,
                'error': 'MinerU 未安装或不可用'
            }
        
        # 限制 pages_per_chunk 范围
        pages_per_chunk = max(10, min(30, pages_per_chunk))
        
        print(f"[MinerU] 开始解析 PDF: {Path(file_path).name} (每 {pages_per_chunk} 页一个分片)")
        
        # 创建主临时目录（使用项目根目录的 temp/）
        project_temp_dir = Config.TEMP_DIR
        project_temp_dir.mkdir(parents=True, exist_ok=True)
        main_temp_dir = tempfile.mkdtemp(prefix="mineru_main_", dir=str(project_temp_dir))
        split_temp_dir = None
        chunk_output_dirs = []
        
        try:
            # Step 1: 检查是否需要切割
            if not PYMUPDF_AVAILABLE:
                print("[WARNING] PyMuPDF 未安装，无法切割 PDF，将直接解析整个文件")
                chunk_files = [file_path]
            else:
                try:
                    chunk_files = self._split_pdf_by_pages(file_path, pages_per_chunk)
                    if len(chunk_files) > 1:
                        # 如果生成了分片，记录分片目录以便清理
                        split_temp_dir = os.path.dirname(chunk_files[0])
                except Exception as e:
                    print(f"[WARNING] PDF 切割失败，降级为直接解析: {e}")
                    chunk_files = [file_path]
            
            print(f"[MinerU] 共 {len(chunk_files)} 个分片需要处理")
            
            # Step 2: 并行处理每个分片
            all_results = []
            
            def process_single_chunk(args):
                """处理单个分片的辅助函数"""
                idx, chunk_path = args
                page_offset = idx * pages_per_chunk
                
                # 为每个分片创建独立的输出目录
                chunk_output_dir = tempfile.mkdtemp(
                    prefix=f"mineru_chunk_{idx}_",
                    dir=main_temp_dir
                )
                chunk_output_dirs.append(chunk_output_dir)
                
                # 解析该分片
                result = self._parse_single_pdf_with_mineru(
                    pdf_path=chunk_path,
                    output_dir=chunk_output_dir,
                    page_offset=page_offset
                )
                
                return idx, result
            
            # 使用线程池并行处理
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(process_single_chunk, (idx, chunk_path)): idx
                    for idx, chunk_path in enumerate(chunk_files)
                }
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        idx, result = future.result()
                        all_results.append((idx, result))
                    except Exception as e:
                        print(f"[WARNING] 分片处理异常: {e}")
            
            # Step 3: 按顺序合并结果
            all_results.sort(key=lambda x: x[0])  # 按索引排序
            
            merged_markdown_parts = []
            all_images = []
            failed_chunks = []
            
            for idx, result in all_results:
                if result['success']:
                    # 添加页码标记
                    if idx > 0:
                        merged_markdown_parts.append(f"\n\n--- 第 {idx * pages_per_chunk + 1} 页起 ---\n\n")
                    merged_markdown_parts.append(result['markdown_text'])
                    all_images.extend(result['images'])
                else:
                    failed_chunks.append(idx)
                    print(f"[WARNING] 分片 {idx} 解析失败: {result['error']}")
            
            if not merged_markdown_parts:
                return {
                    'markdown_text': '',
                    'images': [],
                    'success': False,
                    'error': f"所有分片解析失败: {'; '.join([all_results[i][1]['error'] for i in failed_chunks])}"
                }
            
            merged_markdown = ''.join(merged_markdown_parts).strip()
            
            print(f"[MinerU] 解析完成！总文本: {len(merged_markdown)} 字符, 总图片: {len(all_images)} 张")
            
            if failed_chunks:
                print(f"[WARNING] 有 {len(failed_chunks)} 个分片解析失败: {failed_chunks}")
            
            return {
                'markdown_text': merged_markdown,
                'images': all_images,
                'success': True,
                'error': '',
                'temp_dirs_to_cleanup': [main_temp_dir] + ([split_temp_dir] if split_temp_dir else [])
            }
            
        except Exception as e:
            return {
                'markdown_text': '',
                'images': [],
                'success': False,
                'error': f"MinerU 解析失败: {str(e)}",
                'temp_dirs_to_cleanup': [main_temp_dir] + ([split_temp_dir] if split_temp_dir else [])
            }

    def process_file(
        self,
        file_path: str,
        owner: Optional[str] = None,
        doc_id: Optional[str] = None,
        images_root: Optional[Path] = None,
    ) -> List[Document]:
        """基于 PyMuPDF 的工业级稳定解析：文本与图片分离抽取。"""
        file_path_obj = Path(file_path)

        # 可选强制使用 Docling（仅用于调试/对比，默认关闭）
        force_docling = os.getenv("RAG_USE_DOCLING", "0").strip().lower() in {"1", "true", "yes"}
        if force_docling and DOCLING_AVAILABLE:
            print("[Docling] RAG_USE_DOCLING=1，启用 Docling 路径")

            md_text = ""
            docling_result: Optional[Any] = None
            try:
                docling_result = self.converter.convert(file_path)
                md_text = docling_result.document.export_to_markdown()
            except Exception as e:
                print(f"[Docling] 解析失败，降级基础读取: {e}")
                md_text = self._fallback_read(file_path)

            if not md_text.strip():
                raise ValueError(f"无法从文件 {file_path_obj.name} 中提取有效文本内容。")

            base_doc = Document(
                page_content=md_text,
                metadata={
                    "source": file_path,
                    "document_name": file_path_obj.name,
                    "page": 0,
                    "modality": "text",
                },
            )
            text_chunks = self.split_documents([base_doc])
            for doc in text_chunks:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["modality"] = "text"

            image_chunks: List[Document] = []
            if docling_result is not None:
                try:
                    image_chunks = self._extract_image_documents_from_docling(
                        docling_result,
                        file_path_obj,
                        owner=owner,
                        doc_id=doc_id,
                        images_root=images_root,
                    )
                except Exception as e:
                    print(f"[Docling] 图片导出失败: {e}")

            return text_chunks + image_chunks

        if file_path_obj.suffix.lower() != ".pdf":
            # 非 PDF 维持原有降级读取流程
            md_text = self._fallback_read(file_path)
            if not md_text.strip():
                raise ValueError(f"无法从文件 {file_path_obj.name} 中提取有效文本内容。")
            base_doc = Document(
                page_content=md_text,
                metadata={
                    "source": file_path,
                    "document_name": file_path_obj.name,
                    "page": 0,
                    "modality": "text",
                },
            )
            text_chunks = self.split_documents([base_doc])
            for doc in text_chunks:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["modality"] = "text"
            return text_chunks

        # ===== PDF 处理逻辑 =====
        # 检查是否强制使用 MinerU（通过环境变量控制）
        force_mineru = os.getenv("RAG_USE_MINERU", "1").strip().lower() in {"1", "true", "yes"}
        
        text_chunks: List[Document] = []
        image_chunks: List[Document] = []
        _, safe_doc_id, target_root = self._resolve_image_target_root(file_path_obj, owner, doc_id, images_root)

        # 尝试使用 MinerU 解析（优先）
        mineru_success = False
        if force_mineru and MINERU_AVAILABLE:
            try:
                print(f"[MinerU] 开始解析文档: {file_path_obj.name}")
                
                # 获取 MinerU 配置参数
                pages_per_chunk = int(os.getenv("RAG_MINERU_PAGES_PER_CHUNK", "20"))
                max_workers = int(os.getenv("RAG_MINERU_MAX_WORKERS", "4"))
                
                # 调用新的解析方法（返回文本+图片）
                mineru_result = self._parse_pdf_with_mineru(
                    file_path=file_path,
                    pages_per_chunk=pages_per_chunk,
                    max_workers=max_workers
                )
                
                if not mineru_result['success']:
                    raise ValueError(f"MinerU 解析失败: {mineru_result['error']}")
                
                markdown_text = mineru_result['markdown_text']
                mineru_images = mineru_result['images']
                
                if not markdown_text.strip():
                    raise ValueError(f"MinerU 未提取到有效文本内容")
                
                # 创建文本文档并分块
                base_doc = Document(
                    page_content=markdown_text,
                    metadata={
                        "source": file_path,
                        "document_name": file_path_obj.name,
                        "page": 0,
                        "modality": "text",
                    },
                )
                text_chunks = self.split_documents([base_doc])
                for doc in text_chunks:
                    if doc.metadata is None:
                        doc.metadata = {}
                    doc.metadata["modality"] = "text"
                
                # 处理 MinerU 提取的图片（在清理临时目录之前）
                print(f"[MinerU] 开始保存图片 ({len(mineru_images)} 张)...")
                
                # 检查是否启用了图片向量（BGE 通常不支持，建议设为 0）
                enable_image_embedding = os.getenv("RAG_ENABLE_IMAGE_EMBEDDING", "0").strip().lower() in {"1", "true", "yes"}
                
                for img_info in mineru_images:
                    try:
                        # 将图片复制到目标目录
                        src_path = img_info['path']
                        
                        # 检查源文件是否存在
                        if not os.path.exists(src_path):
                            print(f"[WARNING] 图片源文件不存在: {src_path}")
                            continue
                        
                        dst_name = f"mineru_{img_info['name']}"
                        dst_path = target_root / dst_name
                        
                        # 复制文件到 storage
                        shutil.copy2(src_path, dst_path)
                        print(f"[MinerU图片] 已保存到硬盘: {dst_name}")
                        
                        # 只有当启用图片向量时，才创建图片 Document 并入库
                        if enable_image_embedding:
                            image_chunks.append(
                                self._build_image_chunk_document(
                                    file_path_obj=file_path_obj,
                                    image_path=dst_path,
                                    image_index=img_info.get('page_offset', 0),
                                    alt_text=f"MinerU 解析的插图",
                                    safe_doc_id=safe_doc_id,
                                )
                            )
                        else:
                            print(f"[MinerU图片] 跳过向量化入库 (RAG_ENABLE_IMAGE_EMBEDDING=0)")
                            
                    except Exception as e:
                        print(f"[WARNING] 处理 MinerU 图片失败: {e}")
                
                mineru_success = True
                print(f"[MinerU] 解析成功！文本块: {len(text_chunks)}，图片: {len(image_chunks)}")
                
                # 清理 MinerU 临时目录（在图片保存完成后）
                temp_dirs = mineru_result.get('temp_dirs_to_cleanup', [])
                for temp_dir in temp_dirs:
                    if temp_dir and os.path.exists(temp_dir):
                        try:
                            shutil.rmtree(temp_dir)
                            print(f"[MinerU] 已清理临时目录: {temp_dir}")
                        except Exception as e:
                            print(f"[WARNING] 清理临时目录失败: {e}")
                
            except Exception as e:
                print(f"[WARNING] MinerU 解析失败，降级到 PyMuPDF: {e}")
                mineru_success = False
        
        # 如果 MinerU 失败或不可用，使用 PyMuPDF
        if not mineru_success:
            if not PYMUPDF_AVAILABLE:
                raise RuntimeError("PyMuPDF 未安装，无法解析 PDF。请先安装: pip install PyMuPDF")
            
            print(f"[PyMuPDF] 开始极速解析文档: {file_path_obj.name}")
            
            try:
                pdf_document = fitz.open(file_path)
                full_text_parts: List[str] = []
                image_index = 0

                for page_num in range(len(pdf_document)):
                    page = pdf_document.load_page(page_num)

                    page_text = (page.get_text("text") or "").strip()
                    if page_text:
                        full_text_parts.append(f"--- 第 {page_num + 1} 页 ---\n\n{page_text}")

                    image_list = page.get_images(full=True)
                    for img_info in image_list:
                        xref = img_info[0]
                        try:
                            base_image = pdf_document.extract_image(xref)
                        except Exception:
                            continue

                        image_bytes = base_image.get("image")
                        image_ext = base_image.get("ext") or "png"
                        width = int(base_image.get("width") or 0)
                        height = int(base_image.get("height") or 0)

                        # 增强过滤条件（方案 1）
                        if not image_bytes:
                            continue
                        
                        # 1. 尺寸过滤：宽高至少 200px（防止小图标）
                        if width < 200 or height < 200:
                            print(f"[图片过滤] 跳过过小图片：{width}x{height}")
                            continue
                        
                        # 2. 面积过滤：总面积至少 40000 像素
                        area = width * height
                        if area < 40000:
                            print(f"[图片过滤] 跳过面积过小：{area:,}px")
                            continue
                        
                        # 3. 宽高比过滤：排除极端比例（防止细长条背景）
                        aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 0
                        if aspect_ratio > 5:
                            print(f"[图片过滤] 跳过宽高比异常：{aspect_ratio:.2f}")
                            continue
                        
                        # 4. 扫描版 PDF 检测：如果图片几乎和页面一样大，可能是整页扫描
                        page_rect = page.rect
                        page_area = page_rect.width * page_rect.height if page_rect else 0
                        image_area_ratio = area / page_area if page_area > 0 else 0
                        
                        if image_area_ratio > 0.9:  # 图片占页面 90% 以上
                            print(f"[图片过滤] 跳过疑似整页扫描：{image_area_ratio:.1%}")
                            continue

                        dst_name = f"page{page_num + 1}_{image_index:04d}.{image_ext}"
                        dst_path = target_root / dst_name
                        with open(dst_path, "wb") as f:
                            f.write(image_bytes)

                        print(f"[图片提取] 成功保存：{dst_name} ({width}x{height}, {area:,}px)")
                        
                        image_chunks.append(
                            self._build_image_chunk_document(
                                file_path_obj=file_path_obj,
                                image_path=dst_path,
                                image_index=image_index,
                                alt_text=f"PDF 第 {page_num + 1} 页的插图",
                                safe_doc_id=safe_doc_id,
                            )
                        )
                        image_index += 1

                pdf_document.close()

                full_text = "\n\n".join(full_text_parts).strip()
                if not full_text:
                    print(f"[PyMuPDF] 未检测到原生文本，触发 fallback 读取: {file_path_obj.name}")
                    full_text = self._fallback_read(file_path)

                if not full_text.strip():
                    raise ValueError(f"无法从文件 {file_path_obj.name} 中提取有效文本内容。")

                base_doc = Document(
                    page_content=full_text,
                    metadata={
                        "source": file_path,
                        "document_name": file_path_obj.name,
                        "page": 0,
                        "modality": "text",
                    },
                )
                text_chunks = self.split_documents([base_doc])
                for doc in text_chunks:
                    if doc.metadata is None:
                        doc.metadata = {}
                    doc.metadata["modality"] = "text"

                print(f"[PyMuPDF] 解析成功！提取文本块: {len(text_chunks)}，高清插图: {len(image_chunks)}")
                
            except Exception as e:
                raise RuntimeError(f"文档解析彻底失败，请检查文件是否损坏: {e}")
        
        return text_chunks + image_chunks

    def _fallback_read(self, file_path: str) -> str:
        """降级读取方案（针对 docling 失败或未安装的情况）"""
        encodings = ["utf-8", "gbk", "gb2312", "utf-8-sig"]
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        with open(file_path, 'r', encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _resolve_image_target_root(
        self,
        file_path_obj: Path,
        owner: Optional[str],
        doc_id: Optional[str],
        images_root: Optional[Path],
    ) -> tuple[str, str, Path]:
        safe_owner = owner or "anonymous"
        safe_doc_id = doc_id or hashlib.md5(str(file_path_obj).encode("utf-8")).hexdigest()[:16]
        target_root = (images_root or (Config.STORAGE_ROOT / "images")).resolve() / safe_owner / safe_doc_id
        target_root.mkdir(parents=True, exist_ok=True)
        return safe_owner, safe_doc_id, target_root

    def _build_image_chunk_document(
        self,
        file_path_obj: Path,
        image_path: Path,
        image_index: int,
        alt_text: str,
        safe_doc_id: str,
    ) -> Document:
        width = 0
        height = 0
        if PIL_AVAILABLE:
            try:
                with Image.open(image_path) as img:
                    width, height = img.size
            except Exception:
                pass

        image_size = image_path.stat().st_size if image_path.exists() else 0
        image_rel_path = os.path.relpath(str(image_path), str(Config.STORAGE_ROOT.resolve()))
        virtual_text = (
            f"[IMAGE_CHUNK] 文件名: {image_path.name}; alt: {alt_text or '无'}; "
            f"尺寸: {width}x{height}; 大小: {image_size} bytes"
        )

        return Document(
            page_content=virtual_text,
            metadata={
                "source": str(file_path_obj),
                "document_name": file_path_obj.name,
                "page": 0,
                "modality": "image",
                "image_path": str(image_path.resolve()),
                "image_rel_path": image_rel_path,
                "image_name": image_path.name,
                "image_alt": alt_text,
                "image_width": width,
                "image_height": height,
                "image_size": image_size,
                "image_index": image_index,
                "image_doc_id": safe_doc_id,
            },
        )

    def _extract_image_documents_from_docling(
        self,
        docling_result: Any,
        file_path_obj: Path,
        owner: Optional[str] = None,
        doc_id: Optional[str] = None,
        images_root: Optional[Path] = None,
    ) -> List[Document]:
        """Docling 原生图片导出：使用 document.pictures + picture.get_image(document)。"""
        image_docs: List[Document] = []
        _, safe_doc_id, target_root = self._resolve_image_target_root(file_path_obj, owner, doc_id, images_root)

        doc_obj = getattr(docling_result, "document", None)
        if doc_obj is None:
            return image_docs

        pictures = getattr(doc_obj, "pictures", None)
        if not pictures:
            return image_docs

        for idx, pic in enumerate(pictures):
            try:
                img_pil = pic.get_image(doc_obj)
                if img_pil is None:
                    continue

                dst_path = target_root / f"{idx:04d}.png"
                img_pil.save(str(dst_path), format="PNG")

                alt = str(getattr(pic, "caption", "") or "").strip()
                image_docs.append(
                    self._build_image_chunk_document(
                        file_path_obj=file_path_obj,
                        image_path=dst_path,
                        image_index=idx,
                        alt_text=alt,
                        safe_doc_id=safe_doc_id,
                    )
                )
            except Exception as e:
                print(f"[Docling][Picture] 导出单张图片失败 idx={idx}: {e}")
                continue

        return image_docs

    def _extract_image_documents(
        self,
        md_text: str,
        file_path_obj: Path,
        owner: Optional[str] = None,
        doc_id: Optional[str] = None,
        images_root: Optional[Path] = None,
    ) -> List[Document]:
        """从 Markdown 中提取图片引用，构造图片虚拟 chunk，并统一复制到 images 目录。"""
        image_docs: List[Document] = []
        base_dir = file_path_obj.parent

        _, safe_doc_id, target_root = self._resolve_image_target_root(file_path_obj, owner, doc_id, images_root)

        # 匹配 Markdown 图片语法: ![alt](url)
        pattern = re.compile(r"!\[(?P<alt>.*?)\]\((?P<src>[^)]+)\)")
        matches = list(pattern.finditer(md_text or ""))
        if not matches:
            return image_docs

        seen_paths = set()
        for idx, m in enumerate(matches):
            alt_text = (m.group("alt") or "").strip()
            raw_src = (m.group("src") or "").strip().strip('"').strip("'")
            raw_src = unquote(raw_src)

            if not raw_src or raw_src.startswith("http://") or raw_src.startswith("https://"):
                continue

            # 去掉片段与查询参数
            clean_src = raw_src.split("#", 1)[0].split("?", 1)[0]
            image_path = (base_dir / clean_src).resolve()
            if not image_path.exists() or image_path.suffix.lower() not in self.image_exts:
                continue

            normalized = str(image_path)
            if normalized in seen_paths:
                continue
            seen_paths.add(normalized)

            # 统一拷贝到 storage/images/<owner>/<doc_id>/
            dst_name = f"{idx:04d}_{image_path.name}"
            dst_path = target_root / dst_name
            try:
                shutil.copy2(str(image_path), str(dst_path))
            except Exception:
                # copy 失败时降级使用原路径，避免整份文档导入失败
                dst_path = image_path

            image_docs.append(
                self._build_image_chunk_document(
                    file_path_obj=file_path_obj,
                    image_path=dst_path,
                    image_index=idx,
                    alt_text=alt_text,
                    safe_doc_id=safe_doc_id,
                )
            )

        return image_docs

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        核心智能切分逻辑：先按 Markdown 结构切，再按长度强制截断，并将标题链注入正文
        """
        all_chunks = []
        
        for doc in documents:
            base_metadata = doc.metadata.copy()
            
            # 第一步：按 Markdown 标题层级切分
            md_docs = self.md_splitter.split_text(doc.page_content)
            
            # 若文档没有任何标题，退化为普通切分
            if not md_docs:
                md_docs = [doc]
            
            # 第二步：长度兜底与上下文强化
            for md_doc in md_docs:
                merged_metadata = {**base_metadata, **md_doc.metadata}
                
                # 将 AST 标题层级（族谱）注入正文开头，防止 RAG 丢失上下文
                h_parts = []
                for h_key in ["Header 1", "Header 2", "Header 3", "Header 4"]:
                    if h_key in merged_metadata:
                        h_parts.append(merged_metadata[h_key])
                
                if h_parts:
                    enriched_content = f"【章节上下文】: {' > '.join(h_parts)}\n\n{md_doc.page_content}"
                else:
                    enriched_content = md_doc.page_content
                
                temp_doc = Document(page_content=enriched_content, metadata=merged_metadata)
                
                # 第三步：长度防爆防线
                if len(enriched_content) > self.chunk_size:
                    sub_chunks = self.text_splitter.split_documents([temp_doc])
                    all_chunks.extend(sub_chunks)
                else:
                    all_chunks.append(temp_doc)
                    
        return all_chunks


class RAGSystem:
    """RAG系统主类"""
    
    def __init__(
        self,
        api_base: str,
        api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-ada-002",
        llm_model: str = "qwen3.5-plus",
        vector_db_path: Union[str, Path] = Config.VECTOR_DB_PATH,
        document_index_path: Optional[Union[str, Path]] = None
    ):
        """
        初始化RAG系统
        
        Args:
            api_base: API基础URL
            api_key: API密钥
            embedding_model: embedding模型名称
            llm_model: LLM模型名称
            vector_db_path: 向量数据库路径
        """
        self.api_base = api_base
        self.api_key = api_key
        self.llm_model = os.getenv("LLM_MODEL") or llm_model or "qwen3.5-plus"
        # 统一“生成类”模型默认值：qwen3.5-plus
        self.summary_model = os.getenv("LLM_MODEL_SUMMARY") or "qwen3.5-plus"
        
        # 初始化组件
        self.embedding_client = EmbeddingClient(api_base, api_key, embedding_model)
        self.vector_store = VectorStore(vector_db_path, embedding_client=self.embedding_client)
        # 传递 embedding_client 给 DocumentProcessor，用于语义分块
        # 关键：Ollama embedding 对单次输入长度更敏感，chunk_size 需要更小以避免 500: context length exceeded
        try:
            default_chunk_size = 2000
            default_chunk_overlap = 400
            chunk_size = int(os.getenv("RAG_CHUNK_SIZE", str(default_chunk_size)))
            chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", str(default_chunk_overlap)))
        except Exception:
            chunk_size = 2000
            chunk_overlap = 400

        self.document_processor = DocumentProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_client=self.embedding_client,
        )

        # Query Rewriting 配置
        self.query_rewrite_enabled = os.getenv("RAG_ENABLE_QUERY_REWRITE", "0").strip().lower() in {"1", "true", "yes"}
        self.query_rewrite_history_turns = int(os.getenv("RAG_QUERY_REWRITE_HISTORY_TURNS", "4"))
        self.query_rewrite_max_chars = int(os.getenv("RAG_QUERY_REWRITE_MAX_CHARS", "128"))
        self.query_rewrite_min_chars = int(os.getenv("RAG_QUERY_REWRITE_MIN_CHARS", "2"))
        self.query_rewrite_min_tokens = int(os.getenv("RAG_QUERY_REWRITE_MIN_TOKENS", "2"))
        
        # 文档索引（用于增量导入管理）
        self.index_file = Path(document_index_path or Config.DOCUMENT_INDEX_PATH)
        self.document_index = self._load_index()
    
    def _load_index(self) -> Dict:
        """加载文档索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_index(self):
        """保存文档索引"""
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.document_index, f, ensure_ascii=False, indent=2)
    
    def _get_file_hash(self, file_path: str) -> str:
        """获取文件哈希值"""
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _make_source_key(self, file_path: str, owner: Optional[str]) -> str:
        """生成按 owner 隔离的 source key，用于向量库 metadata"""
        # 若 file_path 已经包含 "user_" 前缀，说明它本身就是一个 index_key，直接返回
        if str(file_path).startswith("user_"):
            return str(file_path)
        if owner:
            return f"user_{owner}:{file_path}"
        return str(file_path)

    def _make_index_key(self, file_path: str, owner: Optional[str]) -> str:
        """生成按 owner 隔离的 index key，用于 document_index"""
        # 如果已经带前缀，说明是现成的 key
        if str(file_path).startswith("user_"):
            return str(file_path)
        if owner:
            return f"user_{owner}:{file_path}"
        return str(file_path)
    
    def _rewrite_query(self, question: str, conversation_history: Optional[List[Dict[str, Any]]] = None) -> str:
        """将当前问题重写为可独立检索的查询词。失败或不满足触发条件时回退原问题。"""
        if not self.query_rewrite_enabled:
            return question

        q = (question or "").strip()
        if not q:
            return question

        # 触发策略：过长问题默认不重写；明显短句/指代句优先重写
        pronoun_markers = ["这个", "那个", "上面", "下面", "前面", "后面", "它", "他", "她", "其", "这部分", "那部分", "最后那部分"]
        has_pronoun_marker = any(m in q for m in pronoun_markers)
        token_count = len([t for t in re.split(r"\s+", q) if t]) if " " in q else len([c for c in q if c.strip()])

        if len(q) < self.query_rewrite_min_chars:
            print("[QueryRewrite] 问题过短，跳过重写")
            return question

        if len(q) >= self.query_rewrite_max_chars and not has_pronoun_marker:
            print("[QueryRewrite] 问题已较完整且较长，跳过重写")
            return question

        if token_count >= 12 and not has_pronoun_marker:
            print("[QueryRewrite] 问题信息充分，跳过重写")
            return question

        history = conversation_history or []
        recent = history[-self.query_rewrite_history_turns:] if history else []

        history_lines: List[str] = []
        for msg in recent:
            role = msg.get("role", "user")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role not in {"user", "assistant", "system"}:
                role = "user"
            history_lines.append(f"{role}: {content}")

        prompt = (
            "你是检索查询重写器。请将“当前问题”改写为一个可独立检索的简洁查询，"
            "保留核心实体、时间、约束条件；如果当前问题已完整清晰，则原样返回。"
            "只输出改写后的查询，不要解释。"
        )

        user_content = (
            "【对话历史】\n"
            + ("\n".join(history_lines) if history_lines else "（无）")
            + "\n\n【当前问题】\n"
            + q
            + "\n\n请输出改写后的检索查询："
        )

        try:
            rewritten = self._call_llm(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ]
            ).strip()

            if not rewritten:
                print("[QueryRewrite] 返回为空，降级使用原问题")
                return question

            rewritten = rewritten.replace("\n", " ").strip()
            if len(rewritten) > self.query_rewrite_max_chars * 2:
                rewritten = rewritten[: self.query_rewrite_max_chars * 2]

            # 质量门控1：重写结果过短或无效
            rewritten_tokens = len([t for t in re.split(r"\s+", rewritten) if t]) if " " in rewritten else len([c for c in rewritten if c.strip()])
            if rewritten_tokens < self.query_rewrite_min_tokens:
                print("[QueryRewrite] 重写结果过短，降级使用原问题")
                return question

            # 质量门控2：关键实体保留检查（简单启发式）
            entity_candidates = re.findall(r"[A-Za-z0-9\u4e00-\u9fa5]{2,}", q)
            entity_candidates = [e for e in entity_candidates if e not in {"这个", "那个", "上面", "下面", "最后", "部分", "问题"}]
            key_entities = entity_candidates[:3]
            if key_entities:
                missing_entities = [e for e in key_entities if e not in rewritten]
                if len(missing_entities) == len(key_entities) and not has_pronoun_marker:
                    print(f"[QueryRewrite] 关键实体可能丢失 {missing_entities}，降级使用原问题")
                    return question

            # 质量门控3：避免改写偏离为问候/废话
            bad_patterns = ["你好", "谢谢", "请帮我", "不知道", "随便"]
            if any(bp == rewritten for bp in bad_patterns):
                print("[QueryRewrite] 重写结果疑似无效，降级使用原问题")
                return question

            if rewritten != q:
                print(f"[QueryRewrite] 重写成功：'{q}' -> '{rewritten}'")
            else:
                print("[QueryRewrite] 原问题已足够清晰，保持不变")
            return rewritten
        except Exception as e:
            print(f"[QueryRewrite] 重写失败，降级使用原问题：{e}")
            return question
    
    def _generate_hypothetical_answer(self, question: str) -> str:
        """
        HyDE（Hypothetical Document Embeddings）策略
        生成一个假设性答案，然后用答案的 embedding 进行检索
        
        原理：答案空间比问题空间更密集，更容易匹配到相关文档
        """
        prompt = f"""
你是一个 RAG HyDE 系统，需要根据给定的问题生成一个假设性答案。
请针对以下问题，写一个简短的假设性答案（不需要准确，只需覆盖可能的关键词和概念）：

问题：{question}

要求：
1. 100-200 字左右
2. 包含可能的相关术语、概念和关键词
3. 不需要事实正确，只需提供搜索线索
4. 使用与知识库可能相同的表述方式

假设性答案：
"""
        
        try:
            # 使用 LLM 生成假设性答案
            hypothetical_doc = self._call_llm(prompt=prompt)
            return hypothetical_doc.strip() if hypothetical_doc else ""
        except Exception as e:
            print(f"[HyDE] 生成假设性答案失败：{e}")
            return ""

    def import_document(
        self,
        file_path: str,
        force_reimport: bool = False,
        progress_callback: Optional[Callable[[int, str], None]] = None,  # 进度回调（可选）
        owner: Optional[str] = None,  # 文档所属用户（用户名），用于按用户隔离文档
    ) -> Dict:
        """
        增量导入文档
        
        Args:
            file_path: 文件路径
            force_reimport: 是否强制重新导入（即使文件未变化）
            
        Returns:
            导入结果
        """
        file_path_obj = Path(file_path).absolute()
        
        if not file_path_obj.exists():
            raise FileNotFoundError(f"文件不存在: {file_path_obj}")

        if progress_callback:
            progress_callback(5, "queued")
        
        # 检查文件是否已导入
        file_str = str(file_path_obj)
        file_hash = self._get_file_hash(file_str)
        
        index_key = self._make_index_key(file_str, owner)

        if not force_reimport and index_key in self.document_index:
            existing_entry = self.document_index[index_key]
            # 关键：同一路径可能被不同用户“各自导入”，因此增量判断必须同时校验 owner
            # 否则会出现：A 导入后，B 导入同一路径时被错误判定为“已导入”，导致 owner/索引混乱
            existing_owner = existing_entry.get("owner")
            if owner is not None and existing_owner is not None and existing_owner != owner:
                # 不同用户同路径：视为“需要重新导入到该用户名下”（继续往下走）
                pass
            else:
                existing_hash = existing_entry.get("hash")
            if existing_hash == file_hash:
                if progress_callback:
                    progress_callback(100, "completed")
                return {
                    "status": "skipped",
                    "message": "文件未变化，跳过导入",
                    "file": file_str
                }
        
        # 处理文档
        if progress_callback:
            progress_callback(15, "loading_pdf")
        
        print(f"[RAG导入] 开始处理文件: {file_str}")
        file_size = Path(file_str).stat().st_size if Path(file_str).exists() else 0
        print(f"[RAG导入] 文件大小: {file_size} 字节")
        
        image_doc_id = hashlib.md5(index_key.encode("utf-8")).hexdigest()[:16]
        images_root = Config.STORAGE_ROOT / "images"
        documents = self.document_processor.process_file(
            file_str,
            owner=owner,
            doc_id=image_doc_id,
            images_root=images_root,
        )
        
        print(f"[RAG导入] 文档处理完成，生成 {len(documents)} 个文档块")
        if documents:
            text_count = sum(1 for d in documents if str((d.metadata or {}).get("modality", "text")).lower() != "image")
            image_count = len(documents) - text_count
            print(f"[RAG导入] 模态分布: text={text_count}, image={image_count}")

            total_content_length = sum(len(doc.page_content) for doc in documents)
            print(f"[RAG导入] 所有文档块总内容长度: {total_content_length} 字符")
            print(f"[RAG导入] 平均每块长度: {total_content_length // len(documents) if documents else 0} 字符")
            max_chunk_len = max(len(doc.page_content) for doc in documents)
            min_chunk_len = min(len(doc.page_content) for doc in documents)
            print(f"[RAG导入] 最大块长度: {max_chunk_len} 字符")
            print(f"[RAG导入] 最小块长度: {min_chunk_len} 字符")
        
        if progress_callback:
            progress_callback(35, "splitting")

        # 为每个文档块添加所有者信息，并把“source”改为按用户隔离的 key
        # 关键点：向量库删除/查询是按 metadata.source 做 where / 比较的。
        # 如果不同用户共享同一个 source=文件路径，那么 delete_by_source(source) 会把所有用户的 chunks 一起删掉。
        # 因此需要把 source 变成 owner 维度隔离的 source_key。
        source_key = self._make_source_key(file_str, owner)
        if owner:
            for doc in documents:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["owner"] = owner
                doc.metadata["owner_username"] = owner
                doc.metadata["source"] = source_key
        else:
            # 兼容无 owner 的旧行为：仍然使用 file_path 作为 source
            for doc in documents:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["source"] = file_str

        # 生成 embeddings（图文双轨：文本走 text embedding，图片走 image embedding）
        if progress_callback:
            progress_callback(50, "embedding")

        text_indices: List[int] = []
        text_inputs: List[str] = []
        image_indices: List[int] = []
        image_paths: List[str] = []
        image_hints: List[Optional[str]] = []

        for i, doc in enumerate(documents):
            metadata = doc.metadata or {}
            modality = str(metadata.get("modality", "text")).lower()
            if modality == "image" and metadata.get("image_path"):
                image_indices.append(i)
                image_paths.append(str(metadata.get("image_path")))
                image_hints.append(doc.page_content)
            else:
                # 防止空文本块触发 Gemini embedding "input is empty"
                text_value = str(doc.page_content or "").strip()
                if not text_value:
                    text_value = "[EMPTY_CHUNK]"
                    print(f"[RAG导入][Sanitize] empty_text_chunk idx={i} replaced")
                text_indices.append(i)
                text_inputs.append(text_value)

        print(
            f"[RAG导入][Stage] embedding_start total={len(documents)} text={len(text_inputs)} image={len(image_paths)} source_key={source_key}"
        )

        all_embeddings: List[Optional[List[float]]] = [None] * len(documents)

        if text_inputs:
            text_vectors = self.embedding_client.embed_documents(text_inputs)
            if len(text_vectors) != len(text_indices):
                raise Exception(f"文本向量数量异常，期望={len(text_indices)} 实际={len(text_vectors)}")
            for idx, vec in zip(text_indices, text_vectors):
                all_embeddings[idx] = vec

        if image_paths:
            enable_image_embedding = os.getenv("RAG_ENABLE_IMAGE_EMBEDDING", "1").strip().lower() in {"1", "true", "yes"}
            image_fallback_to_text = os.getenv("RAG_IMAGE_EMBED_FALLBACK_TO_TEXT", "1").strip().lower() in {"1", "true", "yes"}

            image_vectors: List[List[float]] = []
            if enable_image_embedding:
                try:
                    image_vectors = self.embedding_client.embed_images(image_paths, image_hints)
                except Exception as e:
                    if not image_fallback_to_text:
                        raise
                    print(f"[RAG导入][ImageEmbedding] 图片向量失败，降级为文本向量: {e}")
                    fallback_texts: List[str] = []
                    for i, hint in enumerate(image_hints):
                        t = str(hint or "").strip()
                        if not t:
                            t = f"[IMAGE_FALLBACK] image_{i}"
                        fallback_texts.append(t)
                    image_vectors = self.embedding_client.embed_documents(fallback_texts)
            else:
                if not image_fallback_to_text:
                    raise Exception("图片向量已禁用且未开启文本降级，无法处理图片块")
                print("[RAG导入][ImageEmbedding] 已禁用图片向量，使用文本降级")
                fallback_texts = []
                for i, hint in enumerate(image_hints):
                    t = str(hint or "").strip()
                    if not t:
                        t = f"[IMAGE_FALLBACK] image_{i}"
                    fallback_texts.append(t)
                image_vectors = self.embedding_client.embed_documents(fallback_texts)

            if len(image_vectors) != len(image_indices):
                raise Exception(f"图片向量数量异常，期望={len(image_indices)} 实际={len(image_vectors)}")
            for idx, vec in zip(image_indices, image_vectors):
                all_embeddings[idx] = vec

        if any(vec is None for vec in all_embeddings):
            missing = sum(1 for vec in all_embeddings if vec is None)
            raise Exception(f"存在未生成向量的块，missing={missing}")

        embeddings: List[List[float]] = [vec for vec in all_embeddings if vec is not None]
        print(f"[RAG导入][Stage] embedding_done vectors={len(embeddings)}")

        # 如果文件已存在：
        # - 同一用户重复导入：需要清理旧 chunks
        # - 不同用户同一路径：不能直接按 source 删除（会误删对方数据）
        # 注意：索引现在是按 index_key（含 owner）存的，不能再用 file_str 直接查
        existing_entry = self.document_index.get(index_key)
        if existing_entry:
            existing_owner = existing_entry.get("owner")
            if owner is None or existing_owner == owner:
                # 只有在“同一 owner（或无 owner 概念的旧数据）”时才清理
                old_source_key = existing_entry.get("source_key") or self._make_source_key(
                    existing_entry.get("physical_path") or file_str,
                    existing_owner,
                )
                self.vector_store.delete_by_source(old_source_key)
            else:
                # 不同 owner：不删除，后续会用 owner 隔离的 source_key 写入
                pass

        if progress_callback:
            progress_callback(80, "indexing")
        # 添加到向量数据库
        print(f"[RAG导入][Stage] vector_add_start docs={len(documents)} vectors={len(embeddings)}")
        self.vector_store.add_documents(documents, embeddings)
        print("[RAG导入][Stage] vector_add_done")

        # 更新索引
        # 对于文本文档（.doc/.docx/.txt/.md），没有页面概念，统一设置为0
        page_numbers = {
            str(doc.metadata.get("page", "0")) for doc in documents if doc.metadata
        }
        # 如果所有文档的page都是0，说明是文本文档，page_count设为1
        if len(page_numbers) == 1 and "0" in page_numbers:
            page_count = 1
        else:
            page_count = len(page_numbers)
        
        existing_entry = self.document_index.get(index_key, {})
        include_flag = existing_entry.get("include_in_search", True)

        # 不再“优先保留旧 owner”。同一路径允许不同用户各自拥有一份索引，
        # 但索引键不能只用 file_str，否则会互相覆盖。
        index_key = self._make_index_key(file_str, owner)

        image_storage_dir = (Config.STORAGE_ROOT / "images" / (owner or "anonymous") / image_doc_id).resolve()
        image_chunk_count = sum(1 for d in documents if str((d.metadata or {}).get("modality", "text")).lower() == "image")

        self.document_index[index_key] = {
            "hash": file_hash,
            "imported_at": datetime.now().isoformat(),
            "chunk_count": len(documents),
            "image_chunk_count": image_chunk_count,
            "file_name": file_path_obj.name,
            "file_size": file_path_obj.stat().st_size,
            "page_count": page_count,  # 使用计算后的page_count（文本文档为1）
            "include_in_search": include_flag,
            "summary": existing_entry.get("summary"),
            "summary_updated_at": existing_entry.get("summary_updated_at"),
            "owner": owner,
            # 记录原始物理路径，便于展示/下载/定位
            "physical_path": file_str,
            # 向量库中的 source（已按 owner 隔离）
            "source_key": source_key,
            # 图片统一存储目录（用于联动清理）
            "image_doc_id": image_doc_id,
            "image_storage_dir": str(image_storage_dir),
        }
        print(f"[RAG导入][Stage] index_save_start key={index_key}")
        self._save_index()
        print("[RAG导入][Stage] index_save_done")

        if progress_callback:
            progress_callback(100, "completed")

        return {
            "status": "success",
            "message": f"成功导入 {len(documents)} 个文档块",
            "file": file_str,
            "chunk_count": len(documents)
        }
    
    def query(
        self,
        question: str,
        top_k: int = 5,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        use_rag: bool = True,  # 新增 RAG 开关参数
        selected_doc_ids: Optional[List[str]] = None,  # 用户选中的文档 ID 列表（优先传 RAG v2 index_key）
        owner: Optional[str] = None,  # 当前用户，用于过滤文档
        use_enhanced_retrieval: bool = False,  # 是否使用增强检索（HyDE + 多路召回 + RRF）
        hyde_weight: float = 0.5,  # HyDE 权重
        use_rrf: bool = True,  # 是否使用 RRF 融合
    ) -> Dict:
        """
        RAG问答 - 支持RAG模式和自由对话模式
        
        Args:
            question: 问题
            top_k: 检索的文档数量
            conversation_history: 对话历史
            llm_config: LLM配置
            use_rag: 是否使用RAG检索（True=RAG模式，False=自由对话模式）
            
        Returns:
            问答结果
        """
        # 构建消息列表（标准 Chat 格式）
        messages = []
        
        # 1. 系统提示词
        if use_rag:
            # RAG 模式：行内沉浸式溯源 System Prompt（极度严格版本）
            messages.append({
                "role": "system",
                "content": """你是一名专业的教育知识助手。请基于【参考资料】回答用户问题。

【核心原则】
1. **优先使用参考资料**：有资料时优先基于资料回答
2. **降级使用通用知识**：资料不足时使用内部知识，并说明"*知识库中未找到特定记录...*"
3. **混合使用**：可以结合资料和专业知识

【引用规范】（极其重要！必须逐字遵守）

## 绝对禁止的行为（违反任何一条都会导致严重后果）：
❌ **禁止大段复制原文**：绝对不要把几百字的原始资料整段粘贴到 `<cite>` 标签内！
❌ **禁止重复标题**：如果资料中有重复的章节标题（如"第 7 章图"、"3.2 节"），忽略它们！
❌ **禁止乱码字符**：如果资料中有破损代码（如 `\pmb{}`、`###`、`***`），自动过滤掉！
❌ **禁止长文本**：`<cite>` 标签内的文字**绝对不能超过 20 个字**！
❌ **禁止文末列表**：绝对不要在回答末尾单独列出参考资料！

## 正确的 `<cite>` 标签格式：
```xml
<cite source="文件名.md" score="0.85">用 10-20 个字高度概括引用内容</cite>
```

### 关键要求（必须严格遵守）：
1. **标签体内只能用 10-20 个字简短概括**，绝不允许复制几百字原文！
2. **只提取核心关键词**，例如：
   - ✅ 正确：`<cite source="红黑树.md" score="0.92">时间复杂度 O(log n)</cite>`
   - ❌ 错误：`<cite source="红黑树.md" score="0.92">红黑树是一种自平衡二叉查找树...（太长！）</cite>`
3. **score 属性必须是纯数字（0-1 之间的小数）**：
   - ✅ 正确：`score="0.85"`
   - ❌ 错误：`score="分数：0.85"`、`score="得分 0.85"`、`score="0.85 分"`
4. **遇到脏数据自动过滤**：
   - 重复标题：如"第 7 章图 第 7 章图" → 直接忽略
   - 破损代码：如"\pmb{\\frac{1}{2}}" → 直接忽略
   - 乱码符号：如"***###" → 直接忽略
5. **标签位置**：紧跟在相关句子后面，句号之前或之后均可

## Few-Shot 示例（严格模仿以下格式）：

### ✅ 优秀示例（学习这种风格）：
```
红黑树是一种自平衡二叉查找树<cite source="红黑树基础.md" score="0.92">O(log n) 时间复杂度</cite>。

它具有五个基本性质<cite source="数据结构.md" score="0.88">节点颜色和路径平衡规则</cite>：
1. 每个节点要么红色要么黑色
2. 根节点必须是黑色
3. 叶子节点都是黑色
4. 红色节点的子节点是黑色
5. 任意节点到叶子的黑色节点数相同

这些特性保证了高效的操作<cite source="算法分析.md" score="0.85">旋转和变色维持平衡</cite>。
```

### ❌ 糟糕示例（绝对不要这样写）：
```
红黑树是一种自平衡二叉查找树<cite source="红黑树基础.md" score="0.92">红黑树是一种自平衡二叉查找树，其查找、插入、删除操作的时间复杂度均为 O(log n)。红黑树具有以下五个基本性质：1.每个节点要么是红色要么是黑色；2.根节点是黑色；3.所有叶子节点是黑色；4.如果一个节点是红色，则它的两个子节点都是黑色；5.对每个节点，从该节点到其所有后代叶子的简单路径都包含相同数目的黑色节点。这些性质保证了红黑树的平衡性...</cite>。（错误：大段复制几百字原文！）

第 7 章图 第 7 章图<cite source="图论.md" score="0.75">###\\pmb{\\frac{1}{2}}***</cite>。（错误：包含重复标题和乱码！）
```

【回答质量要求】
- 准确、清晰、有条理，分点作答
- 适当举例帮助理解
- 基于参考资料深度剖析，不少于 800 字
- 保持友好、专业的语气
- 每个要点都要有充分解释和示例

【重要提醒】
再次强调：`<cite>` 标签内**只能用 10-20 个字概括**，绝不允许大段复制原文！遇到重复标题、乱码字符直接忽略！"""
            })
        else:
            # 自由对话模式：通用助手
            messages.append({
                "role": "system",
                "content": "你是 qwen3.5-plus，一个专业、清晰、务实的中文助手。"
            })

        # 2. 历史对话
        if conversation_history:
            # 取最近 N 轮对话
            recent_history = conversation_history[-Config.CHAT_HISTORY_WINDOW:]
            for msg in recent_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # 确保 role 是标准值
                if role not in ["user", "assistant", "system"]:
                    role = "user"
                
                # 如果是用户消息且当前是RAG模式，需要清理历史消息中的检索上下文
                if role == "user" and use_rag:
                    # 使用更安全的方式提取纯问题部分（去掉检索上下文）
                    context_marker = "【参考资料】"
                    question_marker = "问题："
                    if context_marker in content and question_marker in content:
                        # 找到问题标记的位置，提取其后的内容
                        question_start = content.find(question_marker)
                        if question_start != -1:
                            content = content[question_start + len(question_marker):].strip()
                
                messages.append({"role": role, "content": content})

        # 3. 当前问题处理
        if use_rag:
            # 【关键修复】查询重写：结合对话历史进行指代消解（使用系统已有的成熟功能）
            retrieval_query = self._rewrite_query(question, conversation_history)
                    
            print(f"[QueryRewrite] 原问题：{question}")
            print(f"[QueryRewrite] 重写后：{retrieval_query}")
                    
            # 生成查询 embedding（使用重写后的检索查询）
            query_embedding = self.embedding_client.embed_query(retrieval_query)

            # 构建允许参与检索的 source_key 集合（在检索之前就确定，用于限制检索范围）
            # document_index 的 key 是 index_key（user_owner:physical_path）
            # 向量库中的 source 字段存储的是 source_key（也是 user_owner:physical_path 格式）
            # 两者应该一致，所以可以直接使用 index_key 作为 allowed_sources
            
            # 1. 首先根据用户和 include_in_search 过滤
            candidate_sources = {
                index_key: meta
                for index_key, meta in self.document_index.items()
                if meta.get("include_in_search", True) and (owner is None or meta.get("owner") == owner)
            }
            
            # 2. 如果提供了 selected_doc_ids，进一步过滤：只保留选中的文档
            allowed_sources_for_search = None  # 用于传递给检索函数的源列表
            if selected_doc_ids and len(selected_doc_ids) > 0:
                # 将 selected_doc_ids 转换为 index_key 格式（可能是文件名或 source_key）
                selected_index_keys = set()
                
                # 规范化 doc_id：去除可能的路径分隔符差异
                def normalize_for_match(text: str) -> str:
                    """规范化文本用于匹配"""
                    if not text:
                        return ""
                    return text.replace('\\', '/').strip()
                
                # 调试日志：打印匹配过程
                print(f"[RAG] 开始匹配选中的文档，selected_doc_ids: {selected_doc_ids}")
                # print(f"[RAG] candidate_sources 数量: {len(candidate_sources)}")
                # print(f"[RAG] candidate_sources keys (前5个): {list(candidate_sources.keys())[:5]}")
                
                for doc_id in selected_doc_ids:
                    if not doc_id:
                        continue
                    
                    doc_id_normalized = normalize_for_match(doc_id)
                    matched_key = None
                    
                    print(f"[RAG] 尝试匹配 doc_id: {doc_id}")
                    
                    # 方式1：直接匹配 index_key（doc_id 可能是完整的 index_key）
                    # 这是最常见的匹配方式，因为前端传递的 file_path 就是 index_key
                    if doc_id in candidate_sources:
                        matched_key = doc_id
                        print(f"[RAG] 直接匹配成功: {doc_id}")
                    elif doc_id_normalized in candidate_sources:
                        matched_key = doc_id_normalized
                        print(f"[RAG] 规范化后直接匹配成功: {doc_id_normalized}")
                    # 方式1.5：检查是否是 index_key 的变体（处理 user_owner:path 格式）
                    elif ':' in doc_id:
                        # doc_id 可能是 user_owner:path 格式，尝试直接匹配
                        for index_key in candidate_sources.keys():
                            if doc_id == index_key or doc_id_normalized == normalize_for_match(index_key):
                                matched_key = index_key
                                print(f"[RAG] 通过 index_key 格式匹配成功: {doc_id} -> {index_key}")
                                break
                    else:
                        # 方式2：通过 physical_path 和 file_name 匹配
                        for index_key, meta in candidate_sources.items():
                            physical_path = meta.get("physical_path", "")
                            file_name = meta.get("file_name", "")
                            
                            # 规范化路径用于匹配
                            physical_path_norm = normalize_for_match(physical_path)
                            file_name_norm = normalize_for_match(file_name)
                            
                            # 检查多种匹配方式
                            if (doc_id == physical_path or 
                                doc_id_normalized == physical_path_norm or
                                doc_id == file_name or
                                doc_id_normalized == file_name_norm or
                                # 检查文件名是否包含在 doc_id 中（处理带前缀的情况）
                                (file_name and file_name in doc_id) or
                                (file_name_norm and file_name_norm in doc_id_normalized) or
                                # 检查 physical_path 的文件名部分
                                (physical_path and Path(physical_path).name in doc_id) or
                                # 检查 doc_id 是否是 index_key 的一部分
                                (doc_id in index_key or index_key in doc_id)):
                                matched_key = index_key
                                print(f"[RAG] 通过路径/文件名匹配成功: {doc_id} -> {index_key}")
                                break
                    
                    if matched_key:
                        selected_index_keys.add(matched_key)
                    else:
                        print(f"[RAG] 警告：无法匹配 doc_id: {doc_id}")
                
                print(f"[RAG] 匹配结果: {len(selected_index_keys)} 个文档被选中")
                print(f"[RAG] selected_index_keys: {list(selected_index_keys)}")
                
                # 只保留选中的文档
                if selected_index_keys:
                    # 构建 allowed_sources_for_search：包含 index_key 和对应的 source_key
                    # 这些将用于限制检索范围（只检索这些文档的chunks）
                    allowed_sources_for_search = []
                    for index_key in selected_index_keys:
                        allowed_sources_for_search.append(index_key)
                        meta = candidate_sources.get(index_key, {})
                        source_key = meta.get("source_key")
                        if source_key and source_key != index_key:
                            allowed_sources_for_search.append(source_key)
                    print(f"[RAG] 限制检索范围：只检索 {len(selected_index_keys)} 个选中的文档")
                else:
                    # 如果没有匹配到任何文档，返回空结果（不检索任何文档）
                    print(f"[RAG] 警告：没有匹配到任何文档，返回空结果")
                    allowed_sources_for_search = []
            else:
                # 如果没有提供 selected_doc_ids，使用所有 include_in_search=True 的文档
                allowed_sources_for_search = []
                for index_key, meta in candidate_sources.items():
                    allowed_sources_for_search.append(index_key)
                    source_key = meta.get("source_key")
                    if source_key and source_key != index_key:
                        allowed_sources_for_search.append(source_key)
                print(f"[RAG] 未提供 selected_doc_ids，使用所有符合条件的文档: {len(candidate_sources)} 个")
            
            # 混合检索：结合向量检索和关键词检索
            # 关键词检索权重：40%，向量检索权重：60%
            # 这样可以提高对特定关键词的精确匹配能力，同时保持语义理解能力
            # 重要：如果指定了 allowed_sources_for_search，只在这些文档中检索
                        
            if use_enhanced_retrieval:
                # 增强检索模式：HyDE + 多路召回 + RRF 融合 + Rerank 精排
                print(f"[RAG] 使用增强检索模式：HyDE + 多路召回 + RRF")
                retrieved_docs = self.vector_store.enhanced_hybrid_search_with_hyde(
                    query=retrieval_query,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    distance_threshold=1.5,
                    keyword_weight=0.4,
                    vector_weight=0.6,
                    use_hyde=True,  # 启用 HyDE
                    hyde_weight=hyde_weight,  # HyDE 权重
                    use_rrf=use_rrf,  # 使用 RRF 融合
                    allowed_sources=allowed_sources_for_search,
                    rerank_enabled=True,  # 启用 Rerank
                    rag_system=self,  # 传入 RAGSystem 实例
                )
            else:
                # 传统混合检索模式
                print(f"[RAG] 使用传统混合检索模式")
                retrieved_docs = self.vector_store.hybrid_search(
                    query=retrieval_query,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    distance_threshold=1.5,
                    keyword_weight=0.4,  # 关键词检索占比 40%
                    vector_weight=0.6,    # 向量检索占比 60%
                    allowed_sources=allowed_sources_for_search  # 限制检索范围
                )

            
            # 构建 allowed_sources 用于后续过滤（双重保险）
            if selected_doc_ids and len(selected_doc_ids) > 0:
                # 使用之前匹配的 selected_index_keys
                allowed_sources = set(selected_index_keys)
                # 同时添加对应的 source_key
                for index_key in selected_index_keys:
                    meta = candidate_sources.get(index_key, {})
                    source_key = meta.get("source_key")
                    if source_key:
                        allowed_sources.add(source_key)
            else:
                allowed_sources = set(candidate_sources.keys())
                for index_key, meta in candidate_sources.items():
                    source_key = meta.get("source_key")
                    if source_key:
                        allowed_sources.add(source_key)

            # 过滤：只保留在 allowed_sources 中的文档（双重保险）
            # 重要：同时检查文档是否在 document_index 中（防止已删除的文档参与检索）
            # 注意：retrieved_docs 已经去重和按相似度排序，这里只需要过滤权限和选中状态
            print(f"[RAG] 检索到的文档数: {len(retrieved_docs)}")
            # print(f"[RAG] 允许的文档源数: {len(allowed_sources)}")
            # print(f"[RAG] document_index 中的文档数: {len(self.document_index)}")
            # print(f"[RAG] allowed_sources (前5个): {list(allowed_sources)[:5]}")

            filtered_docs: List[Dict] = []
            for doc in retrieved_docs:
                doc_source = doc["metadata"].get("source")
                            
                # 匹配逻辑：doc_source 可能直接是 index_key，也可能是 source_key
                # 需要检查多种匹配方式
                matched = False
                matched_key = None
                
                # 方式1：直接匹配
                if doc_source in allowed_sources:
                    matched = True
                    matched_key = doc_source
                else:
                    # 方式2：检查 document_index 中的 source_key
                    # 向量库中的 source 应该等于 document_index 中的 source_key
                    for index_key in allowed_sources:
                        meta = self.document_index.get(index_key, {})
                        source_key = meta.get("source_key")
                        # 如果 doc_source 匹配 source_key，则认为匹配
                        if source_key and doc_source == source_key:
                            matched = True
                            matched_key = index_key
                            break
                        # 如果 doc_source 匹配 index_key，也认为匹配（因为 source_key 应该等于 index_key）
                        if doc_source == index_key:
                            matched = True
                            matched_key = index_key
                    break

                if matched:
                    # 额外检查：确保文档确实在 document_index 中（防止已删除的文档）
                    if matched_key in self.document_index:
                        meta = self.document_index[matched_key]
                        # 再次检查 include_in_search 和 owner（双重保险）
                        if (meta.get("include_in_search", True) and 
                            (owner is None or meta.get("owner") == owner)):
                            filtered_docs.append(doc)
                        else:
                            pass  # 文档被过滤
                    else:
                        # 文档不在 document_index 中，说明已被删除，不应该参与检索
                        pass  # 已过滤
                else:
                    pass  # 文档被过滤
                # 不需要提前 break，因为 retrieved_docs 已经去重，不会重复

            print(f"[RAG] 过滤后的文档数: {len(filtered_docs)}")
            
            # 如果过滤后没有结果，说明所有文档都被禁用了，返回空结果而不是使用未过滤的结果
            # 这样可以确保用户明确知道哪些文档参与检索
            if not filtered_docs:
                # 不返回未过滤的结果，而是返回空列表，让用户知道没有文档参与检索
                print(f"[RAG] 警告：过滤后没有结果，可能的原因：")
                print(f"[RAG] 1. 选中的文档ID与向量库中的source不匹配")
                print(f"[RAG] 2. 文档未被导入到向量库")
                print(f"[RAG] 3. 文档的 include_in_search=False")
                print(f"[RAG] 4. 文档已被删除（不在 document_index 中）")
                filtered_docs = []

            # 不需要再次截取，因为 search 方法已经动态调整了数量
            selected_docs = filtered_docs
            
            # ========== 任务三：清洗检索结果中的脏数据 ==========
            # 在构建 Context 之前，先清洗每个文档的 content
            import re as regex_module
            for doc in selected_docs:
                original_content = doc.get("content", "")
                if original_content:
                    cleaned_content = original_content
                    
                    # 1. 移除重复的章节标题（如"7.1 图的定义和术语"重复出现）
                    # 匹配模式：数字 + 点 + 中文标题，连续出现多次
                    repeat_header_pattern = r'([\d\.]+\s*[\u4e00-\u9fa5]+[^\n]*)(\s*\n?\s*\1)+'
                    cleaned_content = regex_module.sub(repeat_header_pattern, r'\1', cleaned_content)
                    
                    # 2. 移除 LaTeX 数学公式乱码（如 \pmb{...}, \frac{...}{...}）
                    latex_pattern = r'\\(pmb|frac|sqrt|sum|prod|int|left|right|begin|end)\{[^}]*\}'
                    cleaned_content = regex_module.sub(latex_pattern, '', cleaned_content)
                    
                    # 3. 移除连续的特殊符号（如 ***、##、=== 等）
                    special_chars_pattern = r'[*#=]{3,}'
                    cleaned_content = regex_module.sub(special_chars_pattern, '', cleaned_content)
                    
                    # 4. 移除重复的短句（同一句话连续出现 2 次以上）
                    repeat_sentence_pattern = r'([^。！？\.!?]{10,50})([。！？\.!?])\s*\1+'
                    cleaned_content = regex_module.sub(repeat_sentence_pattern, r'\1\2', cleaned_content)
                    
                    # 5. 移除包含乱码的整行（如果一行中乱码字符超过 50%）
                    lines = cleaned_content.split('\n')
                    clean_lines = []
                    for line in lines:
                        if len(line.strip()) < 5:  # 跳过空行或极短的行
                            continue
                        # 计算乱码字符比例（LaTeX 命令、特殊符号等）
                        messy_chars = len(regex_module.findall(r'[\\{}\[\]_*#]', line))
                        total_chars = len(line)
                        if total_chars > 0 and messy_chars / total_chars < 0.3:  # 乱码比例低于 30% 才保留
                            clean_lines.append(line)
                    cleaned_content = '\n'.join(clean_lines)
                    
                    # 6. 压缩多余的空白字符
                    cleaned_content = regex_module.sub(r'\s+', ' ', cleaned_content).strip()
                    
                    # 更新文档内容
                    doc["content"] = cleaned_content
                    
                    # 打印清洗日志
                    if len(original_content) != len(cleaned_content):
                        print(f"[脏数据清洗] 文档来源：{doc.get('metadata', {}).get('source', 'unknown')}")
                        print(f"  - 原始长度：{len(original_content)} 字符")
                        print(f"  - 清洗后长度：{len(cleaned_content)} 字符")
                        print(f"  - 删除比例：{(1 - len(cleaned_content)/len(original_content))*100:.1f}%")
            # =======================================================

            # 构建知识库上下文（任务二：行内沉浸式溯源）
            kb_context_parts = []
            for idx, doc in enumerate(selected_docs, start=1):
                metadata = doc.get("metadata") or {}
                source_name = metadata.get("document_name") or Path(metadata.get("source", "unknown")).name
                content = doc.get("content", "")
                
                # 为每段参考资料添加编号和详细信息（用于 LLM 引用）
                # 注意：不再使用 [1] 这种尾注格式，而是提供完整的引用信息
                context_entry = f"【资料 {idx}】\n文件名：{source_name}\n内容：{content}"
                kb_context_parts.append(context_entry)
            
            kb_context = "\n\n".join(kb_context_parts)
            image_docs = [
                doc for doc in selected_docs
                if str((doc.get("metadata") or {}).get("modality", "text")).lower() == "image"
                and (doc.get("metadata") or {}).get("image_path")
            ]


            # 构建带检索上下文的问题
            # 即使没有检索结果，也允许模型基于自己的知识回答
            if kb_context:
                context_text = f"""【参考资料】
以下是从知识库中检索到的相关内容，请优先参考这些资料，但可以基于你的专业知识进行补充和扩展：

{kb_context}

---
请基于以上参考资料回答用户问题。注意：
1. 引用资料时请使用 <cite source="文件名.md" score="0.XX">原文片段</cite> 标签
2. 标签紧跟在相关句子后面，不要统一放在文末
3. 可以适当补充专业知识使回答更完整"""
            else:
                if not filtered_docs:
                    context_text = "【提示】当前没有文档参与检索，但你可以基于你的专业知识回答用户的问题。\n\n"
                else:
                    context_text = "【提示】未找到相关参考资料，请基于你的专业知识回答用户的问题。\n\n"

            final_user_text = f"{context_text}问题：{question}"

            # 多模态：将检索到的图片作为上下文一并提供给模型
            image_payloads = []
            for img_doc in image_docs[:3]:
                meta = img_doc.get("metadata") or {}
                img_path = str(meta.get("image_path") or "").strip()
                if not img_path:
                    continue
                try:
                    data_url = self.embedding_client._encode_image_to_data_url(img_path)
                    image_payloads.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        }
                    )
                except Exception as e:
                    print(f"[RAG] 图片上下文编码失败: {img_path}, err={e}")

            if image_payloads:
                final_user_content: Any = [
                    {
                        "type": "text",
                        "text": final_user_text + "\n\n请结合以上图片内容进行理解与作答。",
                    },
                    *image_payloads,
                ]
            else:
                final_user_content = final_user_text

            messages.append({"role": "user", "content": final_user_content})
            
            # 格式化检索结果（支持图文混合上下文）
            formatted_sources = []
            retrieval_metrics = None  # 初始化检索指标
            
            for idx, doc in enumerate(selected_docs):
                metadata = doc.get("metadata") or {}
                raw_source = metadata.get("source", "unknown")
                source_name = metadata.get("document_name")
                if not source_name and raw_source not in ("unknown", None):
                    source_name = Path(raw_source).name

                modality = str(metadata.get("modality", "text")).lower()
                image_path = metadata.get("image_path")
                image_name = metadata.get("image_name")
                image_alt = metadata.get("image_alt")
                image_width = metadata.get("image_width")
                image_height = metadata.get("image_height")

                image_url = None
                if modality == "image" and image_path:
                    image_url = f"/api/rag/image?path={quote(str(image_path), safe='')}"

                # ========== 任务一：提取检索指标 ==========
                # 从第一个文档中提取 retrieval_metrics
                if idx == 0 and "retrieval_metrics" in doc:
                    retrieval_metrics = doc["retrieval_metrics"]
                    print(f"[检索指标] 提取成功：{retrieval_metrics}")
                # ===========================================

                # 打印每个文档的得分信息
                rerank_score = doc.get("rerank_score")
                vector_score = doc.get("vector_score")
                combined_score = doc.get("combined_score")
                if rerank_score is not None:
                    print(f"[文档 {idx+1}] {source_name}: Rerank 分数={rerank_score:.4f}")
                else:
                    print(f"[文档 {idx+1}] {source_name}: 向量分数={vector_score:.4f if vector_score else 'N/A'}, 融合分数={combined_score:.4f if combined_score else 'N/A'}")

                formatted_sources.append(
                    {
                        "content": doc.get("content", "")[:300],
                        "source": source_name or "未知文档",
                        "source_path": raw_source,
                        "page": metadata.get("page", 0),
                        "distance": doc.get("distance"),
                        "modality": modality,
                        "image_path": image_path,
                        "image_url": image_url,
                        "image_name": image_name,
                        "image_alt": image_alt,
                        "image_width": image_width,
                        "image_height": image_height,
                        # 添加分数信息，便于前端展示
                        "rerank_score": rerank_score,
                        "vector_score": vector_score,
                        "combined_score": combined_score
                    }
                )
        else:
            # 自由对话模式：直接使用用户问题，不进行检索
            messages.append({"role": "user", "content": question})
            formatted_sources = []  # 自由对话模式没有检索结果
        
        # 调用LLM
        answer = self._call_llm(messages=messages, llm_config=llm_config)
        
        # 返回结果
        return {
            "question": question,
            "answer": answer,
            "sources": formatted_sources,
            # 返回纯净的问答对，供调用方维护对话历史
            "clean_question": question,  # 纯问题，不包含检索上下文
            "clean_answer": answer,      # 答案
            # ========== 任务一：检索质量量化 ==========
            "retrieval_metrics": retrieval_metrics
            # ===========================================
        }
    
    def _call_llm(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        preferred_model: Optional[str] = None,
        stream: bool = False,
    ):
        """
        调用LLM生成回答

        Args:
            prompt: 提示词（单条模式）
            messages: 消息列表（对话模式，优先使用）
            stream: 是否使用流式输出

        Returns:
            LLM生成的回答（非流式）或生成器（流式）
        """
        # 模型选择优先级：显式参数 > llm_config > 默认模型
        model_name = preferred_model or (llm_config or {}).get("model_name") or self.llm_model
        api_key_override = (llm_config or {}).get("api_key")
        api_base_override = (llm_config or {}).get("api_base")

        # 处理API Base URL
        api_base = (api_base_override or self.api_base or "").rstrip("/")
        # 如果API base不包含/v1，则添加
        if not api_base.endswith("/v1"):
            api_base = api_base + "/v1"

        url = f"{api_base}/chat/completions"
        headers = {"Content-Type": "application/json"}
        api_key = api_key_override or self.api_key
        # 设置Authorization header（如果提供了API key）
        if api_key and api_key != "dummy-key":
            headers["Authorization"] = f"Bearer {api_key}"

        # 构造消息列表
        final_messages = []
        if messages:
            final_messages = messages
        elif prompt:
            final_messages = [{"role": "user", "content": prompt}]
        else:
            raise ValueError("必须提供 prompt 或 messages")

        payload = {
            "model": model_name,
            "messages": final_messages,
            "temperature": 0.4,
            "max_tokens": 4096,
            "stream": stream,
        }
        print(
            "[rag_llm_debug] "
            f"model={model_name} base={api_base} stream={stream} "
            f"msg_count={len(final_messages)} max_tokens={payload['max_tokens']}"
        )

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=360, stream=stream)

            if stream:
                # 流式输出：返回生成器
                def generate():
                    for line in response.iter_lines():
                        if line:
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]
                                if data_str.strip() == '[DONE]':
                                    break
                                try:
                                    data = json.loads(data_str)
                                    delta = data.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except json.JSONDecodeError:
                                    continue
                return generate()
            else:
                # 非流式输出
                if response.status_code == 200:
                    data = response.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                raise Exception(f"LLM API错误: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"调用LLM失败: {str(e)}")
    
    def list_documents(self, owner: Optional[str] = None) -> List[Dict]:
        """列出已索引文档
        
        Args:
            owner: 如果提供，则仅返回该用户拥有的文档
        """
        documents: List[Dict] = []
        for file_path, metadata in self.document_index.items():
            # 如果指定了owner，则只返回该用户的文档
            if owner is not None and metadata.get("owner") != owner:
                continue
            documents.append(
                {
                    "file_path": file_path,
                    "file_name": metadata.get("file_name") or Path(file_path).name,
                    "include_in_search": metadata.get("include_in_search", True),
                    "chunk_count": metadata.get("chunk_count", 0),
                    "image_chunk_count": metadata.get("image_chunk_count", 0),
                    "imported_at": metadata.get("imported_at"),
                    "summary": metadata.get("summary"),
                    "summary_updated_at": metadata.get("summary_updated_at"),
                    "file_size": metadata.get("file_size"),
                    "page_count": metadata.get("page_count"),
                    "hash": metadata.get("hash"),
                    "owner": metadata.get("owner"),
                    # 网页来源相关字段
                    "source_url": metadata.get("source_url"),
                    "source_title": metadata.get("source_title"),
                    "source_domain": metadata.get("source_domain"),
                }
            )
        documents.sort(key=lambda item: item.get("imported_at") or "", reverse=True)
        return documents

    def update_document_participation(self, file_path: str, include: bool, owner: Optional[str] = None) -> Dict:
        """设置文档是否参与检索
        
        Args:
            file_path: 文档路径（可能是物理路径或 index_key）
            include: 是否参与检索
            owner: 文档所有者（可选，用于从物理路径推导 index_key）
        """
        # 兼容：file_path 可能是物理路径，也可能是 index_key
        index_key = self._make_index_key(file_path, owner)
        if index_key not in self.document_index:
            # 如果没找到，尝试直接使用传入的路径作为 key（兼容性处理）
            if str(file_path) not in self.document_index:
                raise FileNotFoundError(f"未找到索引文档: {file_path}")
            index_key = str(file_path)
        
        self.document_index[index_key]["include_in_search"] = include
        self._save_index()
        return {
            "file_path": index_key,
            "include_in_search": include,
        }

    def get_document_details(self, file_path: str, sample_limit: int = 5) -> Dict:
        """获取文档详情及示例片段"""
        record = self.document_index.get(file_path)
        if record is None:
            raise FileNotFoundError(f"未找到索引文档: {file_path}")

        # 向量库中的 chunks 是按 source_key（含 owner）存储的
        source_key = record.get("source_key") or self._make_source_key(
            record.get("physical_path") or file_path,
            record.get("owner"),
        )
        documents = self.vector_store.get_documents_by_source(source_key)
        samples = []
        for doc in documents[:sample_limit]:
            metadata = doc.get("metadata") or {}
            image_path = metadata.get("image_rel_path")
            if not image_path and metadata.get("image_path"):
                try:
                    candidate = Path(str(metadata.get("image_path")))
                    if candidate.is_absolute():
                        image_path = candidate.resolve().relative_to(Config.STORAGE_ROOT.resolve()).as_posix()
                    else:
                        image_path = candidate.as_posix()
                except ValueError:
                    image_path = None
            samples.append(
                {
                    "content": doc["content"],
                    "page": metadata.get("page"),
                    "id": doc.get("id"),
                    "modality": metadata.get("modality", "text"),
                    "image_path": image_path,
                }
            )

        # 对外优先返回索引 key，避免暴露宿主机物理路径
        display_path = file_path

        image_chunk_count = sum(
            1 for d in documents if str((d.get("metadata") or {}).get("modality", "text")).lower() == "image"
        )
        text_chunk_count = max(0, len(documents) - image_chunk_count)

        return {
            "file_path": display_path,
            "file_name": record.get("file_name") or Path(display_path).name,
            "summary": record.get("summary"),
            "imported_at": record.get("imported_at"),
            "chunk_count": record.get("chunk_count", 0),
            "text_chunk_count": text_chunk_count,
            "image_chunk_count": image_chunk_count,
            "include_in_search": record.get("include_in_search", True),
            "file_size": record.get("file_size"),
            "page_count": record.get("page_count"),
            "samples": samples,
        }

    def summarize_document(self, file_path: str, force_refresh: bool = False, owner: Optional[str] = None) -> Dict:
        """生成或获取文档摘要（带缓存，写入 document_index 并持久化到 JSON）

        Args:
            file_path: 前端传入的路径，可能是物理路径，也可能是 index_key（user_<owner>:<path>）
            force_refresh: 是否强制重新生成
            owner: 当前用户（可选，用于从物理路径推导 index_key）
        """
        # 兼容：前端可能传物理路径，也可能传 index_key
        index_key = self._make_index_key(file_path, owner)
        record = self.document_index.get(index_key)
        if record is None and str(file_path).startswith("user_"):
            # 如果本身就是 index_key，则再试一次原样
            index_key = str(file_path)
            record = self.document_index.get(index_key)
        if record is None:
            raise FileNotFoundError(f"未找到索引文档: {file_path}")

        # 返回缓存的摘要（如果有且不需要强制刷新）
        if record.get("summary") and not force_refresh:
            return {
                "file_path": index_key,
                "summary": record.get("summary"),
                "summary_updated_at": record.get("summary_updated_at"),
            }

        # 向量库中的 chunks 是按 source_key（含 owner）存储的
        source_key = record.get("source_key") or self._make_source_key(
            record.get("physical_path") or file_path,
            record.get("owner") or owner,
        )
        documents = self.vector_store.get_documents_by_source(source_key)
        if not documents:
            raise ValueError("文档内容缺失，无法生成摘要")

        # 按 page 排序，确保内容顺序正确
        documents.sort(key=lambda x: int(x.get("metadata", {}).get("page", 0)))
        full_text = "\n\n".join([doc.get("content", "") for doc in documents if doc.get("content")])

        # 长文本防爆：避免超大教材一次性塞入导致超时/上下文溢出
        max_chars = int(os.getenv("RAG_SUMMARY_MAX_CHARS", "40000"))
        if len(full_text) > max_chars:
            print(f"[RAG摘要] 文本超长 ({len(full_text)} 字符)，触发安全截断到 {max_chars}")
            full_text = full_text[:max_chars] + "\n\n...（后文由于长度限制已安全截断）"

        file_name = record.get("file_name") or Path(record.get("physical_path") or file_path).name
        file_size_kb = (record.get("file_size") or 0) // 1024
        page_count = record.get("page_count") or "未知"

        prompt = f"""你是一位专业的教学文档分析专家。请仔细阅读以下文档内容，并生成一份全面、结构化的摘要。

# 文档信息
- 文档名称: {file_name}
- 文档大小: {file_size_kb} KB
- 页数: {page_count}

# 截取文档内容
{full_text}

# 摘要要求
请按照以下结构生成摘要（使用 Markdown 格式）：

## 1. 核心主题
用 1-2 句话总结文档的核心主题和目的。

## 2. 主要内容
按逻辑顺序列出文档的主要部分（3-5 个），每个部分简要说明其关键内容。

## 3. 知识要点
提取文档中的关键知识点或概念（5-8 个），每个要点用一句话概括。

## 4. 教学价值
分析文档在教学中的适用场景、目标受众和使用建议。

## 5. 难度评估
评估文档的难度级别（初级/中级/高级），并说明理由。

# 注意事项
- 摘要应准确反映文档的核心脉络
- 语言简洁明了，逻辑清晰
- 确保摘要对教师和学生都有参考价值

请开始生成摘要："""

        try:
            # 显式使用 deep 配置：确保 qwen3.5-plus 走官方通道，而不是默认路由
            deep_model_cfg = Config.get_deep_model()
            summary = self._call_llm(
                prompt,
                llm_config=deep_model_cfg,
                preferred_model=deep_model_cfg.get("model_name") or self.summary_model,
            )

            timestamp = datetime.now().isoformat()
            record["summary"] = summary
            record["summary_updated_at"] = timestamp
            self.document_index[index_key] = record
            self._save_index()

            return {
                "file_path": index_key,
                "summary": summary,
                "summary_updated_at": timestamp,
            }
        except Exception as e:
            print(f"[RAG摘要] 调用大模型失败: {e}")
            raise Exception(f"生成摘要失败: {str(e)}")

    def get_stats(self) -> Dict:
        """获取系统统计信息"""
        return {
            "document_count": self.vector_store.get_document_count(),
            "indexed_files": len(self.document_index),
            "indexed_files_list": list(self.document_index.keys())
        }
    
    def delete_document(self, file_path: str, owner: Optional[str] = None):
        """删除文档（按 owner 隔离）
        
        Args:
            file_path: 物理文件路径（绝对路径）
            owner: 文档所属用户；提供时只删除该用户的数据
        """
        source_key = self._make_source_key(file_path, owner)
        index_key = self._make_index_key(file_path, owner)

        # 从向量数据库删除：使用隔离后的 source_key，避免误删其他用户 chunk
        deleted_count = self.vector_store.delete_by_source(source_key)
        print(f"[RAG] 从向量库删除文档: source_key={source_key}, 删除了 {deleted_count} 个chunks")

        record = self.document_index.get(index_key)

        # 联动清理图片目录
        image_storage_dir = (record or {}).get("image_storage_dir")
        if image_storage_dir:
            try:
                shutil.rmtree(image_storage_dir, ignore_errors=True)
                print(f"[RAG] 已清理图片目录: {image_storage_dir}")
            except Exception as e:
                print(f"[RAG] 清理图片目录失败: {image_storage_dir}, err={e}")

        # 从索引中删除：使用隔离后的 index_key
        if index_key in self.document_index:
            del self.document_index[index_key]
            self._save_index()
            print(f"[RAG] 从索引删除文档: index_key={index_key}")
        else:
            print(f"[RAG] 警告：索引中未找到文档: index_key={index_key}")
