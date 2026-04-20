import logging
from typing import List, Dict

import requests
from langchain_core.tools import tool
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

logger = logging.getLogger(__name__)


def _extract_results(resp_dict: dict) -> List[Dict[str, str]]:
    """从SerpAPI响应里提取url + title"""
    results: List[Dict[str, str]] = []
    items = resp_dict.get("organic_results") or resp_dict.get("results") or []
    for item in items:
        link = item.get("link") or item.get("url")
        title = item.get("title") or item.get("name")
        if not link or not title:
            continue
        results.append({"url": link, "title": title})
    return results


@tool
def google_search(query: str, gl: str = "cn", return_number: int = 15) -> List[Dict[str, str]]:
    """
    使用谷歌搜索引擎（SerpAPI）搜索，返回指定数量的搜索结果列表，搜索结果包含 url 和 title
    :param query: 查询文本
    :param gl: 国家
    :param return_number: 返回数量
    :return: 一个列表，每个元素包含url和title
    """

    logger.info(f"使用谷歌搜索工具搜索 {query}...")

    params = {
        "engine": "google",
        "q": query,
        "gl": gl,
        "api_key": '',
    }

    results: List[Dict[str, str]] = []

    # ---------- 第1 页----------
    current_page = 1
    logger.info("正在谷歌搜索第1 页内容")
    response = requests.get("https://serpapi.com/search", params=params, timeout=30)
    resp_dict = response.json()

    err = resp_dict.get("error")
    if err:
        # 区分「配置类」错误和「查询类」错误
        err_lower = err.lower()
        if "api key" in err_lower or "missing api key" in err_lower:
            # 这类说明 key 真有问题，直接抛出给开发者看
            raise RuntimeError(f"SerpAPI API KEY 配置错误: {err}")
        else:
            # 比如 "Google hasn't returned any results for this query."
            logger.warning(f"SerpAPI 首次请求返回错误（视为当前查询0 结果）：{err}")
            return []  # 返回空列表，不再让Agent崩掉

    page_results = _extract_results(resp_dict)
    results.extend(page_results)

    # ---------- 后续分页 ----------
    MAX_PAGES = 10  # 保险起见

    while len(results) < return_number and current_page < MAX_PAGES:
        pagination = resp_dict.get("serpapi_pagination") or {}
        next_page_link = pagination.get("next")
        if not next_page_link:
            logger.info("没有更多分页结果，提前结束")
            break

        current_page += 1
        logger.info(f"正在谷歌搜索第{current_page} 页内容")

        response = requests.get(next_page_link, timeout=30, params={'api_key':''})
        resp_dict = response.json()

        err = resp_dict.get("error")
        if err:
            # 注意：分页阶段任何错误一律只 warn + break，不再抛异常
            logger.warning(f"SerpAPI 第{current_page} 页返回错误 {err}")
            break

        page_results = _extract_results(resp_dict)
        if not page_results:
            logger.info(f"第{current_page} 页没有有效结果，提前结束")
            break

        results.extend(page_results)

    return results[:return_number]


from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests

def _canon_url(u: str) -> str:
    """规范化URL：去除fragment，避免同一页面 #xxx 造成重复"""
    try:
        p = urlparse(u)
        return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))  # drop fragment
    except Exception:
        return u


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text or "")


def _is_unhelpful_baidu_url(link: str) -> bool:
    try:
        parsed = urlparse(link)
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        if netloc in {"top.baidu.com", "passport.baidu.com"}:
            return True
        if netloc in {"www.baidu.com", "baidu.com"} and (path in {"", "/"} or path.startswith("/s")):
            return True
    except Exception:
        return False
    return False


# 公共SearxNG实例列表（按稳定性排序）
PUBLIC_SEARXNG_INSTANCES = [
    "https://search.sapti.me/search",
    "https://searx.tiekoetter.com/search",
    "https://searx.be/search",
    "https://searx.prvcy.eu/search",
]

