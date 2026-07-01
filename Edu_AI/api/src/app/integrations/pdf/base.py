"""PDF 解析 provider 抽象 —— 让业务层与具体解析实现（MinerU Cloud 等）解耦。

设计目标（见 docs/spec/SPEC-03）：
- 业务层只依赖 `PdfParseProvider` 接口和 `ParsedPdf` 数据模型，不关心底层是
  MinerU Cloud、本地 CLI 还是别的实现。
- 一次解析产出统一的 `ParsedPdf`，各调用点按需取 markdown / images / formulas。

无第三方依赖，纯类型 + 抽象基类。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ParsedPdf:
    """统一的 PDF 解析结果（镜像 OpenMAIC ParsedPdfContent 的关心子集）。"""

    text: str
    """提取的正文（MinerU 为 full.md 的 markdown 内容）。"""

    images: List[str] = field(default_factory=list)
    """图片，base64 data URL 数组（形如 ``data:image/png;base64,...``）。"""

    tables: List[Dict[str, Any]] = field(default_factory=list)
    """表格（MinerU 特性，可能为空）。"""

    formulas: List[Dict[str, Any]] = field(default_factory=list)
    """公式，元素含 ``latex`` 字段（MinerU 会把公式识别成 LaTeX）。"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """元数据：pageCount / parser / taskId(batch_id) / imageMapping 等。"""

    def is_empty(self) -> bool:
        return not (self.text and self.text.strip())


class PdfParseError(RuntimeError):
    """PDF 解析失败（网络、上游报错、超时、格式异常等统一抛这个）。"""


class PdfParseProvider(abc.ABC):
    """PDF 解析 provider 接口。实现类只需给出 ``parse`` 同步方法。"""

    #: provider 标识（如 "mineru-cloud"），写入 ParsedPdf.metadata['parser']
    provider_id: str = "unknown"

    @abc.abstractmethod
    def parse(self, pdf: bytes, *, filename: str = "document.pdf") -> ParsedPdf:
        """解析一份 PDF 字节流，返回统一结果。失败抛 :class:`PdfParseError`。"""
        raise NotImplementedError

    async def parse_async(self, pdf: bytes, *, filename: str = "document.pdf") -> ParsedPdf:
        """异步封装：默认把同步 ``parse`` 丢到线程池，供 async 调用点直接 await。"""
        import asyncio

        return await asyncio.to_thread(self.parse, pdf, filename=filename)
