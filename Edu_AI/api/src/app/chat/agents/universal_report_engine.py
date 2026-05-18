"""Universal Report Engine v2 — Phase-based state machine.

Replaces the Plan-Execute-Analyze loop with an explicit 6-node state machine:

    extractor → evaluator → [asker | confirmer | outliner | generator] → __end__

Each invoke runs one full pass (extract → evaluate → one action node), then pauses
for the next user turn or terminates.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict
from langgraph.graph import StateGraph

from ..tools.agent_tools import (
    ToolRegistry,
    generate_long_report_content,
    revise_outline_with_feedback,
    submit_outline_for_review,
)
from ..report_domain import REPORT_DEFAULTS, REPORT_IMPATIENT_KEYWORDS
from ..agents.report_utils import auto_fill_report_slots, normalize_outline_ast
from ..utils.llm_compat import llm_base_url, llm_model_label, should_skip_function_calling
from ..skill_manager import SkillManager
from core.config import Config
from .report_state import ReportState


# ---------------------------------------------------------------------------
# Tracing (kept from v1)
# ---------------------------------------------------------------------------

def _parse_env_toggle(raw: str) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes"}


_TRACE_ENABLED = _parse_env_toggle(getattr(Config, "UNIVERSAL_REPORT_TRACE", "0"))
# 技能注入日志：默认关闭，按需通过环境变量打开。
# 开启方式：UNIVERSAL_REPORT_SKILL_TRACE=1
_SKILL_INJECTION_TRACE_ENABLED = _parse_env_toggle(getattr(Config, "UNIVERSAL_REPORT_SKILL_TRACE", "0"))


def _trace(title: str, lines: List[str], payload: Optional[Dict[str, Any]] = None) -> None:
    if title.startswith("skills_injection"):
        if not _SKILL_INJECTION_TRACE_ENABLED:
            return
    elif not _TRACE_ENABLED:
        return
    print(f"[报告引擎v2] {title}")
    for ln in lines:
        print(f"  - {ln}")
    if payload is not None:
        try:
            print(f"  - 数据: {json.dumps(payload, ensure_ascii=False)}")
        except Exception:
            print(f"  - 数据: {payload}")


# ---------------------------------------------------------------------------
# Slot extraction models (kept from v1)
# ---------------------------------------------------------------------------


class SlotFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    core_topic: Optional[str] = None
    focus_area: Optional[str] = None
    length_requirement: Optional[str] = None
    depth_level: Optional[str] = None
    format_style: Optional[str] = None
    dynamic_constraints: Optional[str] = None


class SlotExtractOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_slots: SlotFields = Field(default_factory=SlotFields)
    notes: str = Field(default="")


class FocusAssessOut(BaseModel):
    """Output model for focus sufficiency assessment."""
    model_config = ConfigDict(extra="forbid")

    is_sufficient: bool
    reason: str
    suggested_question: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_SLOTS = ["core_topic", "focus_area"]

ALLOWED_SLOT_KEYS = {
    "core_topic", "focus_area", "length_requirement",
    "depth_level", "format_style", "dynamic_constraints",
}
LOW_SIGNAL_SLOT_VALUES = {
    "具体一点",
    "详细一点",
    "展开一点",
    "介绍下整个过程",
    "介绍整个过程",
    "整个过程",
    "继续分析",
    "继续生成",
    "生成报告",
    "请基于当前内容生成一份报告",
}


def _is_affirmative(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return False
    positives = ["可以", "同意", "没问题", "行", "好", "确认", "继续",
                 "ok", "yes", "y", "好的", "没问题的", "就这样", "可以的",
                 "嗯", "对", "是的", "确定", "就按这个"]
    return any(p in t for p in positives)


def _is_outline_confirm(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return False
    confirms = ["确认", "可以", "就按这个", "没问题", "开始生成", "继续",
                "生成正文", "ok", "好", "行", "就这样", "按这个来"]
    return any(c in t for c in confirms)


def _is_impatient(text: str) -> bool:
    t = str(text or "").strip()
    return any(kw in t for kw in REPORT_IMPATIENT_KEYWORDS)


def _llm_meta(llm: Optional[Any]) -> Dict[str, str]:
    if llm is None:
        return {"model": "none", "base_url": "none"}
    model = llm_model_label(llm) or "unknown"
    base_url = llm_base_url(llm) or "unknown"
    return {"model": model, "base_url": base_url}


def _render_extractor_prompt(template: str, state: ReportState) -> str:
    gathered_context = dict(state.get("gathered_context") or {})
    slot_hints = dict(gathered_context.get("slot_hints") or {})
    context_digest = str(gathered_context.get("context_digest") or "").strip()
    tpl = str(template or "").strip()
    if not tpl:
        tpl = (
            "你是需求提取器。请从用户输入提取报告槽位，仅输出JSON。\n"
            "【当前已知】：{current_slots}\n"
            "【用户输入】：{user_input}"
        )
    if "{slot_hints}" not in tpl:
        tpl += "\n【上下文候选槽位】：{slot_hints}"
    if "{context_digest}" not in tpl:
        tpl += "\n【上下文摘要】：{context_digest}"
    return (
        tpl.replace("{current_slots}", json.dumps(state.get("report_slots") or {}, ensure_ascii=False))
        .replace("{slot_hints}", json.dumps(slot_hints, ensure_ascii=False))
        .replace("{context_digest}", context_digest)
        .replace("{user_input}", str(state.get("human_feedback") or state.get("user_input") or ""))
    )


def _is_low_signal_slot_value(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return True
    if normalized in LOW_SIGNAL_SLOT_VALUES:
        return True
    if normalized.startswith("比如"):
        return True
    if normalized.endswith("过程") and len(normalized) <= 8:
        return True
    if normalized.endswith("一点") and len(normalized) <= 8:
        return True
    return False


# ---------------------------------------------------------------------------
# Slot extraction (simplified from v1 — no retry/self-correction removed)
# ---------------------------------------------------------------------------


def _prefill_slots_from_gathered_context(state: ReportState) -> Dict[str, Any]:
    gathered_context = dict(state.get("gathered_context") or {})
    slot_hints = dict(gathered_context.get("slot_hints") or {})
    current_slots = dict(state.get("report_slots") or {})
    merged = dict(current_slots)
    for key in ALLOWED_SLOT_KEYS:
        current = str(merged.get(key) or "").strip()
        hinted = str(slot_hints.get(key) or "").strip()
        if not current and hinted:
            merged[key] = hinted
    return merged


def _extract_slots_with_llm(
    state: ReportState,
    *,
    extractor_llm: Optional[Any],
    extractor_prompt_template: str,
) -> Dict[str, Any]:
    """Extract slots from user input via LLM. Returns a merged slots dict."""
    if extractor_llm is None:
        return {}

    prompt = _render_extractor_prompt(extractor_prompt_template, state)
    incoming: Dict[str, Any] = {}

    meta = _llm_meta(extractor_llm)
    _trace("槽位提取", [f"model={meta['model']}", f"base_url={meta['base_url']}"])

    def _extract_json_candidate(text: str) -> Dict[str, Any]:
        candidate = text
        if "```" in text:
            for part in text.split("```"):
                chunk = part.strip()
                if chunk.startswith("json"):
                    chunk = chunk[4:].strip()
                if chunk.startswith("{") and chunk.endswith("}"):
                    candidate = chunk
                    break
        obj = json.loads(candidate) if candidate else {}
        return obj if isinstance(obj, dict) else {}

    def _validate_contract(obj: Dict[str, Any]) -> SlotExtractOut:
        if "report_slots" in obj:
            return SlotExtractOut.model_validate(obj)
        return SlotExtractOut.model_validate({"report_slots": obj, "notes": ""})

    skip_function_calling = should_skip_function_calling(extractor_llm)
    if skip_function_calling:
        _trace("槽位提取", ["llm_mode=structured_output", "status=skipped_qwen_compat"])

    # Try structured output first, fallback to text JSON
    try:
        if skip_function_calling:
            raise RuntimeError("skip_function_calling")
        structured = extractor_llm.with_structured_output(SlotExtractOut, method="function_calling")
        out: SlotExtractOut = structured.invoke(prompt)
        incoming = out.report_slots.model_dump(exclude_none=True)
    except Exception as e1:
        try:
            raw = extractor_llm.invoke(prompt)
            text = str(getattr(raw, "content", raw) or "").strip()
            obj = _extract_json_candidate(text)
            validated = _validate_contract(obj)
            incoming = validated.report_slots.model_dump(exclude_none=True)
        except Exception as e2:
            _trace("槽位提取", [f"提取失败: {str(e1)[:50]} / {str(e2)[:50]}，保持原槽位"])
            return {}

    # Merge into existing slots (only allowed keys, non-empty values)
    merged = dict(state.get("report_slots") or {})
    for k, v in incoming.items():
        key = str(k).strip()
        if key not in ALLOWED_SLOT_KEYS:
            continue
        text = str(v or "").strip()
        if text:
            existing_text = str(merged.get(key) or "").strip()
            if existing_text and key in {"core_topic", "focus_area"} and _is_low_signal_slot_value(text):
                continue
            # Special case: if focus_area is being refined (user answering follow-up),
            # append to existing focus_area instead of replacing
            if (
                key == "focus_area"
                and existing_text
                and text != existing_text
                and str(state.get("phase") or "").strip().lower() == "asking"
            ):
                # User is refining focus, append the new detail
                merged[key] = f"{merged[key]}（{text}）"
            else:
                merged[key] = text

    _trace("槽位提取", [f"merged_keys={list(merged.keys())}"], {"slots": merged})
    return merged


# ---------------------------------------------------------------------------
# Skill-template rendering (prefer skills, fallback to code defaults)
# ---------------------------------------------------------------------------


def _get_skill_section(section_name: str) -> str:
    try:
        return str(SkillManager().extract_section("edu-report-agent", section_name) or "").strip()
    except Exception:
        return ""


def _extract_first_natural_line(section_text: str) -> str:
    if not section_text:
        return ""
    lines = [ln.strip() for ln in section_text.splitlines()]
    for ln in lines:
        if not ln:
            continue
        if ln.startswith("#") or ln.startswith("-"):
            continue
        if "{" in ln and "}" in ln:
            continue
        if ln.startswith("输入") or ln.startswith("Few-shot") or ln.startswith("表达规范"):
            continue
        return ln
    return ""


def _resolve_tool_callable(
    tool_registry: Optional[ToolRegistry],
    tool_name: str,
    default_callable: Any,
) -> Any:
    if not isinstance(tool_registry, dict):
        return default_callable
    entry = tool_registry.get(tool_name)
    if not isinstance(entry, dict):
        return default_callable
    return entry.get("callable") or default_callable


# ---------------------------------------------------------------------------
# Build soft-confirm question
# ---------------------------------------------------------------------------


def _build_soft_confirm_question(report_slots: Dict[str, Any]) -> str:
    core = str(report_slots.get("core_topic") or "这个主题").strip() or "这个主题"
    focus = str(report_slots.get("focus_area") or "当前方向").strip() or "当前方向"
    length = str(report_slots.get("length_requirement") or "常规（3-4章）").strip()
    depth = str(report_slots.get("depth_level") or "中等深度").strip()
    style = str(report_slots.get("format_style") or "结构化分块论述").strip()

    # 1) 优先读取 skills 模板
    tmpl = _extract_first_natural_line(_get_skill_section("REPORT_SOFT_CONFIRM_PROMPT"))
    if tmpl and "{" in tmpl and "}" in tmpl:
        try:
            rendered = tmpl.format(
                known_core=f"核心主题：{core}；聚焦方向：{focus}",
                core_topic=core,
                focus_area=focus,
                length_requirement=length,
                depth_level=depth,
                format_style=style,
            )
            if rendered.strip():
                return rendered.strip()
        except Exception:
            pass

    # 2) fallback
    return (
        f"方向很清晰，我建议先按“{core}”里“{focus}”来推进。"
        f"我会用{length}的篇幅、{depth}的深度，写成{style}风格。"
        f"如果你觉得可以，我就马上给出大纲。"
    )


# ---------------------------------------------------------------------------
# Build ask question for missing slot
# ---------------------------------------------------------------------------


def _build_ask_question(missing_slot: str, report_slots: Dict[str, Any], llm: Optional[Any] = None) -> str:
    core = str(report_slots.get("core_topic") or "").strip()

    # 1) 优先走 skills 注入 + LLM 动态追问（不改整体流程，仅替换追问生成方式）
    skill_text = _get_skill_section("REPORT_HARD_ASK_PROMPT")
    _trace(
        "skills_injection.ask",
        [
            "section=REPORT_HARD_ASK_PROMPT",
            f"loaded={bool(skill_text)}",
            f"length={len(skill_text)}",
            f"llm_available={llm is not None}",
            f"missing_slot={missing_slot}",
        ],
    )
    if llm is not None and skill_text:
        try:
            prompt = (
                f"{skill_text}\n\n"
                "请根据输入变量，生成一句自然的人类教学助手追问。"
                "要求：只输出最终追问句，不要解释、不要编号、不要 JSON。\n\n"
                f"missing_slot={missing_slot}\n"
                f"known_slots={json.dumps(report_slots or {}, ensure_ascii=False)}\n"
                f"missing_reason=missing_{missing_slot}\n"
            )
            prompt_preview = prompt.replace("\n", " ")[:120]
            _trace("skills_injection.ask", ["using_skill_prompt_for_llm=true", f"prompt_preview={prompt_preview}"])
            raw = llm.invoke(prompt)
            text = str(getattr(raw, "content", raw) or "").strip()
            if text:
                if "```" in text:
                    parts = [p.strip() for p in text.split("```") if p.strip()]
                    if parts:
                        text = parts[-1]
                text = text.replace("\n", " ").strip()
                if text:
                    _trace("skills_injection.ask", ["skill_prompt_llm_output=ok", f"preview={text[:80]}"])
                    return text
            _trace("skills_injection.ask", ["skill_prompt_llm_output=empty"])
        except Exception as exc:
            _trace("skills_injection.ask", [f"skill_prompt_llm_error={exc}"])

    # 2) fallback（skills 缺失或模型失败）
    _trace("skills_injection.ask", ["fallback=code_default"])
    if missing_slot == "core_topic":
        return "我们可以开始写了。先告诉我你最想研究的主题，我就按这个主题往下推进。"

    if missing_slot == "focus_area":
        if core:
            return (
                f"“{core}”这个方向很不错。为了让报告更有针对性，你更想聚焦哪一块？"
                "比如偏机制拆解、案例分析，或落地实践都可以；如果你愿意，我也可以先给你一个常规切口。"
            )
        return "为了更快推进，你希望这份报告主要聚焦哪一块？如果暂时不确定，我可以先按常规分析框架来起草。"

    return f"为了继续推进，我还需要你补充一下 {missing_slot}。"


# ---------------------------------------------------------------------------
# Assess focus sufficiency via LLM
# ---------------------------------------------------------------------------


def _assess_focus_sufficiency_llm(
    slots: Dict[str, Any],
    *,
    assessor_llm: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    LLM one-time assessment of focus_area sufficiency.
    Returns: {"is_sufficient": bool, "reason": str, "suggested_question": Optional[str]}
    """
    if assessor_llm is None:
        return {"is_sufficient": True, "reason": "no_llm", "suggested_question": None}

    core_topic = str(slots.get("core_topic") or "").strip()
    focus_area = str(slots.get("focus_area") or "").strip()

    if not core_topic or not focus_area:
        return {"is_sufficient": True, "reason": "missing_slots", "suggested_question": None}

    prompt = (
        f"你是 focus 充分性评估师。判断用户的 focus_area 是否足够具体、可操作。\n\n"
        f"【核心主题】：{core_topic}\n"
        f"【聚焦方向】：{focus_area}\n\n"
        f"请输出 JSON，包含：\n"
        f"- is_sufficient: bool\n"
        f"- reason: 评估原因\n"
        f"- suggested_question: 如果不充分，生成 2-3 个具体选项的联想式追问"
    )

    meta = _llm_meta(assessor_llm)
    _trace("focus_assessor_llm", [f"model={meta['model']}", "评估 focus_area"])

    try:
        # Try structured output
        try:
            if should_skip_function_calling(assessor_llm):
                raise RuntimeError("skip_function_calling")
            llm_with_struct = assessor_llm.with_structured_output(FocusAssessOut, method="function_calling")
            result = llm_with_struct.invoke(prompt)
            return {
                "is_sufficient": result.is_sufficient,
                "reason": result.reason,
                "suggested_question": result.suggested_question,
            }
        except Exception:
            # Fallback to text parsing
            text_result = assessor_llm.invoke(prompt)
            text = str(getattr(text_result, "content", text_result) or "")

            # Extract JSON from markdown code fence
            import re
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                json_str = match.group(1)
                parsed = json.loads(json_str)
                return {
                    "is_sufficient": parsed.get("is_sufficient", True),
                    "reason": parsed.get("reason", ""),
                    "suggested_question": parsed.get("suggested_question"),
                }

            # Fallback: assume sufficient
            return {"is_sufficient": True, "reason": "parse_failed", "suggested_question": None}
    except Exception as e:
        _trace("focus_assessor_llm", [f"LLM 调用失败: {str(e)[:100]}"])
        return {"is_sufficient": True, "reason": "llm_error", "suggested_question": None}


