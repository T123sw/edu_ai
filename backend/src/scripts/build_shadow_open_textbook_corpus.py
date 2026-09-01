from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from dotenv import load_dotenv

from app.services.course_knowledge_builder import (
    OPEN_TEXTBOOK_SOURCES,
    _materialize_remote_assets,
    _parse_translated_page,
    fetch_open_textbook_pages,
    translate_markdown_to_chinese,
    utc_now,
)


PAGE_TO_NODE = {
    "01-computational-thinking": "ct-definition",
    "02-algorithms": "algorithm-properties",
    "03-computability": "computability-model",
    "04-programming-languages": "program-execution",
    "05-ordered-structures": "array-linked-list",
    "06-brute-force": "linear-binary-search",
    "07-unordered-structures": "hash",
    "08-recursion": "iteration-recursion",
    "lab-02": "variables-data-types",
    "lab-03": "sequence-selection-loop",
    "09-divide-and-conquer": "divide-conquer",
    "10-dynamic-programming": "dynamic-programming",
    "11-trees": "tree",
    "12-backtracking": "backtracking",
    "13-graphs": "graph",
    "14-greedy": "greedy",
    "15-what-is-a-datum": "data-lifecycle",
    "16-data-models": "model-abstraction",
    "17-pandas": "data-cleaning",
    "18-statistics": "statistical-thinking",
    "19-relational-database": "relational-data",
    "20-graph-database": "graph",
    "21-querying-databases": "relational-data",
}


def _safe_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", value).strip(" .-")
    return cleaned[:90] or "material"


def main() -> int:
    parser = argparse.ArgumentParser(description="构建开放教材影子语料，不修改活动课程库")
    parser.add_argument("--source-id", default="think-and-compute-zh")
    parser.add_argument("--max-pages", type=int, default=80)
    parser.add_argument(
        "--translate",
        action="store_true",
        help="翻译为中文；默认先按英文补充资料入影子库，避免阻塞构建",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("evaluation/shadow/computational-thinking-v2"),
    )
    args = parser.parse_args()
    load_dotenv(Path.cwd() / ".env", override=False)

    source = OPEN_TEXTBOOK_SOURCES[args.source_id]
    pages, revision = fetch_open_textbook_pages(source, max_pages=args.max_pages)
    version_dir = args.output_root / source.source_id / revision[:12]
    documents_dir = version_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    failures: list[dict] = []

    selected = [page for page in pages if page.get("file_stem") in PAGE_TO_NODE]
    for index, page in enumerate(selected, start=1):
        file_stem = str(page["file_stem"])
        node_id = PAGE_TO_NODE[file_stem]
        parsed = _parse_translated_page(page)
        english_title = str(parsed.get("title") or file_stem)
        digest = hashlib.sha256(f"{node_id}\n{page['url']}".encode("utf-8")).hexdigest()[:12]
        filename = f"shadow-think-compute-{node_id}-{digest}.md"
        asset_prefix = f"{Path(filename).stem}.assets"
        path = documents_dir / filename
        if path.exists():
            cached_body = path.read_text(encoding="utf-8")
            cached_chinese_count = len(re.findall(r"[\u3400-\u9fff]", cached_body))
            cached_visible_count = len(re.sub(r"\s+", " ", cached_body).strip())
            if (args.translate and cached_chinese_count >= 500) or (
                not args.translate and cached_visible_count >= 800
            ):
                manifest.append(
                    {
                        "id": f"shadow-{digest}",
                        "filename": filename,
                        "path": str(path.relative_to(version_dir)).replace("\\", "/"),
                        "scope_type": "knowledge_point",
                        "scope_id": node_id,
                        "library_type": "course",
                        "source_id": source.source_id,
                        "source_url": page["url"],
                        "source_title": english_title,
                        "source_license": source.license_name,
                        "source_license_url": source.license_url,
                        "source_revision": revision,
                        "source_language": source.source_language,
                        "content_language": "zh-CN" if args.translate else "en",
                        "translation_notice": (
                            "机器翻译/中文适配，保留原文链接供核验"
                            if args.translate
                            else "英文开放教材原文，作为中文课程的补充资料"
                        ),
                        "authority_tier": "reviewed_open_textbook",
                        "linked_assets": [],
                        "substantive_chinese_chars": cached_chinese_count,
                        "status": "staged",
                        "reused": True,
                    }
                )
                continue
        action = "翻译与审查" if args.translate else "英文原文审查"
        print(f"[ShadowCorpus] {index}/{len(selected)} {action}: {english_title}")
        translated = (
            translate_markdown_to_chinese(str(page.get("content") or ""))
            if args.translate
            else str(page.get("content") or "")
        )
        chinese_count = len(re.findall(r"[\u3400-\u9fff]", translated))
        visible_count = len(re.sub(r"\s+", " ", translated).strip())
        if args.translate and chinese_count < 500:
            raise ValueError(f"译文中文正文不足 500 字: {english_title}")
        if not args.translate and visible_count < 800:
            raise ValueError(f"英文教材正文不足 800 字: {english_title}")
        if translated.count("```") % 2 or translated.count("$$") % 2:
            raise ValueError(f"译文破坏了代码或公式边界: {english_title}")

        try:
            translated, assets = _materialize_remote_assets(
                translated,
                raw_url=str(page.get("raw_url") or page.get("url") or ""),
                asset_dir=documents_dir / asset_prefix,
                markdown_asset_prefix=asset_prefix,
                allowed_hosts=source.allowed_hosts,
            )
        except Exception as exc:
            failures.append(
                {
                    "file_stem": file_stem,
                    "scope_id": node_id,
                    "source_url": page.get("url"),
                    "error": str(exc),
                }
            )
            continue
        body = (
            f"# {_safe_name(english_title)}{'（中文适配）' if args.translate else ''}\n\n"
            f"> 来源：[{source.publisher}]({page['url']})  \n"
            f"> 许可：[{source.license_name}]({source.license_url})  \n"
            f"> 语言：{'简体中文（由开放许可英文原文翻译/适配）' if args.translate else '英文补充资料'}  \n"
            f"> 版本：{revision}  \n"
            f"> 署名：{source.attribution}\n\n"
            f"{translated.strip()}\n"
        )
        path.write_text(body, encoding="utf-8")
        manifest.append(
            {
                "id": f"shadow-{digest}",
                "filename": filename,
                "path": str(path.relative_to(version_dir)).replace("\\", "/"),
                "scope_type": "knowledge_point",
                "scope_id": node_id,
                "library_type": "course",
                "source_id": source.source_id,
                "source_url": page["url"],
                "source_title": english_title,
                "source_license": source.license_name,
                "source_license_url": source.license_url,
                "source_revision": revision,
                "source_language": source.source_language,
                "content_language": "zh-CN" if args.translate else "en",
                "translation_notice": (
                    "机器翻译/中文适配，保留原文链接供核验"
                    if args.translate
                    else "英文开放教材原文，作为中文课程的补充资料"
                ),
                "authority_tier": "reviewed_open_textbook",
                "linked_assets": assets,
                "substantive_chinese_chars": chinese_count,
                "substantive_chars": visible_count,
                "status": "staged",
            }
        )

    payload = {
        "builder": "shadow-open-textbook-v2",
        "source_id": source.source_id,
        "source_revision": revision,
        "status": "staged" if not failures else "partially_staged",
        "document_count": len(manifest),
        "failure_count": len(failures),
        "failures": failures,
        "built_at": utc_now(),
        "documents": manifest,
    }
    (version_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**payload, "documents": "omitted"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
