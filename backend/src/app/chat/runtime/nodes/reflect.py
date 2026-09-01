from __future__ import annotations

from langgraph.config import get_stream_writer

from app.chat.runtime.graph.state import AgentState
from app.chat.runtime.reflection.base import ReflectVerdict
from app.chat.runtime.reflection.rules import ReflectorPipeline, _VERDICT_PRIORITY


def reflect_node(state: AgentState) -> dict:
    writer = get_stream_writer()

    last_tool_results = state.get("last_tool_results") or []
    if not last_tool_results:
        return {"reflect_verdict": "pass", "reflect_hint": "", "reflect_filtered": {}}

    pipeline = _build_pipeline()

    # Phase 6-A.2: expose owner / course_id to VisionReflector (for sidecar
    # attribution when it downloads images locally). Read-only injection into
    # the in-memory state dict — not persisted to checkpoint.
    try:
        from langgraph.config import get_config as _get_config
        _rt = _get_config()["configurable"]["runtime"]
        _request = _rt.get("request")
        state["_owner"] = getattr(_request, "owner", None)
        state["_course_id"] = getattr(_request, "course_id", None)
    except Exception:
        pass

    plan_step_index = state.get("plan_step_index") or 0
    current_plan = state.get("current_plan")

    step_constraints: dict = {}
    current_step: dict = {}
    if current_plan:
        steps = current_plan.get("steps", [])
        if 0 <= plan_step_index < len(steps):
            current_step = dict(steps[plan_step_index] or {})
            step_constraints = current_step.get("constraints", {})

    plan_gc: dict = (current_plan or {}).get("global_constraints", {})
    max_per_step: int = plan_gc.get("max_retries_per_step", 2)
    max_total: int = plan_gc.get("max_total_reflect_retries", 4)

    new_retry_counts = dict(state.get("retry_counts") or {})

    worst_verdict = "pass"
    combined_hint = ""
    combined_filtered: dict = {}
    new_visual_assets: list[dict] = []

    for item in last_tool_results:
        tool_name = item.get("tool_name", "")
        raw_result = item.get("raw_result", {})
        key = f"step_{plan_step_index}:{tool_name}"

        failure_verdict = _execution_failure_verdict(tool_name, raw_result, current_step)
        verdicts = [failure_verdict] if failure_verdict else pipeline.evaluate_all(
            tool_name, raw_result, state, step_constraints
        )

        # Phase 6-A: harvest image_search filtered images for downstream report injection.
        # Source order of preference:
        #   1. VisionReflector filtered_data["images"] (VLM-approved subset)
        #   2. raw payload images (when no VLM review ran but tool returned ok)
        if tool_name == "image_search" and raw_result.get("ok"):
            harvested: list[dict] = []
            for v in verdicts:
                vlm_filtered = v.filtered_data.get("images") if v.filtered_data else None
                if vlm_filtered:
                    harvested = [img for img in vlm_filtered if isinstance(img, dict)]
                    break
            if not harvested:
                payload_images = (raw_result.get("payload") or {}).get("images") or []
                harvested = [img for img in payload_images if isinstance(img, dict)]
            new_visual_assets.extend(harvested)

        for v in verdicts:
            if v.verdict in ("retry", "replan", "abort"):
                current_count = new_retry_counts.get(key, 0)
                total = sum(new_retry_counts.values())

                if current_count >= max_per_step or total >= max_total:
                    required = bool(current_step.get("required", False))
                    if v.verdict == "retry":
                        v = ReflectVerdict(
                            verdict="abort" if required else "pass_with_warning",
                            hint=v.hint + ("（已达重试上限，终止必需步骤）" if required else "（已达重试上限，跳过继续执行）"),
                            severity="blocking" if required else "warning",
                        )
                    else:
                        v = ReflectVerdict(
                            verdict="abort",
                            hint=v.hint + "（已达重试上限）",
                            severity="blocking",
                        )
                else:
                    new_retry_counts[key] = current_count + 1

            if _VERDICT_PRIORITY.get(v.verdict, 0) > _VERDICT_PRIORITY.get(worst_verdict, 0):
                worst_verdict = v.verdict

            if v.hint:
                combined_hint = (combined_hint + "\n" + v.hint).strip()

            combined_filtered.update(v.filtered_data)

            if v.verdict != "pass":
                writer({"type": "reflect", "payload": {
                    "tool": tool_name,
                    "verdict": v.verdict,
                    "severity": v.severity,
                    "issue": v.hint,
                }})

    print(
        f"[审查] 结果={worst_verdict}  工具数={len(last_tool_results)}"
        + (f"  提示={combined_hint[:40]}" if combined_hint else ""),
        flush=True,
    )

    updates: dict = {
        "reflect_verdict": worst_verdict,
        "reflect_hint": combined_hint,
        "reflect_filtered": combined_filtered,
        "retry_counts": new_retry_counts,
        "last_tool_results": [],  # consumed — clear
    }

    # Phase 6-A: persist newly approved image_search results across the turn.
    # On retry verdicts we still keep prior accepted images (subsequent retries
    # may surface different candidates we want to add).
    if new_visual_assets:
        prior = list(state.get("accumulated_images") or [])
        # dedup by url
        seen_urls = {img.get("url") for img in prior}
        for img in new_visual_assets:
            if img.get("url") and img["url"] not in seen_urls:
                prior.append(img)
                seen_urls.add(img["url"])
        updates["accumulated_images"] = prior
        print(
            f"[审查] image_search 累积 +{len(new_visual_assets)} 张  累计={len(prior)} 张",
            flush=True,
        )

    # guided mode: advance plan_step_index when step passes
    _maybe_advance_step(writer, state, worst_verdict, updates)

    # abort: emit a graceful result so the user sees a termination message
    if worst_verdict == "abort":
        _emit_abort_result(writer, state, combined_hint, updates)

    return updates