def extractor_node(
    state: ReportState,
    *,
    extractor_llm: Optional[Any] = None,
    extractor_prompt_template: str = "",
) -> Dict[str, Any]:
    """Extract slots from user input and merge into state. Pure extraction, no routing."""
    _trace("extractor", ["开始槽位提取"])

    prefilled_slots = _prefill_slots_from_gathered_context(state)
    if prefilled_slots:
        _trace("extractor", [f"context_prefill_keys={list(prefilled_slots.keys())}"])

    # P1-B: Skip LLM if all required slots are already filled from gathered context
    if all(
        bool(str(prefilled_slots.get(s) or "").strip()) and not _is_low_signal_slot_value(str(prefilled_slots.get(s) or ""))
        for s in REQUIRED_SLOTS
    ):
        _trace("extractor", ["required_slots prefilled & valid → skip LLM extraction"])
        patch: Dict[str, Any] = {"phase": "evaluating"}
        if prefilled_slots:
            patch["report_slots"] = prefilled_slots
        return patch

    extraction_state = dict(state)
    extraction_state["report_slots"] = prefilled_slots

    merged_slots = _extract_slots_with_llm(
        extraction_state,
        extractor_llm=extractor_llm,
        extractor_prompt_template=extractor_prompt_template,
    )
    effective_slots = merged_slots or prefilled_slots

    patch = {"phase": "evaluating"}
    if effective_slots:
        patch["report_slots"] = effective_slots

    return patch


