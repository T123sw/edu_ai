"""Reuse websearch provider integrations; extraction and search remain distinct."""
import ipaddress
import time
from urllib.parse import urlsplit, urlunsplit

from app.integrations.websearch import search_bocha, search_tavily, extract_tavily

from .research_agent import ResearchError, RecoverableSourceError
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
        self.attempt = lambda kind, payload, call: call()
        self.health = {}

    def capabilities(self):
        def entry(name, configured):
            return {'provider':name,'configured':bool(configured),
                    'health':self.health.get(name,'unknown' if configured else 'not_configured')}
        return {'search':[entry('tavily_search',self.tavily_key),entry('bocha_search',self.bocha_key)],
                'extract':[entry('tavily_extract',self.tavily_key)]}

    def _attempt(self, provider, operation, payload, call):
        try:
            result=self.attempt(operation.lower(),{**payload,'provider':provider},call)
        except (ResearchError, PermissionError):
            raise
        except Exception as exc:
            error=provider_error(exc, operation)
            self.health[provider]=getattr(error,'category','unavailable')
            raise error from exc
        self.health[provider]='healthy'
        return result

    def search(self, query, *, limit, timeout):
        if not self.tavily_key and not self.bocha_key:
            raise ResearchError('SEARCH_NOT_CONFIGURED', '网络搜索服务未配置')
        deadline=time.monotonic()+timeout
        def remaining():
            value=deadline-time.monotonic()
            if value <= 0: raise ResearchError('DEADLINE_EXCEEDED','搜索预算已耗尽')
            return value
        hits=None
        if self.tavily_key:
            try:
                hits=self._attempt('tavily_search','SEARCH',{'query':query},lambda:
                    search_tavily(query,count=limit,api_key=self.tavily_key,
                        base_url=self.tavily_base,timeout=remaining(),search_depth='advanced'))
            except RecoverableSourceError:
                if not self.bocha_key: raise
        if hits is None:
            hits=self._attempt('bocha_search','SEARCH',{'query':query},lambda:
                search_bocha(query,count=limit,api_key=self.bocha_key,
                    base_url=self.bocha_base,timeout=remaining(),freshness='noLimit'))
        result = []
        for hit in hits:
            try:
                url = public_url(hit.url)
            except ValueError:
                continue
            result.append({'url': url, 'title': hit.title, 'snippet': hit.content})
        return result

    def read(self, url, *, timeout):
        return self.read_body(url,timeout=timeout)['content']

    def read_body(self, url, *, timeout):
        url = public_url(url)
        if not self.tavily_key:
            raise ResearchError('EXTRACT_NOT_CONFIGURED', '正文提取服务未配置，不能把搜索摘要作为已读资料')
        if timeout <= 0: raise ResearchError('DEADLINE_EXCEEDED','正文读取预算已耗尽')
        results=self._attempt('tavily_extract','EXTRACT',{'url':url},lambda:
            extract_tavily([url], depth='advanced', timeout=timeout,
                api_key=self.tavily_key,base_url=self.tavily_base,max_urls=1))
        # One input URL: one successful result can identify an actual redirect.
        successful=[r for r in results if r.status=='success' and r.content.strip()]
        if len(successful)==1:
            result=successful[0]
            return {'canonical_url':public_url(result.url),'content':result.content}
        raise RecoverableSourceError('EXTRACT_NO_BODY','该来源未提取到正文，请换来源或报告资料缺口')