def _try_searxng_instances(query: str, params: dict, headers: dict, req_timeout: tuple) -> Optional[dict]:
    """
    尝试多个SearxNG公共实例，直到成功
    如果SSL验证失败，会尝试禁用SSL验证（仅用于测试）
    """
    # 首先尝试SSL验证
    for endpoint in PUBLIC_SEARXNG_INSTANCES:
        try:
            logger.info(f"尝试SearxNG实例: {endpoint}")
            r = requests.get(endpoint, params=params, headers=headers, timeout=req_timeout, verify=True)
            r.raise_for_status()
            data = r.json()
            if data.get("results"):
                logger.info(f"SearxNG实例 {endpoint} 成功返回 {len(data.get('results', []))} 个结果")
                return data
        except requests.exceptions.SSLError as e:
            logger.warning(f"SearxNG实例 {endpoint} SSL错误，尝试禁用SSL验证: {e}")
            # SSL失败时，尝试禁用SSL验证（仅用于测试环境）
            try:
                r = requests.get(endpoint, params=params, headers=headers, timeout=req_timeout, verify=False)
                r.raise_for_status()
                data = r.json()
                if data.get("results"):
                    logger.warning(f"SearxNG实例 {endpoint} 在禁用SSL验证后成功（不推荐用于生产环境）")
                    return data
            except Exception as e2:
                logger.warning(f"SearxNG实例 {endpoint} 即使禁用SSL验证也失败: {type(e2).__name__}: {e2}")
                continue
        except requests.exceptions.RequestException as e:
            logger.warning(f"SearxNG实例 {endpoint} 请求失败: {type(e).__name__}: {e}")
            continue
        except Exception as e:
            logger.warning(f"SearxNG实例 {endpoint} 未知错误: {type(e).__name__}: {e}")
            continue
    return None