# ---------------------------------------------------------------------------
# Node 2: evaluator_node (pure rules, no LLM)
# ---------------------------------------------------------------------------


def evaluator_node(state: ReportState) -> Dict[str, Any]:
    """Determine next phase based on current state. Pure Python rules, no LLM."""
    if state.get("generation_ready"):
        _trace("evaluator", ["generation_ready=true -> outlining"])
        return {"phase": "outlining"}

    slots = dict(state.get("report_slots") or {})
    feedback = str(state.get("human_feedback") or "").strip()
    user_input = str(state.get("user_input") or "").strip()
    text = feedback or user_input

    # Impatient detection: auto-fill and skip to confirming/outlining
    if _is_impatient(text):
        _trace("evaluator", ["检测到不耐烦关键词，自动填充默认值"])
        filled = auto_fill_report_slots(slots)
        return {
            "report_slots": filled,
            "soft_confirmed": True,
            "phase": "outlining",
        }

    # Check required slots
    missing = [s for s in REQUIRED_SLOTS if not str(slots.get(s, "")).strip()]
    if missing:
        _trace("evaluator", [f"缺失槽位: {missing}", f"→ asking ({missing[0]})"])
        return {"phase": "asking", "_missing_slot": missing[0]}

    # If returning from asking (user answered focus follow-up), re-assess focus
    if state.get("phase") == "asking" and slots.get("focus_area"):
        _trace("evaluator", ["从追问返回，重新评估 focus_area → focus_assessor"])
        return {"phase": "focus_assessor"}

    # Focus sufficiency assessment (check immediately after slots are filled)
    if (not state.get("focus_sufficient") and
        slots.get("focus_area") and
        state.get("phase") != "focus_assessor"):
        _trace("evaluator", ["focus_area 存在但未评估 → focus_assessor"])
        return {"phase": "focus_assessor"}

    # Soft confirm
    if not state.get("soft_confirmed"):
        # If returning from confirmer and user said yes
        if feedback and _is_affirmative(feedback):
            _trace("evaluator", ["用户确认软确认 → outlining"])
            return {"soft_confirmed": True, "phase": "outlining"}
        _trace("evaluator", ["未软确认 → confirming"])
        return {"phase": "confirming"}

    # Outline confirm
    if not state.get("outline_confirmed"):
        _trace("evaluator", ["未确认大纲 → outlining"])
        return {"phase": "outlining"}

    # All gates passed
    _trace("evaluator", ["全部就绪 → generating"])
    return {"phase": "generating"}


