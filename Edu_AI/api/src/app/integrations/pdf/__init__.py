"""PDF 解析 provider 包。

对外统一入口：业务层只从这里 import，不直接依赖具体实现。

    from app.integrations.pdf import get_pdf_parser, ParsedPdf

    parser = get_pdf_parser()                    # 默认 MinerU Cloud（读 .env）
    result = parser.parse(pdf_bytes, filename="ch1.pdf")
    md = result.text

见 docs/spec/SPEC-03（解析迁移）与 docs/acceptance/ACC-03。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .base import ParsedPdf, PdfParseError, PdfParseProvider
from .mineru_cloud import MinerUCloudProvider

__all__ = [
    "ParsedPdf",
    "PdfParseError",
    "PdfParseProvider",
    "MinerUCloudProvider",
    "get_pdf_parser",
    "write_parsed_markdown",
]

# 解析后端选择：默认 mineru-cloud。留出扩展位（未来可加 sidecar/unpdf 实现）。
_PDF_PARSER_PROVIDER = os.getenv("PDF_PARSER_PROVIDER", "mineru-cloud").strip().lower()

_singleton: Optional[PdfParseProvider] = None


def get_pdf_parser() -> PdfParseProvider:
    """返回默认 PDF 解析 provider（进程内单例）。"""
    global _singleton
    if _singleton is None:
        if _PDF_PARSER_PROVIDER in ("mineru-cloud", "mineru", "mineru_cloud"):
            _singleton = MinerUCloudProvider()
        else:
            raise PdfParseError(f"未知 PDF_PARSER_PROVIDER: {_PDF_PARSER_PROVIDER}")
    return _singleton


def write_parsed_markdown(result: ParsedPdf, out_dir: Path, stem: str) -> Path:
    """把解析结果按「{stem}.md + images/」落盘，兼容旧本地 MinerU 的目录消费方。

    返回写出的 markdown 文件路径。图片按 imageMapping 的 basename 写到 out_dir/images/。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{stem}.md"
    md_path.write_text(result.text or "", encoding="utf-8")

    image_mapping = result.metadata.get("imageMapping") or {}
    if image_mapping:
        import base64 as _b64

        img_dir = out_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        for basename, data_url in image_mapping.items():
            try:
                b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
                (img_dir / basename).write_bytes(_b64.b64decode(b64))
            except Exception:
                continue
    return md_path
