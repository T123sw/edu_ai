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

    plan_step_index = state.get("plan_step_index") or 0
    current_plan = state.get("current_plan")

    step_constraints: dict = {}
    if current_plan:
        steps = current_plan.get("steps", [])
        if 0 <= plan_step_index < len(steps):
            step_constraints = steps[plan_step_index].get("constraints", {})

    plan_gc: dict = (current_plan or {}).get("global_constraints", {})
    max_per_step: int = plan_gc.get("max_retries_per_step", 2)
    max_total: int = plan_gc.get("max_total_reflect_retries", 4)

    pipeline = ReflectorPipeline.default()
    new_retry_counts = dict(state.get("retry_counts") or {})

    worst_verdict = "pass"
    combined_hint = ""
    combined_filtered: dict = {}

    for item in last_tool_results:
        tool_name = item.get("tool_name", "")
        raw_result = item.get("raw_result", {})
        key = f"step_{plan_step_index}:{tool_name}"

        verdicts = pipeline.evaluate_all(tool_name, raw_result, state, step_constraints)

        for v in verdicts:
            if v.verdict in ("retry", "replan", "abort"):
                current_count = new_retry_counts.get(key, 0)
                total = sum(new_retry_counts.values())

                if current_count >= max_per_step or total >= max_total:
                    # Retry limit hit — downgrade
                    if v.verdict == "retry":
                        v = ReflectVerdict(
                            verdict="pass_with_warning",
                            hint=v.hint + "（已达重试上限，跳过继续执行）",
                            severity="warning",
                        )
                    else:
                        v = ReflectVerdict(
                            verdict="abort",
                            hint=v.hint + "（已达重试上限）",
                            severity="blocking",
                        )
                else:
                    new_retry_counts[key] = current_count + 1

            # Track worst verdict
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

    return {
        "reflect_verdict": worst_verdict,
        "reflect_hint": combined_hint,
        "reflect_filtered": combined_filtered,
        "retry_counts": new_retry_counts,
        "last_tool_results": [],  # consumed — clear for next tools_node run
    }
