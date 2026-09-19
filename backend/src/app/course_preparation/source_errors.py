"""Only transient provider failures may be retried inside a research session."""
import httpx
from .research_agent import ResearchError, RecoverableSourceError


def provider_error(exc, operation):
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (408, 429) or status >= 500:
            return RecoverableSourceError(operation+'_TEMPORARY', '来源服务暂时不可用，可有限重试或换来源')
        return ResearchError(operation+'_REJECTED', '来源服务拒绝请求，请检查服务配置或权限')
    if isinstance(exc, httpx.TransportError):
        return RecoverableSourceError(operation+'_TEMPORARY', '来源服务连接失败或超时，可有限重试或换来源')
    return ResearchError(operation+'_UNAVAILABLE', '来源服务响应无效，已停止本次调用')
