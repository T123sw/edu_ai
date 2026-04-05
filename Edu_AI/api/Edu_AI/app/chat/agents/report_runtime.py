from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from ..graph_state import GraphState
from ..report_domain import REPORT_DEFAULTS, REPORT_SLOT_KEYS, ExtractedIntent
from ..slot_tracker import SLOT_KEYS, SlotTracker
from ..utils.json_utils import extract_json_block, read_report_schema
from ..utils.prompt_utils import render_prompt_template


def ask_node_impl(host: Any, state: GraphState) -> GraphState:
    host._record_node_skills(state=state, node_name="ask", base_prompt="你是追问节点，请仅提出一个最高价值的补充问题。")
    if state.get("report_meta", {}).get("is_report"):
        raw_missing = state.get("report_missing") or []
        first_missing = raw_missing[0] if raw_missing else None
        if isinstance(first_missing, dict):
            missing_slot = str(first_missing.get("slot_name") or "").strip() or None
        elif isinstance(first_missing, str):
            missing_slot = first_missing.strip() or None
        else:
            missing_slot = None

        known_info_prefix = host._render_report_known(state.get("report_slots", {}))
        soft_params_confirmed = bool(state.get("soft_params_confirmed", False))

        if not missing_slot and not soft_params_confirmed:
            missing_slot = "soft_confirm"

        state["anti_repeat_used"] = False
        state["missing_slot"] = missing_slot or ""
        state["known_info_prefix"] = known_info_prefix
        state["followup_question"] = ""
        state["messages"] = host._build_report_ask_messages(
            state["question"],
            missing_slot=missing_slot or "core_topic",
            known_info_prefix=known_info_prefix,
        )
        host._log_agent_process(
            "ask",
            plan=("根据缺失槽位生成追问。" f"缺失字段：{missing_slot or '无'}"),
            reflection=("已保留历史槽位并回显已知信息。" "追问仅聚焦一个字段，避免重新覆盖已有主题。"),
            next_step="等待用户回复并进入 extractor。",
        )
        return state

    missing_slot = SlotTracker.pick_next_missing_slot(state["slots"])
    known_info_prefix = host._render_known_slots(state["gateway"], state["slots"], missing_slot)

    missing_info = state.get("missing_info", [])
    if missing_info:
        missing_slot = "objective" if "教学目标" in missing_info else missing_slot
        missing_slot = "audience" if "目标受众/年级" in missing_info else missing_slot

    state["anti_repeat_used"] = False
    state["missing_slot"] = missing_slot
    state["known_info_prefix"] = known_info_prefix
    state["followup_question"] = ""
    state["messages"] = host._build_dynamic_ask_messages(
        state["question"],
        missing_slot=missing_slot,
        known_info_prefix=known_info_prefix,
        followup_question="",
    )
    return state


