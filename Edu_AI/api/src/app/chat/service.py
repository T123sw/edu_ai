from __future__ import annotations

import json
import os
import re
import traceback
import base64
import mimetypes
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
import time
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from core.config import Config
from core.conversation_storage import conversation_storage
from core.user_profile_storage import user_profile_storage
from langgraph.graph import StateGraph

from .model_gateway import ChatModelGateway
from .slot_tracker import SLOT_KEYS, SlotTracker
from .reflection_engine import ReflectionEngine
from .skill_manager import SkillManager
from .report_domain import (
    REPORT_DEFAULTS,
    REPORT_IMPATIENT_KEYWORDS,
)
from .utils.prompt_utils import strip_trailing_questions, smooth_followup_transition
from .tools.video_search import should_use_video_search, search_video_segments_for_chat
from .tools.search_tools import create_search_tools
from .application.lesson_plan_service_v2 import build_default_lesson_plan_engine
from .agents.report_utils import (
    init_report_slots,
    merge_report_slots,
    render_report_known,
    log_agent_process,
    normalize_outline_ast,
    apply_outline_patch,
    ast_outline_stats,
    auto_fill_report_slots,
    outline_scale_hint,
)
from .agents.report_generation import build_report_markdown, get_fallback_llm
from .agents.universal_report_engine import build_universal_report_graph, make_initial_report_state
from .tools.agent_tools import get_default_tool_registry


RAG_CONTEXT: ContextVar[Dict[str, Any]] = ContextVar(
    "RAG_CONTEXT",
    default={"selected_doc_ids": [], "owner": None},
)

_CHAT_VERBOSE_LOG = os.getenv("CHAT_VERBOSE_LOG", "0").strip().lower() in {"1", "true", "yes"}


def _log(*args: Any, **kwargs: Any) -> None:
    if _CHAT_VERBOSE_LOG:
        _log(*args, **kwargs)

def _load_prompt_from_skill(skill_name: str, section_name: str, fallback: str = "") -> str:
    try:
        text = SkillManager().extract_section(skill_name, section_name)
        return text or fallback
    except Exception:
        return fallback


SYSTEM_PROMPT = _load_prompt_from_skill("edu-dialogue-agent", "SYSTEM_PROMPT", "你是教学对话助手，请提供准确、清晰、可执行的回答。")
GENERATE_PLACEHOLDER = "我已识别到你希望生成教学内容（如PPT/教案/报告）。当前版本先完成了对话与意图识别，生成功能即将接入。你可以先告诉我你的主题、受众和目标，我先帮你梳理需求。"
MAX_CLARIFICATION_TURNS = 2

REPORT_DYNAMIC_ASK_SYSTEM_PROMPT = _load_prompt_from_skill("edu-report-agent", "REPORT_HARD_ASK_PROMPT", "你是报告助理，请回显已知信息并追问一个缺失点。")
VIDEO_SEARCH_INTENT_PROMPT = _load_prompt_from_skill("edu-dialogue-agent", "VIDEO_SEARCH_INTENT_PROMPT", "判断是否需要课程视频检索，只输出JSON。")
NATURALIZER_SYSTEM_PROMPT = _load_prompt_from_skill("edu-dialogue-agent", "NATURALIZER_SYSTEM_PROMPT", "请将输入改写为自然简洁中文。")
FOLLOWUP_REWRITE_SYSTEM_PROMPT = _load_prompt_from_skill("edu-dialogue-agent", "FOLLOWUP_REWRITE_SYSTEM_PROMPT", "请将追问改写为自然、单点、问号结尾。")
ASK_SYSTEM_PROMPT = _load_prompt_from_skill("edu-dialogue-agent", "ASK_SYSTEM_PROMPT", "你是需求收集员，仅输出一句追问。")
DYNAMIC_ASK_SYSTEM_PROMPT = _load_prompt_from_skill("edu-dialogue-agent", "DYNAMIC_ASK_SYSTEM_PROMPT", "你是教学设计助理，请回显并追问缺失信息。")
EXTRACTOR_SYSTEM_PROMPT = _load_prompt_from_skill("edu-report-agent", "EXTRACTOR_SYSTEM_PROMPT", "你是需求提取器，只提取增量字段。")
REPORT_SLOT_SCHEMA = _load_prompt_from_skill("edu-report-agent", "REPORT_SLOT_SCHEMA", "{}")
RAG_TOOL_DESCRIPTION = _load_prompt_from_skill("edu-dialogue-agent", "RAG_TOOL_DESCRIPTION", "本地知识库检索工具，仅在需要基于资料回答时调用。")
DEEP_RESEARCH_TOOL_DESCRIPTION = _load_prompt_from_skill("edu-dialogue-agent", "DEEP_RESEARCH_TOOL_DESCRIPTION", "全网研究工具，仅在需要最新信息时调用。")


