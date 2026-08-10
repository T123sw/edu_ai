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
import threading
import zipfile
import uuid
from urllib.parse import unquote, quote
from typing import List, Dict, Optional, Any, Union, Callable
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as ET
from langchain_core.documents import Document
import chromadb
from chromadb.config import Settings
from .core.config import Config
from modules.rag_v2.document_resolver import resolve_rag_document
from app.services.knowledge_ingestion.structural_chunker import (
    CHUNKER_VERSION,
    StructuralChunker,
)
from app.services.runtime_config_resolver import runtime_config_resolver

# MinerU 解析已迁移为「直连 MinerU Cloud」provider（见 docs/spec/SPEC-03）。
# 不再依赖本地 mineru CLI；可用性 = provider 是否配置了 API key。
def _check_mineru_available() -> bool:
    """MinerU（云端）是否可用 = provider 是否配置了 API key。"""
    try:
        from app.integrations.pdf import get_pdf_parser

        parser = get_pdf_parser()
        return bool(getattr(parser, "is_configured", lambda: True)())
    except Exception:
        return False


def _owner_can_access_document(
    metadata: Dict[str, Any],
    owner: Optional[str],
    course_id: Optional[str] = None,
) -> bool:
    normalized_course_id = str(course_id or "").strip()
    document_course_id = str(metadata.get("course_id") or "").strip()
    library_type = str(metadata.get("library_type") or "").strip().lower()
    if normalized_course_id and library_type == "course":
        return document_course_id == normalized_course_id

    if owner is None:
        return True

    record_owner = metadata.get("owner")
    if record_owner is None:
        return True

    if isinstance(record_owner, str) and not record_owner.strip():
        return True

    return record_owner == owner


def _match_allowed_source(
    document_index: Dict[str, Dict[str, Any]],
    allowed_sources: set[str],
    doc_source: Optional[str],
) -> Optional[str]:
    if not doc_source:
        return None

    if doc_source in allowed_sources and doc_source in document_index:
        return doc_source

    for index_key in allowed_sources:
        meta = document_index.get(index_key)
        if not meta:
            continue
        source_key = meta.get("source_key")
        if source_key and doc_source == source_key:
            return index_key
        if doc_source == index_key:
            return index_key

    if doc_source in allowed_sources:
        return doc_source

    return None


def _expand_parent_context(
    document_index: Dict[str, Dict[str, Any]],
    doc: Dict[str, Any],
    index_key: str,
) -> Dict[str, Any]:
    """Expand a retrieved child to its persisted parent without changing rank metadata."""
    expanded = doc.copy()
    expanded["retrieved_content"] = str(doc.get("content") or "").strip()
    metadata = (doc.get("metadata") or {}).copy()
    expanded["metadata"] = metadata
    if str(metadata.get("modality", "text")).lower() == "image":
        return expanded
    parent_id = str(metadata.get("parent_id") or "")
    parent_entry = ((document_index.get(index_key) or {}).get("parent_chunks") or {}).get(parent_id)
    if not isinstance(parent_entry, dict):
        return expanded
    parent_content = str(parent_entry.get("content") or "").strip()
    if not parent_content:
        return expanded
    heading_path = str(parent_entry.get("heading_path") or metadata.get("heading_path") or "")
    prefix = f"【章节上下文】: {heading_path}\n\n" if heading_path else ""
    expanded["content"] = f"{prefix}{parent_content}".strip()
    metadata["context_expanded"] = "parent"
    return expanded


def _retrieved_display_content(doc: Dict[str, Any]) -> str:
    """Return the exact child hit for source tracing, without embedding-only context."""
    content = str(doc.get("retrieved_content") or doc.get("content") or "")
    normalized = re.sub(r"\r\n?", "\n", content).strip()
    return re.sub(
        r"^【章节上下文】\s*[:：]\s*[^\n]*\n+",
        "",
        normalized,
        count=1,
    ).strip()

MINERU_AVAILABLE = _check_mineru_available()
if MINERU_AVAILABLE:
    print("[MinerU] 已启用 MinerU Cloud（直连远程 API）用于 PDF 解析")