# ---------------------------------------------------------------------------
# Node 3: asker_node
# ---------------------------------------------------------------------------


def asker_node(
    state: ReportState,
    *,
    extractor_llm: Optional[Any] = None,
) -> Dict[str, Any]:
    """Ask user for a missing slot. Respects ask_limit."""
    missing_slot = str(state.get("_missing_slot") or "core_topic")
    ask_count = dict(state.get("ask_count") or {})
    ask_limit = int(state.get("ask_limit") or 2)
    slots = dict(state.get("report_slots") or {})
    count = int(ask_count.get(missing_slot) or 0)

    # If over ask limit, fill with default and re-evaluate
    if count >= ask_limit:
        _trace("asker", [f"{missing_slot} 追问次数({count})已达上限({ask_limit})，使用默认值"])
        default_val = REPORT_DEFAULTS.get(missing_slot, "")
        slots[missing_slot] = default_val
        return {
            "report_slots": slots,
            "phase": "evaluating",
            "status": "executing",
        }

    # Build question: use suggested_question if available (from focus_assessor)
    if missing_slot == "focus_area" and state.get("focus_suggested_question"):
        question = state["focus_suggested_question"]
    else:
        question = _build_ask_question(missing_slot, slots, extractor_llm)

    # Increment ask count
    ask_count[missing_slot] = count + 1

    _trace("asker", [f"追问 {missing_slot} (第{count + 1}次)", f"问题: {question}"])

    return {
        "ask_count": ask_count,
        "status": "awaiting_human",
        "final_response": question,
        "error": "",
        "phase": "asking",  # Explicitly stay in asking phase until user responds
    }


