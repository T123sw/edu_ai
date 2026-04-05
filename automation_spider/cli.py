"""Command-line interface for automation_spider.

Usage examples:

    python -m automation_spider pdf --keywords "材料力学" --pages 2
    python -m automation_spider txt --keywords "深度学习"
    python -m automation_spider cnki --keywords "机器人视觉"
    python -m automation_spider url --urls "https://example.com/a.pdf\nhttps://example.com/b" 

All sub-command options override defaults from automation_spider.config.settings.
"""
from __future__ import annotations

import argparse
import sys
from importlib import import_module
from pathlib import Path

from .config import settings

# ---------------- helpers -----------------

def _import(attr_path: str):
    """Import module.attr from dotted path string."""
    module_path, attr = attr_path.rsplit(".", 1)
    mod = import_module(module_path)
    return getattr(mod, attr)


def _ensure_output_dir(path: str | Path):
    Path(path).mkdir(parents=True, exist_ok=True)


# ---------------- command handlers -----------------

def _run_pdf(args: argparse.Namespace):
    pdf_runner = _import("自动化爬虫.src.selenium_way.get_PDF_links_by_keywords.pdf_runner")
    settings.keywords = args.keywords
    settings.pages = args.pages
    settings.save_root_dir = args.output
    _ensure_output_dir(settings.save_root_dir)
    pdf_runner(settings.save_root_dir, settings.keywords, settings.pages)


def _run_txt(args: argparse.Namespace):
    txt_runner = _import("自动化爬虫.src.selenium_way.Selenium_get_html.txt_runner")
    settings.keywords = args.keywords
    settings.pages = args.pages
    settings.save_root_dir = args.output
    _ensure_output_dir(settings.save_root_dir)
    txt_runner(settings.save_root_dir, settings.keywords, settings.pages)


def _run_cnki(args: argparse.Namespace):
    cnki_run = _import("自动化爬虫.src.selenium_way.CNKI.run")
    settings.keywords = args.keywords
    settings.pages = args.pages
    settings.save_root_dir = args.output
    _ensure_output_dir(settings.save_root_dir)
    cnki_run(settings.save_root_dir, settings.keywords, settings.pages)


def _run_urls(args: argparse.Namespace):
    crawle_runner_cls = _import("自动化爬虫.src.selenium_way.crawle_url.crawle_url")
    settings.urls = args.urls
    settings.save_root_dir = args.output
    _ensure_output_dir(settings.save_root_dir)
    crawler = crawle_runner_cls(settings.urls, settings.save_root_dir)
    crawler.run()


# ---------------- main -----------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="automation_spider", description="Unified automation spider CLI")
    parser.add_argument("--output", default=settings.save_root_dir, help="根输出目录 (默认: %(default)s)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # pdf
    pdf_p = subparsers.add_parser("pdf", help="抓取 PDF")
    pdf_p.add_argument("--keywords", required=True)
    pdf_p.add_argument("--pages", type=int, default=settings.pages)
    pdf_p.set_defaults(func=_run_pdf)

    # txt
    txt_p = subparsers.add_parser("txt", help="抓取网页正文为 txt")
    txt_p.add_argument("--keywords", required=True)
    txt_p.add_argument("--pages", type=int, default=settings.pages)
    txt_p.set_defaults(func=_run_txt)

    # cnki
    cnki_p = subparsers.add_parser("cnki", help="抓取 CNKI 文献")
    cnki_p.add_argument("--keywords", required=True)
    cnki_p.add_argument("--pages", type=int, default=settings.pages)
    cnki_p.set_defaults(func=_run_cnki)

    # urls
    url_p = subparsers.add_parser("url", help="抓取指定 URL (PDF 或 网页)")
    url_p.add_argument("--urls", required=True, help="多个 URL 用换行或空格分割")
    url_p.set_defaults(func=_run_urls)

    return parser


def main(argv: list[str] | None = None):
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    # dispatch
    return args.func(args)


if __name__ == "__main__":
    main()

