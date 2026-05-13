# 文件路径: core/config.py
from pathlib import Path


class Config:
    # 定义基础路径
    BASE_DIR = Path(__file__).resolve().parent.parent

    # 定义存储路径
    TEMP_DIR = BASE_DIR / "temp"
    DOCUMENTS_ROOT = BASE_DIR / "storage" / "documents"
    STORAGE_ROOT = BASE_DIR / "storage"
    VECTOR_DB_PATH = BASE_DIR / "knowledge_base" / "chroma_db"
    DOCUMENT_INDEX_PATH = BASE_DIR / "knowledge_base" / "document_index.json"
    VIDEO_INDEX_PATH = BASE_DIR / "knowledge_base" / "video_index.json"
    IMAGE_INDEX_PATH = BASE_DIR / "knowledge_base" / "image_index.json"

    # 给系统的一些默认兜底配置
    EMBEDDING_API_BASE = ""
    OPENROUTER_BASE_URL = ""
    OPENROUTER_API_KEY = ""
    EMBEDDING_MODEL = "gemini-embedding-2-preview"
    LLM_MODEL_DEEP = "deepseek-chat"
    CHAT_HISTORY_WINDOW = 5

    @staticmethod
    def get_deep_model():
        return {
            "model_name": "deepseek-chat",
            "api_base": "https://api.deepseek.com/v1"
        }