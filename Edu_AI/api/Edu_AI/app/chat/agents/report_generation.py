from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI

from core.config import Config
from ..report_domain import REPORT_DEFAULTS


def _normalize_openai_compatible_base_url(base_url: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ""
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def get_fallback_llm() -> Optional[ChatOpenAI]:
    try:
        model_cfg = Config.get_deep_model()
        selected_model = str(model_cfg.get("model_name") or Config.LLM_MODEL_DEEP)
        selected_base = _normalize_openai_compatible_base_url(
            model_cfg.get("api_base")
            or Config.DEEPSEEK_BASE_URL
            or Config.REMOTE_MODEL_API_BASE
        )
        print(
            f"[report_model_debug] stage=fallback_llm "
            f"model={selected_model} base={selected_base}"
        )
        return ChatOpenAI(
            api_key=str(
                model_cfg.get("api_key")
                or Config.DEEPSEEK_API_KEY
                or Config.REMOTE_MODEL_API_KEY
            ),
            base_url=selected_base,
            model=selected_model,
            temperature=0.4,
        )
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
        print(
            f"[report_model_debug] stage=ppt_llm "
            f"model={selected_model} base={selected_base}"
        )
        return ChatOpenAI(
            api_key=selected_key,
            base_url=selected_base,
            model=selected_model,
            temperature=0.4,
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


def build_report_markdown(
    *,
    skill_manager: Any,
    slots: Dict[str, str],
    outline: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """分段生成：按章节->按小节生成，再拼接。

    每次调用模型都携带：全部槽位 + 全量大纲标题 + 当前章节/小节上下文。
    """
    llm = get_fallback_llm()
    if not llm:
        return "", {"chapter_count": 0, "completed_chapters": 0, "retry_count": 0, "failed_chapters": []}

    chapter_prompt = skill_manager.extract_section("edu-report-agent", "REPORT_CHAPTER_GENERATE_PROMPT")
    chapter_prompt = chapter_prompt or "请根据当前章节信息生成正文。"

    outline_items = outline if isinstance(outline, list) else []
    titles = []
    for ch in outline_items:
        if isinstance(ch, dict):
            t = str(ch.get("chapter_title") or ch.get("title") or "").strip()
            if t:
                titles.append(t)
    outline_titles = " | ".join(titles)

    checkpoint: Dict[str, Any] = {
        "chapter_count": len(outline_items),
        "completed_chapters": 0,
        "current_chapter_index": 0,
        "retry_count": 0,
        "failed_chapters": [],
        "failed_sections": [],
        "last_previous_ending": "",
        "chapter_snapshots": [],
    }

    full_chunks: List[str] = []
    previous_ending = ""

    # 单小节重试，避免整章失败
    max_retry_per_section = 2

    strict_appendix = (
        "\n\n【强约束-必须遵守】\n"
        "1) 只围绕当前 section_title 写该小节，禁止展开无关故事。\n"
        "2) 输出必须是该小节正文，且第一行必须以 `### ` 开头并包含 section_title。\n"
        "3) 禁止小说化叙事、人物对话、虚构情节。\n"
        "4) 信息不足时可做审慎分析，不得编造事实。\n"
    )

    for idx, ch in enumerate(outline_items, 1):
        if not isinstance(ch, dict):
            continue

        checkpoint["current_chapter_index"] = idx

        chapter_title = str(ch.get("chapter_title") or ch.get("title") or f"第{idx}章").strip()
        chapter_goal = str(ch.get("chapter_goal") or "").strip() or "本章围绕核心主题进行分析"

        sections = ch.get("sections") if isinstance(ch.get("sections"), list) else []
        section_items: List[Dict[str, Any]] = [s for s in sections if isinstance(s, dict)]
        if not section_items:
            points = ch.get("points") if isinstance(ch.get("points"), list) else []
            section_items = [{"section_id": f"{idx}.{p_i + 1}", "title": str(p).strip()} for p_i, p in enumerate(points) if str(p).strip()]

        section_titles = [str(s.get("title") or "").strip() for s in section_items if str(s.get("title") or "").strip()]

        chapter_blocks: List[str] = [
            f"## {chapter_title}",
            "",
            f"本章目标：{chapter_goal}",
            "",
        ]

        for s_i, s in enumerate(section_items, 1):
            section_id = str(s.get("section_id") or f"{idx}.{s_i}").strip()
            section_title = str(s.get("title") or f"小节{s_i}").strip()

            section_prompt = chapter_prompt.format(
                core_topic=slots.get("core_topic") or REPORT_DEFAULTS["core_topic"],
                focus_area=slots.get("focus_area") or REPORT_DEFAULTS["focus_area"],
                depth_level=slots.get("depth_level") or REPORT_DEFAULTS["depth_level"],
                format_style=slots.get("format_style") or REPORT_DEFAULTS["format_style"],
                outline_titles=outline_titles,
                chapter_title=chapter_title,
                chapter_goal=chapter_goal,
                section_titles="、".join(section_titles) if section_titles else "核心要点",
                previous_ending=previous_ending,
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

            section_content = ""
            for attempt in range(max_retry_per_section + 1):
                try:
                    response = llm.invoke([
                        {"role": "system", "content": "你是资深研究写作助手。"},
                        {"role": "user", "content": section_prompt},
                    ])
                    content = _extract_text_from_response(response)
                    if content:
                        # 若模型没写 ### 标题，自动补齐
                        if not content.lstrip().startswith("###"):
                            content = f"### {section_title}\n\n{content}".strip()
                        section_content = content
                        break
                except Exception:
                    pass

                if attempt < max_retry_per_section:
                    checkpoint["retry_count"] = int(checkpoint.get("retry_count", 0)) + 1
                    time.sleep(0.3)

            if not section_content:
                checkpoint["failed_sections"].append({
                    "chapter_index": idx,
                    "chapter_title": chapter_title,
                    "section_id": section_id,
                    "section_title": section_title,
                })
                section_content = (
                    f"### {section_title}\n\n"
                    "（该小节生成中断，先保留占位，后续可补写。）"
                )

            chapter_blocks.append(section_content)
            chapter_blocks.append("")

            paras = [p.strip() for p in section_content.split("\n") if p.strip()]
            if paras:
                previous_ending = paras[-1]
                checkpoint["last_previous_ending"] = previous_ending

        chapter_text = "\n".join(chapter_blocks).strip()
        if chapter_text:
            full_chunks.append(chapter_text)
            checkpoint["completed_chapters"] = int(checkpoint.get("completed_chapters", 0)) + 1
            checkpoint["chapter_snapshots"].append(
                {
                    "chapter_index": idx,
                    "chapter_title": chapter_title,
                    "content": chapter_text,
                }
            )
        else:
            checkpoint["failed_chapters"].append({"index": idx, "title": chapter_title})

    if not full_chunks:
        return "", checkpoint

    body = "\n\n".join(full_chunks).strip()

    stitch_prompt = skill_manager.extract_section("edu-report-agent", "REPORT_STITCH_SUMMARY_PROMPT")
    if not stitch_prompt:
        return body, checkpoint

    try:
        response = llm.invoke([
            {"role": "system", "content": stitch_prompt},
            {"role": "user", "content": body},
        ])
        stitched = _extract_text_from_response(response)
        if stitched:
            return f"{stitched}\n\n{body}".strip(), checkpoint
    except Exception:
        pass

    return body, checkpoint