# ---------------------------------------------------------------------------
# Node 2b: focus_assessor_node (new)
# ---------------------------------------------------------------------------


def focus_assessor_node(
    state: ReportState,
    *,
    assessor_llm: Optional[Any] = None,
) -> Dict[str, Any]:
    """Assess focus_area sufficiency. Route to confirming or asker."""
    slots = dict(state.get("report_slots") or {})

    result = _assess_focus_sufficiency_llm(slots, assessor_llm=assessor_llm)
    is_sufficient = result.get("is_sufficient", True)
    reason = result.get("reason", "")
    suggested_q = result.get("suggested_question")

    _trace("focus_assessor", [
        f"充分性: {is_sufficient}",
        f"原因: {reason}",
    ])

    patch = {
        "focus_sufficient": is_sufficient,
        "focus_assessment_reason": reason,
    }

    if is_sufficient:
        patch["phase"] = "confirming"
    else:
        patch["phase"] = "asking"
        patch["_missing_slot"] = "focus_area"
        if suggested_q:
            patch["focus_suggested_question"] = suggested_q

    return patch


# ---------------------------------------------------------------------------
# Node 4: confirmer_node
# ---------------------------------------------------------------------------


def confirmer_node(state: ReportState) -> Dict[str, Any]:
    """Soft-confirm report parameters (length/depth/style)."""
    slots = dict(state.get("report_slots") or {})

    # Fill secondary slot defaults before asking
    if not str(slots.get("length_requirement") or "").strip():
        slots["length_requirement"] = REPORT_DEFAULTS.get("length_requirement", "常规长度（约3-4章）")
    if not str(slots.get("depth_level") or "").strip():
        slots["depth_level"] = REPORT_DEFAULTS.get("depth_level", "标准研报级（逻辑严密、可读）")
    if not str(slots.get("format_style") or "").strip():
        slots["format_style"] = REPORT_DEFAULTS.get("format_style", "结构化分块论述")

    question = _build_soft_confirm_question(slots)

    _trace("confirmer", [f"发起软确认: {question}"])

    return {
        "report_slots": slots,
        "status": "awaiting_human",
        "final_response": question,
        "error": "",
    }


# ---------------------------------------------------------------------------
# Node 5: outliner_node
# ---------------------------------------------------------------------------