def outline_node_impl(host: Any, state: GraphState) -> GraphState:
    host._record_node_skills(state=state, node_name="outline", base_prompt="你是报告大纲节点，请输出结构清晰、可执行的大纲。")
    outline_t0 = time.perf_counter()
    if state.get("report_meta", {}).get("is_report"):
        report_slots = state.get("report_slots", {})
        prev_outline = host._normalize_outline_ast(state.get("report_outline") or [])
        user_intent = str(state.get("report_meta", {}).get("user_intent") or "").strip()

        llm = host._get_fallback_llm()
        outline: List[Dict[str, Any]] = []
        is_modification = bool(prev_outline) and user_intent == "modify_outline"
        state["outline_override_applied"] = bool(is_modification)
        state["outline_source"] = "llm_patch" if is_modification else "llm_ast"
        state["outline_reason"] = "modify_existing_outline" if is_modification else "build_initial_outline"

        outline_ast_prompt = host._skill_manager.extract_section("edu-report-agent", "REPORT_OUTLINE_AST_PROMPT")
        patch_prompt = host._skill_manager.extract_section("edu-report-agent", "OUTLINE_PATCH_PROMPT")

        outline_parse_success = False
        patch_ops_count = 0
        patch_hit_count = 0
        patch_actions: List[str] = []
        clarification_needed = False

        if llm and is_modification:
            prompt = patch_prompt or "请根据用户要求对当前大纲进行局部 patch 修改并返回 JSON。"
            user_payload = f"current_outline_ast={json.dumps(prev_outline, ensure_ascii=False)}\n" f"user_request={state.get('question') or ''}"
            response = llm.invoke([
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_payload},
            ])
            raw = str(getattr(response, "content", "") or "").strip()
            patch_json = extract_json_block(raw)

            ask_clarification = bool((patch_json or {}).get("ask_clarification")) if isinstance(patch_json, dict) else False
            if ask_clarification:
                clarification_needed = True
                state["response_type"] = "ask"
                state["report_missing"] = [{"slot_name": "outline_target", "reason": "请明确要修改的章节/小节编号（如2或2.1）"}]
                state["report_reflection"] = {
                    "outline_review": {"enabled": False, "skipped_reason": "patch_need_clarification"},
                    "outline_modify": {
                        "mode": "patch",
                        "patch_ops_count": 0,
                        "patch_hit_count": 0,
                        "outline_modify_hit_rate": 0.0,
                        "clarification_needed": True,
                        "actions": [],
                    },
                }
                return state

            mods = patch_json.get("modifications") if isinstance(patch_json, dict) else []
            patch_ops_count = len(mods) if isinstance(mods, list) else 0
            if isinstance(mods, list):
                patch_actions = [str(op.get("action") or "") for op in mods if isinstance(op, dict)]
            modified_outline, change_log = host._apply_outline_patch(prev_outline, mods)
            patch_hit_count = len(change_log)
            outline = modified_outline if modified_outline else prev_outline
            outline_parse_success = bool(outline)

            feedback_tpl = host._skill_manager.extract_section("edu-report-agent", "OUTLINE_MODIFY_FEEDBACK_TEMPLATE")
            if feedback_tpl:
                change_summary = "；".join(change_log[:4]) if change_log else "已按你的意见完成局部调整"
                rationale = "调整聚焦指定节点，提升结构连贯性与论证路径清晰度"
                state["final_answer"] = feedback_tpl.format(change_summary=change_summary, rationale=rationale)
        else:
            scale_hint = host._outline_scale_hint(report_slots.get("length_requirement") or REPORT_DEFAULTS["length_requirement"])
            if llm:
                prompt = render_prompt_template(
                    outline_ast_prompt or "请按 AST JSON 生成报告大纲。",
                    {
                        "report_slots": json.dumps(report_slots, ensure_ascii=False),
                        "dynamic_constraints": report_slots.get("dynamic_constraints") or "{}",
                    },
                )
                prompt = (
                    f"{prompt}\n\n"
                    "【结构规模目标】\n"
                    f"长度档位：{scale_hint.get('label')}；"
                    f"章节建议：{scale_hint.get('chapter_min')}-{scale_hint.get('chapter_max')}章；"
                    f"每章小节建议：{scale_hint.get('sections_min')}-{scale_hint.get('sections_max')}节。\n"
                    "请在不牺牲逻辑完整性的前提下，尽量贴近该规模。"
                )
                response = llm.invoke([
                    {"role": "system", "content": "你是报告大纲生成器。"},
                    {"role": "user", "content": prompt},
                ])
                raw = str(getattr(response, "content", "") or "").strip()
                parsed_outline = extract_json_block(raw)
                outline = host._normalize_outline_ast(parsed_outline)
                outline_parse_success = bool(outline)

                ch_cnt, sec_cnt = host._ast_outline_stats(outline)
                min_ch = int(scale_hint.get("chapter_min") or 0)
                max_ch = int(scale_hint.get("chapter_max") or 99)
                min_sec = int(scale_hint.get("sections_min") or 0)
                max_sec = int(scale_hint.get("sections_max") or 99)
                avg_sec = (float(sec_cnt) / float(ch_cnt)) if ch_cnt > 0 else 0.0
                severe_mismatch = ch_cnt > 0 and (ch_cnt < min_ch - 1 or ch_cnt > max_ch + 1 or avg_sec < max(1.0, min_sec - 1) or avg_sec > (max_sec + 1))
                if severe_mismatch:
                    reprompt = (
                        f"{prompt}\n\n"
                        "【纠偏重生成（一次）】\n"
                        f"你上一次输出规模偏离目标：当前{ch_cnt}章，平均每章{avg_sec:.2f}节。"
                        f"请重生为{min_ch}-{max_ch}章、每章约{min_sec}-{max_sec}节，"
                        "并继续保持主题聚焦与结构完整。只输出 AST JSON。"
                    )
                    response2 = llm.invoke([
                        {"role": "system", "content": "你是报告大纲生成器。"},
                        {"role": "user", "content": reprompt},
                    ])
                    raw2 = str(getattr(response2, "content", "") or "").strip()
                    parsed2 = extract_json_block(raw2)
                    outline2 = host._normalize_outline_ast(parsed2)
                    if outline2:
                        outline = outline2
                        outline_parse_success = True

            if not outline:
                outline = host._normalize_outline_ast(prev_outline)

        state["report_outline"] = host._normalize_outline_ast(outline)
        state["report_outline_pending"] = True
        outline_modify_hit_rate = float(patch_hit_count) / float(patch_ops_count) if patch_ops_count > 0 else (1.0 if is_modification and patch_hit_count > 0 else 0.0)
        final_ch_cnt, final_sec_cnt = host._ast_outline_stats(state["report_outline"])
        state["report_reflection"] = {
            "outline_review": {"enabled": False, "skipped_reason": "phase_b_llm_first_ast_with_schema_normalize"},
            "outline_build": {
                "mode": "patch" if is_modification else "ast_generate",
                "outline_ast_parse_success": bool(outline_parse_success),
                "outline_source": state.get("outline_source", ""),
                "outline_reason": state.get("outline_reason", ""),
                "outline_override_applied": bool(state.get("outline_override_applied", False)),
                "length_scale_hint": host._outline_scale_hint(report_slots.get("length_requirement") or REPORT_DEFAULTS["length_requirement"]),
                "final_chapter_count": int(final_ch_cnt),
                "final_section_count": int(final_sec_cnt),
            },
            "outline_modify": {
                "mode": "patch" if is_modification else "none",
                "patch_ops_count": int(patch_ops_count),
                "patch_hit_count": int(patch_hit_count),
                "outline_modify_hit_rate": float(round(outline_modify_hit_rate, 4)),
                "clarification_needed": bool(clarification_needed),
                "actions": patch_actions[:10],
            },
        }

        chapter_count = len(state["report_outline"])
        section_count = sum(len(ch.get("sections") or []) for ch in state["report_outline"] if isinstance(ch, dict))
        print(f"大纲阶段 行动：已生成/更新 AST 大纲，章节数={chapter_count}，小节数={section_count}")
        print(f"大纲阶段 思考：耗时 {time.perf_counter() - outline_t0:.3f} 秒")
    else:
        print(f"大纲阶段 思考：非报告请求，跳过大纲生成，耗时 {time.perf_counter() - outline_t0:.3f} 秒")
    return state


