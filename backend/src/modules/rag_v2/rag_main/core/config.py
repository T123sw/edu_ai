"""Runtime config for ``rag_v2.rag_main``.

This mirrors the host backend's storage roots so the runtime package does not
fork persistent state under ``rag_v2/rag_main``.
"""

import os
from pathlib import Path

from core.config import Config as HostConfig


class Config(HostConfig):
    BASE_DIR = Path(__file__).resolve().parents[4]

    STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", BASE_DIR / "storage"))
    VECTOR_DB_PATH = Path(os.getenv("VECTOR_DB_PATH", STORAGE_ROOT / "vector_db"))
    DOCUMENT_INDEX_PATH = Path(os.getenv("DOCUMENT_INDEX_PATH", STORAGE_ROOT / "document_index.json"))
    DOCUMENTS_ROOT = Path(os.getenv("DOCUMENTS_ROOT", STORAGE_ROOT / "documents"))
    VIDEOS_ROOT = Path(os.getenv("VIDEOS_ROOT", STORAGE_ROOT / "videos"))
    VIDEO_CHUNKS_ROOT = Path(os.getenv("VIDEO_CHUNKS_ROOT", STORAGE_ROOT / "video_chunks"))
    TEMP_DIR = Path(os.getenv("TEMP_DIR", STORAGE_ROOT / "temp"))
    CONVERSATIONS_FILE = Path(os.getenv("CONVERSATIONS_FILE", STORAGE_ROOT / "conversations.json"))
    USER_PROFILES_FILE = Path(os.getenv("USER_PROFILES_FILE", STORAGE_ROOT / "user_profiles.json"))
    LESSON_PLANS_FILE = Path(os.getenv("LESSON_PLANS_FILE", STORAGE_ROOT / "lesson_plans.json"))

    EMBEDDING_API_BASE = HostConfig.EMBEDDING_API_BASE
    OPENROUTER_BASE_URL = HostConfig.OPENROUTER_BASE_URL
    OPENROUTER_API_KEY = HostConfig.OPENROUTER_API_KEY
    REMOTE_MODEL_API_BASE = HostConfig.REMOTE_MODEL_API_BASE
    REMOTE_MODEL_API_KEY = HostConfig.REMOTE_MODEL_API_KEY
    DEEPSEEK_BASE_URL = HostConfig.DEEPSEEK_BASE_URL
    DEEPSEEK_API_KEY = HostConfig.DEEPSEEK_API_KEY
    OLLAMA_BASE_URL = HostConfig.OLLAMA_BASE_URL
    EMBEDDING_MODEL = HostConfig.EMBEDDING_MODEL
    VISION_MODEL_ID = HostConfig.VISION_MODEL_ID
    LLM_MODEL = HostConfig.LLM_MODEL
    LLM_MODEL_DEEP = HostConfig.LLM_MODEL_DEEP
    CHAT_HISTORY_WINDOW = HostConfig.CHAT_HISTORY_WINDOW

    VIDEO_INDEX_PATH = Path(os.getenv("VIDEO_INDEX_PATH", STORAGE_ROOT / "video_index.json"))
    IMAGE_INDEX_PATH = Path(os.getenv("IMAGE_INDEX_PATH", STORAGE_ROOT / "image_index.json"))

    @classmethod
    def ensure_directories(cls):
        super().ensure_directories()
        cls.VIDEO_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.IMAGE_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)


Config.ensure_directories()