def _execution_failure_verdict(
    tool_name: str,
    result: dict,
    step: dict,
) -> ReflectVerdict | None:
    """Turn execution facts into deterministic verdicts before quality review."""
    if result.get("ok"):
        return None
    code = str(result.get("error") or "unknown_error")
    summary = str(result.get("summary") or "工具执行失败")
    policy = str(step.get("failure_policy") or "stop")
    recoverable = code in {
        "validation_error", "transient_provider_error", "retrieval_empty",
        "timeout", "web_not_available", "rag_not_available",
    }
    if code in {"permission_denied", "strict_violation", "contract_violation"}:
        return ReflectVerdict(
            verdict="abort",
            hint=f"{tool_name} 违反工具契约：{summary}",
            severity="blocking",
        )
    if recoverable and policy in {"retry", "supplement"}:
        return ReflectVerdict(
            verdict="retry",
            hint=f"{tool_name} 执行失败（{code}）：{summary}，按策略重试一次",
            severity="blocking",
        )
    if policy == "partial" and not bool(step.get("required", True)):
        return ReflectVerdict(
            verdict="pass_with_warning",
            hint=f"{tool_name} 未完成：{summary}；继续交付可用部分",
            severity="warning",
        )
    return ReflectVerdict(
        verdict="abort",
        hint=f"{tool_name} 执行失败（{code}）：{summary}",
        severity="blocking",
    )


def _build_pipeline() -> ReflectorPipeline:
    """Select pipeline tier based on available gateways in runtime config."""
    try:
        from langgraph.config import get_config as _get_config
        rt = _get_config()["configurable"]["runtime"]
        llm_gateway = rt.get("agent_gateway")
        vision_gateway = rt.get("vision_gateway")
        if vision_gateway:
            return ReflectorPipeline.with_vision(llm_gateway, vision_gateway)
        if llm_gateway:
            return ReflectorPipeline.with_llm(llm_gateway)
    except Exception:
        pass  # running outside graph context (unit tests, etc.)
    return ReflectorPipeline.default()


def _maybe_advance_step(writer, state: dict, worst_verdict: str, updates: dict) -> None:
    """Advance plan_step_index when a step passes reflect.

    Applies to BOTH guided and strict modes. (Originally guided-only — that
    bug meant strict-mode plans never advanced: the executor stayed pinned to
    step 0's expected_tools forever, looping image_search until react_timeout.)
    """
    if state.get("plan_mode") not in ("guided", "strict"):
        return
    if worst_verdict not in ("pass", "pass_with_warning"):
        return

    current_plan = state.get("current_plan")
    if not current_plan:
        return

    steps = current_plan.get("steps", [])
    idx = state.get("plan_step_index", 0)
    if not (0 <= idx < len(steps)):
        return

    step = steps[idx]

    # Mark current step as done in the plan dict
    updated_steps = list(steps)
    updated_steps[idx] = dict(step, status="done")
    updated_plan = dict(current_plan, steps=updated_steps)

    writer({
        "type": "plan_step_update",
        "payload": {
            "step_index": idx,
            "status": "done",
            "user_title": step.get("user_title", ""),
        },
    })

    print(f"[规划] 步骤 {idx + 1}/{len(steps)} 完成 → 推进到步骤 {idx + 2}", flush=True)

    updates["current_plan"] = updated_plan
    updates["plan_step_index"] = idx + 1


def _emit_abort_result(writer, state: dict, hint: str, updates: dict) -> None:
    """On abort, surface a final assistant message + result event so the user sees a clean end."""
    try:
        from langgraph.config import get_config as _get_config
        rt = _get_config()["configurable"]["runtime"]
        request = rt["request"]
        conv_id = getattr(request, "conversation_id", "") or ""
    except Exception:
        conv_id = ""

    user_msg = "抱歉，本次任务因质量问题已中止" + (f"：{hint}" if hint else "。")

    writer({
        "type": "result",
        "payload": {
            "message": {"role": "assistant", "content": user_msg},
            "conversation": {"conversation_id": conv_id},
            "action": {"name": "agent.aborted"},
            "artifacts": [],
            "workflow": None,
            "sources": [],
            "trace": {"path": "agent", "aborted": True, "reason": hint},
            "tool_exchange": state.get("tool_exchange", []),
        },
    })
    print(f"[审查] abort → 终止链路  原因={hint[:50]}", flush=True)
    # also append to messages for persistence
    msgs = list(state.get("messages") or [])
    msgs.append({"role": "assistant", "content": user_msg})
    updates["messages"] = msgs