def generate_node_impl(host: Any, state: GraphState) -> GraphState:
    host._record_node_skills(state=state, node_name="generate", base_prompt="你是报告生成节点，请严格按大纲输出正文。")
    generate_t0 = time.perf_counter()
    if state.get("report_meta", {}).get("is_report"):
        report_slots = state.get("report_slots", {})
        state["generate_override_applied"] = bool(state.get("report_auto_fill"))
        state["generate_source"] = "override" if state.get("report_auto_fill") else "llm"
        state["generate_reason"] = "report_auto_fill" if state.get("report_auto_fill") else "normal_generate"
        if state.get("report_auto_fill"):
            report_slots = host._auto_fill_report_slots(report_slots)
        state["report_slots"] = report_slots

        host._log_agent_process(
            "generate",
            plan=f"基于最终槽位分章生成报告。槽位：{host._render_report_known(report_slots) or '无'}",
            reflection=("生成前已完成兜底并保留历史槽位。" "将按章节循环生成并保持上下文衔接。"),
            next_step="调用 LLM 分章生成最终报告内容。",
        )

        content, checkpoint = host._build_report_markdown(report_slots, state.get("report_outline"))

        state["report_content"] = content
        state["report_ready"] = True
        state["report_outline_pending"] = False
        state["report_checkpoint"] = checkpoint
        state["report_reflection"] = {
            **(state.get("report_reflection") or {}),
            "generate": {
                "mode": "chapter_loop",
                "chapter_count": int(checkpoint.get("chapter_count", 0)),
                "completed_chapters": int(checkpoint.get("completed_chapters", 0)),
                "retry_count": int(checkpoint.get("retry_count", 0)),
                "failed_chapters": checkpoint.get("failed_chapters", []),
            },
        }
        print(
            "正文阶段 行动：已完成正文生成，"
            f"章节={checkpoint.get('completed_chapters', 0)}/{checkpoint.get('chapter_count', 0)}，"
            f"重试={checkpoint.get('retry_count', 0)}，"
            f"耗时 {time.perf_counter() - generate_t0:.3f} 秒"
        )

        return state

    state["messages"] = []
    print(f"正文阶段 思考：非报告请求，跳过正文生成，耗时 {time.perf_counter() - generate_t0:.3f} 秒")
    return state