else:
    print("[WARNING] 未配置 MinerU Cloud API key，PDF 导入将直接失败")

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
        runtime_embedding = runtime_config_resolver.resolve("embedding")
        runtime_override = (
            runtime_embedding
            if runtime_embedding.get("_source") in {"user", "system"}
            else {}
        )
        self.backend = (backend or os.getenv("EMBEDDING_BACKEND", "gemini")).lower()
        if self.backend not in {"gemini", "openai"}:
            raise ValueError(f"当前仅支持 EMBEDDING_BACKEND=gemini/openai，收到: {self.backend}")

        base = (
            runtime_override.get("base_url")
            or os.getenv("EMBEDDING_API_BASE")
            or api_base
            or getattr(Config, "EMBEDDING_API_BASE", "")
            or getattr(Config, "OPENROUTER_BASE_URL", "")
        ).rstrip("/")
        if base and not base.endswith("/v1"):
            base = f"{base}/v1"

        self.api_base = base
        # embedding 优先使用独立密钥，默认回落到 OpenRouter key
        self.api_key = (
            runtime_override.get("api_key")
            or os.getenv("EMBEDDING_API_KEY")
            or api_key
            or getattr(Config, "OPENROUTER_API_KEY", "")
            or "dummy-key"
        )
        self.model = (
            runtime_override.get("model")
            or model
            or os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")
        )

        self.timeout_sec = int(
            runtime_override.get("timeout_seconds")
            or os.getenv(
                "EMBEDDING_TIMEOUT_SEC",
                str(getattr(Config, "EMBEDDING_TIMEOUT_SEC", 120)),
            )
        )
        self.max_retries = int(os.getenv("EMBEDDING_MAX_RETRIES", str(getattr(Config, "EMBEDDING_MAX_RETRIES", 3))))
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", str(getattr(Config, "EMBEDDING_BATCH_SIZE", 64))))
        self.max_workers = int(os.getenv("EMBEDDING_MAX_WORKERS", str(getattr(Config, "EMBEDDING_MAX_WORKERS", 4))))
        self.gemini_dimensions = int(
            runtime_override.get("dimensions")
            or os.getenv(
                "GEMINI_EMBEDDING_DIMENSIONS",
                str(getattr(Config, "GEMINI_EMBEDDING_DIMENSIONS", 0)),
            )
        )

    def _post_embeddings_batch(self, batch_texts: List[str]) -> List[List[float]]:
        """调用 OpenAI-compatible /embeddings，支持重试与退避。"""
        if not self.api_base:
            raise ValueError("EMBEDDING_API_BASE 未配置")

        # 空输入显式替换；长度必须由统一结构化分块器控制，禁止在此静默截断，
        # 否则索引内容与预览内容不一致，且长块尾部永远无法被召回。
        safe_texts: List[str] = []
        empty_count = 0
        for t in batch_texts:
            s = str(t or "").strip()
            if not s:
                empty_count += 1
                s = "[EMPTY_CHUNK]"
            safe_texts.append(s)
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
        allowed_sources: Optional[List[str]] = None,  # 允许检索的文档源列表（如果提供，只检索这些文档）
        modality_filter: Optional[str] = None,
        knowledge_node_ids: Optional[List[str]] = None,
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
        def build_where(source_condition: Optional[Any] = None) -> Optional[Dict[str, Any]]:
            conditions: List[Dict[str, Any]] = []
            if source_condition is not None:
                conditions.append({"source": source_condition})
            if modality_filter:
                conditions.append({"modality": modality_filter})
            nodes = sorted({str(value) for value in (knowledge_node_ids or []) if str(value)})
            if len(nodes) == 1:
                conditions.append({"knowledge_node_id": nodes[0]})
            elif nodes:
                conditions.append({"knowledge_node_id": {"$in": nodes}})
            if not conditions:
                return None
            return conditions[0] if len(conditions) == 1 else {"$and": conditions}

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
                where_condition = build_where(unique_sources[0])
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
                    where_condition = build_where({"$in": unique_sources})
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
                            where_condition = build_where(source)
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
            query_kwargs: Dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": min(top_k * 5, 100),
            }
            where_condition = build_where()
            if where_condition:
                query_kwargs["where"] = where_condition
            results = self.collection.query(**query_kwargs)
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
                if modality_filter and str(metadata.get("modality") or "").lower() != modality_filter.lower():
                    continue
                if knowledge_node_ids and str(metadata.get("knowledge_node_id") or "") not in knowledge_node_ids:
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
        
        # 候选阶段仅删除完全相同的内容，不按来源去重。
        unique_documents = []
        seen_content_hashes = set()
        
        for doc in documents:
            content = doc.get("content", "")
            
            content_hash = hashlib.sha256(str(content).encode("utf-8")).hexdigest()
            
            # 哈希相同才进一步确认，避免 Python 进程级 hash 不稳定。
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
                seen_content_hashes.add(content_hash)
                unique_documents.append(doc)
        
        return unique_documents[:top_k]
    
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
        allowed_sources: Optional[List[str]] = None,  # 允许检索的文档源列表（如果提供，只检索这些文档）
        additional_queries: Optional[List[tuple[str, List[float]]]] = None,
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
        candidate_k = max(40, top_k * 8)
        visual_intent = bool(
            re.search(r"(?:一张|1张|图示|图片|图解|示意图|可视化|直观看|图表|插图)", query)
        )

        # 1. 向量检索（宽召回；如果指定 allowed_sources 则在库内过滤）
        vector_results = self.search(
            query_embedding, 
            top_k=candidate_k,
            distance_threshold=distance_threshold,
            allowed_sources=allowed_sources
        )
        visual_results = self.search(
            query_embedding,
            top_k=max(20, top_k * 4),
            distance_threshold=1.9,
            allowed_sources=allowed_sources,
            modality_filter="image",
        ) if visual_intent else []
        
        # 2. 关键词检索（如果可用，也只检索 allowed_sources 中的文档）
        keyword_results = self.keyword_search(
            query, 
            top_k=candidate_k,
            allowed_sources=allowed_sources
        ) if BM25_AVAILABLE else []

        # 指代消解后的查询只作为补充召回，原问题始终保留。对各查询变体先做
        # 一次 RRF，避免重写错误把用户原始关键词完全覆盖。
        if additional_queries:
            vector_recall: Dict[str, List[Dict]] = {"original": vector_results}
            keyword_recall: Dict[str, List[Dict]] = {"original": keyword_results}
            variant_weights: Dict[str, float] = {"original": 1.0}
            for index, (alternate_query, alternate_embedding) in enumerate(additional_queries):
                name = f"rewrite_{index + 1}"
                vector_recall[name] = self.search(
                    alternate_embedding,
                    top_k=candidate_k,
                    distance_threshold=distance_threshold,
                    allowed_sources=allowed_sources,
                )
                keyword_recall[name] = self.keyword_search(
                    alternate_query,
                    top_k=candidate_k,
                    allowed_sources=allowed_sources,
                ) if BM25_AVAILABLE else []
                variant_weights[name] = 0.7
            vector_results = self._weighted_reciprocal_rank_fusion(
                vector_recall,
                weights=variant_weights,
            )
            keyword_results = self._weighted_reciprocal_rank_fusion(
                keyword_recall,
                weights=variant_weights,
            )
        
        # 关键词不可用时仍继续走统一候选/重排链路。
        if not keyword_results:
            print(f"[Hybrid] 关键词检索不可用，仅使用向量检索: {len(vector_results)} 个结果")
        
        # 3. 融合结果
        # 构建文档ID到结果的映射
        doc_scores: Dict[str, Dict] = {}
        
        # 处理向量检索结果
        if vector_results:
            for rank, doc in enumerate(vector_results):
                doc_id = doc.get("id") or doc.get("metadata", {}).get("source", "")
                # RRF 只使用名次，不混合不可比的 cosine distance 与 BM25 原始分。
                similarity_score = 1.0 / (60 + rank + 1)
                
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "doc": doc,
                        "vector_score": 0.0,
                        "keyword_score": 0.0,
                        "combined_score": 0.0
                    }
                doc_scores[doc_id]["vector_score"] = similarity_score
        
        # 处理关键词检索结果
        if keyword_results:
            for rank, doc in enumerate(keyword_results):
                doc_id = doc.get("id") or doc.get("metadata", {}).get("source", "")
                normalized_score = 1.0 / (60 + rank + 1)
                
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
            doc["rrf_score"] = item["combined_score"]
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

        # 重排后做软多样性约束：优先每份资料最多 3 块，但候选不足时再回填，
        # 因此不会重现旧版“一份资料只能召回一块”的问题。
        max_per_source = max(1, int(os.getenv("RAG_MAX_CHUNKS_PER_SOURCE", "3")))
        diverse_results: List[Dict] = []
        deferred_results: List[Dict] = []
        source_counts: Dict[str, int] = {}
        for doc in final_results:
            source = str((doc.get("metadata") or {}).get("source") or "")
            if not source or source_counts.get(source, 0) < max_per_source:
                diverse_results.append(doc)
                if source:
                    source_counts[source] = source_counts.get(source, 0) + 1
            else:
                deferred_results.append(doc)
        if len(diverse_results) < top_k:
            diverse_results.extend(deferred_results[: top_k - len(diverse_results)])
        final_results = diverse_results[:top_k]

        # Text rerankers often remove every image even when the user explicitly
        # asks for a diagram. Run a modality-filtered dense recall and reserve
        # one image, preferring the knowledge node/source already supported by
        # the top textual evidence.
        if visual_intent and visual_results and not any(
            str((doc.get("metadata") or {}).get("modality", "text")).lower() == "image"
            for doc in final_results
        ):
            preferred_nodes = [
                str((doc.get("metadata") or {}).get("knowledge_node_id") or "")
                for doc in final_results
            ]
            preferred_sources = [
                str((doc.get("metadata") or {}).get("source") or "")
                for doc in final_results
            ]
            top_node = next((node_id for node_id in preferred_nodes if node_id), "")
            node_visual_results = self.search(
                query_embedding,
                top_k=max(10, top_k),
                distance_threshold=1.9,
                allowed_sources=allowed_sources,
                modality_filter="image",
                knowledge_node_ids=[top_node],
            ) if top_node else []
            candidate_visuals = node_visual_results or visual_results

            def visual_rank(item: tuple[int, Dict]) -> tuple[int, int, int]:
                index, doc = item
                metadata = doc.get("metadata") or {}
                node_id = str(metadata.get("knowledge_node_id") or "")
                source = str(metadata.get("source") or "")
                node_rank = preferred_nodes.index(node_id) if node_id in preferred_nodes else len(preferred_nodes)
                source_rank = preferred_sources.index(source) if source in preferred_sources else len(preferred_sources)
                return node_rank, source_rank, index

            selected_visual = min(enumerate(candidate_visuals), key=visual_rank)[1]
            final_results.insert(min(2, len(final_results)), selected_visual)
            final_results = final_results[:top_k]

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
    """所有导入入口共用的文档解析与结构化父子分块器。"""

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        embedding_client: Optional[Any] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_client = embedding_client
        self.structural_chunker = StructuralChunker(
            child_target_tokens=int(os.getenv("RAG_CHILD_TARGET_TOKENS", "500")),
            child_max_tokens=int(os.getenv("RAG_CHILD_MAX_TOKENS", "800")),
            parent_target_tokens=int(os.getenv("RAG_PARENT_TARGET_TOKENS", "1600")),
            parent_max_tokens=int(os.getenv("RAG_PARENT_MAX_TOKENS", "2400")),
            minimum_child_tokens=int(os.getenv("RAG_MINIMUM_CHILD_TOKENS", "120")),
        )

        self.image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

    def load_text_like(self, file_path: str) -> List[Document]:
        file_path_obj = Path(file_path)
        text = self._fallback_read(file_path)
        if not text.strip():
            return []
        return [
            Document(
                page_content=text,
                metadata={
                    "source": file_path,
                    "document_name": file_path_obj.name,
                    "page": 0,
                    "modality": "text",
                },
            )
        ]

    def load_doc(self, file_path: str) -> List[Document]:
        file_path_obj = Path(file_path)
        file_ext = file_path_obj.suffix.lower()
        if file_ext == ".docx":
            text = self._read_docx_text(file_path)
        else:
            text = self._fallback_read(file_path)

        if not text.strip():
            return []
        return [
            Document(
                page_content=text,
                metadata={
                    "source": file_path,
                    "document_name": file_path_obj.name,
                    "page": 0,
                    "modality": "text",
                },
            )
        ]

    def _read_docx_text(self, file_path: str) -> str:
        paragraphs: List[str] = []
        word_namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

        with zipfile.ZipFile(file_path) as archive:
            xml_names = [
                "word/document.xml",
                *sorted(name for name in archive.namelist() if re.fullmatch(r"word/header\d+\.xml", name)),
                *sorted(name for name in archive.namelist() if re.fullmatch(r"word/footer\d+\.xml", name)),
            ]
            for xml_name in xml_names:
                try:
                    xml_bytes = archive.read(xml_name)
                except KeyError:
                    continue

                root = ET.fromstring(xml_bytes)
                for paragraph in root.iter(f"{word_namespace}p"):
                    parts: List[str] = []
                    for node in paragraph.iter():
                        if node.tag == f"{word_namespace}t":
                            parts.append(node.text or "")
                        elif node.tag == f"{word_namespace}tab":
                            parts.append("\t")
                        elif node.tag in {f"{word_namespace}br", f"{word_namespace}cr"}:
                            parts.append("\n")

                    paragraph_text = "".join(parts).strip()
                    if paragraph_text:
                        paragraphs.append(paragraph_text)

        return "\n\n".join(paragraphs)

    def _prepare_text_chunks(self, documents: List[Document]) -> List[Document]:
        text_chunks = self.split_documents(documents)
        for doc in text_chunks:
            if doc.metadata is None:
                doc.metadata = {}
            doc.metadata["modality"] = "text"
        return text_chunks

    def _parse_pdf_with_mineru(
        self,
        file_path: str,
        pages_per_chunk: int = 20,
        max_workers: int = 4,
    ) -> Dict[str, Any]:
        """解析 PDF —— 直连 MinerU Cloud（替代旧的本地 mineru CLI + 分片并行）。

        见 docs/spec/SPEC-03。云端已处理整份文档，无需本地按页切割/并行；
        ``pages_per_chunk`` / ``max_workers`` 仅为兼容旧签名保留，忽略之。

        返回保持旧契约（供 rag 入库与 textbook_knowledge_graph 复用）::

            {'markdown_text': str, 'images': [{'path','name','page_offset'}],
             'success': bool, 'error': str, 'temp_dirs_to_cleanup': [str]}
        """
        result: Dict[str, Any] = {
            'markdown_text': '',
            'images': [],
            'success': False,
            'error': '',
            'temp_dirs_to_cleanup': [],
        }
        try:
            from app.integrations.pdf import get_pdf_parser

            parser = get_pdf_parser()
            if not getattr(parser, "is_configured", lambda: True)():
                result['error'] = '未配置 MinerU Cloud API key (PDF_MINERU_CLOUD_API_KEY)'
                return result

            print(f"[MinerU Cloud] 开始解析: {Path(file_path).name}")
            data = Path(file_path).read_bytes()
            parsed = parser.parse(data, filename=Path(file_path).name)

            result['markdown_text'] = parsed.text or ''
            if not result['markdown_text'].strip():
                result['error'] = 'MinerU Cloud 未提取到有效文本'
                return result

            # 图片：base64 → 写入临时目录，暴露 {path,name,page_offset} 供上层保存
            image_mapping = (parsed.metadata or {}).get('imageMapping') or {}
            if image_mapping:
                Config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
                tmp = tempfile.mkdtemp(prefix='mineru_cloud_', dir=str(Config.TEMP_DIR))
                result['temp_dirs_to_cleanup'].append(tmp)
                for name, data_url in image_mapping.items():
                    try:
                        b64 = data_url.split(',', 1)[1] if ',' in data_url else data_url
                        img_path = os.path.join(tmp, name)
                        with open(img_path, 'wb') as fh:
                            fh.write(base64.b64decode(b64))
                        result['images'].append(
                            {'path': img_path, 'name': name, 'page_offset': 0}
                        )
                    except Exception as img_exc:
                        print(f"[MinerU Cloud] 图片落盘失败 {name}: {img_exc}")

            result['success'] = True
            print(
                f"[MinerU Cloud] 解析成功：文本 {len(result['markdown_text'])} 字，"
                f"图片 {len(result['images'])} 张"
            )
        except Exception as exc:  # noqa: BLE001
            result['error'] = f'MinerU Cloud 解析失败: {exc}'
        return result

    def process_file(
        self,
        file_path: str,
        owner: Optional[str] = None,
        doc_id: Optional[str] = None,
        images_root: Optional[Path] = None,
    ) -> List[Document]:
        """解析并切分导入文件。PDF 只使用 MinerU Cloud，失败即失败。"""
        file_path_obj = Path(file_path)

        if file_path_obj.suffix.lower() == ".doc":
            raise ValueError(
                f"不支持旧版 Word .doc 文件（{file_path_obj.name}），请先转换为 DOCX 后再导入。"
            )

        if file_path_obj.suffix.lower() == ".docx":
            documents = self.load_doc(file_path)
            if not documents:
                raise ValueError(f"Unable to extract text from Word document: {file_path_obj.name}")
            text_chunks = self._prepare_text_chunks(documents)
            image_chunks = self._extract_docx_image_documents(
                file_path_obj,
                owner=owner,
                doc_id=doc_id,
                images_root=images_root,
            )
            if image_chunks:
                linked_images = [
                    {
                        "image_path": str(doc.metadata.get("image_path") or ""),
                        "image_name": str(doc.metadata.get("image_name") or ""),
                        "image_alt": str(doc.metadata.get("image_alt") or ""),
                        "page": 0,
                        "source": "docx",
                    }
                    for doc in image_chunks
                ]
                for doc in text_chunks:
                    doc.metadata["linked_images"] = linked_images
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
            if file_path_obj.suffix.lower() in {".md", ".markdown"}:
                image_chunks = self._extract_image_documents(
                    md_text,
                    file_path_obj,
                    owner=owner,
                    doc_id=doc_id,
                    images_root=images_root,
                )
                if image_chunks:
                    linked_images = [
                        {
                            "image_path": str(doc.metadata.get("image_path") or ""),
                            "image_name": str(doc.metadata.get("image_name") or ""),
                            "image_alt": str(doc.metadata.get("image_alt") or ""),
                            "page": int(doc.metadata.get("page") or 0),
                            "source": "markdown",
                        }
                        for doc in image_chunks
                    ]
                    for doc in text_chunks:
                        doc.metadata["linked_images"] = linked_images
                return text_chunks + image_chunks
            return text_chunks

        if not MINERU_AVAILABLE:
            raise RuntimeError("未配置 MinerU Cloud API key (PDF_MINERU_CLOUD_API_KEY)，无法解析 PDF。")

        text_chunks: List[Document] = []
        image_chunks: List[Document] = []
        _, safe_doc_id, target_root = self._resolve_image_target_root(file_path_obj, owner, doc_id, images_root)

        print(f"[MinerU] 开始解析文档: {file_path_obj.name}")
        mineru_result: Dict[str, Any] = {}
        try:
            pages_per_chunk = int(os.getenv("RAG_MINERU_PAGES_PER_CHUNK", "20"))
            max_workers = int(os.getenv("RAG_MINERU_MAX_WORKERS", "4"))
            mineru_result = self._parse_pdf_with_mineru(
                file_path=file_path,
                pages_per_chunk=pages_per_chunk,
                max_workers=max_workers,
            )

            if not mineru_result["success"]:
                raise ValueError(f"MinerU 解析失败: {mineru_result['error']}")

            markdown_text = mineru_result["markdown_text"]
            mineru_images = mineru_result["images"]

            if not markdown_text.strip():
                raise ValueError("MinerU 未提取到有效文本内容")

            base_doc = Document(
                page_content=markdown_text,
                metadata={
                    "source": file_path,
                    "document_name": file_path_obj.name,
                    "page": 0,
                    "modality": "text",
                    "image_doc_id": safe_doc_id,
                },
            )
            text_chunks = self.split_documents([base_doc])
            for doc in text_chunks:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["modality"] = "text"
                doc.metadata["image_doc_id"] = safe_doc_id

            print(f"[MinerU] 开始保存图片 ({len(mineru_images)} 张)...")
            enable_image_embedding = os.getenv("RAG_ENABLE_IMAGE_EMBEDDING", "1").strip().lower() in {"1", "true", "yes"}
            linked_images: List[Dict[str, Any]] = []

            for img_info in mineru_images:
                src_path = img_info["path"]
                if not os.path.exists(src_path):
                    print(f"[WARNING] 图片源文件不存在: {src_path}")
                    continue

                dst_name = Path(str(img_info.get("name") or Path(src_path).name)).name
                dst_path = target_root / dst_name
                shutil.copy2(src_path, dst_path)
                print(f"[MinerU图片] 已保存到硬盘: {dst_name}")

                page = int(img_info.get("page_offset", 0) or 0)
                linked_image = {
                    "image_path": str(dst_path),
                    "image_name": dst_name,
                    "image_alt": "MinerU 解析的插图",
                    "page": page,
                    "source": "mineru",
                }
                linked_images.append(linked_image)

                if enable_image_embedding:
                    image_chunks.append(
                        self._build_image_chunk_document(
                            file_path_obj=file_path_obj,
                            image_path=dst_path,
                            image_index=page,
                            alt_text=linked_image["image_alt"],
                            safe_doc_id=safe_doc_id,
                        )
                    )
                else:
                    print("[MinerU图片] 跳过向量化入库 (RAG_ENABLE_IMAGE_EMBEDDING=0)")

            if linked_images:
                for doc in text_chunks:
                    if doc.metadata is None:
                        doc.metadata = {}
                    doc.metadata["linked_images"] = linked_images

            print(f"[MinerU] 解析成功！文本块: {len(text_chunks)}，图片: {len(linked_images)}")
        except Exception:
            raise
        finally:
            temp_dirs = mineru_result.get("temp_dirs_to_cleanup", []) if mineru_result else []
            for temp_dir in temp_dirs:
                if temp_dir and os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir)
                        print(f"[MinerU] 已清理临时目录: {temp_dir}")
                    except Exception as e:
                        print(f"[WARNING] 清理临时目录失败: {e}")

        return text_chunks + image_chunks

    def _fallback_read(self, file_path: str) -> str:
        """Read plain text-like files with a small encoding fallback list."""
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
        try:
            image_rel_path = os.path.relpath(
                str(image_path), str(Config.STORAGE_ROOT.resolve())
            )
        except ValueError:
            # Windows cannot calculate relative paths across drive letters.
            image_rel_path = image_path.name
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

    def _extract_docx_image_documents(
        self,
        file_path_obj: Path,
        *,
        owner: Optional[str] = None,
        doc_id: Optional[str] = None,
        images_root: Optional[Path] = None,
    ) -> List[Document]:
        """Extract embedded DOCX media without loading a heavyweight parser."""

        _, safe_doc_id, target_root = self._resolve_image_target_root(
            file_path_obj, owner, doc_id, images_root
        )
        documents: List[Document] = []
        with zipfile.ZipFile(file_path_obj) as archive:
            media_names = sorted(
                name
                for name in archive.namelist()
                if name.casefold().startswith("word/media/")
                and Path(name).suffix.casefold() in self.image_exts
            )
            for index, archive_name in enumerate(media_names):
                safe_name = f"{index:04d}_{Path(archive_name).name}"
                destination = target_root / safe_name
                destination.write_bytes(archive.read(archive_name))
                documents.append(
                    self._build_image_chunk_document(
                        file_path_obj=file_path_obj,
                        image_path=destination,
                        image_index=index,
                        alt_text=f"DOCX 内嵌图片 {Path(archive_name).name}",
                        safe_doc_id=safe_doc_id,
                    )
                )
        return documents

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
        """按 Markdown 结构生成稳定的父子块；PDF/DOCX/网页/上传均调用此处。"""
        all_chunks: List[Document] = []

        for doc in documents:
            base_metadata = (doc.metadata or {}).copy()
            source = str(base_metadata.get("source") or "unknown")
            title = str(base_metadata.get("document_name") or Path(source).name or "未命名文档")
            document_id = hashlib.sha256(f"{source}\n{title}".encode("utf-8")).hexdigest()[:24]
            result = self.structural_chunker.chunk_markdown(
                doc.page_content,
                document_id=document_id,
                document_title=title,
            )
            parents = {parent.parent_id: parent for parent in result.parents}

            for child in result.children:
                metadata = base_metadata.copy()
                heading_path = " > ".join(child.heading_path)
                metadata.update(
                    {
                        "chunker_version": CHUNKER_VERSION,
                        "chunk_id": child.chunk_id,
                        "parent_id": child.parent_id,
                        "previous_chunk_id": child.previous_id or "",
                        "next_chunk_id": child.next_id or "",
                        "heading_path": heading_path,
                        "chunk_kind": child.kind,
                        "token_count": child.token_count,
                        "source_start_line": child.start_line,
                        "source_end_line": child.end_line,
                        "embedding_input_hash": hashlib.sha256(
                            child.embedding_text.encode("utf-8")
                        ).hexdigest(),
                    }
                )
                if child.token_count < 120:
                    metadata["small_chunk_reason"] = (
                        f"structure_protected:{child.kind}"
                        if child.kind in {"code", "formula", "table", "image", "video", "callout"}
                        else "atomic_section_boundary"
                    )
                for level, heading in enumerate(child.heading_path[:6], start=1):
                    metadata[f"Header {level}"] = heading

                parent = parents.get(child.parent_id)
                if parent is not None:
                    # 仅在导入事务内携带，写索引清单前会取出，避免把整段父块
                    # 重复写进每个 Chroma metadata。
                    metadata["_parent_content_runtime"] = parent.display_content
                    metadata["_parent_token_count_runtime"] = parent.token_count

                all_chunks.append(
                    Document(page_content=child.embedding_text, metadata=metadata)
                )

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
        document_index_path: Optional[Union[str, Path]] = None,
        storage_root: Optional[Union[str, Path]] = None,
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
        self.storage_root = Path(storage_root or Config.STORAGE_ROOT).resolve()
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
        # Embedding and parsing may run concurrently during bulk imports, while
        # Chroma writes and the JSON registry must remain serialized.
        self._vector_write_lock = threading.RLock()
        self._index_write_lock = threading.RLock()
        self.document_index = self._load_index()
    
    def _load_index(self) -> Dict:
        """加载文档索引"""
        if str(os.getenv("KNOWLEDGE_PERSISTENCE_MODE", "json")).strip().lower() == "postgres":
            from app.persistence.dependencies import get_postgres_knowledge_repository

            return get_postgres_knowledge_repository().load_runtime_index("document")
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_index(self):
        """保存文档索引"""
        with self._index_write_lock:
            if str(os.getenv("KNOWLEDGE_PERSISTENCE_MODE", "json")).strip().lower() == "postgres":
                from app.persistence.dependencies import get_postgres_knowledge_repository

                get_postgres_knowledge_repository().replace_runtime_index(
                    "document", self.document_index
                )
                return
            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            temp_index = self.index_file.with_suffix(
                f"{self.index_file.suffix}.{uuid.uuid4().hex}.tmp"
            )
            with open(temp_index, "w", encoding="utf-8") as f:
                json.dump(self.document_index, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_index, self.index_file)
    
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
        metadata_overrides: Optional[Dict[str, Any]] = None,
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

        # Keep caller-provided classification metadata both on vector chunks and
        # in the durable document catalog.  Previously it was only attached to
        # chunks, so course documents looked like personal documents when the UI
        # listed the catalog.
        safe_overrides: Dict[str, Any] = {
            str(key): value
            for key, value in (metadata_overrides or {}).items()
            if value is not None and isinstance(value, (str, int, float, bool))
        }

        if not force_reimport and index_key in self.document_index:
            existing_entry = self.document_index[index_key]
            existing_hash = None
            # 关键：同一路径可能被不同用户“各自导入”，因此增量判断必须同时校验 owner
            # 否则会出现：A 导入后，B 导入同一路径时被错误判定为“已导入”，导致 owner/索引混乱
            existing_owner = existing_entry.get("owner")
            if owner is not None and existing_owner is not None and existing_owner != owner:
                # 不同用户同路径：视为“需要重新导入到该用户名下”（继续往下走）
                pass
            else:
                existing_hash = existing_entry.get("hash")
            metadata_changed = any(
                existing_entry.get(key) != value
                for key, value in safe_overrides.items()
            )
            if existing_hash == file_hash and not metadata_changed:
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
        images_root = self.storage_root / "images"
        documents = self.document_processor.process_file(
            file_str,
            owner=owner,
            doc_id=image_doc_id,
            images_root=images_root,
        )
        if safe_overrides:
            # Course/node identity must live on every text and media chunk. It
            # enables node-aware evaluation, filtering and citations without
            # relying on filenames or a second database lookup at query time.
            for doc in documents:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata.update(safe_overrides)
        
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
        base_source_key = self._make_source_key(file_str, owner)
        previous_index_entry = self.document_index.get(index_key)
        previous_source_key = (
            previous_index_entry.get("source_key")
            if previous_index_entry
            else None
        )
        # Rebuilds write to a new source first. The document index is switched
        # only after all new chunks are durable, so a failed rebuild keeps the
        # previous retrievable version intact.
        source_key = (
            f"{base_source_key}#rev_{uuid.uuid4().hex[:12]}"
            if previous_index_entry
            else base_source_key
        )
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

        # 父块用于命中后的上下文扩展，保存在文档索引清单中；运行时临时字段
        # 必须在写入 Chroma 前移除，避免每个子块重复存储整段父块。
        parent_chunks: Dict[str, Dict[str, Any]] = {}
        for doc in documents:
            metadata = doc.metadata or {}
            parent_id = str(metadata.get("parent_id") or "")
            parent_content = metadata.pop("_parent_content_runtime", None)
            parent_token_count = metadata.pop("_parent_token_count_runtime", None)
            if not parent_id or parent_content is None:
                continue
            parent_entry = parent_chunks.setdefault(
                parent_id,
                {
                    "content": str(parent_content),
                    "heading_path": str(metadata.get("heading_path") or ""),
                    "token_count": int(parent_token_count or 0),
                    "child_ids": [],
                },
            )
            chunk_id = str(metadata.get("chunk_id") or "")
            if chunk_id and chunk_id not in parent_entry["child_ids"]:
                parent_entry["child_ids"].append(chunk_id)

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

        if progress_callback:
            progress_callback(80, "indexing")
        # 添加到向量数据库
        print(f"[RAG导入][Stage] vector_add_start docs={len(documents)} vectors={len(embeddings)}")
        try:
            with self._vector_write_lock:
                self.vector_store.add_documents(documents, embeddings)
        except Exception:
            # Some vector stores can partially write a batch before raising.
            # This source is not active yet, so it is safe to clean it up.
            with self._vector_write_lock:
                self.vector_store.delete_by_source(source_key)
            raise
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
        
        existing_entry = previous_index_entry or {}
        include_flag = existing_entry.get("include_in_search", True)

        # 不再“优先保留旧 owner”。同一路径允许不同用户各自拥有一份索引，
        # 但索引键不能只用 file_str，否则会互相覆盖。
        index_key = self._make_index_key(file_str, owner)

        image_storage_dir = (self.storage_root / "images" / (owner or "anonymous") / image_doc_id).resolve()
        image_chunk_count = sum(1 for d in documents if str((d.metadata or {}).get("modality", "text")).lower() == "image")
        linked_images: List[Dict[str, Any]] = []
        linked_image_keys: set[str] = set()
        for doc in documents:
            for linked_image in (doc.metadata or {}).get("linked_images") or []:
                image_path = str(linked_image.get("image_path") or "")
                if not image_path or image_path in linked_image_keys:
                    continue
                linked_image_keys.add(image_path)
                linked_images.append(dict(linked_image))

        next_index_entry = {
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
            "summary_title": existing_entry.get("summary_title"),
            "summary_title_updated_at": existing_entry.get("summary_title_updated_at"),
            "owner": owner,
            # 记录原始物理路径，便于展示/下载/定位
            "physical_path": file_str,
            # 向量库中的 source（已按 owner 隔离）
            "source_key": source_key,
            "chunker_version": CHUNKER_VERSION,
            "parent_chunks": parent_chunks,
            # 图片统一存储目录（用于联动清理）
            "image_doc_id": image_doc_id,
            "image_storage_dir": str(image_storage_dir),
            "linked_images": linked_images,
        }
        # These fields are intentionally persisted in the catalog.  Listing and
        # authorization must never need to infer course/personal ownership from
        # a filename.  Keep the allow-list narrow so callers cannot overwrite
        # hashes, physical paths, owners, or other internal bookkeeping fields.
        catalog_metadata_keys = {
            "course_id",
            "library_type",
            "scope_type",
            "scope_id",
            "knowledge_node_id",
            "course_document_id",
            "course_material_id",
            "content_language",
            "authority_tier",
        }
        next_index_entry.update(
            {key: value for key, value in safe_overrides.items() if key in catalog_metadata_keys}
        )
        print(f"[RAG导入][Stage] index_save_start key={index_key}")
        with self._index_write_lock:
            self.document_index[index_key] = next_index_entry
            try:
                self._save_index()
            except Exception:
                with self._vector_write_lock:
                    self.vector_store.delete_by_source(source_key)
                if previous_index_entry is None:
                    self.document_index.pop(index_key, None)
                else:
                    self.document_index[index_key] = previous_index_entry
                raise
        print("[RAG导入][Stage] index_save_done")

        if previous_source_key and previous_source_key != source_key:
            try:
                with self._vector_write_lock:
                    self.vector_store.delete_by_source(previous_source_key)
            except Exception as cleanup_error:
                print(
                    "[RAG导入] 新索引已切换，但旧索引清理失败："
                    f"source={previous_source_key}, err={cleanup_error}"
                )

        if progress_callback:
            progress_callback(100, "completed")

        return {
            "status": "success",
            "message": f"成功导入 {len(documents)} 个文档块",
            "file": file_str,
            "chunk_count": len(documents)
        }

    def retrieve_documents(
        self,
        question: str,
        *,
        top_k: int = 5,
        allowed_sources: Optional[List[str]] = None,
        rewritten_query: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict]:
        """Production retrieval path shared by Q&A, document tests and evaluation."""
        original = str(question or "").strip()
        if not original:
            return []
        effective_embedding = query_embedding or self.embedding_client.embed_query(original)
        additional_queries: List[tuple[str, List[float]]] = []
        rewritten = str(rewritten_query or "").strip()
        if rewritten and rewritten != original:
            additional_queries.append(
                (rewritten, self.embedding_client.embed_query(rewritten))
            )
        return self.vector_store.hybrid_search(
            query=original,
            query_embedding=effective_embedding,
            top_k=top_k,
            distance_threshold=1.5,
            keyword_weight=0.4,
            vector_weight=0.6,
            allowed_sources=allowed_sources,
            additional_queries=additional_queries,
        )
    
    def query(
        self,
        question: str,
        top_k: int = 5,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        use_rag: bool = True,  # 新增 RAG 开关参数
        selected_doc_ids: Optional[List[str]] = None,  # 用户选中的文档 ID 列表（优先传 RAG v2 index_key）
        owner: Optional[str] = None,  # 当前用户，用于过滤文档
        course_id: Optional[str] = None,  # 当前课程；允许读取该课程公开知识，同时保持个人资料按 owner 隔离
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
                "content": r"""你是一名专业的教育知识助手。请基于【参考资料】回答用户问题。

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
                    
            # 构建允许参与检索的 source_key 集合（在检索之前就确定，用于限制检索范围）
            # document_index 的 key 是 index_key（user_owner:physical_path）
            # 向量库中的 source 字段存储的是 source_key（也是 user_owner:physical_path 格式）
            # 两者应该一致，所以可以直接使用 index_key 作为 allowed_sources
            
            # 1. 首先根据用户和 include_in_search 过滤
            candidate_sources = {
                index_key: meta
                for index_key, meta in self.document_index.items()
                if meta.get("include_in_search", True) and _owner_can_access_document(meta, owner, course_id)
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

                    resolved_document = resolve_rag_document(self, doc_id, owner=owner)
                    if resolved_document and resolved_document.index_key in candidate_sources:
                        matched_key = resolved_document.index_key
                        print(f"[RAG] 通过公共解析器匹配成功: {doc_id} -> {matched_key}")
                    
                    # 方式1：直接匹配 index_key（doc_id 可能是完整的 index_key）
                    # 这是最常见的匹配方式，因为前端传递的 file_path 就是 index_key
                    if not matched_key and doc_id in candidate_sources:
                        matched_key = doc_id
                        print(f"[RAG] 直接匹配成功: {doc_id}")
                    elif not matched_key and doc_id_normalized in candidate_sources:
                        matched_key = doc_id_normalized
                        print(f"[RAG] 规范化后直接匹配成功: {doc_id_normalized}")
                    # 方式1.5：检查是否是 index_key 的变体（处理 user_owner:path 格式）
                    elif not matched_key and ':' in doc_id:
                        # doc_id 可能是 user_owner:path 格式，尝试直接匹配
                        for index_key in candidate_sources.keys():
                            if doc_id == index_key or doc_id_normalized == normalize_for_match(index_key):
                                matched_key = index_key
                                print(f"[RAG] 通过 index_key 格式匹配成功: {doc_id} -> {index_key}")
                                break
                    elif not matched_key:
                        # 方式2：通过 physical_path 和 file_name 匹配
                        for index_key, meta in candidate_sources.items():
                            physical_path = meta.get("physical_path", "")
                            record_path = meta.get("path", "")
                            file_name = meta.get("file_name", "")
                            
                            # 规范化路径用于匹配
                            physical_path_norm = normalize_for_match(physical_path)
                            record_path_norm = normalize_for_match(record_path)
                            file_name_norm = normalize_for_match(file_name)
                            
                            # 检查多种匹配方式
                            if (doc_id == physical_path or 
                                doc_id_normalized == physical_path_norm or
                                doc_id == record_path or
                                doc_id_normalized == record_path_norm or
                                doc_id == file_name or
                                doc_id_normalized == file_name_norm or
                                # 检查文件名是否包含在 doc_id 中（处理带前缀的情况）
                                (file_name and file_name in doc_id) or
                                (file_name_norm and file_name_norm in doc_id_normalized) or
                                # 检查 physical_path 的文件名部分
                                (physical_path and Path(physical_path).name in doc_id) or
                                (record_path and Path(record_path).name in doc_id) or
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
                query_embedding = self.embedding_client.embed_query(question)
                retrieved_docs = self.vector_store.enhanced_hybrid_search_with_hyde(
                    query=question,
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
                print(f"[RAG] 使用生产混合检索模式：原问题 + 重写补充 + RRF + Rerank")
                retrieved_docs = self.retrieve_documents(
                    question,
                    top_k=top_k,
                    allowed_sources=allowed_sources_for_search,  # 限制检索范围
                    rewritten_query=retrieval_query,
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
                matched_key = _match_allowed_source(self.document_index, allowed_sources, doc_source)

                if matched_key is not None:
                    # 额外检查：确保文档确实在 document_index 中（防止已删除的文档）
                    if matched_key in self.document_index:
                        meta = self.document_index[matched_key]
                        # 再次检查 include_in_search 和 owner（双重保险）
                        if (
                            meta.get("include_in_search", True)
                            and _owner_can_access_document(meta, owner, course_id)
                        ):
                            accepted = doc.copy()
                            accepted_metadata = (doc.get("metadata") or {}).copy()
                            accepted_metadata["_matched_index_key"] = matched_key
                            accepted["metadata"] = accepted_metadata
                            filtered_docs.append(accepted)
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

            # 子块负责精确命中，命中后扩展到同章节父块，给生成模型完整语义。
            selected_docs = filtered_docs
            selected_docs = [
                _expand_parent_context(
                    self.document_index,
                    doc,
                    str((doc.get("metadata") or {}).get("_matched_index_key") or ""),
                )
                for doc in selected_docs
            ]
            
            # ========== 任务三：清洗检索结果中的脏数据 ==========
            # 在构建 Context 之前，先清洗每个文档的 content
            import re as regex_module
            for doc in selected_docs:
                original_content = doc.get("content", "")
                # 保留 Markdown、代码、表格和 LaTeX；这里只统一换行与过量空行。
                # 旧逻辑会主动删除 \frac / \sum 等公式命令，已禁止执行。
                if original_content:
                    normalized = regex_module.sub(r"\r\n?", "\n", str(original_content))
                    doc["content"] = regex_module.sub(r"\n{4,}", "\n\n\n", normalized).strip()
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
                full_content = _retrieved_display_content(doc)
                chunk_id = str(metadata.get("chunk_id") or doc.get("id") or "").strip()
                if not chunk_id:
                    chunk_id = hashlib.sha1(
                        f"{raw_source}\0{full_content}".encode("utf-8")
                    ).hexdigest()[:20]
                if rerank_score is not None:
                    retrieval_method = "hybrid_rerank"
                elif combined_score is not None:
                    retrieval_method = "hybrid"
                else:
                    retrieval_method = "vector"
                if rerank_score is not None:
                    print(f"[文档 {idx+1}] {source_name}: Rerank 分数={rerank_score:.4f}")
                else:
                    vector_display = f"{vector_score:.4f}" if isinstance(vector_score, (int, float)) else "N/A"
                    combined_display = f"{combined_score:.4f}" if isinstance(combined_score, (int, float)) else "N/A"
                    print(f"[文档 {idx+1}] {source_name}: 向量分数={vector_display}, 融合分数={combined_display}")

                formatted_sources.append(
                    {
                        "content": full_content,
                        "chunk_id": chunk_id,
                        "rank": idx + 1,
                        "retrieval_method": retrieval_method,
                        "source_start_line": metadata.get("source_start_line"),
                        "source_end_line": metadata.get("source_end_line"),
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

        session = requests.Session()
        session.trust_env = False
        try:
            request_timeout = float((llm_config or {}).get("timeout_seconds") or 360)
            response = session.post(url, json=payload, headers=headers, timeout=request_timeout, stream=stream)

            if stream:
                # 流式输出：返回生成器
                def generate():
                    try:
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
                    finally:
                        response.close()
                        session.close()
                return generate()
            else:
                # 非流式输出
                try:
                    if response.status_code == 200:
                        data = response.json()
                        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    raise Exception(f"LLM API错误: {response.status_code} - {response.text}")
                finally:
                    response.close()
                    session.close()
        except Exception as e:
            session.close()
            raise Exception(f"调用LLM失败: {str(e)}")
    
    def list_documents(self, owner: Optional[str] = None) -> List[Dict]:
        """列出已索引文档
        
        Args:
            owner: 如果提供，则仅返回该用户拥有的文档
        """
        documents: List[Dict] = []
        for file_path, metadata in self.document_index.items():
            # 如果指定了owner，则只返回该用户的文档
            if not _owner_can_access_document(metadata, owner):
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
                    "summary_title": metadata.get("summary_title"),
                    "summary_title_updated_at": metadata.get("summary_title_updated_at"),
                    "file_size": metadata.get("file_size"),
                    "page_count": metadata.get("page_count"),
                    "hash": metadata.get("hash"),
                    "owner": metadata.get("owner"),
                    # 网页来源相关字段
                    "source_url": metadata.get("source_url"),
                    "source_title": metadata.get("source_title"),
                    "source_domain": metadata.get("source_domain"),
                    "source_site_name": metadata.get("source_site_name"),
                    "source_icon_path": metadata.get("source_icon_path"),
                    "doc_kind": metadata.get("doc_kind"),
                    # Knowledge-library classification fields.  These are used
                    # by the API to enforce course/personal catalog isolation.
                    "course_id": metadata.get("course_id"),
                    "library_type": metadata.get("library_type"),
                    "scope_type": metadata.get("scope_type"),
                    "scope_id": metadata.get("scope_id"),
                    "knowledge_node_id": metadata.get("knowledge_node_id"),
                    "course_document_id": metadata.get("course_document_id"),
                    "course_material_id": metadata.get("course_material_id"),
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
            "summary_title": record.get("summary_title"),
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
        index_key = self._make_index_key(file_path, owner)
        record = self.document_index.get(index_key)
        source_key = (record or {}).get("source_key") or self._make_source_key(
            file_path, owner
        )

        # 从向量数据库删除：使用隔离后的 source_key，避免误删其他用户 chunk
        deleted_count = self.vector_store.delete_by_source(source_key)
        print(f"[RAG] 从向量库删除文档: source_key={source_key}, 删除了 {deleted_count} 个chunks")

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
