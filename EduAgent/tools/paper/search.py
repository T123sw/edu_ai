from time import sleep
from typing import Literal

import requests
from langchain_core.tools import tool


class PaperSearch:


    def __init__(self):
        self.base_url = 'https://api.openalex.org/works'
        self.headers = {
            'User-Agent': 'mailto:envycrow@163.com',
        }

    def search(self, query: str, time_filter: str, sort: str = "publication_date:desc") -> str:
        """
        使用 OpenAlex 搜索论文，返回前 10 条的精简信息。
        :param query: 查询关键词（可用布尔表达式；用引号包裹短语）
        :param time_filter: 例：'from_publication_date:2024-01-01,to_publication_date:2025-12-31'
        :param sort: 排序字段，默认 'publication_date:desc'，也可 'cited_by_count:desc'
        :return: 字符串形式的列表；元素形如：
                 {'display_name': str, 'publication_year': int|None, 'authorships': list, 'access_url': str|None}
        """
        import requests, html

        def _pick_access_url(work: dict):
            pl = work.get("primary_location") or {}
            pdf = pl.get("pdf_url")
            if pdf:
                return pdf
            homepage = (pl.get("source") or {}).get("homepage_url")
            if homepage:
                return homepage
            oa = (work.get("open_access") or {}).get("oa_url")
            if oa:
                return oa
            return None

        params = {
            "search": query,
            "filter": time_filter,
            "sort": sort,
            "per_page": 10,
        }

        resp = requests.get(self.base_url, params=params, headers=getattr(self, "headers", None), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        works = data.get("results", [])[:10]

        results = []
        for work in works:
            title = work.get("display_name", "") or ""
            # 双重反转义，处理 &amp;lt;...&amp;gt; 这类情况
            title = html.unescape(html.unescape(title))

            item = {
                "display_name": title,
                "publication_year": work.get("publication_year"),
                "authorships": work.get("authorships", []) if isinstance(work.get("authorships"), list) else [],
                "access_url": _pick_access_url(work),
            }
            results.append(item)

        return str(results)


ps = PaperSearch()
@tool
def paper_search(query: str, time_filter: str, sort: str='publication_date:desc'):
    """
    使用openalex进行搜索，返回论文对象列表，默认10条
    :param query: 查询关键词，可以使用bool表达式用"XX"包裹为把XX当作短语，必须要连续出现。
    :param time_filter: 时间过滤器，例：'from_publication_date:2024-01-01,to_publication_date:2025-12-31'
    :param sort: 排序字段，默认'publication_date:desc'。也可用 'cited_by_count:desc'。
    :return: result列表,result = {'display_name':'', 'publication_year':'', 'author_ships':[], 'access_url':''}
    """
    results = ps.search(query, time_filter, sort)
    return results


@tool
def arxiv_search(query: str,
                 start: int = 0,
                 max_results: int = 20,
                 sort_by: str = "submittedDate",   # 可选: relevance | lastUpdatedDate | submittedDate
                 sort_order: str = "descending",    # ascending | descending
                 timeout: int = 30):
    """
    用 arXiv 官方 API 搜索论文，返回字典列表。
    query 语法（示例）:
      - 'all:"graph neural networks" AND cat:cs.LG'
      - 'ti:"large language model" AND au:Smith'
      - 字段前缀: ti(标题), au(作者), abs(摘要), co(机构), jr(期刊), cat(分类), all(全局)
      - 布尔: AND / OR / ANDNOT
    arXiv API 不直接支持时间范围筛选，可用 sort_by=submittedDate 然后**本地过滤日期**。

    返回项字段：
      id, title, summary, authors, pdf_url, primary_category, categories, published, updated, doi, journal_ref
    """
    import requests, feedparser, html

    base_url = "https://export.arxiv.org/api/query"
    headers = {
        "User-Agent": "arxiv-search/1.0 (+your_email@example.com)"  # 按 arXiv 建议写个可联系 UA
    }
    params = {
        "search_query": query,
        "start": max(0, int(start)),
        "max_results": max(1, int(max_results)),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }

    r = requests.get(base_url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()

    feed = feedparser.parse(r.text)
    results = []
    for e in feed.entries:
        # 标题/摘要去 HTML 实体
        title = html.unescape(e.get("title", "").strip())
        summary = html.unescape(e.get("summary", "").strip())

        # 作者列表
        authors = [a.get("name") for a in e.get("authors", []) if a.get("name")]

        # PDF 链接优先从 links 中取 rel=related 或 title=pdf；若无则从 id 构造
        pdf_url = None
        for link in e.get("links", []):
            href = link.get("href")
            if not href:
                continue
            # 常见两种：type=application/pdf 或 title=pdf
            if link.get("type") == "application/pdf" or link.get("title", "").lower() == "pdf" or href.endswith(".pdf"):
                pdf_url = href
                break
        if not pdf_url and e.get("id"):
            # 规范的 pdf 链接：把 abs 换成 pdf
            pdf_url = e["id"].replace("/abs/", "/pdf/") + ".pdf"

        # 主分类与全部分类
        primary_category = None
        if "arxiv_primary_category" in e:
            primary_category = e.arxiv_primary_category.get("term")
        categories = [t.get("term") for t in e.get("tags", []) if t.get("term")]

        # 可选字段
        doi = getattr(e, "arxiv_doi", None)
        journal_ref = getattr(e, "arxiv_journal_ref", None)

        results.append({
            "id": e.get("id"),
            "title": title,
            "summary": summary,
            "authors": authors,
            "pdf_url": pdf_url,
            "primary_category": primary_category,
            "categories": categories,
            "published": e.get("published"),  # ISO8601 字符串
            "updated": e.get("updated"),
            "doi": doi,
            "journal_ref": journal_ref,
        })
    sleep(1)
    return str(results)
