from __future__ import annotations


class MemoryEmbeddingProvider:
    def __init__(self):
        from core.config import Config

        self.model_name = Config.EMBEDDING_MODEL
        backend = str(Config.EMBEDDING_BACKEND or "").lower()
        if backend == "ollama":
            from langchain_ollama import OllamaEmbeddings

            self._client = OllamaEmbeddings(
                model=Config.EMBEDDING_MODEL,
                base_url=Config.OLLAMA_BASE_URL,
            )
        else:
            from langchain_openai import OpenAIEmbeddings

            self._client = OpenAIEmbeddings(
                model=Config.EMBEDDING_MODEL,
                api_key=Config.DEEP_MODEL_API_KEY or Config.OPENROUTER_API_KEY,
                base_url=Config.EMBEDDING_API_BASE,
                request_timeout=Config.EMBEDDING_TIMEOUT_SEC,
                max_retries=0,
            )

    def embed(self, text: str) -> list[float]:
        return list(self._client.embed_query(text))