def search(
    query: str,
    top_k: int = 10,
    endpoint: Optional[str] = None,  # None表示自动选择最佳实例
    *,
    api_key: Optional[str] = None,
    api_key_header: str = "Authorization",
    api_key_prefix: str = "Bearer ",
    language: Optional[str] = "zh-CN",
    safesearch: int = 1,
    timeout: int = 20,
    dedup: bool = True,
) -> List[Dict[str, Any]]:
    """
    调用 SearxNG JSON API 搜索并返回结构化结果
    如果endpoint为None，会自动尝试多个公共实例
    返回格式：[{title, url, snippet, engine}, ...]
    """
    if not query or not query.strip():
        return []

    params = {
        "q": query,
        "format": "json",
    }
    if language:
        params["language"] = language
    if safesearch is not None:
        params["safesearch"] = safesearch

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    if api_key:
        headers[api_key_header] = f"{api_key_prefix}{api_key}"

    # 将timeout 显式拆为 (connect, read) 避免 DNS/连接阶段卡死太久
    req_timeout = (min(5, timeout), timeout)

    def _fallback_bing_html(q: str) -> List[Dict[str, Any]]:
        """
        不依赖本地SearxNG 的兜底搜索：抓取 Bing HTML 结果页面
        注意：这是兜底方案，解析规则可能随页面变化而需要调整
        """
        url = f"https://www.bing.com/search?q={quote_plus(q)}"
        try:
            # 使用更完整的headers模拟真实浏览器
            bing_headers = {
                "User-Agent": headers["User-Agent"],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://www.bing.com/",
            }
            r = requests.get(url, headers=bing_headers, timeout=req_timeout)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            out: List[Dict[str, Any]] = []
            seen_urls = set()
            
            # 尝试多种选择器（Bing 页面结构可能变化）
            selectors = [
                "li.b_algo",
                "ol#b_results > li.b_algo",
                ".b_algo",
                ".b_algoSlug",
                "li[data-bm]",
            ]
            
            results_found = False
            for selector in selectors:
                items = soup.select(selector)
                if not items:
                    continue
                    
                for li in items:
                    # 尝试多种标题链接选择器
                    a = (li.select_one("h2 a") or 
                         li.select_one("h2 > a") or
                         li.select_one(".b_title a") or
                         li.select_one("a[href]"))
                    
                    if not a:
                        continue
                        
                    link = a.get("href") or ""
                    title = a.get_text(strip=True) or ""
                    
                    if not link or link.startswith("/") or "bing.com" in link.lower():
                        continue
                    
                    # 规范化URL并去重
                    link = _canon_url(link)
                    if link in seen_urls:
                        continue
                    seen_urls.add(link)
                        
                    # 尝试多种摘要选择器
                    snippet_el = (
                        li.select_one(".b_caption p") or
                        li.select_one(".b_caption") or
                        li.select_one(".b_descr") or
                        li.select_one("p")
                    )
                    snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
                    
                    if (link and title and 
                        not link.startswith("javascript:") and
                        not link.startswith("void(0)") and
                        link.startswith("http") and
                        "bing.com" not in link.lower()):
                        out.append({"title": title, "url": link, "snippet": snippet, "engine": "bing"})
                        results_found = True
                        
                    if len(out) >= top_k:
                        break
                        
                if results_found and len(out) >= top_k:
                    break
            
            if out:
                return out
                
            # 如果仍然没有找到结果，尝试从页面中提取所有外部链接
            logger.warning(f"Bing HTML 解析未找到标准结果，尝试提取所有外部链接")
            for a in soup.select("a[href]"):
                link = a.get("href", "")
                if (not link or 
                    link.startswith("/") or 
                    link.startswith("javascript:") or
                    "bing.com" in link.lower() or
                    not link.startswith("http") or
                    len(link) < 10):
                    continue
                
                link = _canon_url(link)
                if link in seen_urls:
                    continue
                seen_urls.add(link)
                
                title = a.get_text(strip=True) or link[:50]
                if title and title != "javascript:void(0)":
                    out.append({"title": title, "url": link, "snippet": "", "engine": "bing"})
                if len(out) >= top_k:
                    break
                    
            return out
        except Exception as e:
            logger.warning(f"Bing HTML解析失败: {type(e).__name__}: {e}")
            return []

    def _resolve_baidu_link(link: str) -> str:
        if not link:
            return link
        link = urljoin("https://www.baidu.com", link)
        try:
            parsed = urlparse(link)
            if "baidu.com" not in parsed.netloc.lower() or not parsed.path.startswith("/link"):
                return link
            r = requests.get(
                link,
                headers={"User-Agent": headers["User-Agent"]},
                timeout=req_timeout,
                allow_redirects=False,
            )
            location = r.headers.get("Location") or r.headers.get("location")
            if location:
                return urljoin(link, location)
        except Exception as e:
            logger.warning(f"Baidu redirect resolve failed: {type(e).__name__}: {e}")
        return link

    def _fallback_baidu_html(q: str) -> List[Dict[str, Any]]:
        """Fallback for Chinese queries when DDG/Bing return anti-bot challenge pages."""
        url = f"https://www.baidu.com/s?wd={quote_plus(q)}"
        try:
            baidu_headers = {
                "User-Agent": headers["User-Agent"],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Referer": "https://www.baidu.com/",
            }
            r = requests.get(url, headers=baidu_headers, timeout=req_timeout)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            out: List[Dict[str, Any]] = []
            seen_urls = set()

            result_items = soup.select("div.result, div.result-op")
            for item in result_items:
                a = (
                    item.select_one("h3.t a[href]")
                    or item.select_one("h3 a[href]")
                    or item.select_one("a[href]")
                )
                if not a:
                    continue

                title = a.get_text(" ", strip=True)
                link = a.get("href") or ""
                if not title or not link or link.startswith("javascript:"):
                    continue

                link = _canon_url(_resolve_baidu_link(link))
                if (
                    not link.startswith("http")
                    or _is_unhelpful_baidu_url(link)
                    or link in seen_urls
                ):
                    continue
                seen_urls.add(link)

                snippet_el = (
                    item.select_one(".c-abstract")
                    or item.select_one("[class*='abstract']")
                    or item.select_one("[class*='content-right']")
                    or item.select_one(".c-span-last")
                )
                snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
                out.append({"title": title, "url": link, "snippet": snippet, "engine": "baidu"})
                if len(out) >= top_k:
                    break

            return out
        except Exception as e:
            logger.warning(f"Baidu HTML解析失败: {type(e).__name__}: {e}")
            return []

    def _fallback_ddg_html(q: str) -> List[Dict[str, Any]]:
        """
        兜底搜索：抓取DuckDuckGo HTML 结果页面
        DuckDuckGo 的HTML 结构相对稳定，优先使用
        """
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
        try:
            r = requests.get(url, headers={"User-Agent": headers["User-Agent"]}, timeout=req_timeout)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            out: List[Dict[str, Any]] = []
            seen_urls = set()  # 用于URL去重
            
            # DuckDuckGo HTML 结果页的选择器（尝试多种）
            result_items = (
                soup.select(".result") or 
                soup.select(".web-result") or 
                soup.select("div.result") or
                soup.select("article.result") or
                soup.select(".links_main .result") or
                soup.select("div[class*='result']")
            )
            
            if not result_items:
                # 如果标准选择器失败，尝试更宽泛的选择
                logger.warning("DuckDuckGo标准选择器未找到结果，尝试更宽泛的选择")
                result_items = soup.select("div[class*='result'], article[class*='result']")
            
            for item in result_items:
                a = (item.select_one("a.result__a") or 
                     item.select_one("a.result-link") or
                     item.select_one("h2 a") or
                     item.select_one("a[href]"))
                
                if not a:
                    continue
                    
                link = a.get("href") or ""
                title = a.get_text(strip=True) or ""
                
                if not link or not title:
                    continue
                
                # 处理 DuckDuckGo 重定向链接
                if link.startswith("//duckduckgo.com/l/") or link.startswith("/l/"):
                    from urllib.parse import parse_qs, urlparse
                    try:
                        parsed = urlparse(link if link.startswith("//") else f"https:{link}")
                        params = parse_qs(parsed.query)
                        if "uddg" in params:
                            real_url = params["uddg"][0]
                            link = real_url
                    except Exception:
                        pass
                
                # 规范化URL并去重
                link = _canon_url(link)
                if link in seen_urls:
                    continue
                seen_urls.add(link)
                
                if (not link or
                    link.startswith("/") or 
                    "duckduckgo.com" in link.lower() or
                    link.startswith("javascript:") or
                    not link.startswith("http") or
                    len(link) < 10):
                    continue
                
                # 查找摘要（尝试多种选择器）
                snippet_el = (
                    item.select_one(".result__snippet") or
                    item.select_one(".result-snippet") or
                    item.select_one("a.result__snippet") or
                    item.select_one("div.result__snippet") or
                    item.select_one(".result__body")
                )
                snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
                
                out.append({"title": title, "url": link, "snippet": snippet, "engine": "ddg"})
                
                if len(out) >= top_k:
                    break
            return out
        except Exception as e:
            logger.warning(f"DuckDuckGo HTML解析失败: {type(e).__name__}: {e}")
            return []

    # 如果 endpoint 是 localhost，直接走HTML解析（跳过SearxNG尝试，节省时间）
    if endpoint and (endpoint.startswith("http://localhost:8090") or endpoint.startswith("http://127.0.0.1:8090")):
        logger.info("跳过SearxNG，直接使用HTML解析以提高速度")
        # 优先使用DuckDuckGo（更稳定，对中文支持更好）
        try:
            ddg_results = _fallback_ddg_html(query)
            if ddg_results and len(ddg_results) > 0:
                logger.info(f"DuckDuckGo HTML搜索成功，返回 {len(ddg_results)} 个结果")
                return ddg_results[:top_k]
        except Exception as e:
            logger.warning(f"DuckDuckGo HTML解析失败: {type(e).__name__}: {e}")
        
        if _contains_cjk(query):
            try:
                baidu_results = _fallback_baidu_html(query)
                if baidu_results and len(baidu_results) > 0:
                    logger.info(f"Baidu HTML搜索成功，返回 {len(baidu_results)} 个结果")
                    return baidu_results[:top_k]
            except Exception as e:
                logger.warning(f"Baidu HTML解析失败: {type(e).__name__}: {e}")

        # 备选：Bing
        try:
            bing_results = _fallback_bing_html(query)
            if bing_results and len(bing_results) > 0:
                logger.info(f"Bing HTML搜索成功，返回 {len(bing_results)} 个结果")
                return bing_results[:top_k]
        except Exception as e:
            logger.warning(f"Bing HTML解析失败: {type(e).__name__}: {e}")

        if not _contains_cjk(query):
            try:
                baidu_results = _fallback_baidu_html(query)
                if baidu_results and len(baidu_results) > 0:
                    logger.info(f"Baidu HTML搜索成功，返回 {len(baidu_results)} 个结果")
                    return baidu_results[:top_k]
            except Exception as e:
                logger.warning(f"Baidu HTML解析失败: {type(e).__name__}: {e}")
        
        logger.warning("所有HTML解析都失败，返回空列表")
        return []

    # 1) 优先尝试SearxNG（如果endpoint为None，尝试多个实例）
    data = None
    if endpoint:
        # 使用指定的endpoint
        try:
            r = requests.get(endpoint, params=params, headers=headers, timeout=req_timeout, verify=True)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning(f"SearxNG endpoint {endpoint} failed: {type(e).__name__}: {e}")
    else:
        # 自动尝试多个公共实例
        data = _try_searxng_instances(query, params, headers, req_timeout)
    
    if data and data.get("results"):
        out: List[Dict[str, Any]] = []
        seen = set()

        for it in data.get("results", []):
            url = it.get("url") or ""
            if not url:
                continue

            url = _canon_url(url)

            if dedup:
                if url in seen:
                    continue
                seen.add(url)

            out.append(
                {
                    "title": it.get("title", "") or "",
                    "url": url,
                    "snippet": it.get("content", "") or "",
                    "engine": it.get("engine", "") or "",
                }
            )
            if len(out) >= top_k:
                break

        return out

    # 2) 兜底：HTML 搜索抓取
    logger.warning("所有SearxNG实例失败，回退到HTML搜索")
    try:
        # 优先使用DuckDuckGo（更稳定）
        ddg_results = _fallback_ddg_html(query)
        if ddg_results and len(ddg_results) > 0:
            logger.info(f"DuckDuckGo HTML搜索成功，返回 {len(ddg_results)} 个结果")
            return ddg_results[:top_k]
    except Exception as e:
        logger.warning(f"DuckDuckGo HTML fallback failed: {type(e).__name__}: {e}")
    
    if _contains_cjk(query):
        try:
            baidu_results = _fallback_baidu_html(query)
            if baidu_results and len(baidu_results) > 0:
                logger.info(f"Baidu HTML搜索成功，返回 {len(baidu_results)} 个结果")
                return baidu_results[:top_k]
        except Exception as e:
            logger.warning(f"Baidu HTML fallback failed: {type(e).__name__}: {e}")

    try:
        bing_results = _fallback_bing_html(query)
        if bing_results and len(bing_results) > 0:
            logger.info(f"Bing HTML搜索成功，返回 {len(bing_results)} 个结果")
            return bing_results[:top_k]
    except Exception as e:
        logger.warning(f"Bing HTML fallback failed: {type(e).__name__}: {e}")

    if not _contains_cjk(query):
        try:
            baidu_results = _fallback_baidu_html(query)
            if baidu_results and len(baidu_results) > 0:
                logger.info(f"Baidu HTML搜索成功，返回 {len(baidu_results)} 个结果")
                return baidu_results[:top_k]
        except Exception as e:
            logger.warning(f"Baidu HTML fallback failed: {type(e).__name__}: {e}")
    
    logger.warning("所有搜索方法都失败，返回空列表")
    return []


