import os
import json
import chromadb
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from chromadb.config import Settings
from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class DocumentMetadata:
    """文档元数据类"""
    source: str
    page: int
    chunk_index: int
    content_length: int
    document_name: str
    ingestion_time: str


class Config:
    """项目配置类"""

    # 模型配置
    LLM_MODEL = "qwen:7b"
    EMBEDDING_MODEL = "nomic-embed-text"
    OLLAMA_BASE_URL = "http://localhost:11434"

    # 向量数据库配置
    VECTOR_DB_PATH = "./storage/vector_db"
    COLLECTION_NAME = "dsa_knowledge_base"

    # 混合检索配置
    HYBRID_VECTOR_WEIGHT = 0.7
    HYBRID_BM25_WEIGHT = 0.3

    # 文档存储配置
    DOCUMENTS_CACHE_PATH = "./storage/cache/documents_cache.json"

    # 文本处理配置
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 80
    TOP_K_RESULTS = 4

    # 文件路径配置
    DATA_DIR = "./storage/data"
    TEXTBOOKS_DIR = os.path.join(DATA_DIR, "textbooks")

    # 智能文档增强配置
    ENABLE_DOCUMENT_ENHANCEMENT = True
    ENHANCEMENT_MAX_QUESTIONS = 2
    ENHANCEMENT_BATCH_SIZE = 5
    ENHANCEMENT_DELAY = 1

    # 增强文档保存配置
    SAVE_ENHANCED_DOCUMENTS = True
    ENHANCED_DOCUMENTS_DIR = "./storage/enhanced_docs"
    ENHANCED_DOCUMENTS_FORMAT = "json"

    @classmethod
    def save_enhanced_documents(cls, documents: List[Document], filename_suffix: str = ""):
        """保存增强后的文档到文件"""
        if not cls.SAVE_ENHANCED_DOCUMENTS:
            return True

        try:
            # 确保目录存在
            os.makedirs(cls.ENHANCED_DOCUMENTS_DIR, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = f"_{filename_suffix}" if filename_suffix else ""
            base_filename = f"enhanced_docs_{timestamp}{suffix}"

            # 根据格式保存
            if cls.ENHANCED_DOCUMENTS_FORMAT == "json":
                return cls._save_enhanced_documents_json(documents, base_filename)

        except Exception as e:
            print(f" 保存增强文档失败: {e}")
            return False

    @classmethod
    def _save_enhanced_documents_json(cls, documents: List[Document], base_filename: str):
        """以JSON格式保存增强文档"""
        filepath = os.path.join(cls.ENHANCED_DOCUMENTS_DIR, f"{base_filename}.json")

        enhanced_data = {
            "metadata": {
                "total_documents": len(documents),
                "generation_time": datetime.now().isoformat(),
                "format": "enhanced_documents"
            },
            "documents": []
        }

        for i, doc in enumerate(documents):
            doc_data = {
                "index": i,
                "content": doc.page_content,
                "metadata": doc.metadata,
                "document_type": doc.metadata.get('document_type', 'original'),
                "source": doc.metadata.get('source', '未知')
            }
            enhanced_data["documents"].append(doc_data)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(enhanced_data, f, ensure_ascii=False, indent=2)

        print(f" 增强文档已保存到: {filepath}")
        return True




    @classmethod
    def get_embedding_model(cls):
        """获取嵌入模型实例"""
        return OllamaEmbeddings(
            model=cls.EMBEDDING_MODEL,
            base_url=cls.OLLAMA_BASE_URL,
            #show_progress=True
        )

    @classmethod
    def get_llm(cls):
        """获取LLM实例"""
        return ChatOllama(
            model=cls.LLM_MODEL,
            base_url=cls.OLLAMA_BASE_URL,
            temperature=0.1,
            num_predict=1000
        )

    @staticmethod
    def get_chroma_settings():
        """获取Chroma数据库设置"""
        return Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=Config.VECTOR_DB_PATH,
            anonymized_telemetry=False,
            # 禁用HTTP服务，使用直接持久化
            is_persistent=True
        )

    @staticmethod
    def get_chroma_client():
        """获取Chroma客户端"""
        try:
            client = chromadb.PersistentClient(
                path=Config.VECTOR_DB_PATH,
                settings=Config.get_chroma_settings()
            )
            return client
        except Exception as e:
            print(f"Chroma客户端创建失败: {e}")
            return None

    @classmethod
    def get_vector_db(cls, embedding_function=None, collection_name=None):
        """获取向量数据库实例"""
        if embedding_function is None:
            embedding_function = cls.get_embedding_model()

        if collection_name is None:
            collection_name = cls.COLLECTION_NAME

        return Chroma(
            persist_directory=cls.VECTOR_DB_PATH,
            embedding_function=embedding_function,
            collection_name=collection_name
        )

    @classmethod
    def get_text_splitter(cls):
        """获取文本分割器实例"""
        return RecursiveCharacterTextSplitter(
            chunk_size=cls.CHUNK_SIZE,
            chunk_overlap=cls.CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", "？", "！", "．", ",", " "],
            length_function=len,
            is_separator_regex=False
        )

    @classmethod
    def save_documents(cls, documents: List[Document]):
        """保存文档到缓存文件用于混合检索"""
        try:
            # 转换为可序列化的格式
            serializable_docs = []
            for i, doc in enumerate(documents):
                serializable_docs.append({
                    "page_content": doc.page_content,
                    "metadata": doc.metadata,
                    "doc_id": f"doc_{i}_{hash(doc.page_content)}"
                })

            # 保存到文件
            with open(cls.DOCUMENTS_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(serializable_docs, f, ensure_ascii=False, indent=2)

            print(f" 已保存 {len(documents)} 个文档到 {cls.DOCUMENTS_CACHE_PATH}")
            return True

        except Exception as e:
            print(f" 保存文档失败: {e}")
            return False

    @classmethod
    def load_documents(cls) -> List[Document]:
        """从缓存文件加载文档用于混合检索"""
        try:
            if not os.path.exists(cls.DOCUMENTS_CACHE_PATH):
                print("  文档缓存文件不存在")
                return []

            with open(cls.DOCUMENTS_CACHE_PATH, 'r', encoding='utf-8') as f:
                serializable_docs = json.load(f)

            # 转换回Document对象
            documents = []
            for doc_data in serializable_docs:
                doc = Document(
                    page_content=doc_data["page_content"],
                    metadata=doc_data["metadata"]
                )
                documents.append(doc)

            print(f" 已加载 {len(documents)} 个文档从缓存文件")
            return documents

        except Exception as e:
            print(f" 加载文档失败: {e}")
            return []

    @classmethod
    def document_cache_exists(cls) -> bool:
        """检查文档缓存是否存在"""
        return os.path.exists(cls.DOCUMENTS_CACHE_PATH)


# 确保数据目录存在
os.makedirs(Config.TEXTBOOKS_DIR, exist_ok=True)
os.makedirs(Config.VECTOR_DB_PATH, exist_ok=True)
os.makedirs(Config.ENHANCED_DOCUMENTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(Config.DOCUMENTS_CACHE_PATH) if os.path.dirname(Config.DOCUMENTS_CACHE_PATH) else ".", exist_ok=True)