def outliner_node(
    state: ReportState,
    *,
    outliner_llm: Optional[Any] = None,
    skill_prompt: str = "",
    tool_registry: Optional[ToolRegistry] = None,
) -> Dict[str, Any]:
    """Generate or revise outline. Returns awaiting_human for user review."""
    slots = dict(state.get("report_slots") or {})
    existing_outline = list(state.get("report_outline") or [])
    feedback = str(state.get("human_feedback") or "").strip()

    # Case 1: Existing outline + user confirms → mark confirmed
    if existing_outline and feedback and _is_outline_confirm(feedback):
        _trace("outliner", ["用户确认大纲 → outline_confirmed=True"])
        return {
            "outline_confirmed": True,
            "phase": "generating",
            "status": "executing",
        }

    # Case 2: Existing outline + user wants changes → revise
    if existing_outline and feedback and not _is_outline_confirm(feedback):
        _trace("outliner", ["用户修改大纲", f"feedback={feedback[:80]}"])
        revise_callable = _resolve_tool_callable(
            tool_registry,
            "revise_outline_with_feedback",
            revise_outline_with_feedback,
        )
        result = revise_callable(outline=existing_outline, feedback=feedback)
        if result.get("ok"):
            revised = result.get("payload", {}).get("outline", existing_outline)
            if isinstance(revised, list):
                revised = normalize_outline_ast(revised)
            feedback_template = _get_skill_section("OUTLINE_MODIFY_FEEDBACK_TEMPLATE")
            feedback_text = ""
            if feedback_template and "{change_summary}" in feedback_template and "{rationale}" in feedback_template:
                try:
                    feedback_text = feedback_template.format(
                        change_summary="已按你的反馈更新对应章节与小节结构",
                        rationale="使结构与目标聚焦方向更一致、后续正文更连贯",
                    ).strip()
                except Exception:
                    feedback_text = ""
            if not feedback_text:
                feedback_text = "我已经按你的意见把大纲调好了。你看这版结构是否可以？如果可以，我就按这版直接开始写正文。"

            return {
                "report_outline": revised,
                "status": "awaiting_human",
                "final_response": feedback_text,
                "error": "",
            }
        else:
            _trace("outliner", [f"大纲修改失败: {result.get('error')}"])
            return {
                "status": "awaiting_human",
                "final_response": f"大纲修改遇到问题：{result.get('error', '未知错误')}。请重新描述修改意见。",
                "error": str(result.get("error", "")),
            }

    # Case 3: No outline → generate new one
    _trace("outliner", ["生成新大纲"])
    outline = _generate_outline(slots, outliner_llm=outliner_llm)
    outline = normalize_outline_ast(outline)

    if not outline:
        outline = _fallback_outline(slots)

    outline_json = json.dumps(outline, ensure_ascii=False)
    submit_callable = _resolve_tool_callable(
        tool_registry,
        "submit_outline_for_review",
        submit_outline_for_review,
    )
    result = submit_callable(outline_json_str=outline_json)

    summary_parts = []
    for ch in outline:
        title = str(ch.get("chapter_title", "")).strip()
        if title:
            summary_parts.append(f"- {title}")
    outline_text = "\n".join(summary_parts)

    return {
        "report_outline": outline,
        "status": "awaiting_human",
        "final_response": f"大纲已生成，请确认或指出要修改的地方：\n\n{outline_text}",
        "error": "",
    }


