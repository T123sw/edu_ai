from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Tuple

from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI

from core.config import Config
from app.services.runtime_config_resolver import runtime_config_resolver
from ..report_domain import REPORT_DEFAULTS


def _normalize_openai_compatible_base_url(base_url: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ""
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def _thinking_extra_body(model_name: str) -> dict:
    # Qwen3 models enable chain-of-thought thinking by default, causing huge latency.
    if str(model_name or "").lower().startswith("qwen3"):
        return {"enable_thinking": False}
    return {}


class _ConfiguredFallbackChatModel(Runnable[Any, Any]):
    """Keep the selected model primary while failing over to configured backups.

    A provider can have a valid token but still reject completions because of
    account, region, model or transient availability problems.  Resource
    generation should not fail when another locally configured provider is
    healthy.  The wrapper also preserves the structured-output and tool-binding
    interfaces used by the report/quiz orchestration code.
    """

    def __init__(self, models: List[Any]) -> None:
        if not models:
            raise ValueError("at least one chat model is required")
        self.models = list(models)

    def invoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        last_error: Exception | None = None
        for model in self.models:
            try:
                return model.invoke(input, config=config, **kwargs)
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def ainvoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        last_error: Exception | None = None
        for model in self.models:
            try:
                return await model.ainvoke(input, config=config, **kwargs)
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    def stream(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Iterator[Any]:
        # Buffer one completion so a mid-stream provider error never duplicates
        # partial content when the next provider is attempted.
        yield self.invoke(input, config=config, **kwargs)

    async def astream(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        yield await self.ainvoke(input, config=config, **kwargs)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable:
        runnables = [
            model.with_structured_output(schema, **kwargs)
            for model in self.models
        ]
        return runnables[0].with_fallbacks(runnables[1:])

    def bind_tools(self, tools: Any, **kwargs: Any) -> Runnable:
        runnables = [model.bind_tools(tools, **kwargs) for model in self.models]
        return runnables[0].with_fallbacks(runnables[1:])

    def __getattr__(self, name: str) -> Any:
        return getattr(self.models[0], name)


def _chat_model(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout_seconds: float,
) -> ChatOpenAI:
    extra_body = _thinking_extra_body(model)
    return ChatOpenAI(
        api_key=api_key,
        base_url=_normalize_openai_compatible_base_url(base_url),
        model=model,
        temperature=0.4,
        request_timeout=timeout_seconds,
        **({"extra_body": extra_body} if extra_body else {}),
    )


def get_fallback_llm() -> Optional[Any]:
    try:
        runtime_cfg = runtime_config_resolver.resolve("llm")
        model_cfg = Config.get_deep_model()
        selected_model = str(
            runtime_cfg.get("model")
            or model_cfg.get("model_name")
            or Config.LLM_MODEL_DEEP
        )
        selected_base = str(
            runtime_cfg.get("base_url")
            or model_cfg.get("api_base")
            or Config.DEEP_MODEL_API_BASE
            or Config.REMOTE_MODEL_API_BASE
        )
        selected_key = str(
            runtime_cfg.get("api_key")
            or model_cfg.get("api_key")
            or Config.DEEP_MODEL_API_KEY
            or Config.REMOTE_MODEL_API_KEY
        )
        timeout_seconds = float(runtime_cfg.get("timeout_seconds") or 120)
        specs = [(selected_base, selected_key, selected_model)]
        specs.extend(
            [
                (
                    str(Config.OPENROUTER_BASE_URL or ""),
                    str(Config.OPENROUTER_API_KEY or ""),
                    str(Config.LOGIC_MODEL_MINI or ""),
                ),
                (
                    str(Config.REMOTE_MODEL_API_BASE or ""),
                    str(Config.REMOTE_MODEL_API_KEY or ""),
                    "deepseek-chat",
                ),
            ]
        )
        models: List[ChatOpenAI] = []
        seen: set[tuple[str, str]] = set()
        for base_url, api_key, model in specs:
            identity = (
                _normalize_openai_compatible_base_url(base_url),
                model.strip(),
            )
            if not api_key.strip() or not all(identity) or identity in seen:
                continue
            seen.add(identity)
            models.append(
                _chat_model(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    timeout_seconds=timeout_seconds,
                )
            )
        if not models:
            return None
        return _ConfiguredFallbackChatModel(models)
    except Exception as e:
        print(f"[report_model_debug] stage=fallback_llm error={e}")
        return None


def get_ppt_llm() -> Optional[ChatOpenAI]:
    selected_base = _normalize_openai_compatible_base_url(
        os.getenv("PPT_LLM_API_BASE") or ""
    )
    selected_key = str(os.getenv("PPT_LLM_API_KEY") or "").strip()
    selected_model = str(os.getenv("PPT_LLM_MODEL") or "").strip()

    if not (selected_base and selected_key and selected_model):
        return get_fallback_llm()

    try:
        extra_body = _thinking_extra_body(selected_model)
        return ChatOpenAI(
            api_key=selected_key,
            base_url=selected_base,
            model=selected_model,
            temperature=0.4,
            **({"extra_body": extra_body} if extra_body else {}),
        )
    except Exception as e:
        print(f"[report_model_debug] stage=ppt_llm error={e}")
        return get_fallback_llm()


def _extract_text_from_response(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, dict):
                txt = str(item.get("text") or "").strip()
                if txt:
                    chunks.append(txt)
            else:
                txt = str(item or "").strip()
                if txt:
                    chunks.append(txt)
        return "\n".join(chunks).strip()
    return str(content or "").strip()


def _build_report_fast(
    *,
    llm: Any,
    slots: Dict[str, str],
    outline_items: List[Dict[str, Any]],
) -> Tuple[str, Dict[str, Any]]:
    """Fast mode: generate the full report body in a single LLM call.

    Use when expected length is small (≤5000 chars). Trades per-section
    retry granularity for lower latency.
    """
    outline_text_parts: List[str] = []
    for idx, ch in enumerate(outline_items, 1):
        if not isinstance(ch, dict):
            continue
        chapter_title = str(ch.get("chapter_title") or ch.get("title") or f"第{idx}章").strip()
        chapter_goal = str(ch.get("chapter_goal") or "").strip()
        sections = ch.get("sections") if isinstance(ch.get("sections"), list) else []
        section_items = [s for s in sections if isinstance(s, dict)]
        section_lines = "\n".join(
            f"  - {str(s.get('title') or '').strip()}"
            for s in section_items
            if str(s.get("title") or "").strip()
        )
        chapter_block = f"## {chapter_title}"
        if chapter_goal:
            chapter_block += f"\n本章目标：{chapter_goal}"
        if section_lines:
            chapter_block += f"\n小节：\n{section_lines}"
        outline_text_parts.append(chapter_block)

    outline_text = "\n\n".join(outline_text_parts)
    evidence_context = str(slots.get("evidence_context") or "").strip()
    evidence_block = (
        "【可用证据】\n"
        f"{evidence_context}\n\n"
        "证据使用要求：优先依据上述资料写作；涉及来源时保留来源标题或 URL；"
        "资料没有覆盖的事实不得编造。\n\n"
        if evidence_context
        else ""
    )
    prompt = (
        f"你是资深研究写作助手。请根据以下大纲，一次性生成完整的报告正文。\n\n"
        f"主题：{slots.get('core_topic') or REPORT_DEFAULTS['core_topic']}\n"
        f"重点：{slots.get('focus_area') or REPORT_DEFAULTS['focus_area']}\n"
        f"深度：{slots.get('depth_level') or REPORT_DEFAULTS['depth_level']}\n"
        f"格式：{slots.get('format_style') or REPORT_DEFAULTS['format_style']}\n\n"
        f"大纲：\n{outline_text}\n\n"
        f"{evidence_block}"
        "【输出格式要求】\n"
        "1) 使用 Markdown 格式，每章以 `## ` 开头，每节以 `### ` 开头。\n"
        "2) 按大纲顺序输出所有章节和小节，不要省略。\n"
        "3) 禁止小说化叙事、人物对话、虚构情节；信息不足时可审慎分析。\n"
        "4) 直接输出正文内容，不要重复输出大纲标题行。\n"
    )

    t0 = time.perf_counter()
    try:
        response = llm.invoke([
            {"role": "system", "content": "你是资深研究写作助手。"},
            {"role": "user", "content": prompt},
        ])
        body = _extract_text_from_response(response)
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        print(f"[REPORT fast] 一次性生成完成 {elapsed_ms}ms", flush=True)
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        print(f"[REPORT fast] 生成失败 {elapsed_ms}ms | {exc}", flush=True)
        body = ""

    chapter_count = len([ch for ch in outline_items if isinstance(ch, dict)])
    checkpoint: Dict[str, Any] = {
        "chapter_count": chapter_count,
        "completed_chapters": chapter_count if body else 0,
        "retry_count": 0,
        "failed_chapters": [],
        "failed_sections": [],
        "chapter_snapshots": [],
        "llm_calls": [{"stage": "report.fast_body", "duration_ms": elapsed_ms, "retry": 0}],
    }
    return body, checkpoint


def build_report_markdown(
    *,
    skill_manager: Any,
    slots: Dict[str, str],
    outline: Optional[List[Dict[str, Any]]] = None,
    mode: str = "balanced",
) -> Tuple[str, Dict[str, Any]]:
    """生成报告正文。

    mode="fast"     一次 prompt 生成完整正文（适合 5000 字以内，延迟最低）
    mode="balanced" 所有小节并发调用 LLM，最后拼装（默认）
    """
    llm = get_fallback_llm()
    if not llm:
        return "", {"chapter_count": 0, "completed_chapters": 0, "retry_count": 0, "failed_chapters": []}

    outline_items = outline if isinstance(outline, list) else []

    _fast_length_keywords = {"5000字以内", "5000以内", "短篇", "简短", "概述", "摘要", "3000字", "3000以内"}
    _resolved_mode = mode
    if _resolved_mode == "balanced":
        length_req = str(slots.get("length_requirement") or "").strip()
        total_sections = sum(
            len([s for s in (ch.get("sections") or []) if isinstance(s, dict)])
            for ch in outline_items if isinstance(ch, dict)
        )
        if any(kw in length_req for kw in _fast_length_keywords) or (len(outline_items) <= 2 and total_sections <= 4):
            _resolved_mode = "fast"

    if _resolved_mode == "fast":
        return _build_report_fast(llm=llm, slots=slots, outline_items=outline_items)

    chapter_prompt = skill_manager.extract_section("edu-report-agent", "REPORT_CHAPTER_GENERATE_PROMPT")
    chapter_prompt = chapter_prompt or "请根据当前章节信息生成正文。"

    titles = []
    for ch in outline_items:
        if isinstance(ch, dict):
            t = str(ch.get("chapter_title") or ch.get("title") or "").strip()
            if t:
                titles.append(t)
    outline_titles = " | ".join(titles)

    max_retry_per_section = 2

    strict_appendix = (
        "\n\n【强约束-必须遵守】\n"
        "1) 只围绕当前 section_title 写该小节，禁止展开无关故事。\n"
        "2) 输出必须是该小节正文，且第一行必须以 `### ` 开头并包含 section_title。\n"
        "3) 禁止小说化叙事、人物对话、虚构情节。\n"
        "4) 信息不足时可做审慎分析，不得编造事实。\n"
    )
    evidence_context = str(slots.get("evidence_context") or "").strip()
    if evidence_context:
        strict_appendix += (
            "\n\n【可用证据】\n"
            f"{evidence_context}\n"
            "优先依据证据写作并保留来源标题或 URL；证据未覆盖的事实不得编造。\n"
        )

    # --- 第一步：预处理大纲，构建所有小节任务 ---
    # task_key: (chapter_idx, section_idx)
    # task_meta: dict with chapter/section metadata and prompt
    task_order: List[tuple] = []  # ordered list of (ch_idx, s_i)
    task_meta: Dict[tuple, Dict[str, Any]] = {}
    chapter_order: List[tuple] = []  # (ch_idx, chapter_title, chapter_goal)

    for idx, ch in enumerate(outline_items, 1):
        if not isinstance(ch, dict):
            continue

        chapter_title = str(ch.get("chapter_title") or ch.get("title") or f"第{idx}章").strip()
        chapter_goal = str(ch.get("chapter_goal") or "").strip() or "本章围绕核心主题进行分析"

        sections = ch.get("sections") if isinstance(ch.get("sections"), list) else []
        section_items: List[Dict[str, Any]] = [s for s in sections if isinstance(s, dict)]
        if not section_items:
            points = ch.get("points") if isinstance(ch.get("points"), list) else []
            section_items = [{"section_id": f"{idx}.{p_i + 1}", "title": str(p).strip()} for p_i, p in enumerate(points) if str(p).strip()]

        section_titles = [str(s.get("title") or "").strip() for s in section_items if str(s.get("title") or "").strip()]
        chapter_order.append((idx, chapter_title, chapter_goal))

        for s_i, s in enumerate(section_items, 1):
            section_id = str(s.get("section_id") or f"{idx}.{s_i}").strip()
            section_title = str(s.get("title") or f"小节{s_i}").strip()

            # previous_ending 无法在并发模式下获取，传空字符串（各节已独立约束）
            section_prompt = chapter_prompt.format(
                core_topic=slots.get("core_topic") or REPORT_DEFAULTS["core_topic"],
                focus_area=slots.get("focus_area") or REPORT_DEFAULTS["focus_area"],
                depth_level=slots.get("depth_level") or REPORT_DEFAULTS["depth_level"],
                format_style=slots.get("format_style") or REPORT_DEFAULTS["format_style"],
                outline_titles=outline_titles,
                chapter_title=chapter_title,
                chapter_goal=chapter_goal,
                section_titles="、".join(section_titles) if section_titles else "核心要点",
                previous_ending="",
            )
            section_prompt += (
                "\n\n"
                f"【当前仅生成小节】\n"
                f"chapter_title={chapter_title}\n"
                f"chapter_goal={chapter_goal}\n"
                f"section_id={section_id}\n"
                f"section_title={section_title}\n"
                "请只输出这个 section 的内容，不要输出整章。"
            ) + strict_appendix

            key = (idx, s_i)
            task_order.append(key)
            task_meta[key] = {
                "chapter_idx": idx,
                "chapter_title": chapter_title,
                "section_id": section_id,
                "section_title": section_title,
                "prompt": section_prompt,
            }

    if not task_order:
        return "", {"chapter_count": 0, "completed_chapters": 0, "retry_count": 0, "failed_chapters": []}

    # --- 第二步：并发执行所有小节 ---
    def _generate_section(key: tuple) -> tuple:
        meta = task_meta[key]
        prompt = meta["prompt"]
        section_title = meta["section_title"]
        retries = 0
        t0 = time.perf_counter()
        for attempt in range(max_retry_per_section + 1):
            try:
                response = llm.invoke([
                    {"role": "system", "content": "你是资深研究写作助手。"},
                    {"role": "user", "content": prompt},
                ])
                content = _extract_text_from_response(response)
                if content:
                    if not content.lstrip().startswith("###"):
                        content = f"### {section_title}\n\n{content}".strip()
                    elapsed = (time.perf_counter() - t0) * 1000
                    print(f"[REPORT] ok {meta['chapter_title']} / {section_title} {elapsed:.0f}ms", flush=True)
                    return key, content, retries, round(elapsed)
            except Exception:
                pass
            if attempt < max_retry_per_section:
                retries += 1
                time.sleep(0.3)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[REPORT] fail {meta['chapter_title']} / {section_title} {elapsed:.0f}ms", flush=True)
        return key, None, retries, round(elapsed)

    max_workers = min(len(task_order), 6)
    section_results: Dict[tuple, Optional[str]] = {}
    section_timings: Dict[tuple, int] = {}
    total_retries = 0

    t_gen = time.perf_counter()
    print(f"[REPORT] 开始并发生成 {len(task_order)} 个小节，并发数={max_workers}", flush=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_generate_section, key): key for key in task_order}
        for future in as_completed(futures):
            key, content, retries, elapsed_ms = future.result()
            section_results[key] = content
            section_timings[key] = elapsed_ms
            total_retries += retries
    print(f"[REPORT] 全部小节生成完毕 {(time.perf_counter() - t_gen) * 1000:.0f}ms | 重试={total_retries}", flush=True)

    # --- 第三步：按原始顺序拼装 ---
    llm_calls: List[Dict[str, Any]] = [
        {
            "stage": "report.section",
            "chapter_title": task_meta[key]["chapter_title"],
            "section_title": task_meta[key]["section_title"],
            "duration_ms": section_timings.get(key, 0),
            "retry": 0,
        }
        for key in task_order
    ]
    checkpoint: Dict[str, Any] = {
        "chapter_count": len(chapter_order),
        "completed_chapters": 0,
        "retry_count": total_retries,
        "failed_chapters": [],
        "failed_sections": [],
        "chapter_snapshots": [],
        "llm_calls": llm_calls,
    }

    full_chunks: List[str] = []

    for ch_idx, chapter_title, chapter_goal in chapter_order:
        chapter_blocks: List[str] = [
            f"## {chapter_title}",
            "",
            f"本章目标：{chapter_goal}",
            "",
        ]
        chapter_has_content = False
        chapter_keys = [k for k in task_order if k[0] == ch_idx]

        for key in chapter_keys:
            meta = task_meta[key]
            content = section_results.get(key)
            if content:
                chapter_blocks.append(content)
                chapter_blocks.append("")
                chapter_has_content = True
            else:
                checkpoint["failed_sections"].append({
                    "chapter_index": ch_idx,
                    "chapter_title": chapter_title,
                    "section_id": meta["section_id"],
                    "section_title": meta["section_title"],
                })
                chapter_blocks.append(
                    f"### {meta['section_title']}\n\n（该小节生成中断，先保留占位，后续可补写。）"
                )
                chapter_blocks.append("")

        chapter_text = "\n".join(chapter_blocks).strip()
        if chapter_has_content:
            full_chunks.append(chapter_text)
            checkpoint["completed_chapters"] = int(checkpoint.get("completed_chapters", 0)) + 1
            checkpoint["chapter_snapshots"].append({
                "chapter_index": ch_idx,
                "chapter_title": chapter_title,
                "content": chapter_text,
            })
        else:
            checkpoint["failed_chapters"].append({"index": ch_idx, "title": chapter_title})

    if not full_chunks:
        return "", checkpoint

    body = "\n\n".join(full_chunks).strip()

    stitch_prompt = skill_manager.extract_section("edu-report-agent", "REPORT_STITCH_SUMMARY_PROMPT")
    if not stitch_prompt:
        return body, checkpoint

    try:
        t_stitch = time.perf_counter()
        response = llm.invoke([
            {"role": "system", "content": stitch_prompt},
            {"role": "user", "content": body},
        ])
        stitch_ms = round((time.perf_counter() - t_stitch) * 1000)
        checkpoint["llm_calls"].append({"stage": "report.stitch", "duration_ms": stitch_ms, "retry": 0})
        stitched = _extract_text_from_response(response)
        if stitched:
            return f"{stitched}\n\n{body}".strip(), checkpoint
    except Exception:
        pass

    return body, checkpoint
