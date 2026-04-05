from __future__ import annotations

from typing import Optional, Tuple, Dict, Any
import re
from urllib.parse import urljoin

import logging
from bs4 import BeautifulSoup
from readabilipy import simple_json_from_html_string
from markdownify import markdownify

from langchain_core.tools import tool
from playwright.sync_api import (
    sync_playwright,
    Error as PWError,
    TimeoutError as PWTimeoutError,
)

logger = logging.getLogger(__name__)

# 过滤 js 链接
_JS_SCHEME = re.compile(
    r"^javascript:\s*(?:void\s*\(\s*0\s*\)\s*;?\s*|;?\s*)$",
    re.I,
)


def _is_pdf_content_type(ctype: str) -> bool:
    ctype = (ctype or "").lower()
    return ("application/pdf" in ctype) or ("pdf" in ctype)


class ScanPage:
    """
    scan_page（稳定可用版，适配国内网络）：

    关键点：
    - Playwright + Chromium，服务器常用稳定 args
    - wait_until=domcontentloaded，timeout 默认 45s
    - 拦截 image/font/media 降低卡住概率
    - 先 readability 抽正文；抽不到则 fallback：title + body 可见文本
      （避免“门户页/搜索页/SPA”直接返回 None）
    - 失败时返回 None，但会在日志里留下 meta（status/final_url/错误原因）
    """

    def __init__(
        self,
        headless: bool = True,
        max_chars: int = 4500,
        playwright_timeout_ms: int = 45_000,
    ):
        self.headless = headless
        self.max_chars = max_chars
        self.playwright_timeout_ms = playwright_timeout_ms

        self.user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    # ---------------- HTML -> 正文抽取 ----------------
    def _extract_article_from_html(self, html: str, base_url: str) -> Optional[str]:
        if not html or not html.strip():
            return None

        soup = BeautifulSoup(html, "lxml")

        # 把 a 替换为 [link:url,文本]
        for a in soup.find_all("a"):
            href = a.get("href", "") or ""
            if not href:
                continue
            if href in ("#", "/", "javascript"):
                continue
            if _JS_SCHEME.match(href):
                continue

            href = urljoin(base_url, href)
            text = a.get_text(strip=True)
            a.replace_with(f"[link:{href},{text}]")

        html_clean = str(soup)

        try:
            article = simple_json_from_html_string(html_clean) or {}
        except Exception as e:
            logger.warning(f"readabilipy failed: {base_url} err={e}")
            return None

        title = (article.get("title") or "").strip()
        content = article.get("content") or ""
        md = markdownify(content)

        final_text = (title + "\n" + md).strip()
        if not final_text:
            return None
        return final_text[: self.max_chars]

    # ---------------- Playwright 加载 ----------------
    def _load_with_playwright(self, url: str) -> Tuple[Optional[str], str, Dict[str, Any]]:
        """
        return: (html, content_type, meta)
        meta: {
          status, final_url, title,
          body_text_len,
          error
        }
        """
        meta: Dict[str, Any] = {
            "status": None,
            "final_url": url,
            "title": "",
            "body_text_len": 0,
            "error": "",
        }
        ctype = ""

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-ipv6",
                    ],
                )

                context = browser.new_context(
                    user_agent=self.user_agent,
                    ignore_https_errors=True,
                    viewport={"width": 1280, "height": 720},
                    java_script_enabled=True,
                )

                # 拦截大资源，减少卡死/超时
                def _route(route, request):
                    if request.resource_type in ("image", "media", "font"):
                        return route.abort()
                    return route.continue_()

                context.route("**/*", _route)

                page = context.new_page()
                page.set_default_timeout(self.playwright_timeout_ms)
                page.set_default_navigation_timeout(self.playwright_timeout_ms)

                # 降噪：只记录非静态资源失败
                def _req_failed(req):
                    if req.resource_type in ("image", "media", "font"):
                        return
                    # 某些被我们拦截/取消的请求会显示 aborted/failed，忽略这类
                    # 修复：req.failure可能是字符串或字典，需要统一处理
                    f = req.failure
                    if f is None:
                        f = {}
                    elif isinstance(f, str):
                        # 如果是字符串，转换为字典格式
                        err_lower = f.lower()
                        if "aborted" in err_lower or "blocked" in err_lower:
                            return
                        logger.warning(f"requestfailed: {req.resource_type} {req.url} failure={req.failure}")
                        return
                    elif not isinstance(f, dict):
                        # 如果不是字典也不是字符串，记录并返回
                        logger.warning(f"requestfailed: {req.resource_type} {req.url} failure={req.failure} (unexpected type: {type(f)})")
                        return
                    
                    # f现在是字典，安全地获取errorText
                    err = (f.get("errorText") or "").lower()
                    if "aborted" in err or "blocked" in err:
                        return
                    logger.warning(f"requestfailed: {req.resource_type} {req.url} failure={req.failure}")

                page.on("requestfailed", _req_failed)

                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=self.playwright_timeout_ms)
                except PWTimeoutError:
                    meta["error"] = "goto_timeout"
                    logger.warning(f"Playwright goto timeout: {url}")
                    return None, ctype, meta
                except PWError as e:
                    meta["error"] = f"goto_error:{e}"
                    logger.warning(f"Playwright goto error: {url} err={e}")
                    return None, ctype, meta

                # status / content-type / final_url
                try:
                    if resp is not None:
                        meta["status"] = resp.status
                        ctype = (resp.headers.get("content-type", "") or "").lower()
                except Exception:
                    pass
                try:
                    meta["final_url"] = page.url
                except Exception:
                    pass

                # title / body_text
                try:
                    meta["title"] = page.title() or ""
                except Exception:
                    meta["title"] = ""

                body_text = ""
                try:
                    # 不盲等：给个小 timeout，避免卡
                    body_text = page.locator("body").inner_text(timeout=2000) or ""
                    meta["body_text_len"] = len(body_text)
                except Exception:
                    body_text = ""
                    meta["body_text_len"] = 0

                if _is_pdf_content_type(ctype):
                    # PDF 不需要 content
                    return None, ctype, meta

                # html
                try:
                    html = page.content()
                except PWError as e:
                    meta["error"] = f"content_error:{e}"
                    logger.warning(f"Playwright content error: {url} err={e}")
                    return None, ctype, meta
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
                    try:
                        browser.close()
                    except Exception:
                        pass

                # 把 body_text 也塞进 meta（parse 里 fallback 用）
                meta["_body_text"] = body_text
                return html, ctype, meta

        except Exception as e:
            meta["error"] = f"playwright_boot_error:{e}"
            logger.warning(f"Playwright boot/exec failed: {url} err={e}")
            return None, ctype, meta

    # ---------------- 对外入口 ----------------
    def parse(self, url: str) -> Optional[str]:
        html, ctype, meta = self._load_with_playwright(url)

        logger.info(
            f"scan_page meta: status={meta.get('status')} final_url={meta.get('final_url')} "
            f"title={meta.get('title')} body_len={meta.get('body_text_len')} error={meta.get('error')}"
        )

        # pdf
        if _is_pdf_content_type(ctype):
            return "PDF"

        # 没拿到 html：尝试 fallback 到 title+body_text（有时能救命）
        if not html:
            title = (meta.get("title") or "").strip()
            body = (meta.get("_body_text") or "").strip()
            fb = (title + "\n" + body).strip()
            return fb[: self.max_chars] if fb else None

        # 先用 readability 抽正文（对新闻/博客很有效）
        text = self._extract_article_from_html(html, meta.get("final_url") or url)
        if text:
            return text

        # 抽不到（门户/搜索/SPA）：fallback 到 title + body 可见文本
        title = (meta.get("title") or "").strip()
        body = (meta.get("_body_text") or "").strip()
        fb = (title + "\n" + body).strip()

        if fb:
            return fb[: self.max_chars]

        # 最后兜底：返回 html 前一段（避免 None）
        h = html.strip()
        if h:
            return h[: min(self.max_chars, 2000)]

        return None


# 全局实例
_page = ScanPage(headless=True, playwright_timeout_ms=25_000)


@tool
def scan_page(url: str) -> Optional[str]:
    """
    访问 url，返回网页的 markdown/文本（<= max_chars）：
    - PDF -> 'PDF'
    - 失败 -> None
    :param url: 你要访问网页的url
    :return: 网页的markdown结果（可能会包含新的可访问的链接）
    """
    logger.info(f"scan_page: {url}")
    return _page.parse(url)
