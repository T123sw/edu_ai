"""pipeline.tasks

实现三阶段异步任务：crawl / parse / chunk。
此版本修复 ROOT 目录计算：不再依赖固定的 parents 层数，
而是向上递归寻找包含“自动化爬虫”目录的路径，保证跨环境稳定。
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from typing import Dict, Any, List

from .models import (
    TaskStatus,
    CrawlConfig,
    ParseConfig,
    ChunkConfig,
    TaskType,
    CrawlTask,
    ParseTask,
    ChunkTask,
)
from .storage import store

# ---------------------------------------------------------------------------
# 动态解析项目根目录 ROOT
ROOT = Path(__file__).resolve()
while ROOT != ROOT.parent and not (ROOT / "自动化爬虫").exists():
    ROOT = ROOT.parent
if not (ROOT / "自动化爬虫").exists():
    raise RuntimeError("未找到包含 ‘自动化爬虫’ 的项目根路径")

SPIDER_SRC = ROOT / "自动化爬虫" / "src" / "selenium_way"
if str(SPIDER_SRC) not in sys.path:
    sys.path.append(str(SPIDER_SRC))

MINERU_PY = ROOT / "mineru.py"
NEW_PY = ROOT / "new.py"

# ---------------------------------------------------------------------------
# 工具函数

def _safe_keyword_dir(keyword: str) -> str:
    illegal = "\\/:*?\"<>|\n\t"
    filtered = "".join(c for c in keyword if c not in illegal) or "keyword"
    return filtered[:60]


def _list_files(base: Path, suffix: str) -> List[str]:
    return [str(p) for p in base.rglob(f"*.{suffix}") if p.is_file()]

# ---------------------------------------------------------------------------
# 任务实现

async def crawl_worker(task_id: str, cfg: Dict[str, Any]):
    task = store.get(task_id)
    if not isinstance(task, CrawlTask):
        return

    store.update(task_id, status=TaskStatus.RUNNING, details={"current": "启动 Selenium 爬虫"})

    keywords: List[str] = cfg.get("keywords") or ["默认关键词"]
    keyword = keywords[0]
    pages: int = cfg.get("pages", 1)

    out_dir = ROOT / "storage" / "raw_pdf" / _safe_keyword_dir(keyword)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 延迟导入，避免热重载时异常
    try:
        import importlib

        CNKI = importlib.import_module("CNKI")
    except Exception as e:
        store.update(task_id, status=TaskStatus.FAILED, error=f"导入爬虫模块失败: {e}")
        return

    loop = asyncio.get_event_loop()

    def _run():
        try:
            CNKI.run(str(out_dir), keyword, pages)
            return True, None
        except Exception as exc:
            return False, str(exc)

    success, err = await loop.run_in_executor(None, _run)
    if not success:
        store.update(task_id, status=TaskStatus.FAILED, error=f"爬虫执行失败: {err}")
        return

    pdf_files = _list_files(out_dir, "pdf")
    if not pdf_files:
        store.update(task_id, status=TaskStatus.FAILED, error="爬虫结束但未下载到 PDF")
        return

    store.update(
        task_id,
        status=TaskStatus.SUCCESS,
        progress=100,
        details={"current": "爬取完成", "downloaded": len(pdf_files), "pdf_files": pdf_files},
    )

    # 自动触发解析任务
    parse_cfg = ParseConfig(pdf_paths=pdf_files)
    parse_task_id = f"parse_{uuid.uuid4().hex[:8]}"
    parse_task = ParseTask(task_id=parse_task_id, config=parse_cfg, task_type=TaskType.PARSE)
    store.save(parse_task)
    asyncio.create_task(parse_worker(parse_task_id, parse_cfg.model_dump()))


async def parse_worker(task_id: str, cfg: Dict[str, Any]):
    task = store.get(task_id)
    if not isinstance(task, ParseTask):
        return

    pdf_paths: List[str] = cfg.get("pdf_paths", [])
    if not pdf_paths:
        store.update(task_id, status=TaskStatus.FAILED, error="解析任务缺少 pdf_paths")
        return

    total = len(pdf_paths)
    first_pdf = Path(pdf_paths[0])
    keyword_dir = first_pdf.parent.name
    out_base = ROOT / "storage" / "raw_text" / keyword_dir
    out_base.mkdir(parents=True, exist_ok=True)

    store.update(task_id, status=TaskStatus.RUNNING, details={"current": "开始 PDF 解析", "total": total})

    out_files: List[str] = []

    async def _convert(idx: int, pdf: str):
        cmd = [sys.executable, str(MINERU_PY), "-p", pdf, "-o", str(out_base)]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        md = Path(out_base) / (Path(pdf).stem + ".md")
        if md.exists():
            out_files.append(str(md))
        store.update(task_id, progress=int(idx/total*100), details={"current": Path(pdf).name, "processed": idx})

    for idx, pdf in enumerate(pdf_paths, 1):
        await _convert(idx, pdf)

    if not out_files:
        store.update(task_id, status=TaskStatus.FAILED, error="MinerU 未生成文本")
        return

    store.update(task_id, status=TaskStatus.SUCCESS, progress=100, details={"output_files": out_files})

    # 触发 chunk
    chunk_cfg = ChunkConfig(text_paths=out_files)
    chunk_task_id = f"chunk_{uuid.uuid4().hex[:8]}"
    chunk_task = ChunkTask(task_id=chunk_task_id, config=chunk_cfg, task_type=TaskType.CHUNK)
    store.save(chunk_task)
    asyncio.create_task(chunk_worker(chunk_task_id, chunk_cfg.model_dump()))


async def chunk_worker(task_id: str, cfg: Dict[str, Any]):
    task = store.get(task_id)
    if not isinstance(task, ChunkTask):
        return

    txt_paths: List[str] = cfg.get("text_paths", [])
    if not txt_paths:
        store.update(task_id, status=TaskStatus.FAILED, error="切块任务缺少 text_paths")
        return

    min_level = cfg.get("min_heading_level", 3)
    out_dir = ROOT / "storage" / "chunks"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 导入 new.py
    try:
        import importlib

        new_mod = importlib.import_module("new")
        split_by_level = new_mod.split_by_level  # type: ignore[attr-defined]
    except Exception as e:
        store.update(task_id, status=TaskStatus.FAILED, error=f"导入 new.py 失败: {e}")
        return

    total = len(txt_paths)
    store.update(task_id, status=TaskStatus.RUNNING, details={"total": total})

    out_files: List[str] = []
    for idx, md in enumerate(txt_paths, 1):
        try:
            text = Path(md).read_text(encoding="utf-8")
            sections = split_by_level(text, min_level)
            sub_dir = out_dir / Path(md).stem
            sub_dir.mkdir(parents=True, exist_ok=True)
            for i, (_, content) in enumerate(sections, 1):
                fp = sub_dir / f"{i:03d}.md"
                fp.write_text(content, encoding="utf-8")
                out_files.append(str(fp))
        except Exception as e:
            print("chunk err", e)
        store.update(task_id, progress=int(idx/total*100), details={"processed": idx})

    if out_files:
        store.update(task_id, status=TaskStatus.SUCCESS, progress=100, details={"chunks": len(out_files), "output_files": out_files})
    else:
        store.update(task_id, status=TaskStatus.FAILED, error="切块未生成文件")