def _generate_outline(
    slots: Dict[str, Any],
    *,
    outliner_llm: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Use LLM to generate an outline AST."""
    if outliner_llm is None:
        return _fallback_outline(slots)

    core = str(slots.get("core_topic") or "研究主题")
    focus = str(slots.get("focus_area") or "关键问题")
    depth = str(slots.get("depth_level") or "中等深度")
    length = str(slots.get("length_requirement") or "3-4章")

    prompt = (
        "你是报告大纲设计师。请根据以下信息生成报告大纲，只输出 JSON 数组。\n\n"
        f"核心主题: {core}\n"
        f"聚焦方向: {focus}\n"
        f"深度要求: {depth}\n"
        f"篇幅要求: {length}\n\n"
        "输出格式：\n"
        '```json\n[{"chapter_id":1,"chapter_title":"...","chapter_goal":"...","sections":[{"section_id":"1.1","title":"..."}]}]\n```'
    )

    try:
        raw = outliner_llm.invoke(prompt)
        text = str(getattr(raw, "content", raw) or "").strip()

        # Extract JSON from markdown code fence
        if "```" in text:
            for part in text.split("```"):
                chunk = part.strip()
                if chunk.startswith("json"):
                    chunk = chunk[4:].strip()
                if chunk.startswith("["):
                    text = chunk
                    break

        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            text = text[start:end + 1]

        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception as exc:
        _trace("outliner", [f"LLM 大纲生成失败: {exc}"])

    return _fallback_outline(slots)


def _fallback_outline(slots: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deterministic fallback outline."""
    topic = str(slots.get("core_topic") or "研究主题")
    focus = str(slots.get("focus_area") or "关键问题")
    return normalize_outline_ast([
        {
            "chapter_id": 1,
            "chapter_title": f"{topic}：问题界定",
            "chapter_goal": "明确研究对象与分析范围",
            "sections": [
                {"section_id": "1.1", "title": "背景与问题提出"},
                {"section_id": "1.2", "title": f"{focus}切口定义"},
            ],
        },
        {
            "chapter_id": 2,
            "chapter_title": f"{topic}：分析展开",
            "chapter_goal": "分维度论证核心观点",
            "sections": [
                {"section_id": "2.1", "title": "关键证据与论点"},
                {"section_id": "2.2", "title": "对比分析与深入讨论"},
            ],
        },
        {
            "chapter_id": 3,
            "chapter_title": f"{topic}：结论与启示",
            "chapter_goal": "总结核心发现与实践建议",
            "sections": [
                {"section_id": "3.1", "title": "核心结论提炼"},
                {"section_id": "3.2", "title": "应用建议与展望"},
            ],
        },
    ])


# ---------------------------------------------------------------------------
# Node 6: generator_node
# ---------------------------------------------------------------------------


def generator_node(
    state: ReportState,
    *,
    tool_registry: Optional[ToolRegistry] = None,
) -> Dict[str, Any]:
    """Generate the full report content. Hard gate: soft_confirmed AND outline_confirmed."""
    # Hard gate
    if not state.get("soft_confirmed") or not state.get("outline_confirmed"):
        _trace("generator", ["硬门禁未通过", f"soft={state.get('soft_confirmed')}", f"outline={state.get('outline_confirmed')}"])
        return {
            "status": "awaiting_human",
            "final_response": "请先确认报告参数和大纲后再生成正文。",
            "error": "gate_not_passed",
        }

    slots = dict(state.get("report_slots") or {})
    outline = list(state.get("report_outline") or [])
    replan_count = int(state.get("replan_count") or 0)
    max_replans = int(state.get("max_replans") or 3)

    _trace("generator", [f"开始生成正文 (replan={replan_count}/{max_replans})"])

    t0 = time.perf_counter()
    generate_callable = _resolve_tool_callable(
        tool_registry,
        "generate_long_report_content",
        generate_long_report_content,
    )
    result = generate_callable(slots=slots, outline=outline)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    _trace("generator", [f"生成完成 ok={result.get('ok')} elapsed={elapsed_ms}ms"])

    if result.get("ok"):
        payload = result.get("payload") or {}
        content = str(payload.get("content") or "").strip()

        # Also check chapter_snapshots for accumulated content
        checkpoint = payload.get("checkpoint") if isinstance(payload.get("checkpoint"), dict) else {}
        snapshots = checkpoint.get("chapter_snapshots") if isinstance(checkpoint.get("chapter_snapshots"), list) else []
        if not content and snapshots:
            content = "\n\n".join(
                str(x.get("content") or "") for x in snapshots
                if isinstance(x, dict) and str(x.get("content") or "").strip()
            ).strip()

        if content:
            return {
                "report_content": content,
                "status": "finished",
                "final_response": content,
                "error": "",
            }

    # Failure path
    error_msg = str(result.get("error") or "unknown_error")
    replan_count += 1

    if replan_count >= max_replans:
        _trace("generator", [f"达到最大重试次数({max_replans})"])
        return {
            "replan_count": replan_count,
            "status": "finished",
            "final_response": "报告生成多次尝试后未成功，请检查网络或稍后重试。",
            "error": error_msg,
        }

    _trace("generator", [f"生成失败，重试 ({replan_count}/{max_replans})", f"error={error_msg}"])
    return {
        "replan_count": replan_count,
        "phase": "generating",
        "status": "executing",
        "error": error_msg,
    }


# ---------------------------------------------------------------------------
# Conditional edge: phase_router
# ---------------------------------------------------------------------------


def phase_router(state: ReportState) -> Literal["asker", "focus_assessor", "confirmer", "outliner", "generator"]:
    phase = str(state.get("phase") or "asking").strip().lower()
    mapping = {
        "asking": "asker",
        "focus_assessor": "focus_assessor",
        "confirming": "confirmer",
        "outlining": "outliner",
        "generating": "generator",
    }
    result = mapping.get(phase, "asker")
    _trace("phase_router", [f"phase={phase} → {result}"])
    return result  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Conditional edge: focus_router
# ---------------------------------------------------------------------------


def focus_router(state: ReportState) -> Literal["confirmer", "asker"]:
    """Route from focus_assessor based on sufficiency."""
    if state.get("focus_sufficient"):
        return "confirmer"
    return "asker"


def outliner_router(state: ReportState) -> Literal["generator", "__end__"]:
    """Route after outliner.

    若用户本轮确认了大纲，直接进入 generator；
    否则结束本轮并等待用户下一轮反馈。
    """
    outline_confirmed = bool(state.get("outline_confirmed"))
    phase = str(state.get("phase") or "").strip().lower()
    status = str(state.get("status") or "").strip().lower()

    if outline_confirmed and phase == "generating" and status == "executing":
        _trace("outliner_router", ["outline 已确认，本轮直达 generator"])
        return "generator"

    _trace("outliner_router", ["等待用户确认/修改大纲，本轮结束"])
    return "__end__"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_universal_report_graph(
    *,
    planner_llm: Optional[Any] = None,
    analyzer_llm: Optional[Any] = None,
    extractor_llm: Optional[Any] = None,
    extractor_prompt_template: str = "",
    planner_skill_prompt: str = "",
    analyzer_skill_prompt: str = "",
    tool_registry: Optional[ToolRegistry] = None,
) -> Any:
    """Build the report engine LangGraph.

    Signature kept compatible with v1 so service.py doesn't need to change
    how it constructs the graph. The planner_llm is reused as the outliner LLM.
    analyzer_llm and analyzer_skill_prompt are accepted but no longer used.
    """
    # Reuse planner_llm as the shared LLM for extraction and outline generation
    shared_llm = planner_llm or extractor_llm

    graph = StateGraph(ReportState)

    graph.add_node(
        "extractor",
        lambda s: extractor_node(
            s,
            extractor_llm=extractor_llm or shared_llm,
            extractor_prompt_template=extractor_prompt_template,
        ),
    )
    graph.add_node("evaluator", evaluator_node)
    graph.add_node(
        "focus_assessor",
        lambda s: focus_assessor_node(s, assessor_llm=extractor_llm or shared_llm),
    )
    graph.add_node(
        "asker",
        lambda s: asker_node(s, extractor_llm=extractor_llm or shared_llm),
    )
    graph.add_node("confirmer", confirmer_node)
    graph.add_node(
        "outliner",
        lambda s: outliner_node(
            s,
            outliner_llm=shared_llm,
            skill_prompt=planner_skill_prompt,
            tool_registry=tool_registry,
        ),
    )
    graph.add_node("generator", lambda s: generator_node(s, tool_registry=tool_registry))

    # Topology
    graph.set_entry_point("extractor")
    graph.add_edge("extractor", "evaluator")
    graph.add_conditional_edges(
        "evaluator",
        phase_router,
        {
            "asker": "asker",
            "focus_assessor": "focus_assessor",
            "confirmer": "confirmer",
            "outliner": "outliner",
            "generator": "generator",
        },
    )
    # focus_assessor conditional edge
    graph.add_conditional_edges(
        "focus_assessor",
        focus_router,
        {
            "confirmer": "confirmer",
            "asker": "asker",
        },
    )
    # Action nodes routing
    graph.add_edge("asker", "__end__")
    graph.add_edge("confirmer", "__end__")
    graph.add_conditional_edges(
        "outliner",
        outliner_router,
        {
            "generator": "generator",
            "__end__": "__end__",
        },
    )
    graph.add_edge("generator", "__end__")

    return graph.compile()


# ---------------------------------------------------------------------------
# Initial state constructor
# ---------------------------------------------------------------------------


def make_initial_report_state(*, user_input: str, human_feedback: str = "") -> ReportState:
    return {
        "messages": [],
        "user_input": user_input,
        "final_response": "",
        # Legacy fields (kept for compatibility)
        "plan": [],
        "current_step_index": 0,
        "gathered_context": {},
        "past_steps": [],
        # Artifacts
        "report_slots": {},
        "report_outline": [],
        "report_content": "",
        # Control
        "status": "planning",
        "human_feedback": human_feedback,
        "error": "",
        "replan_count": 0,
        "max_replans": 3,
        # v2 phase state
        "phase": "extracting",
        "soft_confirmed": False,
        "outline_confirmed": False,
        "ask_count": {},
        "ask_limit": 2,
        "_missing_slot": "",
        # v2 focus assessment
        "focus_sufficient": False,
        "focus_assessment_reason": "",
        "focus_suggested_question": "",
        "generation_ready": False,
    }


def _report_user_message_polish(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return raw
    if raw.startswith("大纲已生成，请确认或指出要修改的地方："):
        _, _, outline_part = raw.partition("：")
        outline_part = outline_part.strip()
        return (
            "我先把报告结构整理好了。你看这版大纲是否合适？"
            "如果可以，我就按这版继续写正文；如果想调整，也可以直接告诉我。\n\n"
            f"{outline_part}"
        )
    if "请先确认报告参数和大纲后再生成正文" in raw:
        return "我已经准备好写正文了。请先确认当前大纲；如果还想调整，也可以直接告诉我。"
    if raw.startswith("大纲修改遇到问题："):
        return raw.replace("大纲修改遇到问题：", "调整大纲时遇到问题：", 1)
    return raw


_ORIGINAL_BUILD_SOFT_CONFIRM_QUESTION = _build_soft_confirm_question


def _build_soft_confirm_question(slots: Dict[str, Any]) -> str:
    core = str(slots.get("core_topic") or "当前主题").strip() or "当前主题"
    focus = str(slots.get("focus_area") or "").strip() or f"围绕“{core}”形成一版结构化分析"
    length = str(slots.get("length_requirement") or "").strip()
    depth = str(slots.get("depth_level") or "").strip()
    style = str(slots.get("format_style") or "").strip()

    extras = [item for item in [length, depth, style] if item]
    extras_text = f" 我会按{ '、'.join(extras) }来组织。" if extras else ""
    return (
        f"我准备基于“{core}”，重点围绕“{focus}”来生成报告。"
        f"{extras_text} 如果这个方向可以，我就继续开始。"
    )


_ORIGINAL_BUILD_ASK_QUESTION = _build_ask_question


def _build_ask_question(missing_slot: str, report_slots: Dict[str, Any], llm: Optional[Any] = None) -> str:
    core = str(report_slots.get("core_topic") or "").strip()
    if missing_slot == "core_topic":
        return "这份报告你希望围绕哪个主题来写？"
    if missing_slot == "focus_area":
        if core:
            return f"围绕“{core}”，你更希望重点展开哪个角度？如果你愿意，我也可以先按综合分析来起草。"
        return "你更希望这份报告重点展开哪个角度？如果你暂时不确定，我也可以先按综合分析来起草。"
    return "为了继续生成报告，我还需要你补充一条最关键的信息。"


_ORIGINAL_OUTLINER_NODE = outliner_node


def outliner_node(
    state: ReportState,
    *,
    outliner_llm: Optional[Any] = None,
    skill_prompt: str = "",
    tool_registry: Optional[ToolRegistry] = None,
) -> Dict[str, Any]:
    result = _ORIGINAL_OUTLINER_NODE(
        state,
        outliner_llm=outliner_llm,
        skill_prompt=skill_prompt,
        tool_registry=tool_registry,
    )
    if isinstance(result, dict) and result.get("final_response"):
        result = dict(result)
        result["final_response"] = _report_user_message_polish(str(result.get("final_response") or ""))
    return result


_ORIGINAL_GENERATOR_NODE = generator_node


def generator_node(
    state: ReportState,
    *,
    tool_registry: Optional[ToolRegistry] = None,
) -> Dict[str, Any]:
    result = _ORIGINAL_GENERATOR_NODE(state, tool_registry=tool_registry)
    if isinstance(result, dict) and result.get("final_response"):
        result = dict(result)
        result["final_response"] = _report_user_message_polish(str(result.get("final_response") or ""))
    return result
