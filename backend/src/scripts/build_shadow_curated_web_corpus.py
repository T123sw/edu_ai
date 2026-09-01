from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown

from app.services.course_knowledge_builder import (
    _http_get_with_retry,
    _materialize_remote_assets,
    _robots_allows,
    _supplement_policy,
    utc_now,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取白名单中文资料到 v2 影子课程库")
    parser.add_argument("--registry", type=Path, default=Path("evaluation/candidates/curated-sources-v2.json"))
    parser.add_argument("--output-root", type=Path, default=Path("evaluation/shadow/computational-thinking-v2/curated-web/v1"))
    parser.add_argument("--max-sources", type=int, default=100)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))[: max(0, args.max_sources)]
    documents_dir = args.output_root / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    failures = []
    headers = {"User-Agent": "EduAI-CourseKnowledgeBuilder/1.0 (+source-attribution)"}
    with httpx.Client(timeout=40, follow_redirects=True, headers=headers) as client:
        for index, source in enumerate(registry, start=1):
            scope_id = str(source["scope_id"])
            url = str(source["url"])
            title = str(source["title"])
            policy = _supplement_policy(url)
            if policy is None:
                failures.append({"scope_id": scope_id, "url": url, "error": "source_not_allowlisted"})
                continue
            digest = hashlib.sha256(f"{scope_id}\n{url}".encode("utf-8")).hexdigest()[:12]
            filename = f"shadow-curated-{scope_id}-{digest}.md"
            path = documents_dir / filename
            if not args.refresh and path.exists() and len(path.read_text(encoding="utf-8")) >= 800:
                manifest.append(
                    {
                        "id": f"curated-{digest}",
                        "filename": filename,
                        "path": str(path.relative_to(args.output_root)).replace("\\", "/"),
                        "scope_type": "knowledge_point",
                        "scope_id": scope_id,
                        "library_type": "course",
                        "source_url": url,
                        "source_title": title,
                        "source_site_name": policy["site_name"],
                        "source_license": policy["license"],
                        "source_license_url": policy["license_url"],
                        "source_language": policy["language"],
                        "content_language": policy["language"],
                        "authority_tier": "reviewed_supplementary_source",
                        "status": "staged",
                        "reused": True,
                    }
                )
                continue
            print(f"[CuratedWeb] {index}/{len(registry)} {scope_id} {url}")
            try:
                if not _robots_allows(client, url):
                    raise PermissionError("robots.txt 不允许抓取")
                response = _http_get_with_retry(client, url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                main = soup.select_one(
                    "#mw-content-text .mw-parser-output, main, article, [role='main'], "
                    "#content, #general-page-content, #content-container"
                )
                if main is None:
                    raise ValueError("未识别到网页正文")
                for element in main.select(
                    "script, style, nav, header, footer, aside, form, noscript, "
                    ".navbox, .vertical-navbox, .metadata, .ambox, .mw-editsection, sup.reference, .printfooter"
                ):
                    element.decompose()
                for table in list(main.select("table")):
                    if table.attrs is None:
                        continue
                    classes = {str(value).casefold() for value in (table.get("class") or [])}
                    link_count = len(table.select("a[href]"))
                    text_length = len(table.get_text(" ", strip=True))
                    if classes.intersection({"navbox", "sidebar", "metadata", "vertical-navbox"}) or (
                        link_count >= 30 and text_length >= 1200
                    ):
                        table.decompose()
                excluded_headings = {
                    "参考资料",
                    "参考文献",
                    "外部链接",
                    "延伸阅读",
                    "拓展阅读",
                    "参见",
                    "references",
                    "external links",
                    "further reading",
                    "see also",
                }
                for heading in list(main.select("h2, h3")):
                    heading_text = heading.get_text(" ", strip=True).casefold()
                    if heading_text not in excluded_headings:
                        continue
                    level = int(heading.name[1])
                    current = heading.next_sibling
                    while current is not None:
                        following = current.next_sibling
                        if getattr(current, "name", None) in {"h2", "h3"}:
                            next_level = int(current.name[1])
                            if next_level <= level:
                                break
                        current.extract()
                        current = following
                    heading.decompose()
                images = list(main.select("img[src]"))
                kept = 0
                for image in images:
                    src = str(image.get("src") or "")
                    # MediaWiki exposes many equations as generated SVG images.
                    # Preserve their LaTeX alternative instead of downloading a
                    # rate-limited rendering endpoint as if it were a figure.
                    if "/media/math/render/" in src:
                        formula = str(image.get("alt") or "").strip()
                        image.replace_with(f"${formula}$" if formula else "")
                        continue
                    width = int(str(image.get("width") or "0").replace("px", "") or 0)
                    if kept >= 5 or (width and width < 80):
                        image.decompose()
                        continue
                    image["src"] = urljoin(str(response.url), src)
                    kept += 1
                markdown = html_to_markdown(str(main), heading_style="ATX").strip()
                chinese_count = len(re.findall(r"[\u3400-\u9fff]", markdown))
                if policy["language"] == "zh-CN" and chinese_count < 300:
                    raise ValueError("中文正文不足 500 字")
                if len(markdown) < 800:
                    raise ValueError("网页正文不足 1200 字")
                asset_prefix = f"{Path(filename).stem}.assets"
                page_host = urlparse(str(response.url)).netloc.casefold().split(":", 1)[0]
                markdown, assets = _materialize_remote_assets(
                    markdown,
                    raw_url=str(response.url),
                    asset_dir=documents_dir / asset_prefix,
                    markdown_asset_prefix=asset_prefix,
                    allowed_hosts=(page_host, "wikimedia.org", "upload.wikimedia.org", "docs.python.org"),
                )
                body = (
                    f"# {title}｜精选补充资料\n\n"
                    f"> 来源：[{policy['site_name']}]({response.url})  \n"
                    f"> 许可：[{policy['license']}]({policy['license_url']})  \n"
                    f"> 语言：{'简体中文' if policy['language'] == 'zh-CN' else '英文'}  \n"
                    f"> 获取时间：{utc_now()}\n\n"
                    f"{markdown}\n"
                )
                path.write_text(body, encoding="utf-8")
                manifest.append(
                    {
                        "id": f"curated-{digest}",
                        "filename": filename,
                        "path": str(path.relative_to(args.output_root)).replace("\\", "/"),
                        "scope_type": "knowledge_point",
                        "scope_id": scope_id,
                        "library_type": "course",
                        "source_url": str(response.url),
                        "source_title": title,
                        "source_site_name": policy["site_name"],
                        "source_license": policy["license"],
                        "source_license_url": policy["license_url"],
                        "source_language": policy["language"],
                        "content_language": policy["language"],
                        "authority_tier": "reviewed_supplementary_source",
                        "linked_assets": assets,
                        "status": "staged",
                    }
                )
            except Exception as exc:
                failures.append({"scope_id": scope_id, "url": url, "error": str(exc)})
            finally:
                # Avoid bursts against public reference sites and reduce 429s.
                time.sleep(0.25)

    payload = {
        "builder": "shadow-curated-web-v1",
        "status": "staged" if not failures else "partially_staged",
        "document_count": len(manifest),
        "failure_count": len(failures),
        "failures": failures,
        "documents": manifest,
    }
    (args.output_root / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**payload, "documents": "omitted"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
