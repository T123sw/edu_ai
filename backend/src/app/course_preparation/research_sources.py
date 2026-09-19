"""Reuse websearch provider integrations; extraction and search remain distinct."""
import ipaddress
from urllib.parse import urlsplit, urlunsplit

from app.integrations.websearch import search_bocha, search_tavily, extract_tavily

from .research_agent import ResearchError
from .source_errors import provider_error


def public_url(url):
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    if parts.scheme not in {'https', 'http'} or not host or parts.username or parts.password:
        raise ValueError('来源URL格式不支持')
    if parts.port not in (None, 80, 443) or '.' not in host or host.endswith(('.local', '.localhost', '.internal')):
        raise ValueError('来源必须为公开网页')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError('来源不能是私有网络地址')
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))


class ResearchSources:
    def __init__(self, *, tavily_key, bocha_key='', tavily_base='https://api.tavily.com', bocha_base='https://api.bocha.cn'):
        self.tavily_key, self.bocha_key = tavily_key, bocha_key
        self.tavily_base, self.bocha_base = tavily_base, bocha_base

    def search(self, query, *, limit, timeout):
        if not self.tavily_key and not self.bocha_key:
            raise ResearchError('SEARCH_NOT_CONFIGURED', '网络搜索服务未配置')
        try:
            if self.tavily_key:
                hits = search_tavily(query, count=limit, api_key=self.tavily_key,
                    base_url=self.tavily_base, timeout=timeout, search_depth='advanced')
            else:
                hits = search_bocha(query, count=limit, api_key=self.bocha_key,
                    base_url=self.bocha_base, timeout=timeout, freshness='noLimit')
        except Exception as exc:
            raise provider_error(exc, 'SEARCH') from exc
        result = []
        for hit in hits:
            try:
                url = public_url(hit.url)
            except ValueError:
                continue
            result.append({'url': url, 'title': hit.title, 'snippet': hit.content})
        return result

    def read(self, url, *, timeout):
        url = public_url(url)
        if not self.tavily_key:
            raise ResearchError('EXTRACT_NOT_CONFIGURED', '正文提取服务未配置，不能把搜索摘要作为已读资料')
        try:
            results = extract_tavily([url], depth='advanced', timeout=max(1, int(timeout)),
                api_key=self.tavily_key, base_url=self.tavily_base, max_urls=1)
        except Exception as exc:
            raise provider_error(exc, 'EXTRACT') from exc
        for result in results:
            if result.status == 'success' and public_url(result.url) == url and result.content.strip():
                return result.content
        raise ValueError('该来源正文提取失败，请选择其他相关来源')