def extractor_node_impl(
    host: Any,
    state: GraphState,
    *,
    extractor_system_prompt: str,
    report_slot_schema: str,
) -> GraphState:
    conv_state_local = state.get("conv_state", {})
    prev_slots = conv_state_local.get("slots") if isinstance(conv_state_local.get("slots"), dict) else {}
    expected_slot = str(conv_state_local.get("next_missing_slot") or "") or None

    report_state = conv_state_local.get("report_state") or {}
    prev_report_slots = host._init_report_slots(report_state.get("slots"))
    prev_report_outline = list(report_state.get("outline") or [])
    prev_outline_pending = bool(report_state.get("outline_pending"))

    state["extractor_override_applied"] = bool(prev_outline_pending)
    state["extractor_source"] = "override" if prev_outline_pending else "llm"
    state["extractor_reason"] = "outline_confirm_intent" if prev_outline_pending else "slot_extraction"

    messages: List[Any] = []
    for msg in state.get("history", []):
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user" and content:
            messages.append(HumanMessage(content=content))
        elif role == "assistant" and content:
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=state["question"]))

    extractor_prompt = ChatPromptTemplate.from_messages([
        ("system", extractor_system_prompt),
        ("placeholder", "{messages}"),
    ])

    planner_llm = state.get("llm")
    deep_llm = state.get("llm_deep") or planner_llm
    extracted_slots: Dict[str, str] = {k: "" for k in SLOT_KEYS}
    report_extracted_dict: Dict[str, str] = {k: "" for k in REPORT_SLOT_KEYS}
    is_report_mode = bool(state.get("report_meta", {}).get("is_report"))
    llm = deep_llm if is_report_mode else planner_llm

    if is_report_mode:
        ask_counts = dict(report_state.get("ask_counts", {}))
        ask_count = int(sum(int(v or 0) for v in ask_counts.values()))
        current_known = json.dumps(prev_report_slots, ensure_ascii=False)

        parsed: Dict[str, Any] = {}
        if llm:
            try:
                extractor_prompt_text = render_prompt_template(
                    extractor_system_prompt,
                    {
                        "current_slots": current_known,
                        "ask_count": ask_count,
                        "user_input": state.get("question") or "",
                    },
                )
                resp = llm.invoke([
                    {"role": "system", "content": extractor_prompt_text},
                    {"role": "user", "content": str(state.get("question") or "")},
                ])
                parsed = extract_json_block(str(getattr(resp, "content", "") or "")) or {}
            except Exception as exc:
                print(f"提取阶段 异常：{exc}")
                parsed = {}

        user_intent = str(parsed.get("user_intent") or "provide").strip().lower() or "provide"
        if user_intent in {"confirm", "confirm_outline", "agree", "accept"}:
            state["soft_params_confirmed"] = True
            user_intent = "confirm_outline"
        state["report_meta"] = {**state.get("report_meta", {}), "user_intent": user_intent}

        extracted_missing = parsed.get("report_missing") or []
        state["report_missing"] = extracted_missing if isinstance(extracted_missing, list) else []

        slots_obj = parsed.get("report_slots") if isinstance(parsed.get("report_slots"), dict) else {}
        for k in ["core_topic", "focus_area", "length_requirement", "depth_level", "format_style"]:
            v = str(slots_obj.get(k) or "").strip()
            if v:
                report_extracted_dict[k] = v

        dyn = parsed.get("dynamic_constraints")
        if isinstance(dyn, dict) and dyn:
            report_extracted_dict["dynamic_constraints"] = json.dumps(dyn, ensure_ascii=False)

        if user_intent == "force_generate" and not str(prev_report_slots.get("core_topic") or "").strip():
            q_text = str(state.get("question") or "").strip()
            if not report_extracted_dict.get("core_topic"):
                schema_defaults = read_report_schema(report_slot_schema).get("defaults", {})
                fallback_core = str(schema_defaults.get("core_topic") or REPORT_DEFAULTS["core_topic"]).strip()
                report_extracted_dict["core_topic"] = q_text or fallback_core

        merged_report_slots = host._merge_report_slots(prev_report_slots, report_extracted_dict)

        state["report_slots"] = merged_report_slots
        state["report_ask_counts"] = dict(report_state.get("ask_counts", {}))
        state["report_auto_fill"] = False
        state["report_ready"] = False
        state["report_content"] = ""
        state["report_outline"] = prev_report_outline if prev_outline_pending else []
        state["report_outline_pending"] = prev_outline_pending

        host._log_agent_process(
            "extractor",
            plan=f"V5.1 提取：当前已知：{host._render_report_known(prev_report_slots) or '无'}",
            reflection=f"解析结果：{json.dumps(parsed, ensure_ascii=False)}",
            next_step="提取槽位与 missing 交给 evaluator",
        )
        return state

    if llm:
        try:
            extractor_chain = extractor_prompt | llm.with_structured_output(ExtractedIntent)
            extracted_data = extractor_chain.invoke({"messages": messages})
            if extracted_data.teaching_target:
                extracted_slots["objective"] = extracted_data.teaching_target
            if extracted_data.target_audience:
                extracted_slots["audience"] = extracted_data.target_audience
        except Exception:
            pass

    obvious_slot, _, _ = SlotTracker._detect_obvious_slot(state["question"])
    if obvious_slot == "topic" and not str(extracted_slots.get("topic", "") or "").strip():
        extracted_slots["topic"] = state["question"].strip()

    merged_slots = SlotTracker.merge_slots(prev_slots, extracted_slots)
    state["slots"] = merged_slots
    state["expected_slot"] = expected_slot
    state["slot_signal"] = {
        "slot_confidence": {k: 0.72 if merged_slots.get(k) else 0.0 for k in SLOT_KEYS},
        "filled_slot": next((k for k in SLOT_KEYS if merged_slots.get(k)), ""),
        "expected_slot": expected_slot,
        "correction_applied": False,
        "correction_from": expected_slot or "",
        "correction_to": "",
    }
    return state


