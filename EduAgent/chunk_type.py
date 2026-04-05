from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


ChunkKind = Literal[
    "pdf_page",
    "ppt_slide",
    "text_lines",
]


class ChunkMeta(TypedDict, total=False):
    ext: str

    # pdf
    page_no: int
    pages: int

    # ppt
    slide_no: int
    slides: int
    title: str
    include_notes: bool

    # lines
    line_range: List[int]      # [start_line, end_line]
    source_unit: str           # "file" | "docx_paragraphs"

    # 解析警告
    warnings: List[str]

    # 允许你额外扩展
    extra: Dict[str, Any]


class Chunk(TypedDict):
    doc_id: str
    chunk_id: str
    source_path: str
    kind: ChunkKind
    index: int        # page_no / slide_no / chunk_idx (1-based)
    text: str
    meta: ChunkMeta
