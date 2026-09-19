"""Only transient provider failures may be retried inside a research session."""
import httpx
from .research_agent import ResearchError, RecoverableSourceError


def provider_error(exc, operation):
    category='invalid_response'
    if isinstance(exc, httpx.HTTPStatusError):
        status=exc.response.status_code
        category = ('rate_limit' if status==429 else 'timeout' if status==408 else
                    'server' if status>=500 else 'authentication' if status==401 else
                    'permission' if status==403 else 'rejected')
    elif isinstance(exc, httpx.TimeoutException): category='timeout'
    elif isinstance(exc, httpx.TransportError): category='connection'
    transient=category in {'rate_limit','timeout','server','connection'}
    error=(RecoverableSourceError if transient else ResearchError)(
        operation+('_TEMPORARY' if transient else '_'+category.upper()),
        '来源服务暂时不可用，可有限重试或换来源' if transient else '来源服务拒绝请求或响应无效，请检查配置、权限或更换来源')
    error.category=category
    return error