def evaluator_node_impl(host: Any, state: GraphState, *, max_clarification_turns: int) -> GraphState:
    missing_info: List[str] = []
    ask_counts = dict(state.get("ask_counts", {}))

    teaching_target = str(state.get("slots", {}).get("objective") or "").strip()
    target_audience = str(state.get("slots", {}).get("audience") or "").strip()

    if not teaching_target:
        if ask_counts.get("teaching_target", 0) < 2:
            missing_info.append("教学目标")
            ask_counts["teaching_target"] = ask_counts.get("teaching_target", 0) + 1
        else:
            teaching_target = "全面掌握当前主题的核心概念与基础知识"

    if not target_audience:
        if ask_counts.get("target_audience", 0) < 2:
            missing_info.append("目标受众/年级")
            ask_counts["target_audience"] = ask_counts.get("target_audience", 0) + 1
        else:
            target_audience = "各年级通用/普通学习者"

    consult_sections = host._skill_manager.extract_prompt_sections("edu-dialogue-agent")
    consult_fallback_template = (
        host._skill_manager.extract_section("edu-dialogue-agent", "CONSULTATIVE_FALLBACK_AFTER_2_TURNS_TEMPLATE")
        or str(consult_sections.get("fallback_after_2_turns_template") or "")
    ).strip()
    if not missing_info and consult_fallback_template:
        capped = int(ask_counts.get("teaching_target", 0)) >= max_clarification_turns or int(ask_counts.get("target_audience", 0)) >= max_clarification_turns
        if capped and state.get("response_type") != "generate":
            state["final_answer"] = consult_fallback_template
            state["skip_chat_llm"] = True
            state["response_type"] = "chat"
            state["next_action"] = "direct_answer"
            state["needs_more_context"] = True
            state["degraded"] = True

    if teaching_target:
        state["slots"]["objective"] = teaching_target
    if target_audience:
        state["slots"]["audience"] = target_audience

    report_slots = state.get("report_slots", {})
    report_missing: List[Any] = []
    report_ask_counts = dict(state.get("report_ask_counts", {}))
    report_auto_fill = False
    report_outline = list(state.get("report_outline") or [])
    report_outline_pending = bool(state.get("report_outline_pending"))
    soft_params_confirmed = bool(state.get("soft_params_confirmed", False))

    report_meta = state.get("report_meta", {})
    if report_meta.get("is_report"):
        user_intent = str(report_meta.get("user_intent") or "provide").strip().lower()
        report_slots = state.get("report_slots", {})
        report_ask_counts = dict(state.get("report_ask_counts", {}))
        report_auto_fill = False
        report_outline = list(state.get("report_outline") or [])
        report_outline_pending = bool(state.get("report_outline_pending"))
        soft_params_confirmed = bool(state.get("soft_params_confirmed", False))

        extractor_missing_raw = state.get("report_missing") or []
        report_missing = []

        current_core = str(report_slots.get("core_topic") or "").strip()
        current_focus = str(report_slots.get("focus_area") or "").strip()
        current_dynamic = str(report_slots.get("dynamic_constraints") or "").strip()

        def _has_dynamic_candidate(v: str) -> bool:
            t = str(v or "").strip()
            if not t or t == "{}":
                return False
            if "candidate" in t:
                return True
            try:
                obj = json.loads(t)
                if isinstance(obj, dict) and obj.get("candidate"):
                    return True
            except Exception:
                pass
            return False

        if isinstance(extractor_missing_raw, list):
            for m in extractor_missing_raw:
                slot_name = ""
                reason = ""
                if isinstance(m, dict) and m.get("slot_name"):
                    slot_name = str(m.get("slot_name")).strip()
                    reason = str(m.get("reason", "")).strip()
                elif isinstance(m, str) and m.strip():
                    slot_name = m.strip()
                    reason = "需要补充核心信息"

                if not slot_name:
                    continue

                if slot_name in {"length_requirement", "depth_level", "format_style", "soft_confirm"}:
                    continue

                if slot_name == "core_topic" and len(current_core) > 0:
                    continue
                if slot_name == "focus_area" and len(current_focus) > 2:
                    focus_too_broad = any(k in reason for k in ["宽泛", "维度", "聚焦", "细化", "具体"])
                    dynamic_not_confirmed = (not current_dynamic) or (current_dynamic == "{}") or _has_dynamic_candidate(current_dynamic)
                    if focus_too_broad and dynamic_not_confirmed:
                        if not any(str(x.get("slot_name") or "") == "dynamic_constraints" for x in report_missing if isinstance(x, dict)):
                            report_missing.append({"slot_name": "dynamic_constraints", "reason": reason or "聚焦范围仍偏宽，请补充一个具体分析维度/限制条件"})
                    continue

                report_missing.append({"slot_name": slot_name, "reason": reason})

        q_text = str(state.get("question") or "").strip()
        if user_intent == "force_generate" or host._is_impatient(q_text):
            user_intent = "force_generate"
            report_missing = []
            soft_params_confirmed = True
            report_auto_fill = True
            state["report_meta"]["user_intent"] = "force_generate"

        if any(str(report_slots.get(k) or "").strip() for k in ["length_requirement", "depth_level", "format_style"]):
            soft_params_confirmed = True

        dynamic_ask_round = int(report_ask_counts.get("dynamic_constraints", 0))
        dynamic_not_confirmed = (not current_dynamic) or (current_dynamic == "{}") or _has_dynamic_candidate(current_dynamic)
        if dynamic_not_confirmed and dynamic_ask_round < 2:
            if not any(str(x.get("slot_name") or "") == "dynamic_constraints" for x in report_missing if isinstance(x, dict)):
                report_missing.insert(0, {"slot_name": "dynamic_constraints", "reason": "请补充一个更具体的分析维度（如性格演变/象征意义/文化影响中的一个）"})

        if report_outline_pending:
            response_type = "generate" if user_intent in {"confirm_outline", "force_generate"} else "outline"
        else:
            if user_intent == "force_generate":
                response_type = "outline"
                report_outline_pending = True
            elif report_missing:
                total_asks = sum(int(v) for v in report_ask_counts.values())
                if total_asks >= 3:
                    report_missing = []
                    response_type = "outline"
                    report_outline_pending = True
                    report_auto_fill = True
                else:
                    response_type = "ask"
                    missing_slot_name = report_missing[0].get("slot_name")
                    report_ask_counts[missing_slot_name] = report_ask_counts.get(missing_slot_name, 0) + 1
            elif not soft_params_confirmed:
                response_type = "ask"
                report_missing = [{"slot_name": "soft_confirm", "reason": "必填已满，发起一次性软确认"}]
                state["report_missing"] = report_missing
            else:
                response_type = "outline"
                report_outline_pending = True

        host._log_agent_process(
            "evaluator",
            plan=f"过滤幻觉与倒车后的路由决策。当前槽位：{host._render_report_known(report_slots) or '无'}",
            reflection=(f"最终采纳缺失项：{report_missing or '无'}，" f"意图：{user_intent}，软确认：{soft_params_confirmed}"),
            next_step=f"决议：进入 {response_type}",
        )

        state["response_type"] = response_type
        state["report_slots"] = report_slots
        state["report_missing"] = report_missing
        state["report_ask_counts"] = report_ask_counts
        state["report_auto_fill"] = report_auto_fill
        state["report_outline"] = report_outline
        state["report_outline_pending"] = report_outline_pending
        state["soft_params_confirmed"] = soft_params_confirmed
        state["report_ready"] = not bool(report_missing) and soft_params_confirmed
        return state

    state["report_slots"] = report_slots
    state["report_missing"] = report_missing
    state["report_ask_counts"] = report_ask_counts
    state["report_auto_fill"] = report_auto_fill
    state["report_outline"] = report_outline
    state["report_outline_pending"] = report_outline_pending
    state["soft_params_confirmed"] = soft_params_confirmed
    state["report_ready"] = bool(state.get("report_meta", {}).get("is_report")) and not report_missing

    state["missing_info"] = missing_info
    state["ask_counts"] = ask_counts

    if state.get("report_meta", {}).get("is_report"):
        state["response_type"] = state.get("response_type") or "ask"
    else:
        state["response_type"] = "ask" if missing_info else "generate"
    return state
