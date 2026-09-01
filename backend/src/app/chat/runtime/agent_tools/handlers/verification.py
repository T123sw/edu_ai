from __future__ import annotations

from app.chat.runtime.agent_tools.result import ok_result
from app.chat.runtime.verification.plan_verifier import verify_plan_execution


def handle_verify_task(name: str, args: dict, ctx) -> dict:
    coverage = getattr(getattr(ctx, "research_bundle", None), "coverage", None)
    if hasattr(coverage, "model_dump"):
        coverage = coverage.model_dump(mode="json")
    report = verify_plan_execution(
        dict(getattr(ctx, "current_plan", {}) or {}),
        dict(getattr(ctx, "trace", {}) or {}),
        artifact_readback=getattr(ctx, "artifact_readback", None),
        research_coverage=dict(coverage or {}),
        persona_issues=list(getattr(ctx, "persona_issues", []) or []),
    )
    ctx.verification_report = report.model_dump(mode="json")
    return ok_result(
        name,
        "执行自检完成" if report.decision == "pass" else "执行自检完成，存在待跟踪项",
        {"verification_report": ctx.verification_report},
    )
