"""Public, structured failures at the embedding provider boundary."""
class EmbeddingServiceError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def embedding_response_error(status: int, payload: dict):
    error = payload.get('error') if isinstance(payload, dict) else {}
    error = error if isinstance(error, dict) else {}
    code = str(error.get('code') or '')
    if code in {'local:insufficient_quota', 'insufficient_quota'}:
        return EmbeddingServiceError('EMBEDDING_QUOTA_EXHAUSTED', '知识库检索服务额度不足，暂时无法读取相关资料。请联系管理员恢复服务。')
    return EmbeddingServiceError('EMBEDDING_UNAVAILABLE', '知识库检索服务暂时不可用，请稍后重试或联系管理员。')


def public_legacy_embedding_error(message: str) -> str:
    """Redact provider payloads in historical failed jobs without rewriting them."""
    import json
    if not str(message).startswith('Embedding API错误:'):
        return message
    try:
        payload = json.loads(message.split(' - ', 1)[1])
    except (ValueError, IndexError):
        payload = {}
    return str(embedding_response_error(0, payload))
