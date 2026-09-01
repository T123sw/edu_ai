import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]

try:
    from dotenv import load_dotenv

    for candidate in (
        BASE_DIR.parent.parent / ".env",
        BASE_DIR / ".env",
        BASE_DIR / "config_openai.env",
        Path.cwd() / ".env",
    ):
        if candidate.exists():
            load_dotenv(candidate, override=True)
            break
except Exception:
    pass


def _default_allow_origins() -> List[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["*"]


def _env_bool(name: str, default: bool) -> bool:
    fallback = "1" if default else "0"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """项目全局配置：三脑架构（planner/deep/vision）。"""

    APP_NAME = os.getenv("APP_NAME", "Edu-AI API")
    API_PREFIX = os.getenv("API_PREFIX", "/api")

    # 1. 逻辑模型（左脑）
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    LOGIC_MODEL_MINI = os.getenv("LOGIC_MODEL_MINI", "openai/gpt-5.4-mini")

    # 2. 深度纯文本模型（中脑）
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEP_MODEL_API_BASE = os.getenv("ANSWER_LLM_API_BASE", os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
    DEEP_MODEL_API_KEY = os.getenv("ANSWER_LLM_API_KEY", os.getenv("QWEN_API_KEY", ""))
    LLM_MODEL_DEEP = os.getenv("ANSWER_LLM_MODEL", os.getenv("VISION_MODEL_ID", "qwen3.5-plus"))

    # 3. 视觉多模态模型（右脑）
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    VISION_MODEL_ID = os.getenv("VISION_MODEL_ID", "qwen3.5-plus")

    # Shared OpenMAIC classroom speech profile for narration and live answers.
    # Provider selection is server-owned and never accepted from the browser.
    OPENMAIC_LIVE_TTS_PROVIDER = os.getenv(
        "OPENMAIC_LIVE_TTS_PROVIDER", "qwen-tts"
    )
    OPENMAIC_LIVE_TTS_VOICE = os.getenv("OPENMAIC_LIVE_TTS_VOICE", "Cherry")
    OPENMAIC_LIVE_TTS_SPEED = min(
        2.0,
        max(0.5, float(os.getenv("OPENMAIC_LIVE_TTS_SPEED", "1.0"))),
    )

    # 4. 图片搜索（Phase 6-A）
    # IMAGE_SEARCH_PROVIDER: "" = disabled (default), "bocha" = Bocha hosted search
    # 未配置时 image_search 工具调用会返回 provider_not_configured 错误，
    # 不影响应用启动；普通对话不依赖此工具。
    IMAGE_SEARCH_PROVIDER = os.getenv("IMAGE_SEARCH_PROVIDER", "")
    IMAGE_SEARCH_TIMEOUT_S = float(os.getenv("IMAGE_SEARCH_TIMEOUT_S", "8") or "8")
    IMAGE_SEARCH_DEFAULT_COUNT = int(os.getenv("IMAGE_SEARCH_DEFAULT_COUNT", "6") or "6")
    IMAGE_SEARCH_MAX_COUNT = int(os.getenv("IMAGE_SEARCH_MAX_COUNT", "12") or "12")
    # VLM 审查 image_search 结果开关。默认关闭：当前 VLM (Qwen on DashScope) 无法
    # 可靠下载境外图片 URL 做多模态审查（频繁 400 / 超时），留着只会拖垮时间预算
    # 并触发 retry → react_timeout → 降级。关闭后仅依赖 handler 启发式过滤。
    # 待图片本地化后改为发送本地 base64 给 VLM，再开启此开关。
    # 默认开启：Phase 6-A.2 重构后，VisionReflector 先把图下载到本地，再以
    # base64 data URI 发给 VLM 审查，DashScope 无需联网下载境外图，审查可用。
    IMAGE_SEARCH_VLM_REVIEW = os.getenv("IMAGE_SEARCH_VLM_REVIEW", "1").strip() not in ("", "0", "false", "False")


    # 统一别名（兼容历史代码中的 REMOTE_*）
    REMOTE_MODEL_API_BASE = os.getenv("REMOTE_MODEL_API_BASE", DEEPSEEK_BASE_URL)
    REMOTE_MODEL_API_KEY = os.getenv("REMOTE_MODEL_API_KEY", DEEPSEEK_API_KEY)

    # 逻辑/深度模型别名
    LLM_MODEL = os.getenv("LLM_MODEL", LOGIC_MODEL_MINI)

    # 嵌入模型配置（迁移到新体系，默认走 OpenRouter）
    EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "openai")
    EMBEDDING_API_BASE = os.getenv("EMBEDDING_API_BASE", OPENROUTER_BASE_URL)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview")
    GEMINI_EMBEDDING_DIMENSIONS = int(os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "0"))
    EMBEDDING_TIMEOUT_SEC = int(os.getenv("EMBEDDING_TIMEOUT_SEC", "120"))
    EMBEDDING_MAX_RETRIES = int(os.getenv("EMBEDDING_MAX_RETRIES", "3"))
    EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
    EMBEDDING_MAX_WORKERS = int(os.getenv("EMBEDDING_MAX_WORKERS", "4"))
    DURABLE_JOB_WORKERS = max(1, int(os.getenv("DURABLE_JOB_WORKERS", "3")))

    # 存储路径
    STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", "storage"))
    RUNTIME_CONFIG_ROOT = Path(
        os.getenv("RUNTIME_CONFIG_ROOT", STORAGE_ROOT / "runtime_config")
    )
    VECTOR_DB_PATH = Path(os.getenv("VECTOR_DB_PATH", STORAGE_ROOT / "vector_db"))
    DOCUMENT_INDEX_PATH = Path(
        os.getenv("DOCUMENT_INDEX_PATH", STORAGE_ROOT / "document_index.json")
    )
    DOCUMENTS_ROOT = Path(os.getenv("DOCUMENTS_ROOT", STORAGE_ROOT / "documents"))
    VIDEOS_ROOT = Path(os.getenv("VIDEOS_ROOT", STORAGE_ROOT / "videos"))
    VIDEO_CHUNKS_ROOT = Path(os.getenv("VIDEO_CHUNKS_ROOT", STORAGE_ROOT / "video_chunks"))
    COURSE_STORAGE_ROOT = Path(os.getenv("COURSE_STORAGE_ROOT", BASE_DIR.parent / "course_data"))
    COURSE_MEMBERSHIPS_FILE = Path(
        os.getenv("COURSE_MEMBERSHIPS_FILE", str(STORAGE_ROOT / "course_memberships.json"))
    )
    LEARNING_DB_PATH = Path(
        os.getenv("LEARNING_DB_PATH", str(STORAGE_ROOT / "learning.db"))
    )
    DEV_AUTO_ENROLL_ALL_COURSES = _env_bool(
        "DEV_AUTO_ENROLL_ALL_COURSES", False
    )
    TEMP_DIR = Path(os.getenv("TEMP_DIR", STORAGE_ROOT / "temp"))

    # Phase 6-A.2 — agent 搜来的图片本地化存储
    SEARCHED_IMAGE_STORAGE_ROOT = Path(
        os.getenv("SEARCHED_IMAGE_STORAGE_ROOT", STORAGE_ROOT / "searched_images")
    )
    SEARCHED_IMAGE_MAX_BYTES = int(
        os.getenv("SEARCHED_IMAGE_MAX_BYTES", str(10 * 1024 * 1024)) or str(10 * 1024 * 1024)
    )
    SEARCHED_IMAGE_DOWNLOAD_TIMEOUT_S = float(
        os.getenv("SEARCHED_IMAGE_DOWNLOAD_TIMEOUT_S", "10") or "10"
    )
    SEARCHED_IMAGE_USER_AGENT = os.getenv(
        "SEARCHED_IMAGE_USER_AGENT",
        "Mozilla/5.0 (compatible; EduAI/1.0)",
    )
    CONVERSATIONS_FILE = Path(
        os.getenv("CONVERSATIONS_FILE", STORAGE_ROOT / "conversations.json")
    )
    USER_PROFILES_FILE = Path(
        os.getenv("USER_PROFILES_FILE", STORAGE_ROOT / "user_profiles.json")
    )
    LESSON_PLANS_FILE = Path(
        os.getenv("LESSON_PLANS_FILE", STORAGE_ROOT / "lesson_plans.json")
    )

    CHAT_HISTORY_WINDOW = int(os.getenv("CHAT_HISTORY_WINDOW", 6))

    # Agent Memory V2
    AGENT_MEMORY_ENABLED = _env_bool("AGENT_MEMORY_ENABLED", True)
    AGENT_MEMORY_LANGMEM_ENABLED = _env_bool("AGENT_MEMORY_LANGMEM_ENABLED", True)
    AGENT_MEMORY_LANGMEM_SHADOW_MODE = _env_bool("AGENT_MEMORY_LANGMEM_SHADOW_MODE", False)
    AGENT_MEMORY_LANGMEM_BACKGROUND = _env_bool("AGENT_MEMORY_LANGMEM_BACKGROUND", True)
    AGENT_MEMORY_LANGMEM_TIMEOUT_MS = int(os.getenv("AGENT_MEMORY_LANGMEM_TIMEOUT_MS", "12000"))
    AGENT_MEMORY_EMBEDDING_ENABLED = _env_bool("AGENT_MEMORY_EMBEDDING_ENABLED", False)

    _DEFAULT_LLM_MODELS: List[Dict[str, Any]] = [
        {
            "id": "logic-gpt-5.4-mini",
            "name": "GPT-5.4 Mini",
            "model_name": LOGIC_MODEL_MINI,
            "api_base": OPENROUTER_BASE_URL,
            "api_key": OPENROUTER_API_KEY,
            "role": "planner",
            "provider": "openrouter",
        },
        {
            "id": "deepseek-v3",
            "name": "Qwen3.5 Plus",
            "model_name": LLM_MODEL_DEEP,
            "api_base": DEEP_MODEL_API_BASE,
            "api_key": DEEP_MODEL_API_KEY,
            "role": "deep",
            "provider": "qwen",
        },
        {
            "id": "qwen-vision",
            "name": "Qwen3.5 Plus (Vision)",
            "model_name": VISION_MODEL_ID,
            "api_base": QWEN_BASE_URL,
            "api_key": QWEN_API_KEY,
            "role": "vision",
            "provider": "qwen",
        },
    ]

    _EXTRA_MODELS_JSON = os.getenv("LLM_MODELS_JSON")
    if _EXTRA_MODELS_JSON:
        try:
            extra_models = json.loads(_EXTRA_MODELS_JSON)
            if isinstance(extra_models, list):
                _DEFAULT_LLM_MODELS.extend(extra_models)
        except json.JSONDecodeError:
            pass

    LLM_MODELS: List[Dict[str, Any]] = _DEFAULT_LLM_MODELS
    DEFAULT_LLM_MODEL_ID = os.getenv("DEFAULT_LLM_MODEL_ID", "logic-gpt-5.4-mini")

    ALLOW_ORIGINS = _default_allow_origins()

    # === Universal report engine tracing ===
    UNIVERSAL_REPORT_TRACE = os.getenv("UNIVERSAL_REPORT_TRACE", "0")
    UNIVERSAL_REPORT_SKILL_TRACE = os.getenv("UNIVERSAL_REPORT_SKILL_TRACE", "0")
    QUIZ_WORKFLOW_TRACE = os.getenv("QUIZ_WORKFLOW_TRACE", "1")

    # === P4-A ReAct Agent ===
    # 旧配置（保留兼容性）
    REACT_AGENT_MODEL_NAME = os.getenv("REACT_AGENT_MODEL", os.getenv("LLM_MODEL_DEEP", "deepseek-v4-flash"))
    REACT_AGENT_API_BASE = os.getenv("REACT_AGENT_API_BASE", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
    REACT_AGENT_API_KEY = os.getenv("REACT_AGENT_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))

    # Agent Planner 模型（负责任务规划，推理能力优先）
    # 默认指向 Qwen（DEEP_MODEL_API_*），后续可在 .env 中独立切换更强的推理模型
    AGENT_PLANNER_MODEL    = os.getenv("AGENT_PLANNER_MODEL",    LLM_MODEL_DEEP)
    AGENT_PLANNER_API_BASE = os.getenv("AGENT_PLANNER_API_BASE", DEEP_MODEL_API_BASE)
    AGENT_PLANNER_API_KEY  = os.getenv("AGENT_PLANNER_API_KEY",  DEEP_MODEL_API_KEY)

    # Agent Executor 模型（负责工具调用决策，响应速度优先）
    # 默认指向 Qwen（DEEP_MODEL_API_*），后续可在 .env 中独立切换更快的模型
    AGENT_EXECUTOR_MODEL    = os.getenv("AGENT_EXECUTOR_MODEL",    LLM_MODEL_DEEP)
    AGENT_EXECUTOR_API_BASE = os.getenv("AGENT_EXECUTOR_API_BASE", DEEP_MODEL_API_BASE)
    AGENT_EXECUTOR_API_KEY  = os.getenv("AGENT_EXECUTOR_API_KEY",  DEEP_MODEL_API_KEY)

    # ReAct 行为参数（可动态调整）
    USE_REACT_AGENT: bool = os.getenv("USE_REACT_AGENT", "true").lower() == "true"
    REACT_MAX_STEPS: int = int(os.getenv("REACT_MAX_STEPS", "6"))
    REACT_TIMEOUT_SECONDS: float = float(os.getenv("REACT_TIMEOUT_SECONDS", "40"))

    @classmethod
    def ensure_directories(cls):
        cls.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
        cls.RUNTIME_CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        cls.DOCUMENTS_ROOT.mkdir(parents=True, exist_ok=True)
        cls.VIDEOS_ROOT.mkdir(parents=True, exist_ok=True)
        cls.VIDEO_CHUNKS_ROOT.mkdir(parents=True, exist_ok=True)
        if cls.DOCUMENT_INDEX_PATH.parent:
            cls.DOCUMENT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        if cls.CONVERSATIONS_FILE.parent:
            cls.CONVERSATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if cls.USER_PROFILES_FILE.parent:
            cls.USER_PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
        if cls.LESSON_PLANS_FILE.parent:
            cls.LESSON_PLANS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if cls.COURSE_MEMBERSHIPS_FILE.parent:
            cls.COURSE_MEMBERSHIPS_FILE.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_llm_model(cls, model_id: Optional[str]) -> Dict[str, Any]:
        if not cls.LLM_MODELS:
            raise ValueError("未配置任何可用模型")
        if model_id:
            for model in cls.LLM_MODELS:
                if model.get("id") == model_id:
                    return model
        return cls.LLM_MODELS[0]

    @classmethod
    def get_planner_model(cls) -> Dict[str, Any]:
        for model in cls.LLM_MODELS:
            if model.get("role") == "planner":
                return model
        return cls.get_llm_model(cls.DEFAULT_LLM_MODEL_ID)

    @classmethod
    def get_deep_model(cls) -> Dict[str, Any]:
        for model in cls.LLM_MODELS:
            if model.get("role") == "deep":
                return model
        return cls.get_llm_model(cls.DEFAULT_LLM_MODEL_ID)

    @classmethod
    def get_vision_model(cls) -> Dict[str, Any]:
        for model in cls.LLM_MODELS:
            if model.get("role") == "vision":
                return model
        return cls.get_deep_model()

    @classmethod
    def get_agent_model(cls) -> Dict[str, Any]:
        """ReAct Agent 专用模型（工具调用决策）：deepseek-v4-flash via DeepSeek 官方。"""
        return {
            "id": "react-agent",
            "model_name": cls.REACT_AGENT_MODEL_NAME,
            "api_base": cls.REACT_AGENT_API_BASE,
            "api_key": cls.REACT_AGENT_API_KEY,
            "role": "agent",
        }

    @classmethod
    def get_public_llm_models(cls) -> List[Dict[str, Any]]:
        models: List[Dict[str, Any]] = []
        for model in cls.LLM_MODELS:
            models.append(
                {
                    "id": model.get("id"),
                    "name": model.get("name"),
                    "model_name": model.get("model_name"),
                }
            )
        return models


Config.ensure_directories()