class ChatService:
    """对话服务（含意图识别；generate 先占位）。"""

    _SINGLE_SLOT_QUESTION: Dict[str, str] = {
        "topic": "为了不答偏，你这次想讲的具体主题是什么？",
        "objective": "你希望这次回答重点帮你达成什么目标？",
        "audience": "这次内容主要面向哪类学生（如高中/大一/大二）？",
    }

    _REASON_FOLLOWUPS: Dict[str, List[str]] = {
        "too_short": [
            "我先接住你的问题了。你再补一句：这次主要讲什么主题？",
            "为了不答偏，我先确认下主题。你这次是围绕哪个知识点？",
            "你给我一个关键词也行，比如 TCP、函数极值、牛顿第二定律。",
        ],
        "ambiguous_reference": [
            "我明白你的意思了。你说的“这个”具体是哪个知识点？",
            "咱们先把对象对齐一下：你现在卡在哪个概念或哪一步？",
            "你给我一个明确对象（概念名/题目/章节）我就能马上展开。",
        ],
        "insufficient_context": [
            "我可以继续。先告诉我主题和目标这两项里的缺失项，我就能给到更准的回答。",
            "为了更贴近你的场景，我先确认：主题是什么、你希望达成什么目标？",
            "你再补充一点点就够了：讲什么（主题）+ 想达到什么（目标）。",
        ],
    }

    def __init__(self):
        self._reflection_engine = ReflectionEngine(self._get_fallback_llm)
        self._skill_manager = SkillManager()
        self._inner_monologue_enabled = os.getenv("AGENT_INNER_MONOLOGUE_ENABLED", "1").strip().lower() in {"1", "true", "yes"}
        self._reflection_stats: Dict[str, int] = {
            "chat_monologue_success": 0,
            "chat_monologue_fallback": 0,
            "generate_monologue_success": 0,
            "generate_monologue_fallback": 0,
            "outline_review_applied": 0,
            "outline_review_fallback": 0,
            "body_review_applied": 0,
            "body_review_fallback": 0,
        }
        self._enable_universal_report_engine = (
            os.getenv("ENABLE_UNIVERSAL_REPORT_ENGINE", "0").strip().lower() in {"1", "true", "yes"}
        )
        # Phase 5.5 强制主路化：保留字段仅为兼容观测，不再参与报告路由决策。
        self._universal_report_rollout_percent = 100
        self._universal_report_allowlist: set[str] = set()
        self._universal_report_metrics: Dict[str, int] = {
            "selected": 0,
            "skipped": 0,
            "awaiting_human": 0,
            "replanning": 0,
            "finished": 0,
            "tool_failure": 0,
        }

        self._universal_report_graph = None
        if self._enable_universal_report_engine:
            planner_llm = self._get_fallback_llm()
            analyzer_llm = planner_llm
            extractor_llm = planner_llm
            planner_skill_prompt = self._build_report_engine_planner_skill_prompt()
            analyzer_skill_prompt = self._build_report_engine_analyzer_skill_prompt()
            extractor_prompt_template = self._skill_manager.extract_section("edu-report-agent", "EXTRACTOR_SYSTEM_PROMPT")
            self._universal_report_graph = build_universal_report_graph(
                planner_llm=planner_llm,
                analyzer_llm=analyzer_llm,
                extractor_llm=extractor_llm,
                extractor_prompt_template=extractor_prompt_template,
                planner_skill_prompt=planner_skill_prompt,
                analyzer_skill_prompt=analyzer_skill_prompt,
                tool_registry=get_default_tool_registry(),
            )
        self._compiled_graph = self._build_graph()
        self._lesson_plan_engine = None

    def _build_report_engine_prompt_from_sections(self, allowlist_sections: List[tuple], fallback: str) -> str:
        blocks: List[str] = []
        for section_name, title in allowlist_sections:
            content = self._skill_manager.extract_section("edu-report-agent", section_name)
            if content and content.strip():
                blocks.append(f"{title}\n{content.strip()}")
        return "\n\n".join(blocks) if blocks else fallback

    def _build_report_engine_planner_skill_prompt(self) -> str:
        """Planner-only prompt: SOP + planner contracts + planner few-shots."""
        allowlist_sections = [
            ("REPORT_SLOT_SCHEMA", "### REPORT_SLOT_SCHEMA"),
            ("⚙️ 引擎阶段流转（v2 状态机）", "## ⚙️ 引擎阶段流转（v2 状态机）"),
            ("阶段流转示例", "## 阶段流转示例"),
            ("🚫 全局禁令", "## 🚫 全局禁令"),
        ]
        return self._build_report_engine_prompt_from_sections(
            allowlist_sections,
            "请遵循：先补关键槽位，再检索补充；先提交大纲并等待确认，确认后再生成正文。",
        )

    def _build_report_engine_analyzer_skill_prompt(self) -> str:
        """Analyzer-only prompt: SOP + analyzer contracts + analyzer few-shots."""
        allowlist_sections = [
            ("REPORT_SLOT_SCHEMA", "### REPORT_SLOT_SCHEMA"),
            ("⚙️ 引擎阶段流转（v2 状态机）", "## ⚙️ 引擎阶段流转（v2 状态机）"),
            ("阶段流转示例", "## 阶段流转示例"),
            ("🚫 全局禁令", "## 🚫 全局禁令"),
        ]
        return self._build_report_engine_prompt_from_sections(
            allowlist_sections,
            "请遵循：工具失败进入重规划；需要用户确认时挂起；正文完成后结束流程。",
        )

    def _use_universal_report_engine_for_request(
        self,
        *,
        conv_id: str,
        owner: Optional[str],
        report_awaiting: bool,
    ) -> bool:
        # Phase 5.5 强制主路化：只要新引擎可用，所有报告请求统一走新引擎。
        return bool(self._enable_universal_report_engine and self._universal_report_graph is not None)

    def get_universal_report_runtime_stats(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self._enable_universal_report_engine),
            "rollout_percent": int(self._universal_report_rollout_percent),
            "allowlist_size": int(len(self._universal_report_allowlist)),
            "metrics": dict(self._universal_report_metrics),
        }

    def get_report_engine(self) -> Any:
        return self._universal_report_graph

    def get_lesson_plan_engine(self) -> Any:
        if self._lesson_plan_engine is None:
            self._lesson_plan_engine = build_default_lesson_plan_engine()
        return self._lesson_plan_engine

    @staticmethod
    def _detect_report_intent(text: str) -> bool:
        t = (text or "").lower()
        triggers = [
            "报告",
            "总结报告",
            "生成报告",
            "写报告",
            "课程总结",
            "整理成报告",
            "summary report",
            "report",
        ]
        return any(k in t for k in triggers)

    @staticmethod
    def _is_impatient(text: str) -> bool:
        t = (text or "").strip()
        return any(k in t for k in REPORT_IMPATIENT_KEYWORDS)

    def _detect_report_user_intent(self, text: str, *, outline_pending: bool = False) -> Optional[str]:
        t = str(text or "").strip()
        if not t:
            return None

        if outline_pending:
            # 大纲挂起阶段：使用模型进行意图识别，避免硬编码关键词
            try:
                llm = self._get_fallback_llm()
                if llm is not None:
                    prompt = (
                        "你是意图分类器。当前处于‘大纲已生成，等待用户下一步’状态。\n"
                        "请判断用户输入意图：\n"
                        "- confirm_outline: 用户确认大纲并要求开始生成正文\n"
                        "- modify_outline: 用户提出大纲修改意见或补充要求\n"
                        "仅输出 JSON: {\"intent\":\"confirm_outline|modify_outline\",\"reason\":\"...\"}\n"
                        f"用户输入：{t}"
                    )
                    raw = llm.invoke(prompt)
                    txt = str(getattr(raw, "content", raw) or "").strip()
                    if "```" in txt:
                        parts = txt.split("```")
                        for p in parts:
                            pp = p.strip()
                            if pp.startswith("json"):
                                pp = pp[4:].strip()
                            if pp.startswith("{") and pp.endswith("}"):
                                txt = pp
                                break
                    obj = json.loads(txt) if txt else {}
                    intent = str((obj or {}).get("intent") or "").strip().lower()
                    if intent in {"confirm_outline", "modify_outline"}:
                        return intent
            except Exception:
                pass
            return "modify_outline"

        if any(k in t for k in REPORT_IMPATIENT_KEYWORDS + ["你看着办", "随便", "按你来", "直接写", "快生成"]):
            return "force_generate"
        if any(k in t for k in ["修改", "改", "删", "新增", "补充", "调整"]):
            return "modify_outline"
        return "provide"


    def _revise_outline_with_feedback(
        self,
        *,
        outline: List[Dict[str, Any]],
        feedback: str,
    ) -> List[Dict[str, Any]]:
        """根据用户反馈直接修改大纲（结构化返回）。失败时回退原大纲。"""
        try:
            llm = self._get_fallback_llm()
            if llm is None:
                return outline

            prompt = (
                "你是报告大纲编辑器。请根据用户修改意见，直接修改给定大纲。\n"
                "要求：\n"
                "1) 保持 JSON 数组结构，元素为章节对象。\n"
                "2) 允许增删改章节与小节，但要保持结构清晰。\n"
                "3) 不要输出任何解释，只输出 JSON 数组。\n\n"
                f"【当前大纲】\n{json.dumps(outline, ensure_ascii=False)}\n\n"
                f"【用户修改意见】\n{feedback}\n"
            )
            raw = llm.invoke(prompt)
            text = str(getattr(raw, "content", raw) or "").strip()

            if "```" in text:
                parts = text.split("```")
                for p in parts:
                    pp = p.strip()
                    if pp.startswith("json"):
                        pp = pp[4:].strip()
                    if pp.startswith("[") and pp.endswith("]"):
                        text = pp
                        break

            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                text = text[start : end + 1]

            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            return outline
        except Exception:
            return outline

    @staticmethod
    def _is_requirement_clear(question: str, slots: Optional[Dict[str, Any]] = None) -> tuple[bool, int, List[str]]:
        q = str(question or "").strip()
        s = slots or {}

        hit_fields: List[str] = []
        topic = str(s.get("topic") or "").strip()
        audience = str(s.get("audience") or "").strip()
        goal = str(s.get("objective") or s.get("goal") or "").strip()

        if topic or any(k in q for k in ["关于", "讲", "知识点", "主题", "单元", "章节"]):
            hit_fields.append("topic")
        if audience or any(k in q for k in ["学生", "年级", "高一", "初中", "小学", "受众"]):
            hit_fields.append("audience")
        if goal or any(k in q for k in ["目标", "希望", "想要", "提升", "达成"]):
            hit_fields.append("goal")
        if any(k in q for k in ["明天", "40分钟", "公开课", "复习课", "导入", "作业"]):
            hit_fields.append("scenario")

        dedup = []
        seen = set()
        for f in hit_fields:
            if f not in seen:
                seen.add(f)
                dedup.append(f)
        return len(dedup) >= 2, len(dedup), dedup

    def _detect_need_type(self, question: str) -> tuple[str, str, str, str]:
        q = str(question or "").strip()
        if not q:
            return "consultative", "teacher_educator", "dialogue-consultative", "fallback_empty_question"

        llm = self._get_fallback_llm()
        if llm:
            try:
                need_router_prompt = self._skill_manager.extract_prompt_sections("dialogue-need-router").get("system_prompt") or ""
                if not need_router_prompt:
                    return "consultative", "teacher_educator", "dialogue-consultative", "fallback_missing_skill_prompt"

                response = llm.invoke([
                    {"role": "system", "content": need_router_prompt},
                    {"role": "user", "content": q},
                ])
                raw = str(getattr(response, "content", "") or "").strip()
                raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    need_type = str(payload.get("need_type") or "consultative").strip()
                    user_role_mode = str(payload.get("user_role_mode") or "teacher_educator").strip()
                    skill_target = str(payload.get("skill_target") or "dialogue-consultative").strip()
                    reason = str(payload.get("reason") or "llm_dialogue_router")

                    valid_need_types = {"explain", "teach_design", "management", "reflective", "consultative", "empathic"}
                    valid_role_modes = {"teacher_learner", "teacher_educator"}
                    valid_skills = {
                        "dialogue-explainer",
                        "dialogue-pedagogical",
                        "dialogue-management",
                        "dialogue-reflective",
                        "dialogue-consultative",
                        "dialogue-empathic",
                    }

                    if need_type not in valid_need_types:
                        need_type = "consultative"
                    if user_role_mode not in valid_role_modes:
                        user_role_mode = "teacher_educator"
                    if skill_target not in valid_skills:
                        skill_target = "dialogue-consultative"

                    return need_type, user_role_mode, skill_target, reason
            except Exception:
                pass

        # 极小安全兜底：仅防崩溃，不做复杂规则树
        return "consultative", "teacher_educator", "dialogue-consultative", "fallback_parse_error"

    def _detect_tool_intent(self, question: str) -> tuple[str, str, str]:
        q = str(question or "").strip()
        if not q:
            return "none", "empty_question", "fallback"

        # 用户主动触发优先（硬规则）
        rag_keywords = ["查找知识库", "知识库", "库内", "本地资料", "上传文档", "课程资料", "教案库", "讲义"]
        web_keywords = ["上网上查找", "上网查找", "联网查", "联网搜索", "网页搜索", "查最新", "搜一下"]

        if any(k in q for k in web_keywords):
            return "web", "user_explicit_web", "override"
        if any(k in q for k in rag_keywords):
            return "rag", "user_explicit_rag", "override"

        llm = self._get_fallback_llm()
        if not llm:
            return "none", "no_fallback_llm", "fallback"

        try:
            tool_router_prompt = self._skill_manager.extract_prompt_sections("tool-auth-router").get("system_prompt") or ""
            if not tool_router_prompt:
                return "none", "missing_tool_auth_router_prompt", "fallback"

            response = llm.invoke([
                {"role": "system", "content": tool_router_prompt},
                {"role": "user", "content": q},
            ])
            raw = str(getattr(response, "content", "") or "").strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            payload = json.loads(raw)
            if isinstance(payload, dict):
                tool = str(payload.get("tool") or "none").strip().lower()
                if tool not in {"none", "rag", "web"}:
                    tool = "none"
                reason = str(payload.get("reason") or "llm_decision")
                return tool, reason, "llm"
            return "none", "invalid_payload", "fallback"
        except Exception as exc:
            return "none", f"llm_error:{exc}", "fallback"

    @staticmethod
    def _build_tool_auth_prompt(tool: str, reason: str) -> str:
        sections = SkillManager().extract_prompt_sections("tool-auth-router")
        tool_auth_template = str(sections.get("tool_auth_template") or "").strip()

        if tool_auth_template:
            tool_name = "联网检索" if tool == "web" else "知识库检索"
            eta = "5-10" if tool == "web" else "5-8"
            return (
                tool_auth_template
                .replace("{tool_name}", tool_name)
                .replace("{eta}", eta)
                + f"\n触发原因：{reason}"
            )

        if tool == "web":
            return (
                "我可以先给你一个常规思路（马上回复），"
                "也可以上网检索最新资料后再给你更贴近时效的建议（约 5-10 秒）。"
                f"\n触发原因：{reason}\n你希望我现在联网检索吗？"
            )
        if tool == "rag":
            return (
                "我可以先给你一个通用方案（马上回复），"
                "也可以先查你已有的知识库/上传资料后再回答（约 5-8 秒）。"
                f"\n触发原因：{reason}\n你希望我先查知识库吗？"
            )
        return ""

    @staticmethod
    def _build_tool_reject_fallback_prompt(tool: str) -> str:
        if tool == "web":
            return (
                "收到，那我先不联网检索。"
                "我先给你一个可直接使用的常规快速解法：\n"
                "1) 先明确你的教学目标和受众；\n"
                "2) 用一个贴近课堂的引入案例快速开场；\n"
                "3) 给出1个易错点提醒和1个可执行课堂动作。\n"
                "如果你后面需要，我可以再补一版基于最新资料的增强方案。"
            )
        if tool == "rag":
            return (
                "明白，那我先不查知识库。"
                "我先给你一个通用、可落地的快速方案：\n"
                "1) 先确定这节课的核心知识点与学生层次；\n"
                "2) 设计一个生活化类比做导入；\n"
                "3) 补上一个常见误区与对应纠偏提问。\n"
                "如果你后面愿意授权，我可以再补一版结合你资料库的定制答案。"
            )
        return "收到，我先按常规快速解法给你一个可执行方案。"

    @staticmethod
    def _is_tool_auth_accepted(text: str) -> bool:
        t = str(text or "").strip().lower()
        if not t:
            return False
        yes_signals = ["可以", "同意", "授权", "去查", "查吧", "联网", "检索", "好", "yes", "ok"]
        return any(s in t for s in yes_signals)

    @staticmethod
    def _is_tool_auth_rejected(text: str) -> bool:
        t = str(text or "").strip().lower()
        if not t:
            return False
        no_signals = ["不用", "不需要", "先别", "不要", "不查", "no"]
        return any(s in t for s in no_signals)

    @staticmethod
    def _init_report_slots(raw: Optional[Dict[str, Any]]) -> Dict[str, str]:
        return init_report_slots(raw)

    @staticmethod
    def _merge_report_slots(old: Dict[str, str], new: Dict[str, str]) -> Dict[str, str]:
        return merge_report_slots(old, new)

    @staticmethod
    def _render_report_known(slots: Dict[str, str]) -> str:
        return render_report_known(slots)

    @staticmethod
    def _log_agent_process(stage: str, plan: str, reflection: str, next_step: str) -> None:
        return log_agent_process(stage, plan, reflection, next_step)

    @staticmethod
    def _decide_outline_review_policy(question_text: str, is_modification: bool) -> tuple[str, str]:
        if not is_modification:
            return "full", ""
        q = (question_text or "").strip()
        if any(k in q for k in ["不审查", "跳过审查", "直接改", "不用审查"]):
            return "skip", ""
        return "partial", q

    def _log_reflection_metrics(self, stage: str, result: Dict[str, Any]) -> None:
        policy = str(result.get("policy") or "")
        applied = int(bool(result.get("review_applied", False)))
        passed = int(bool(result.get("passed", False)))
        issues = result.get("issues") if isinstance(result.get("issues"), list) else []
        issue_preview = ",".join([str(i) for i in issues[:3]]) if issues else "none"
        print(
            f"[ReflectionMetrics] stage={stage} policy={policy} passed={passed} "
            f"applied={applied} issues={len(issues)} issue_preview={issue_preview}"
        )

        if stage == "outline":
            if applied:
                self._reflection_stats["outline_review_applied"] += 1
            elif any("fallback" in str(i) for i in issues):
                self._reflection_stats["outline_review_fallback"] += 1
        elif stage == "body":
            if applied:
                self._reflection_stats["body_review_applied"] += 1
            elif any("fallback" in str(i) for i in issues):
                self._reflection_stats["body_review_fallback"] += 1

        print(f"[ReflectionStats] {self._reflection_stats}")

    @staticmethod
    def _is_generic_outline(outline: Any) -> bool:
        if not isinstance(outline, list) or not outline:
            return True
        generic_count = 0
        for item in outline:
            if not isinstance(item, dict):
                generic_count += 1
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                generic_count += 1
                continue
            if re.fullmatch(r"章节\s*\d+", title) or re.fullmatch(r"第[一二三四五六七八九十百]+章", title):
                generic_count += 1
                continue
            if title.lower() in {"chapter 1", "chapter 2", "chapter 3", "chapter 4", "chapter 5", "chapter 6"}:
                generic_count += 1
                continue
        return generic_count >= max(1, len(outline) // 2)

    @staticmethod
    def _semanticize_outline_titles(outline: List[Dict[str, Any]], topic: str) -> List[Dict[str, Any]]:
        topic_label = (topic or "该主题").strip()
        fixed: List[Dict[str, Any]] = []
        for item in outline:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            points = item.get("points") if isinstance(item.get("points"), list) else []
            clean_points = [str(p).strip() for p in points if str(p).strip()]
            if not clean_points:
                clean_points = ["核心内容梳理", "关键细节分析"]

            if (not title) or re.fullmatch(r"章节\s*\d+", title) or re.fullmatch(r"第[一二三四五六七八九十百]+章", title):
                anchor = clean_points[0][:14]
                title = f"{topic_label}：{anchor}"
            fixed.append({"title": title, "points": clean_points})
        return fixed

    @staticmethod
    def _outline_stats(outline: Any) -> tuple[int, int]:
        if not isinstance(outline, list):
            return 0, 0
        section_count = 0
        point_count = 0
        for item in outline:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            points = item.get("points") if isinstance(item.get("points"), list) else []
            valid_points = [str(p).strip() for p in points if str(p).strip()]
            if title:
                section_count += 1
            point_count += len(valid_points)
        return section_count, point_count

    @staticmethod
    def _ast_outline_stats(outline: Any) -> tuple[int, int]:
        return ast_outline_stats(outline)

    @staticmethod
    def _parse_outline_from_markdown(text: str) -> List[Dict[str, Any]]:
        raw = str(text or "").strip()
        if not raw:
            return []

        lines = [ln.rstrip() for ln in raw.splitlines()]
        outline: List[Dict[str, Any]] = []
        current_title = ""
        current_points: List[str] = []

        def flush_current():
            nonlocal current_title, current_points
            if current_title and current_points:
                outline.append({"title": current_title, "points": current_points[:6]})
            current_title = ""
            current_points = []

        for line in lines:
            t = line.strip()
            if not t:
                continue

            # 章节标题：## 标题 / 一、标题 / 1. 标题
            if t.startswith("## ") or re.match(r"^[一二三四五六七八九十]+[、.．]\s*", t) or re.match(r"^\d+[、.．]\s*", t):
                flush_current()
                title = re.sub(r"^##\s*", "", t)
                title = re.sub(r"^[一二三四五六七八九十]+[、.．]\s*", "", title)
                title = re.sub(r"^\d+[、.．]\s*", "", title)
                current_title = title.strip()
                continue

            # 要点：* / - / 1) ...
            if t.startswith("*") or t.startswith("-") or re.match(r"^\d+[)）]\s*", t):
                point = re.sub(r"^[*\-]\s*", "", t)
                point = re.sub(r"^\d+[)）]\s*", "", point)
                if point:
                    current_points.append(point.strip())

        flush_current()
        return outline

    @staticmethod
    def _normalize_outline_ast(raw_outline: Any) -> List[Dict[str, Any]]:
        return normalize_outline_ast(raw_outline)

    @staticmethod
    def _apply_outline_patch(current_outline: List[Dict[str, Any]], modifications: Any) -> tuple[List[Dict[str, Any]], List[str]]:
        return apply_outline_patch(current_outline, modifications)

    def _build_report_ask_messages(self, question: str, *, missing_slot: str, known_info_prefix: str) -> List[Dict[str, str]]:
        hard_label = {
            "core_topic": "核心主题",
            "focus_area": "具体聚焦方向",
            "dynamic_constraints": "关键限制维度（如章节/时期/对比对象）",
        }.get(missing_slot)

        if hard_label:
            hard_prompt = self._skill_manager.extract_section("edu-report-agent", "REPORT_HARD_ASK_PROMPT")
            system_prompt = (hard_prompt or REPORT_DYNAMIC_ASK_SYSTEM_PROMPT).format(
                known_slots=known_info_prefix or "未提供",
                missing_slot=hard_label,
                missing_reason="当前信息仍偏宽泛，需要这个点来保证报告可写性与深度。",
            )
        else:
            soft_prompt = self._skill_manager.extract_section("edu-report-agent", "REPORT_SOFT_CONFIRM_PROMPT")
            system_prompt = (soft_prompt or REPORT_DYNAMIC_ASK_SYSTEM_PROMPT).format(
                known_core=known_info_prefix or "未提供",
            )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"我的输入是：{question}。请按要求向我发起追问。"},
        ]

    def _auto_fill_report_slots(self, slots: Dict[str, str], fallback_topic: str = "") -> Dict[str, str]:
        return auto_fill_report_slots(slots, fallback_topic)

    @staticmethod
    def _outline_scale_hint(length_requirement: str) -> Dict[str, Any]:
        return outline_scale_hint(length_requirement)

    def _build_report_markdown(self, slots: Dict[str, str], outline: Optional[List[Dict[str, Any]]] = None) -> tuple[str, Dict[str, Any]]:
        return build_report_markdown(
            skill_manager=self._skill_manager,
            slots=slots,
            outline=outline,
        )

    def _get_fallback_llm(self) -> Optional[ChatOpenAI]:
        return get_fallback_llm()

    def _should_use_video_search(self, question: str) -> tuple[bool, str, str]:
        return should_use_video_search(
            question=question,
            llm=self._get_fallback_llm(),
            prompt=VIDEO_SEARCH_INTENT_PROMPT,
        )

    def _search_video_segments_for_chat(
        self,
        *,
        query: str,
        owner: Optional[str],
        course_id: Optional[str],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        return search_video_segments_for_chat(
            query=query,
            owner=owner,
            course_id=course_id,
            top_k=top_k,
        )

    def _build_runtime_system_prompt(
        self,
        *,
        node_name: str,
        base_prompt: str,
        user_profile: Optional[Dict[str, Any]],
        intent_category: str,
        response_type: str,
        is_report: bool,
        has_video_context: bool,
        has_image_context: bool,
        question: str,
        dialogue_skill: str = "",
    ) -> tuple[str, List[str]]:
        enriched_prompt = base_prompt
        if user_profile:
            subject = user_profile.get("subject") or "未知"
            grade = user_profile.get("grade") or "未知"
            style = user_profile.get("style") or "常规"
            enriched_prompt = (
                f"{enriched_prompt}\n\n"
                "【教师画像记忆】\n"
                f"- 任教科目：{subject}\n"
                f"- 年级/受众：{grade}\n"
                f"- 偏好风格：{style}\n"
                "请在回答中贴合上述背景，若用户提出新要求可覆盖。"
            )

        selected_skills = self._skill_manager.select_node_skills(
            node_name=node_name,
            intent_category=intent_category,
            response_type=response_type,
            is_report=is_report,
            has_video_context=has_video_context,
            has_image_context=has_image_context,
            question=question,
            dialogue_skill=dialogue_skill,
        )
        final_prompt = self._skill_manager.render_system_prompt(
            base_prompt=enriched_prompt,
            skill_names=selected_skills,
        )
        return final_prompt, selected_skills

    def _record_node_skills(
        self,
        *,
        state: GraphState,
        node_name: str,
        base_prompt: str,
        has_video_context: bool = False,
        has_image_context: bool = False,
    ) -> str:
        prompt, node_skills = self._build_runtime_system_prompt(
            node_name=node_name,
            base_prompt=base_prompt,
            user_profile=state.get("user_profile") or {},
            intent_category=str(state.get("intent_category") or "chat"),
            response_type=str(state.get("response_type") or "chat"),
            is_report=bool(state.get("report_meta", {}).get("is_report")),
            has_video_context=has_video_context,
            has_image_context=has_image_context,
            question=str(state.get("question") or ""),
            dialogue_skill=str(state.get("dialogue_skill") or ""),
        )
        node_skill_map = dict(state.get("node_skill_map") or {})
        node_skill_map[node_name] = node_skills
        state["node_skill_map"] = node_skill_map
        state["applied_skills"] = node_skills

        dialogue_skill = next((s for s in node_skills if s.startswith("dialogue-")), "")
        if dialogue_skill:
            state["skill_used"] = dialogue_skill
        else:
            routed_dialogue_skill = str(state.get("dialogue_skill") or "").strip()
            if routed_dialogue_skill.startswith("dialogue-"):
                state["skill_used"] = routed_dialogue_skill

        if state.get("skill_used") == "dialogue-consultative":
            state["next_action"] = "ask_user"
            state["needs_more_context"] = True
        else:
            state["next_action"] = "direct_answer"
            state["needs_more_context"] = False

        return prompt

    def _build_chat_messages(
        self,
        question: str,
        history: Optional[List[Dict[str, Any]]] = None,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        system_prompt, _ = self._build_runtime_system_prompt(
            node_name="chat",
            base_prompt=SYSTEM_PROMPT,
            user_profile=user_profile,
            intent_category="chat",
            response_type="chat",
            is_report=False,
            has_video_context=False,
            has_image_context=False,
            question=question,
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

        if history:
            # 仅保留最近窗口，避免上下文无限增长
            recent = history[-Config.CHAT_HISTORY_WINDOW * 2 :]
            for msg in recent:
                role = msg.get("role")
                content = msg.get("content", "")
                if role in {"user", "assistant"} and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": question})
        return messages

    def chat_stream(
        self,
        *,
        question: str,
        conversation_id: Optional[str],
        model_id: Optional[str],
    ) -> Iterable[str]:
        conv_id = conversation_id or f"conv_{datetime.now().timestamp()}"
        conversation_storage.ensure_conversation(conv_id, question)

        gateway, _ = self._get_model_gateway(model_id)
        history = conversation_storage.get_messages(conv_id, limit=Config.CHAT_HISTORY_WINDOW * 2)
        messages = self._build_chat_messages(question=question, history=history)

        conversation_storage.append_message(
            conv_id,
            role="user",
            content=question,
            timestamp=datetime.now().isoformat(),
        )

        collected: List[str] = []
        for idx, chunk in enumerate(gateway.stream_chat(messages), start=1):
            print(f"[stream_chat] chunk={idx} size={len(chunk)}")
            collected.append(chunk)
            yield chunk

        answer = "".join(collected).strip()
        conversation_storage.append_message(
            conv_id,
            role="assistant",
            content=answer,
            timestamp=datetime.now().isoformat(),
        )

    def _build_graph(self):
        from .graph_state import GraphState
        from .agents.supervisor_agent import SupervisorAgent, route_after_supervisor
        from .agents.chat_agent import ChatAgent
        from .agents.report_agent import ReportAgent
        from .agents.research_agent import ResearchAgent
        from .intent_router import IntentRouter
        from .resource_type_router import ResourceTypeRouter
        from .response_planner import ResponsePlanner

        rag_search_tool, deep_research_tool = create_search_tools(
            rag_context_var=RAG_CONTEXT,
            rag_tool_description=RAG_TOOL_DESCRIPTION,
            deep_research_tool_description=DEEP_RESEARCH_TOOL_DESCRIPTION,
            system_prompt=SYSTEM_PROMPT,
        )

        def router_node(state: GraphState) -> GraphState:
            self._record_node_skills(state=state, node_name="router", base_prompt="你是路由决策节点，请专注意图分类与流程分发。")
            conv_state_local = state.get("conv_state", {}) or {}
            awaiting_clarification = bool(conv_state_local.get("awaiting_clarification"))
            conv_report = conv_state_local.get("report_state", {}) or {}
            awaiting_report = bool(conv_report.get("awaiting"))

            if awaiting_clarification or awaiting_report:
                intent_category = "generate_content"
                router_reason = "awaiting_clarification_override"
                awaiting_override_applied = True
                route_source = "override"
            else:
                router = IntentRouter(model_gateway=state["gateway"])
                intent_category, router_reason = router.classify(state.get("question", ""))
                awaiting_override_applied = False
                route_source = "llm" if str(router_reason).startswith("llm_") else "fallback"

            state["intent_category"] = intent_category
            state["router_reason"] = router_reason
            state["intent_router_reason"] = router_reason
            state["awaiting_override_applied"] = awaiting_override_applied
            state["route_source"] = route_source
            state["intent_route_source"] = route_source

            is_report = (
                awaiting_report
                or (intent_category == "generate_content" and self._detect_report_intent(state["question"]))
            )
            state["report_meta"] = {
                "is_report": is_report,
                "report_type": "课程总结报告" if is_report else "",
                "awaiting": awaiting_report,
            }

            if intent_category == "research":
                state["response_type"] = "research"
            elif intent_category == "generate_content" or is_report:
                gateway = state.get("gateway")
                router = ResourceTypeRouter(model_gateway=gateway)
                resource_type, source = router.classify(state.get("question", ""))
                state["resource_type"] = resource_type
                state["resource_router_reason"] = source
                state["resource_route_source"] = (
                    "llm" if str(source).startswith("llm:") else ("keyword" if str(source).startswith("keyword:") else "fallback")
                )
                state["response_type"] = "text_generate" if resource_type in {"report", "lesson_plan", "quiz", "flashcard", "blog"} else "multimodal_generate"
            else:
                state["response_type"] = "chat"

            req_clear, req_count, req_signals = self._is_requirement_clear(state.get("question", ""), state.get("slots"))
            need_type, user_role_mode, dialogue_skill, need_reason = self._detect_need_type(state.get("question", ""))
            state["requirement_clear"] = req_clear
            state["requirement_signal_count"] = req_count
            state["requirement_signals"] = req_signals
            state["need_type"] = need_type
            state["user_role_mode"] = user_role_mode
            state["dialogue_skill"] = dialogue_skill
            state["need_route_reason"] = need_reason
            return state

        def chat_node(state: GraphState) -> GraphState:
            if state.get("skip_chat_llm") and state.get("final_answer"):
                return state

            merged_slots = state.get("slots", {})
            planner = ResponsePlanner(model_gateway=state["gateway"])
            plan = planner.plan(state["question"], merged_slots)
            answer_mode = str(plan.get("answer_mode") or "qa")
            style_hint = str(plan.get("style_hint") or "")
            state["plan"] = plan
            state["answer_mode"] = answer_mode
            state["style_hint"] = style_hint

            planned_question = self._compose_planned_question(state["question"], answer_mode, style_hint)

            skill_used = str(state.get("skill_used") or "")
            output_template_section_map = {
                "dialogue-pedagogical": "PEDAGOGICAL_TEMPLATE",
                "dialogue-management": "MANAGEMENT_TEMPLATE",
                "dialogue-reflective": "REFLECTIVE_TEMPLATE",
                "dialogue-explainer": "EXPLAINER_TEMPLATE",
            }
            template_section = output_template_section_map.get(skill_used)
            if template_section:
                output_template = self._skill_manager.extract_section("edu-dialogue-agent", template_section).strip()
                if output_template:
                    planned_question = (
                        f"{planned_question}\n\n"
                        "【输出结构要求】\n"
                        "请按以下模板结构组织回答，标题与顺序保持一致：\n"
                        f"{output_template}"
                    )

            video_hits: List[Dict[str, Any]] = []
            use_video_search, video_reason, video_source = should_use_video_search(
                question=state.get("question", ""),
                llm=state.get("llm"),
                prompt=VIDEO_SEARCH_INTENT_PROMPT,
            )
            video_override_applied = False

            conv_state_local = state.get("conv_state", {}) or {}
            pending_tool_auth = conv_state_local.get("pending_tool_auth") if isinstance(conv_state_local, dict) else {}
            pending_tool_type = str((pending_tool_auth or {}).get("tool") or "none")

            if pending_tool_type in {"rag", "web"}:
                if self._is_tool_auth_accepted(state.get("question", "")):
                    state["tool_auth_requested"] = True
                    state["tool_auth_granted"] = True
                    state["tool_auth_type"] = pending_tool_type
                    state["tool_auth_reason"] = str((pending_tool_auth or {}).get("reason") or "user_accepted")
                    state["tool_auth_source"] = "override"
                    state["rag_tool_enabled"] = pending_tool_type == "rag"
                    state["deepsearch_tool_enabled"] = pending_tool_type == "web"
                elif self._is_tool_auth_rejected(state.get("question", "")):
                    state["tool_auth_requested"] = True
                    state["tool_auth_granted"] = False
                    state["tool_auth_type"] = pending_tool_type
                    state["tool_auth_reason"] = "user_rejected"
                    state["tool_auth_source"] = "override"
                    state["rag_tool_enabled"] = False
                    state["deepsearch_tool_enabled"] = False
                    state["final_answer"] = self._build_tool_reject_fallback_prompt(pending_tool_type)
                    state["skip_chat_llm"] = True
                    state["next_action"] = "direct_answer"
                    state["degraded"] = True
                    return state
                else:
                    state["final_answer"] = self._build_tool_auth_prompt(
                        pending_tool_type,
                        str((pending_tool_auth or {}).get("reason") or "请确认是否授权"),
                    )
                    state["skip_chat_llm"] = True
                    state["tool_auth_requested"] = True
                    state["tool_auth_granted"] = False
                    state["tool_auth_type"] = pending_tool_type
                    state["tool_auth_reason"] = "awaiting_user_confirmation"
                    state["tool_auth_source"] = "override"
                    return state
            else:
                tool_type, tool_reason, tool_source = self._detect_tool_intent(state.get("question", ""))
                if tool_type in {"rag", "web"}:
                    state["final_answer"] = self._build_tool_auth_prompt(tool_type, tool_reason)
                    state["skip_chat_llm"] = True
                    state["tool_auth_requested"] = True
                    state["tool_auth_granted"] = False
                    state["tool_auth_type"] = tool_type
                    state["tool_auth_reason"] = tool_reason
                    state["tool_auth_source"] = tool_source
                    state["next_action"] = "ask_user"
                    return state

            if use_video_search:
                try:
                    video_hits = search_video_segments_for_chat(
                        query=state.get("question", ""),
                        owner=RAG_CONTEXT.get().get("owner"),
                        course_id=state.get("course_id"),
                        top_k=3,
                    )
                except Exception as exc:
                    print(f"[video_search_chat] error={exc}")
                    video_hits = []
                    video_reason = f"search_error:{exc}"
                    video_source = "fallback"

            state["video_hits"] = video_hits
            state["video_search_reason"] = video_reason
            state["video_search_source"] = video_source
            state["video_override_applied"] = video_override_applied

            if video_hits:
                lines = []
                for idx, hit in enumerate(video_hits, start=1):
                    start_t = hit.get("start_time")
                    end_t = hit.get("end_time")
                    transcript = str(hit.get("transcript") or "").strip().replace("\n", " ")
                    lines.append(
                        f"{idx}. time={start_t}-{end_t}; snippet={transcript[:180]}"
                    )
                planned_question = (
                    f"{planned_question}\n\n"
                    "【视频检索结果】\n"
                    + "\n".join(lines)
                    + "\n\n请优先基于这些视频片段回答，并在结尾给出你引用的时间点。"
                )

            if not state.get("messages_inited"):
                runtime_system_prompt = self._record_node_skills(
                    state=state,
                    node_name="chat",
                    base_prompt=SYSTEM_PROMPT,
                    has_video_context=bool(video_hits),
                    has_image_context=False,
                )
                state["render_messages"] = [
                    {"role": "system", "content": runtime_system_prompt},
                    *(
                        {"role": msg.get("role"), "content": msg.get("content")}
                        for msg in state.get("history", [])
                        if msg.get("role") in {"user", "assistant"} and msg.get("content")
                    ),
                    {"role": "user", "content": planned_question},
                ]
                state["messages"] = state["render_messages"].copy()
                state["messages_inited"] = True

            llm = state.get("llm")
            llm_deep = state.get("llm_deep") or llm
            vlm = state.get("vlm")
            if not llm:
                state["final_answer"] = ""
                return state

            debug_messages = state.get("messages", []) or []

            def _extract_image_paths_from_tool_messages(messages: List[Any]) -> List[str]:
                image_paths: List[str] = []
                for msg in messages:
                    msg_type = getattr(msg, "type", None)
                    is_tool_msg = msg_type == "tool" or (isinstance(msg, dict) and msg.get("type") == "tool")
                    if not is_tool_msg:
                        continue

                    content_raw = getattr(msg, "content", None) if not isinstance(msg, dict) else msg.get("content")
                    try:
                        payload = json.loads(str(content_raw or "{}"))
                    except Exception:
                        continue

                    if not isinstance(payload, dict):
                        continue
                    sources = payload.get("sources")
                    if not isinstance(sources, list):
                        continue

                    for src in sources:
                        if not isinstance(src, dict):
                            continue
                        modality = str(src.get("modality") or "").strip().lower()
                        image_path = str(src.get("image_path") or "").strip()
                        if modality == "image" and image_path:
                            image_paths.append(image_path)

                dedup: List[str] = []
                seen = set()
                for p in image_paths:
                    if p not in seen:
                        seen.add(p)
                        dedup.append(p)
                return dedup

            try:
                msg_tail = debug_messages[-2:] if len(debug_messages) >= 2 else debug_messages
                msg_tail_types = [type(m).__name__ for m in msg_tail]
                msg_tail_roles = [m.get("role") if isinstance(m, dict) else getattr(m, "type", None) for m in msg_tail]
                print(
                    "[chat_node_debug] before_invoke "
                    f"model_id={state.get('model_cfg', {}).get('id')} "
                    f"model_name={state.get('model_cfg', {}).get('model_name')} "
                    f"api_base={state.get('model_cfg', {}).get('api_base')} "
                    f"llm_class={type(llm).__name__} "
                    f"messages_count={len(debug_messages)} "
                    f"tail_types={msg_tail_types} "
                    f"tail_roles={msg_tail_roles}"
                )
            except Exception as debug_exc:
                print(f"[chat_node_debug_error] before_invoke_debug_failed: {debug_exc}")

            tools = [deep_research_tool]
            if state.get("rag_tool_enabled"):
                tools.insert(0, rag_search_tool)
            # 路由/工具调用阶段固定使用快速模型
            tool_llm = llm.bind_tools(tools)
            response = tool_llm.invoke(debug_messages)

            print(f"[chat_node_debug] invoke_ok response_type={type(response)}")

            tool_calls = getattr(response, "tool_calls", None)
            if tool_calls:
                safe_calls = []
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    args = tc.get("args", {})
                    if isinstance(args, dict):
                        args_json = json.dumps(args, ensure_ascii=False)
                    else:
                        args_json = str(args or "{}")
                    safe_calls.append(
                        {
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {"name": tc.get("name"), "arguments": args_json},
                        }
                    )

                safe_msg = AIMessage(
                    content=response.content or "",
                    tool_calls=tool_calls,
                    additional_kwargs={"tool_calls": safe_calls},
                )
                state["messages"].append(safe_msg)
            else:
                has_tool_result = any(
                    (getattr(msg, "type", None) == "tool")
                    or (isinstance(msg, dict) and msg.get("type") == "tool")
                    for msg in state.get("messages", [])
                )
                if (
                    state.get("deepsearch_tool_enabled")
                    and not state.get("deepsearch_done")
                    and not has_tool_result
                ):
                    deep_call_id = f"deep_{int(datetime.now().timestamp() * 1000)}"
                    forced_call = {
                        "id": deep_call_id,
                        "name": "deep_research_tool",
                        "args": {
                            "query": planned_question,
                        },
                    }
                    safe_msg = AIMessage(
                        content="",
                        tool_calls=[forced_call],
                        additional_kwargs={
                            "tool_calls": [
                                {
                                    "id": deep_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": "deep_research_tool",
                                        "arguments": json.dumps(forced_call["args"], ensure_ascii=False),
                                    },
                                }
                            ]
                        },
                    )
                    state["messages"].append(safe_msg)
                    return state

                if state.get("rag_tool_enabled") and state.get("selected_doc_ids") and not has_tool_result:
                    rag_call_id = f"rag_{int(datetime.now().timestamp() * 1000)}"
                    forced_call = {
                        "id": rag_call_id,
                        "name": "rag_search_tool",
                        "args": {
                            "query": planned_question,
                            "top_k": int(state.get("rag_top_k", 5)),
                        },
                    }
                    safe_msg = AIMessage(
                        content="",
                        tool_calls=[forced_call],
                        additional_kwargs={
                            "tool_calls": [
                                {
                                    "id": rag_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": "rag_search_tool",
                                        "arguments": json.dumps(forced_call["args"], ensure_ascii=False),
                                    },
                                }
                            ]
                        },
                    )
                    state["messages"].append(safe_msg)
                    return state

                raw_text = str(getattr(response, "content", "") or "").strip()
                final_text = raw_text

                # 如果工具结果里包含图片 source，则强制构造多模态消息给深度模型
                image_paths = _extract_image_paths_from_tool_messages(state.get("messages", []) or [])
                multimodal_blocks: List[Dict[str, Any]] = []
                injected_image_count = 0
                image_inject_stats = {
                    "total_candidates": len(image_paths),
                    "checked": 0,
                    "injected": 0,
                    "skipped_over_limit": max(0, len(image_paths) - 3),
                    "missing_path": 0,
                    "not_absolute": 0,
                    "not_found": 0,
                    "not_file": 0,
                    "read_error": 0,
                    "encode_error": 0,
                    "unsupported_mime_fallback": 0,
                    "unknown_error": 0,
                }
                image_inject_errors: List[str] = []

                if image_paths:
                    multimodal_blocks.append(
                        {
                            "type": "text",
                            "text": (
                                "请结合检索到的参考图片与文字资料，直接回答用户问题。"
                                f"\n用户问题：{state.get('question') or ''}"
                                f"\n已有文字草稿：{raw_text or '（无）'}"
                            ),
                        }
                    )
                    for idx, img_path in enumerate(image_paths[:3], start=1):
                        image_inject_stats["checked"] += 1
                        raw_path = str(img_path or "").strip()
                        if not raw_path:
                            image_inject_stats["missing_path"] += 1
                            image_inject_errors.append(f"#{idx}:empty_path")
                            continue
                        try:
                            resolved = Path(raw_path)
                            if not resolved.is_absolute():
                                image_inject_stats["not_absolute"] += 1
                                resolved = Path.cwd() / resolved

                            if not resolved.exists():
                                image_inject_stats["not_found"] += 1
                                image_inject_errors.append(f"#{idx}:not_found:{resolved}")
                                continue
                            if not resolved.is_file():
                                image_inject_stats["not_file"] += 1
                                image_inject_errors.append(f"#{idx}:not_file:{resolved}")
                                continue

                            mime, _ = mimetypes.guess_type(str(resolved))
                            if not mime:
                                image_inject_stats["unsupported_mime_fallback"] += 1
                                mime = "image/png"

                            try:
                                file_bytes = resolved.read_bytes()
                            except Exception as read_exc:
                                image_inject_stats["read_error"] += 1
                                image_inject_errors.append(f"#{idx}:read_error:{resolved}:{read_exc}")
                                continue

                            try:
                                b64_data = base64.b64encode(file_bytes).decode("utf-8")
                            except Exception as encode_exc:
                                image_inject_stats["encode_error"] += 1
                                image_inject_errors.append(f"#{idx}:encode_error:{resolved}:{encode_exc}")
                                continue

                            multimodal_blocks.append(
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{b64_data}"},
                                }
                            )
                            injected_image_count += 1
                            image_inject_stats["injected"] += 1
                        except Exception as inject_exc:
                            image_inject_stats["unknown_error"] += 1
                            image_inject_errors.append(f"#{idx}:unknown_error:{raw_path}:{inject_exc}")

                has_video_context = bool(state.get("video_hits"))
                should_use_vlm = bool(vlm) and (injected_image_count > 0 or has_video_context)
                final_model_for_answer = vlm if should_use_vlm else llm_deep
                selected_role = "qwen_vlm" if should_use_vlm else "deep"
                selected_model_name = ""
                try:
                    selected_model_name = str(getattr(final_model_for_answer, "model_name", "") or "")
                except Exception:
                    selected_model_name = ""

                print(
                    "[chat_node_image_inject] "
                    f"sources_images={len(image_paths)} injected={injected_image_count} "
                    f"final_model={selected_model_name or state.get('llm_deep_model_name') or 'unknown'} "
                    f"stats={json.dumps(image_inject_stats, ensure_ascii=False)}"
                )
                print(
                    "[model_select] "
                    f"final_answer_role={selected_role} "
                    f"final_answer_model={selected_model_name or 'unknown'}"
                )
                if image_inject_errors:
                    print(
                        "[chat_node_image_inject_errors] "
                        + " | ".join(image_inject_errors[:10])
                    )

                # 极速模式：移除纯文本重写链路，直接输出草稿；仅图片场景唤醒视觉模型重答
                state["agent_monologue"] = ""
                if should_use_vlm and final_model_for_answer:
                    try:
                        if not multimodal_blocks:
                            multimodal_blocks = [
                                {
                                    "type": "text",
                                    "text": (
                                        "请基于现有检索证据回答用户问题。"
                                        f"\n用户问题：{state.get('question') or ''}"
                                        f"\n已有文字草稿：{raw_text or '（无）'}"
                                    ),
                                }
                            ]
                        vision_messages = [
                            {
                                "role": "system",
                                "content": "你是教学对话 Agent。请结合参考图片、视频片段与文字资料，直接回答用户问题。",
                            },
                            {
                                "role": "user",
                                "content": multimodal_blocks,
                            },
                        ]
                        vision_resp = final_model_for_answer.invoke(vision_messages)
                        vision_text = str(getattr(vision_resp, "content", "") or "").strip()
                        if vision_text:
                            final_text = vision_text
                        print("[chat_fastpath] qwen_reanswer=1")
                    except Exception as e:
                        print(f"[chat_fastpath] qwen_reanswer_error={e}")
                else:
                    print("[chat_fastpath] text_direct_output=1")

                state["final_answer"] = final_text
                state["final_answer_model"] = selected_model_name or (state.get("llm_deep_model_name") if not should_use_vlm else "") or "unknown"
                state["final_answer_role"] = selected_role
                state["messages"].append({"role": "assistant", "content": final_text})

            return state

        def chat_tools_node(state: GraphState) -> GraphState:
            last_msg = state.get("messages", [])[-1] if state.get("messages") else None
            tool_calls = getattr(last_msg, "tool_calls", None) or []

            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                tool_call_id = tc.get("id")
                function = tc.get("function") or {}
                tool_name = str(function.get("name") or tc.get("name") or "").strip()
                args_payload = function.get("arguments") or tc.get("args") or {}

                if not tool_name:
                    continue

                if isinstance(args_payload, str):
                    try:
                        args = json.loads(args_payload)
                    except Exception:
                        args = {}
                elif isinstance(args_payload, dict):
                    args = args_payload
                else:
                    args = {}

                if tool_name == "rag_search_tool":
                    result = rag_search_tool.invoke({"query": args.get("query", ""), "top_k": args.get("top_k", 5)})
                elif tool_name == "deep_research_tool":
                    result = deep_research_tool.invoke({"query": args.get("query", "")})
                else:
                    result = "未找到对应工具"

                content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                state["messages"].append(
                    ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name)
                )

            return state

        graph = StateGraph(GraphState)

        supervisor_agent = SupervisorAgent(router_node)
        chat_agent = ChatAgent(chat_node=chat_node, chat_tools_node=chat_tools_node)
        report_agent = ReportAgent(
            host=self,
            extractor_system_prompt=EXTRACTOR_SYSTEM_PROMPT,
            max_clarification_turns=MAX_CLARIFICATION_TURNS,
            report_slot_schema=REPORT_SLOT_SCHEMA,
        )
        research_agent = ResearchAgent(chat_tools_node=chat_tools_node)

        # P1-04 渐进兼容：先完成两步路由与状态写入；新引擎未落地前统一回落到 report_agent。
        supervisor_agent.attach(
            graph,
            chat_node="chat_agent",
            report_node="report_agent",
            research_node="research_agent",
            route_fn=route_after_supervisor,
            route_mapping={
                "chat": "chat_agent",
                "research": "research_agent",
                "text_generate": "report_agent",
                "ppt": "report_agent",
                "video": "report_agent",
                "podcast": "report_agent",
            },
        )
        chat_agent.attach(graph, node_name="chat_agent")
        report_agent.attach(graph, node_name="report_agent")
        research_agent.attach(graph, node_name="research_agent")
        SupervisorAgent.attach_terminal_edges(
            graph,
            nodes=["chat_agent", "report_agent", "research_agent"],
        )

        return graph.compile()

    def chat_stream_with_meta(
        self,
        *,
        question: str,
        conversation_id: Optional[str],
        model_id: Optional[str],
        use_rag: bool = False,
        selected_doc_ids: Optional[List[str]] = None,
        owner: Optional[str] = None,
        course_id: Optional[str] = None,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
    ) -> tuple[Dict[str, Any], Iterable[Dict[str, Any]]]:
        conv_id = conversation_id or f"conv_{datetime.now().timestamp()}"
        conversation_storage.ensure_conversation(conv_id, question)

        gateway, planner_model_cfg = self._get_model_gateway(model_id)
        deep_model_cfg = Config.get_deep_model()
        vision_model_cfg = Config.get_vision_model()

        history = conversation_storage.get_messages(conv_id, limit=Config.CHAT_HISTORY_WINDOW * 2)
        user_profile = user_profile_storage.get_profile(owner or "") if owner else {}
        conv_state = conversation_storage.get_state(conv_id)

        state: GraphState = {
            "question": question,
            "conversation_id": conv_id,
            "model_id": model_id,
            "gateway": gateway,
            "model_cfg": planner_model_cfg,
            "deep_model_cfg": deep_model_cfg,
            "llm_deep_model_name": str(deep_model_cfg.get("model_name") or Config.LLM_MODEL_DEEP),
            "history": history,
            "conv_state": conv_state,
            "slots": {},
            "expected_slot": None,
            "slot_signal": {},
            "intent_category": "",
            "router_reason": "",
            "intent_router_reason": "",
            "resource_router_reason": "",
            "awaiting_override_applied": False,
            "route_source": "",
            "intent_route_source": "",
            "resource_route_source": "",
            "video_search_reason": "",
            "video_search_source": "",
            "video_override_applied": False,
            "extractor_reason": "",
            "extractor_source": "",
            "extractor_override_applied": False,
            "outline_reason": "",
            "outline_source": "",
            "outline_override_applied": False,
            "generate_reason": "",
            "generate_source": "",
            "generate_override_applied": False,
            "clarify_result": {},
            "plan": {},
            "answer_mode": "",
            "style_hint": "",
            "used_clarification": False,
            "confidence": {},
            "followup_question": "",
            "response_type": "chat",
            "anti_repeat_used": False,
            "missing_slot": "",
            "known_info_prefix": "",
            "missing_info": [],
            "ask_counts": conv_state.get("ask_counts", {}),
            "messages": [],
            "render_messages": [],
            "messages_inited": False,
            "user_profile": user_profile,
            # llm: 路由/工具决策模型（固定走 planner，默认 gpt-5.4-mini）
            "llm": ChatOpenAI(
                api_key=str(planner_model_cfg.get("api_key") or Config.REMOTE_MODEL_API_KEY),
                base_url=str(planner_model_cfg.get("api_base") or Config.REMOTE_MODEL_API_BASE),
                model=str(planner_model_cfg.get("model_name") or Config.LLM_MODEL),
                temperature=0.0,
            ),
            # llm_deep: 对话/大纲/报告正文统一使用默认回答模型（现切到 Qwen3.5 Plus）
            "llm_deep": ChatOpenAI(
                api_key=str(
                    deep_model_cfg.get("api_key")
                    or Config.DEEP_MODEL_API_KEY
                    or Config.REMOTE_MODEL_API_KEY
                ),
                base_url=str(
                    deep_model_cfg.get("api_base")
                    or Config.DEEP_MODEL_API_BASE
                    or Config.REMOTE_MODEL_API_BASE
                ),
                model=str(deep_model_cfg.get("model_name") or Config.LLM_MODEL_DEEP),
                temperature=0.0,
                max_tokens=4096,
            ),
            # vlm: 仅当检测到图片时使用的视觉模型（Qwen）
            "vlm": ChatOpenAI(
                api_key=str(vision_model_cfg.get("api_key") or ""),
                base_url=str(vision_model_cfg.get("api_base") or ""),
                model=str(vision_model_cfg.get("model_name") or ""),
                temperature=0.2,
            ),
            "rag_tool_enabled": (
                bool(use_rag)
                or any(
                    k in question
                    for k in [
                        "知识库",
                        "库内",
                        "本地",
                        "文档",
                        "资料库",
                        "已有资料",
                        "上传资料",
                        "课程资料",
                        "教案库",
                        "课件",
                        "讲义",
                        "笔记",
                    ]
                )
            ),
            "deepsearch_tool_enabled": any(
                k in question
                for k in [
                    "网上",
                    "互联网",
                    "网络",
                    "网页",
                    "搜索",
                    "搜一下",
                    "百度",
                    "谷歌",
                    "查一下",
                    "查找",
                    "爬取",
                    "抓取",
                ]
            ),
            "rag_top_k": 5,
            "final_answer": "",
            "final_answer_source": None,
            "final_answer_model": "",
            "final_answer_role": "",
            "selected_doc_ids": selected_doc_ids or [],
            "deepsearch_done": False,
            "course_id": course_id,
            "report_slots": {},
            "report_missing": [],
            "report_ask_counts": {},
            "report_auto_fill": False,
            "report_ready": False,
            "report_content": "",
            "report_meta": {},
            "report_reflection": {},
            "report_checkpoint": {},
            "soft_params_confirmed": False,
            "agent_monologue": "",
            "video_hits": [],
            "applied_skills": [],
            "node_skill_map": {},
            "skill_used": "",
            "next_action": "direct_answer",
            "needs_more_context": False,
            "tool_auth_requested": False,
            "tool_auth_granted": False,
            "tool_auth_type": "none",
            "tool_auth_reason": "",
            "tool_auth_source": "",
            "requirement_clear": False,
            "requirement_signal_count": 0,
            "requirement_signals": [],
            "need_type": "unclear",
            "user_role_mode": "teacher_educator",
            "dialogue_skill": "dialogue-consultative",
            "need_route_reason": "init_default",
            "degraded": False,
        }

        meta_payload: Dict[str, Any] = {
            "conversation_id": conv_id,
            "model_id": str(deep_model_cfg.get("id") or Config.DEFAULT_LLM_MODEL_ID),
            "intent_category": "chat",
            "title": conversation_storage.get_conversation(conv_id).get("title"),
            "sources": [],
            "meta": {
                "mode": "langgraph_router",
                "provider": "openai_compatible",
                "generate_enabled": False,
                "response_type": "chat",
                "tool_calls": [],
            },
        }

        def stream_answer() -> Iterable[Dict[str, Any]]:
            current_state = state
            stream_t0 = time.perf_counter()
            node_first_seen: Dict[str, float] = {}
            conv_report_state = (conv_state.get("report_state") or {}) if isinstance(conv_state, dict) else {}
            report_awaiting = bool(conv_report_state.get("awaiting"))
            is_report_request = report_awaiting or self._detect_report_intent(question)
            use_universal_engine = (
                is_report_request
                and self._use_universal_report_engine_for_request(
                    conv_id=conv_id,
                    owner=owner,
                    report_awaiting=report_awaiting,
                )
            )

            if is_report_request:
                if use_universal_engine:
                    self._universal_report_metrics["selected"] += 1
                else:
                    self._universal_report_metrics["skipped"] += 1

            if use_universal_engine:
                    # v2: Simplified state restore + invoke. The engine's evaluator
                    # handles all routing internally via pure rules — no LLM intent
                    # classification or default-value backfill needed here.
                    persisted_engine = conv_state.get("report_engine_state") if isinstance(conv_state, dict) else None
                    if isinstance(persisted_engine, dict) and persisted_engine:
                        engine_state = dict(persisted_engine)
                        if report_awaiting:
                            engine_state["human_feedback"] = question
                        else:
                            engine_state["user_input"] = question
                            engine_state["human_feedback"] = ""
                    else:
                        engine_state = make_initial_report_state(user_input=question)

                    # Merge slots/outline from conv_state projection (backward compat)
                    report_slots = dict(conv_report_state.get("slots") or {})
                    report_outline = list(conv_report_state.get("outline") or [])
                    if report_slots:
                        engine_state["report_slots"] = report_slots
                    if report_outline:
                        engine_state["report_outline"] = report_outline

                    # Ensure v2 fields exist (compat with old persisted states)
                    if "phase" not in engine_state:
                        engine_state["phase"] = "extracting"
                    if "soft_confirmed" not in engine_state:
                        engine_state["soft_confirmed"] = False
                    if "outline_confirmed" not in engine_state:
                        engine_state["outline_confirmed"] = False
                    if "ask_count" not in engine_state:
                        engine_state["ask_count"] = {}
                    if "ask_limit" not in engine_state:
                        engine_state["ask_limit"] = 2
                    if "_missing_slot" not in engine_state:
                        engine_state["_missing_slot"] = ""

                    # Only set phase to extracting on initial creation, preserve it on subsequent invokes
                    if "phase" not in engine_state:
                        engine_state["phase"] = "extracting"

                    result_state = self._universal_report_graph.invoke(engine_state)
                    result_status = str(result_state.get("status") or "").strip().lower()
                    self._universal_report_metrics[result_status] = self._universal_report_metrics.get(result_status, 0) + 1
                    if str(result_state.get("error") or "").strip():
                        self._universal_report_metrics["tool_failure"] += 1
                    result_outline = list(result_state.get("report_outline") or [])
                    result_content = str(result_state.get("report_content") or "")
                    result_answer = str(result_state.get("final_response") or "").strip()

                    meta_payload["meta"]["mode"] = "universal_report_engine"
                    meta_payload["meta"]["response_type"] = "ask" if result_status == "awaiting_human" else ("generate" if result_content else "chat")
                    meta_payload["meta"]["report"] = {
                        "status": result_status,
                        "slots": result_state.get("report_slots", {}),
                        "outline": result_outline,
                        "has_content": bool(result_content),
                        "replan_count": int(result_state.get("replan_count") or 0),
                        "max_replans": int(result_state.get("max_replans") or 3),
                    }
                    if result_status == "finished" and result_content:
                        report_id_meta = f"report_{int(datetime.now().timestamp() * 1000)}"
                        meta_payload["meta"]["report_generated"] = {
                            "id": report_id_meta,
                            "title": f"知识报告：{result_state.get('report_slots', {}).get('core_topic') or REPORT_DEFAULTS['core_topic']}",
                            "markdown": result_content,
                        }
                    meta_payload["meta"]["rollout"] = {
                        "enabled": bool(self._enable_universal_report_engine),
                        "percent": int(self._universal_report_rollout_percent),
                        "selected": bool(use_universal_engine),
                    }
                    meta_payload["meta"]["universal_report_metrics"] = dict(self._universal_report_metrics)
                    yield {"type": "meta", "payload": meta_payload}

                    if result_status == "awaiting_human":
                        answer_text = result_answer or "我需要你再补充一点信息，才能继续生成报告。"
                        yield {"type": "delta", "delta": answer_text}
                        conversation_storage.append_message(conv_id, role="user", content=question, timestamp=datetime.now().isoformat())
                        conversation_storage.append_message(conv_id, role="assistant", content=answer_text, timestamp=datetime.now().isoformat())
                        conversation_storage.update_state(
                            conv_id,
                            {
                                "awaiting_clarification": True,
                                "report_engine_state": result_state,
                                "report_state": {
                                    "slots": result_state.get("report_slots", {}),
                                    "awaiting": True,
                                    "expected_slot": "engine_feedback",
                                    "outline": result_outline,
                                    "outline_pending": bool(result_outline) and not bool(result_content),
                                },
                            },
                        )
                        yield {"type": "done"}
                        return

                    if result_status == "finished" and result_content:
                        answer_text = "报告已经生成，请在右侧面板预览。"
                        yield {"type": "delta", "delta": answer_text}
                        conversation_storage.append_message(conv_id, role="user", content=question, timestamp=datetime.now().isoformat())
                        conversation_storage.append_message(conv_id, role="assistant", content=answer_text, timestamp=datetime.now().isoformat())
                        report_id = f"report_{int(datetime.now().timestamp() * 1000)}"
                        report_record = {
                            "id": report_id,
                            "title": f"知识报告：{result_state.get('report_slots', {}).get('core_topic') or REPORT_DEFAULTS['core_topic']}",
                            "content": result_content,
                            "slots": result_state.get("report_slots", {}),
                            "created_at": datetime.now().isoformat(),
                        }
                        conversation_storage.update_state(
                            conv_id,
                            {
                                "awaiting_clarification": False,
                                "report_engine_state": result_state,
                                "report_state": {
                                    "slots": result_state.get("report_slots", {}),
                                    "awaiting": False,
                                    "outline": result_outline,
                                    "outline_pending": False,
                                },
                                "last_report": report_record,
                            },
                        )
                        yield {"type": "done"}
                        return

                    answer_text = result_answer or "已完成本轮处理。"
                    yield {"type": "delta", "delta": answer_text}
                    conversation_storage.append_message(conv_id, role="user", content=question, timestamp=datetime.now().isoformat())
                    conversation_storage.append_message(conv_id, role="assistant", content=answer_text, timestamp=datetime.now().isoformat())
                    conversation_storage.update_state(
                        conv_id,
                        {
                            "awaiting_clarification": False,
                            "report_engine_state": result_state,
                            "report_state": {
                                "slots": result_state.get("report_slots", {}),
                                "awaiting": False,
                                "outline": result_outline,
                                "outline_pending": bool(result_outline) and not bool(result_content),
                            },
                        },
                    )
                    yield {"type": "done"}
                    return

            token = RAG_CONTEXT.set({
                "selected_doc_ids": selected_doc_ids or [],
                "owner": owner,
                "question": question,
                "gateway": gateway,
                "course_id": course_id,
                "state": current_state,
            })
            try:
                print("[stream_debug] entering compiled_graph.stream")
                for event in self._compiled_graph.stream(
                    state,
                    stream_mode="updates",
                    # 关闭 subgraphs 流式命名空间展开，避免某些运行时对象序列化触发 model_dump 异常
                    subgraphs=False,
                ):
                    print(f"[stream_debug] raw_event_type={type(event)}")
                    if isinstance(event, tuple) and len(event) == 2:
                        namespace, chunk = event
                    else:
                        namespace, chunk = (), event
                    print(
                        f"[stream_debug] namespace={list(namespace)} chunk_type={type(chunk)} "
                        f"chunk_keys={(list(chunk.keys()) if isinstance(chunk, dict) else 'n/a')}"
                    )
                    if not isinstance(chunk, dict):
                        continue
                    for node_name, update in chunk.items():
                        now = time.perf_counter()
                        if node_name not in node_first_seen:
                            node_first_seen[node_name] = now
                            print(f"[timing] node_first_seen node={node_name} at={now - stream_t0:.3f}s")
                        print(
                            f"[stream_debug] node={node_name} update_type={type(update)} "
                            f"has_messages={(isinstance(update, dict) and 'messages' in update)}"
                        )
                        if isinstance(update, dict):
                            current_state.update(update)
                        stage = "thinking"
                        if node_name in {"supervisor", "router"}:
                            stage = "thinking"
                        elif node_name == "extractor":
                            stage = "extracting"
                        elif node_name == "evaluator":
                            stage = "evaluating"
                        elif node_name in {"chat_tools", "research_tools"}:
                            stage = "rag"
                        elif node_name == "ask":
                            stage = "asking"
                        elif node_name in {"outline", "generate"}:
                            stage = "generating"
                        elif node_name == "chat":
                            stage = "streaming"
                        yield {
                            "type": "status",
                            "stage": stage,
                            "node": node_name,
                            "namespace": list(namespace),
                        }
            except Exception as stream_exc:
                print(f"[stream_error] type={type(stream_exc)} detail={stream_exc}")
                print("[stream_error_traceback]\n" + traceback.format_exc())
                # 继续抛出，由外层 SSE error 处理并回传前端
                raise
            finally:
                print(f"[timing] stream_answer graph_phase_elapsed={time.perf_counter() - stream_t0:.3f}s")
                RAG_CONTEXT.reset(token)

            tool_calls: set[str] = set()
            for msg in current_state.get("messages", []):
                tool_call_entries = None
                if isinstance(msg, dict):
                    tool_call_entries = msg.get("tool_calls")
                else:
                    tool_call_entries = getattr(msg, "tool_calls", None)
                if not tool_call_entries:
                    continue
                for entry in tool_call_entries:
                    if isinstance(entry, dict):
                        name = entry.get("name") or entry.get("function", {}).get("name")
                    else:
                        name = getattr(entry, "name", None)
                    if name:
                        tool_calls.add(str(name))

            rag_sources: List[Dict[str, Any]] = []
            for msg in current_state.get("messages", []):
                msg_type = getattr(msg, "type", None)
                content = None
                if msg_type == "tool":
                    content = getattr(msg, "content", None)
                elif isinstance(msg, dict) and msg.get("type") == "tool":
                    content = msg.get("content")
                if not content:
                    continue
                try:
                    parsed = json.loads(content)
                except Exception:
                    continue
                if isinstance(parsed, dict) and parsed.get("sources"):
                    rag_sources.extend(parsed.get("sources") or [])

            meta_payload["sources"] = rag_sources
            meta_payload["intent_category"] = current_state.get("intent_category", "")
            report_payload: Optional[Dict[str, Any]] = None
            if (
                current_state.get("response_type") == "generate"
                and current_state.get("report_meta", {}).get("is_report")
            ):
                report_id = f"report_{int(datetime.now().timestamp() * 1000)}"
                report_title = (
                    f"知识报告："
                    f"{current_state.get('report_slots', {}).get('core_topic') or REPORT_DEFAULTS['core_topic']}"
                )
                report_payload = {
                    "id": report_id,
                    "title": report_title,
                    "markdown": current_state.get("report_content") or "",
                }

            contract_payload = {
                "answer": str(current_state.get("final_answer") or ""),
                "skill_used": current_state.get("skill_used", ""),
                "next_action": current_state.get("next_action", "direct_answer"),
                "needs_more_context": bool(current_state.get("needs_more_context", False)),
                "requested_tool": current_state.get("tool_auth_type", "none"),
                "tool_auth_required": bool(current_state.get("tool_auth_requested", False)),
                "followup_question": current_state.get("followup_question", ""),
                "audit": {
                    "reason": current_state.get("need_route_reason") or current_state.get("intent_router_reason", "") or current_state.get("router_reason", ""),
                    "route_source": current_state.get("intent_route_source", "") or current_state.get("route_source", ""),
                    "degraded": bool(current_state.get("degraded", False)),
                },
            }

            meta_payload["meta"]["dialogue_output_contract"] = contract_payload

            meta_payload["meta"].update(
                {
                    "audit": {
                        "router": {
                            "reason": current_state.get("intent_router_reason", "") or current_state.get("router_reason", ""),
                            "override_applied": bool(current_state.get("awaiting_override_applied", False)),
                            "route_source": current_state.get("intent_route_source", "") or current_state.get("route_source", ""),
                            "resource_router_reason": current_state.get("resource_router_reason", ""),
                            "resource_route_source": current_state.get("resource_route_source", ""),
                        },
                        "video_search": {
                            "reason": current_state.get("video_search_reason", ""),
                            "override_applied": bool(current_state.get("video_override_applied", False)),
                            "route_source": current_state.get("video_search_source", ""),
                        },
                        "extractor": {
                            "reason": current_state.get("extractor_reason", ""),
                            "override_applied": bool(current_state.get("extractor_override_applied", False)),
                            "route_source": current_state.get("extractor_source", ""),
                        },
                        "outline": {
                            "reason": current_state.get("outline_reason", ""),
                            "override_applied": bool(current_state.get("outline_override_applied", False)),
                            "route_source": current_state.get("outline_source", ""),
                        },
                        "generate": {
                            "reason": current_state.get("generate_reason", ""),
                            "override_applied": bool(current_state.get("generate_override_applied", False)),
                            "route_source": current_state.get("generate_source", ""),
                        },
                    },
                    "video_hits": current_state.get("video_hits", []),
                    "final_answer_model": current_state.get("final_answer_model", ""),
                    "final_answer_role": current_state.get("final_answer_role", ""),
                    "applied_skills": current_state.get("applied_skills", []),
                    "node_skill_map": current_state.get("node_skill_map", {}),
                    "skill_used": current_state.get("skill_used", ""),
                    "next_action": current_state.get("next_action", "direct_answer"),
                    "needs_more_context": bool(current_state.get("needs_more_context", False)),
                    "tool_auth_requested": bool(current_state.get("tool_auth_requested", False)),
                    "tool_auth_granted": bool(current_state.get("tool_auth_granted", False)),
                    "tool_auth_type": current_state.get("tool_auth_type", "none"),
                    "tool_auth_reason": current_state.get("tool_auth_reason", ""),
                    "tool_auth_source": current_state.get("tool_auth_source", ""),
                    "requested_tool": current_state.get("tool_auth_type", "none"),
                    "tool_auth_required": bool(current_state.get("tool_auth_requested", False)),
                    "degraded": bool(current_state.get("degraded", False)),
                    "requirement_clear": bool(current_state.get("requirement_clear", False)),
                    "requirement_signal_count": int(current_state.get("requirement_signal_count", 0)),
                    "requirement_signals": current_state.get("requirement_signals", []),
                    "need_type": current_state.get("need_type", "unclear"),
                    "user_role_mode": current_state.get("user_role_mode", "teacher_educator"),
                    "dialogue_skill": current_state.get("dialogue_skill", "dialogue-consultative"),
                    "need_route_reason": current_state.get("need_route_reason", ""),
                    "needs_clarification": bool(current_state.get("missing_info")) or bool(current_state.get("report_missing")),
                    "clarification_reason": None,
                    "clarification_source": None,
                    "slots": current_state.get("slots", {}),
                    "next_missing_slot": SlotTracker.pick_next_missing_slot(current_state.get("slots", {})),
                    "slot_confidence": current_state.get("slot_signal", {}).get("slot_confidence", {}),
                    "slot_correction_applied": bool(current_state.get("slot_signal", {}).get("correction_applied", False)),
                    "slot_correction_from": current_state.get("slot_signal", {}).get("correction_from"),
                    "slot_correction_to": current_state.get("slot_signal", {}).get("correction_to"),
                    "missing_info": current_state.get("missing_info", []),
                    "ask_counts": current_state.get("ask_counts", {}),
                    "answer_mode": current_state.get("answer_mode", ""),
                    "planner_source": current_state.get("plan", {}).get("source"),
                    "style_hint": current_state.get("style_hint", ""),
                    "response_type": current_state.get("response_type", "chat"),
                    "tool_calls": sorted(tool_calls),
                    "report": {
                        "is_report": bool(current_state.get("report_meta", {}).get("is_report")),
                        "slots": current_state.get("report_slots", {}),
                        "missing": current_state.get("report_missing", []),
                        "ask_counts": current_state.get("report_ask_counts", {}),
                        "auto_fill": bool(current_state.get("report_auto_fill")),
                        "outline": current_state.get("report_outline", []),
                        "outline_pending": bool(current_state.get("report_outline_pending")),
                        "soft_params_confirmed": bool(current_state.get("soft_params_confirmed", False)),
                        "reflection": current_state.get("report_reflection", {}),
                        "checkpoint": current_state.get("report_checkpoint", {}),
                    },
                    "report_generated": report_payload,
                    **current_state.get("confidence", {}),
                }
            )

            yield {"type": "meta", "payload": meta_payload}

            if current_state.get("response_type") == "generate":
                if current_state.get("report_meta", {}).get("is_report"):
                    answer_text = "报告已经生成，请在右侧面板预览。"
                else:
                    answer_text = GENERATE_PLACEHOLDER

                yield {"type": "delta", "delta": answer_text}

                conversation_storage.append_message(
                    conv_id,
                    role="user",
                    content=question,
                    timestamp=datetime.now().isoformat(),
                )
                conversation_storage.append_message(
                    conv_id,
                    role="assistant",
                    content=answer_text,
                    sources=rag_sources,
                    timestamp=datetime.now().isoformat(),
                )

                if current_state.get("report_meta", {}).get("is_report"):
                    report_id = f"report_{int(datetime.now().timestamp() * 1000)}"
                    report_state = {
                        "slots": current_state.get("report_slots", {}),
                        "last_generated_at": datetime.now().isoformat(),
                    }
                    report_record = {
                        "id": report_id,
                        "title": f"知识报告：{current_state.get('report_slots', {}).get('core_topic') or REPORT_DEFAULTS['core_topic']}",
                        "content": current_state.get("report_content") or "",
                        "slots": current_state.get("report_slots", {}),
                        "created_at": datetime.now().isoformat(),
                    }
                    conversation_storage.update_state(
                        conv_id,
                        {
                            "awaiting_clarification": False,
                            "report_state": {
                                **report_state,
                                "awaiting": False,
                            },
                            "last_report": report_record,
                        },
                    )
                else:
                    conversation_storage.update_state(
                        conv_id,
                        {
                            "awaiting_clarification": False,
                        },
                    )

                yield {"type": "done"}
                return

            if current_state.get("response_type") == "outline":
                answer_text = "已生成报告大纲，请在右侧面板确认。"
                yield {"type": "delta", "delta": answer_text}
                conversation_storage.append_message(
                    conv_id,
                    role="user",
                    content=question,
                    timestamp=datetime.now().isoformat(),
                )
                conversation_storage.append_message(
                    conv_id,
                    role="assistant",
                    content=answer_text,
                    sources=rag_sources,
                    timestamp=datetime.now().isoformat(),
                )
                conversation_storage.update_state(
                    conv_id,
                    {
                        "awaiting_clarification": False,
                        "report_state": {
                            "slots": current_state.get("report_slots", {}),
                            "awaiting": True,
                            "expected_slot": "outline_confirm",
                            "outline": current_state.get("report_outline", []),
                            "outline_pending": True,
                        },
                    },
                )
                yield {"type": "done"}
                return

            collected: List[str] = []
            answer_text = str(current_state.get("final_answer") or "").strip()
            if answer_text:
                chunk_size = 2
                for idx in range(0, len(answer_text), chunk_size):
                    chunk = answer_text[idx : idx + chunk_size]
                    collected.append(chunk)
                    yield {"type": "delta", "delta": chunk}
                    time.sleep(0.005)
            else:
                for chunk in gateway.stream_chat(current_state.get("messages", [])):
                    collected.append(chunk)
                    yield {"type": "delta", "delta": chunk}
                answer_text = "".join(collected).strip()

            if current_state.get("response_type") == "ask" and not current_state.get("report_meta", {}).get("is_report"):
                answer_text = self._postprocess_followup(
                    answer_text,
                    missing_slot=current_state.get("missing_slot", ""),
                    known_info_prefix=current_state.get("known_info_prefix", ""),
                )

            conversation_storage.append_message(
                conv_id,
                role="user",
                content=question,
                timestamp=datetime.now().isoformat(),
            )
            conversation_storage.append_message(
                conv_id,
                role="assistant",
                content=answer_text,
                sources=rag_sources,
                timestamp=datetime.now().isoformat(),
            )

            if current_state.get("response_type") == "ask":
                if current_state.get("report_meta", {}).get("is_report"):
                    conversation_storage.update_state(
                        conv_id,
                        {
                            "awaiting_clarification": True,
                            "pending_tool_auth": (
                                {
                                    "tool": current_state.get("tool_auth_type", "none"),
                                    "reason": current_state.get("tool_auth_reason", ""),
                                    "source": current_state.get("tool_auth_source", ""),
                                }
                                if bool(current_state.get("tool_auth_requested", False)) and not bool(current_state.get("tool_auth_granted", False))
                                else {}
                            ),
                            "report_state": {
                                "slots": current_state.get("report_slots", {}),
                                "missing": current_state.get("report_missing", []),
                                "awaiting": True,
                                "expected_slot": current_state.get("missing_slot", ""),
                            },
                            "slots": current_state.get("slots", {}),
                            "next_missing_slot": SlotTracker.pick_next_missing_slot(current_state.get("slots", {})),
                            "slot_confidence": current_state.get("slot_signal", {}).get("slot_confidence", {}),
                            "slot_correction_applied": bool(current_state.get("slot_signal", {}).get("correction_applied", False)),
                            "slot_correction_from": current_state.get("slot_signal", {}).get("correction_from"),
                            "slot_correction_to": current_state.get("slot_signal", {}).get("correction_to"),
                            "ask_counts": current_state.get("ask_counts", {}),
                        },
                    )
                else:
                    same_reason_count = int(conv_state.get("same_reason_clarify_count", 0))
                    clarify_reason = str(current_state.get("clarify_result", {}).get("reason") or "")
                    if clarify_reason == str(conv_state.get("last_clarification_reason") or ""):
                        same_reason_count += 1
                    else:
                        same_reason_count = 1

                    conversation_storage.update_state(
                        conv_id,
                        {
                            "awaiting_clarification": True,
                            "pending_tool_auth": (
                                {
                                    "tool": current_state.get("tool_auth_type", "none"),
                                    "reason": current_state.get("tool_auth_reason", ""),
                                    "source": current_state.get("tool_auth_source", ""),
                                }
                                if bool(current_state.get("tool_auth_requested", False)) and not bool(current_state.get("tool_auth_granted", False))
                                else {}
                            ),
                            "clarification_turns": int(conv_state.get("clarification_turns", 0)) + 1,
                            "last_clarification_reason": clarify_reason,
                            "last_follow_up_question": answer_text,
                            "last_user_question_before_clarify": question,
                            "same_reason_clarify_count": same_reason_count,
                            "anti_repeat_used": bool(current_state.get("anti_repeat_used", False)),
                            "slots": current_state.get("slots", {}),
                            "next_missing_slot": SlotTracker.pick_next_missing_slot(current_state.get("slots", {})),
                            "slot_confidence": current_state.get("slot_signal", {}).get("slot_confidence", {}),
                            "slot_correction_applied": bool(current_state.get("slot_signal", {}).get("correction_applied", False)),
                            "slot_correction_from": current_state.get("slot_signal", {}).get("correction_from"),
                            "slot_correction_to": current_state.get("slot_signal", {}).get("correction_to"),
                            "ask_counts": current_state.get("ask_counts", {}),
                        },
                    )
            else:
                conversation_storage.update_state(
                    conv_id,
                    {
                        "awaiting_clarification": False,
                        "pending_tool_auth": {},
                        "clarification_capped": False,
                        "same_reason_clarify_count": 0,
                        "anti_repeat_used": False,
                        "slots": current_state.get("slots", {}),
                        "next_missing_slot": SlotTracker.pick_next_missing_slot(current_state.get("slots", {})),
                        "slot_confidence": current_state.get("slot_signal", {}).get("slot_confidence", {}),
                        "slot_correction_applied": bool(current_state.get("slot_signal", {}).get("slot_correction_applied", False)),
                        "slot_correction_from": current_state.get("slot_signal", {}).get("slot_correction_from"),
                        "slot_correction_to": current_state.get("slot_signal", {}).get("slot_correction_to"),
                        "report_state": current_state.get("report_slots", {}),
                    },
                )

            yield {"type": "done"}

        return meta_payload, stream_answer()

    def _get_model_gateway(self, model_id: Optional[str]) -> tuple[ChatModelGateway, Dict[str, Any]]:
        model_cfg = Config.get_llm_model(model_id) if model_id else Config.get_planner_model()
        gateway = ChatModelGateway(
            api_base=str(model_cfg.get("api_base") or Config.REMOTE_MODEL_API_BASE),
            api_key=model_cfg.get("api_key") or Config.REMOTE_MODEL_API_KEY,
            model_name=str(model_cfg.get("model_name") or Config.LLM_MODEL),
        )
        return gateway, model_cfg

    @staticmethod
    def _compose_planned_question(question: str, answer_mode: str, style_hint: str) -> str:
        hint = (style_hint or "").strip()
        mode = (answer_mode or "qa").strip()
        if not hint:
            return question
        return f"{question}\n\n【回答模式】{mode}\n【表达要求】{hint}"

    def _naturalize_text(self, gateway: ChatModelGateway, draft: str, *, followup: bool = False) -> str:
        text = (draft or "").strip()
        if not text:
            return ""
        try:
            system_prompt = FOLLOWUP_REWRITE_SYSTEM_PROMPT if followup else NATURALIZER_SYSTEM_PROMPT
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ]
            out = gateway.chat(messages=messages, temperature=0.2, max_tokens=120)
            return out.strip() or text
        except Exception:
            return text

    @staticmethod
    def _strip_trailing_questions(text: str) -> str:
        return strip_trailing_questions(text)

    @staticmethod
    def _build_ask_messages(question: str, followup_question: str) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": ASK_SYSTEM_PROMPT},
            {"role": "user", "content": f"用户输入：{question}\n\n缺失信息：{followup_question}"},
        ]

    def _build_dynamic_ask_messages(
        self,
        question: str,
        *,
        missing_slot: str,
        known_info_prefix: str,
        followup_question: str,
    ) -> List[Dict[str, str]]:
        missing_label = {
            "topic": "主题",
            "objective": "教学目标",
            "audience": "受众",
        }.get(missing_slot or "", "关键信息")
        known_info_prefix = (known_info_prefix or "").strip() or "未提供"
        followup_question = (followup_question or "").strip()

        sections = self._skill_manager.extract_prompt_sections("edu-dialogue-agent")
        skill_system_prompt = sections.get("system_prompt") or ""
        skill_question_template = self._skill_manager.extract_section("edu-dialogue-agent", "CONSULTATIVE_QUESTION_TEMPLATE") or sections.get("question_template") or ""

        base_prompt = DYNAMIC_ASK_SYSTEM_PROMPT.format(
            user_input=question,
            collected_info=known_info_prefix,
            missing_info=missing_label,
        )

        if skill_system_prompt:
            base_prompt = f"{base_prompt}\n\n【Consultative技能补充】\n{skill_system_prompt}"

        if skill_question_template:
            user_content = (
                f"请按以下模板生成追问，并把占位符替换成当前语境：\n"
                f"{skill_question_template}\n\n"
                f"当前用户输入：{question}\n"
                f"已知信息：{known_info_prefix}\n"
                f"当前缺失字段：{missing_label}"
            )
        else:
            user_content = f"我的输入是：{question}。请按要求向我发起追问。"

        return [
            {"role": "system", "content": base_prompt},
            {"role": "user", "content": user_content},
        ]

    def _render_known_slots(
        self,
        gateway: ChatModelGateway,
        slots: Dict[str, str],
        next_missing_slot: Optional[str] = None,
    ) -> str:
        topic = str(slots.get("topic", "") or "").strip()
        audience = str(slots.get("audience", "") or "").strip()
        objective = str(slots.get("objective", "") or "").strip()

        if next_missing_slot == "audience" and topic:
            draft = f"已知主题：{topic}。"
            return self._naturalize_text(gateway, draft)
        if next_missing_slot == "objective" and topic:
            draft = f"已知主题：{topic}，缺少目标。"
            return self._naturalize_text(gateway, draft)
        if next_missing_slot == "topic" and (audience or objective):
            draft = f"已知受众：{audience or '未提供'}；已知目标：{objective or '未提供'}；缺少主题。"
            return self._naturalize_text(gateway, draft)

        pairs: List[str] = []
        if topic:
            pairs.append(f"主题={topic}")
        if audience:
            pairs.append(f"受众={audience}")
        if objective:
            pairs.append(f"目标={objective}")
        if not pairs:
            return ""
        return self._naturalize_text(gateway, "；".join(pairs))

    def _render_slot_confirmation(self, gateway: ChatModelGateway, slots: Dict[str, str]) -> str:
        all_filled = all(str(slots.get(k, "") or "").strip() for k in SLOT_KEYS)
        if not all_filled:
            return ""
        topic = str(slots.get("topic", "") or "").strip()
        audience = str(slots.get("audience", "") or "").strip()
        objective = str(slots.get("objective", "") or "").strip()
        draft = f"请确认：主题={topic}；受众={audience}；目标={objective}。若无偏差就继续回答。"
        return self._naturalize_text(gateway, draft)

    def _is_complete_requirement(self, slots: Dict[str, str], question: str) -> bool:
        topic_filled = bool(str(slots.get("topic", "") or "").strip())
        objective_filled = bool(str(slots.get("objective", "") or "").strip())
        if topic_filled and objective_filled:
            return True

        # 兜底：当问题本身已包含“做什么+达到什么”的表达，也视为完整需求
        text = (question or "").strip()
        has_topic_like = len(text) >= 6 and any(k in text for k in ["关于", "讲", "解释", "介绍", "分析", "复习"])
        has_objective_like = any(k in text for k in ["理解", "掌握", "学会", "入门", "对比", "梳理", "应用"])
        return has_topic_like and has_objective_like

    def _enforce_single_slot_followup(
        self,
        *,
        followup: str,
        next_missing_slot: Optional[str],
        prefix: str = "",
    ) -> str:
        slot = (next_missing_slot or "").strip()
        canonical = self._SINGLE_SLOT_QUESTION.get(slot, "你可以补充一个关键信息吗？")

        f = (followup or "").strip()
        p = (prefix or "").strip()

        # 清掉多问号与多重问句，强制只留一个槽位问题
        f = re.sub(r"[？?]{2,}", "？", f)
        question_parts = [s.strip() for s in re.split(r"[？?]", f) if s.strip()]

        one_question = canonical
        for part in question_parts:
            if slot == "topic" and any(k in part for k in ["主题", "知识点", "讲什么"]):
                one_question = f"{part}？"
                break
            if slot == "objective" and any(k in part for k in ["目标", "达到", "学会", "掌握"]):
                one_question = f"{part}？"
                break
            if slot == "audience" and any(k in part for k in ["受众", "年级", "学生", "面向"]):
                one_question = f"{part}？"
                break

        # 避免跟 prefix 语义重复
        if p and one_question in p:
            one_question = canonical

        if p:
            return smooth_followup_transition(p, one_question)
        return one_question

    def _postprocess_followup(self, text: str, *, missing_slot: str, known_info_prefix: str) -> str:
        output = (text or "").strip()
        prefix = (known_info_prefix or "").strip()
        slot = (missing_slot or "").strip()
        if not output:
            return self._enforce_single_slot_followup(
                followup=self._SINGLE_SLOT_QUESTION.get(slot, "你可以补充一个关键信息吗？"),
                next_missing_slot=slot or None,
                prefix=prefix,
            )

        output = re.sub(r"[？?]{2,}", "？", output)
        parts = [p.strip() for p in re.split(r"[？?]", output) if p.strip()]

        if parts:
            preferred = None
            keyword_map = {
                "topic": ["主题", "知识点", "讲什么"],
                "objective": ["目标", "达到", "学会", "掌握"],
                "audience": ["受众", "年级", "学生", "面向"],
            }
            for part in parts:
                if slot and any(k in part for k in keyword_map.get(slot, [])):
                    preferred = part
                    break
            if not preferred:
                preferred = parts[0]
            output = f"{preferred}？"

        output = self._enforce_single_slot_followup(
            followup=output,
            next_missing_slot=slot or None,
            prefix=prefix,
        )
        return output

    @staticmethod
    def _smooth_followup_transition(prefix: str, followup: str) -> str:
        return smooth_followup_transition(prefix, followup)

    def _pick_non_repeating_followup(self, *, reason: str, suggested: str, conv_state: Dict[str, Any]) -> tuple[str, bool]:
        last_reason = str(conv_state.get("last_clarification_reason") or "")
        last_follow_up = str(conv_state.get("last_follow_up_question") or "")
        consecutive_count = int(conv_state.get("same_reason_clarify_count", 0))

        if reason == last_reason:
            consecutive_count += 1
        else:
            consecutive_count = 1

        candidates = self._REASON_FOLLOWUPS.get(reason) or self._REASON_FOLLOWUPS.get("insufficient_context", [])
        if not candidates:
            return (suggested.strip() or "为了更准确帮助你，请再补充一点具体背景。"), False

        idx = min(max(consecutive_count - 1, 0), len(candidates) - 1)
        fallback_text = candidates[idx]

        answer = suggested.strip() or fallback_text
        anti_repeat_used = False

        if answer == last_follow_up:
            anti_repeat_used = True
            alt_idx = (idx + 1) % len(candidates)
            answer = candidates[alt_idx]
            if answer == last_follow_up and len(candidates) > 2:
                answer = candidates[(alt_idx + 1) % len(candidates)]

        return answer, anti_repeat_used

    @staticmethod
    def skill_health_check(meta: Dict[str, Any]) -> Dict[str, Any]:
        m = dict(meta or {})
        node_skill_map = dict((m.get("meta") or {}).get("node_skill_map") or {})
        audit = dict((m.get("meta") or {}).get("audit") or {})
        mm = dict(m.get("meta") or {})

        expected_nodes = ["router", "chat", "extractor", "outline", "generate"]
        base_score = 100.0
        penalties: List[Dict[str, Any]] = []

        for node in expected_nodes:
            skills = node_skill_map.get(node)
            if not isinstance(skills, list) or not skills:
                base_score -= 10
                penalties.append({"node": node, "reason": "missing_node_skill_map", "deduct": 10})

        for node, entry in audit.items():
            if not isinstance(entry, dict):
                base_score -= 5
                penalties.append({"node": node, "reason": "invalid_audit_entry", "deduct": 5})
                continue
            if not entry.get("route_source"):
                base_score -= 6
                penalties.append({"node": node, "reason": "missing_route_source", "deduct": 6})
            if "override_applied" not in entry:
                base_score -= 6
                penalties.append({"node": node, "reason": "missing_override_applied", "deduct": 6})
            if not str(entry.get("reason") or "").strip():
                base_score -= 4
                penalties.append({"node": node, "reason": "missing_reason", "deduct": 4})

        if "router" not in audit:
            base_score -= 15
            penalties.append({"node": "router", "reason": "router_audit_missing", "deduct": 15})

        skill_used = str(mm.get("skill_used") or "").strip()
        next_action = str(mm.get("next_action") or "").strip()
        needs_more_context = mm.get("needs_more_context")

        if not skill_used:
            base_score -= 8
            penalties.append({"node": "chat", "reason": "missing_skill_used", "deduct": 8})
        if next_action not in {"direct_answer", "ask_user", "request_tool_auth"}:
            base_score -= 8
            penalties.append({"node": "chat", "reason": "invalid_next_action", "deduct": 8})
        if not isinstance(needs_more_context, bool):
            base_score -= 6
            penalties.append({"node": "chat", "reason": "invalid_needs_more_context", "deduct": 6})

        final_score = max(0.0, min(100.0, round(base_score, 2)))
        if final_score >= 90:
            grade = "A"
        elif final_score >= 75:
            grade = "B"
        elif final_score >= 60:
            grade = "C"
        else:
            grade = "D"

        summary = f"技能健康评分 {final_score}（{grade}），扣分项 {len(penalties)} 个。"

        return {
            "score": final_score,
            "grade": grade,
            "summary": summary,
            "details": {
                "expected_nodes": expected_nodes,
                "node_skill_map_nodes": sorted(node_skill_map.keys()),
                "audit_nodes": sorted(audit.keys()),
                "penalties": penalties,
            },
        }

    def chat(
        self,
        *,
        question: str,
        conversation_id: Optional[str],
        model_id: Optional[str],
        use_rag: bool = False,
        selected_doc_ids: Optional[List[str]] = None,
        owner: Optional[str] = None,
        course_id: Optional[str] = None,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        meta_payload, stream = self.chat_stream_with_meta(
            question=question,
            conversation_id=conversation_id,
            model_id=model_id,
            use_rag=use_rag,
            selected_doc_ids=selected_doc_ids,
            owner=owner,
            course_id=course_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

        answer_chunks: List[str] = []
        for event in stream:
            if not isinstance(event, dict):
                continue
            if event.get("type") == "delta":
                answer_chunks.append(str(event.get("delta") or ""))

        meta_payload["answer"] = "".join(answer_chunks).strip()
        return meta_payload