def search_links(*args, **kwargs) -> List[str]:
    """只要 links 的便捷函数"""
    return [x["url"] for x in search(*args, **kwargs)]

@tool
def web_search(
    query: str,
    top_k: int = 8,
    language: str = "zh-CN",
)->List[Dict[str, Any]]:
    """
    使用搜索引擎搜索并返回url
    由于SearxNG公共实例SSL问题，直接使用HTML解析以提高速度和稳定性
    :param query: 查询文本
    :param top_k: 选取前多少条结果
    :param language: 语言-国家代码, zh-CN、ru-RU...
    :return: 搜索结果
    """

    # 工具函数必须"尽量不抛异常"，否则会打断整个Agent 流程
    # 同时避免网络调用卡死：用线程超时兜底
    logger.info(f"web_search start q={query!r} top_k={top_k}")
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            # 直接使用HTML解析，跳过SearxNG尝试（因为SSL问题导致所有实例都失败）
            # 这样可以节省时间，直接使用稳定的HTML解析
            fut = ex.submit(
                search,
                query=query,
                top_k=top_k,
                endpoint="http://localhost:8090/search",  # 使用localhost会直接走HTML解析
                language=language,
                safesearch=1,
                timeout=10,  # 减少超时时间，加快失败回退
                dedup=True,
            )
            return fut.result(timeout=12)  # 减少总超时时间
    except FuturesTimeout:
        logger.warning("web_search timeout: return empty list")
        return []
    except Exception as e:
        logger.warning(f"web_search failed err={type(e).__name__}: {e}")
        return []
