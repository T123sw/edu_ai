from __future__ import annotations

import json
from typing import Any

from app.chat.domain.resource_quality import (
    ArtifactAudit,
    EvidenceAudit,
    ExecutionAudit,
    PersonaAudit,
    RepairDirective,
)
from app.chat.domain.verification_report import VerificationReport
from app.chat.runtime.verification.resource_verifier import verify_resource_quality


def verify_plan_execution(
    plan: dict,
    trace: dict,
    *,
    artifact_readback: dict | None = None,
    research_coverage: dict | None = None,
    persona_issues: list[str] | None = None,
) -> VerificationReport:
    """Audit execution, evidence, artifacts and persona as separate facts."""

    steps = list((plan or {}).get("steps") or [])
    agent_steps = [
        item for item in list((trace or {}).get("agent_steps") or [])
        if isinstance(item, dict)
    ]
    called = [str(item.get("tool") or "") for item in agent_steps]
    expected = [
        tool
        for step in steps
        for tool in list(step.get("expected_tools") or [])
        if tool != "verify_task"
    ]
    allowlist = {
        tool
        for step in steps
        for tool in list(step.get("tool_allowlist") or step.get("expected_tools") or [])
    }
    required_tools_satisfied = all(tool in called for tool in expected)
    forbidden_tools_absent = all(tool in allowlist for tool in called)

    retrieval_positions = [
        index for index, tool in enumerate(called)
        if tool in {"rag_search", "web_search", "image_search"}
    ]
    generation_positions = [
        index for index, tool in enumerate(called) if tool.startswith("generate_")
    ]
    tool_order_valid = (
        not retrieval_positions
        or not generation_positions
        or max(retrieval_positions) < min(generation_positions)
    )
    submitted = [
        item for item in agent_steps
        if str(item.get("tool") or "").startswith("generate_") and item.get("ok")
    ]
    fingerprints = [
        (
            str(item.get("tool") or ""),
            json.dumps(item.get("args") or {}, ensure_ascii=False, sort_keys=True, default=str),
        )
        for item in submitted
    ]
    duplicate_submission_absent = len(set(fingerprints)) == len(fingerprints)
    failed_tools = [
        str(item.get("tool") or "") for item in agent_steps if not item.get("ok")
    ]
    execution_valid = all((
        required_tools_satisfied,
        forbidden_tools_absent,
        tool_order_valid,
        duplicate_submission_absent,
        not failed_tools,
    ))
    execution_audit = ExecutionAudit(
        valid=execution_valid,
        required_tools_satisfied=required_tools_satisfied,
        forbidden_tools_absent=forbidden_tools_absent,
        tool_order_valid=tool_order_valid,
        duplicate_submission_absent=duplicate_submission_absent,
        failed_tools=failed_tools,
    )

    evidence_count = sum(
        int(item.get("evidence_count") or 0)
        for item in agent_steps
        if item.get("tool") in {"rag_search", "web_search"}
    )
    retrieval_called = any(
        tool in {"rag_search", "web_search"} for tool in called
    )
    missing_aspects = list((research_coverage or {}).get("missing_aspects") or [])
    coverage_sufficient = bool(
        (research_coverage or {}).get("sufficient", not missing_aspects)
    )
    grounding_valid = (not retrieval_called or evidence_count > 0) and coverage_sufficient
    evidence_audit = EvidenceAudit(
        valid=grounding_valid,
        grounding_valid=grounding_valid,
        evidence_count=evidence_count,
        missing_aspects=missing_aspects,
    )

    artifact_audit = _audit_artifacts(artifact_readback)
    persona_issues = list(persona_issues or [])
    persona_audit = PersonaAudit(valid=not persona_issues, issues=persona_issues)
    successful_task_ids = [
        str(item.get("task_id")) for item in submitted if item.get("task_id")
    ]
    repair = _repair_directive(
        steps=steps,
        execution=execution_audit,
        evidence=evidence_audit,
        artifact=artifact_audit,
        persona=persona_audit,
        submitted=bool(submitted),
        successful_task_ids=successful_task_ids,
    )

    warnings: list[str] = []
    if not evidence_audit.valid:
        warnings.append("检索证据不足或研究问题覆盖不完整")
    if submitted and artifact_audit.readable is None:
        warnings.append("资源任务已提交，需在任务成功且材料可读后才能宣称完成")
    for assessment in artifact_audit.assessments:
        warnings.extend(assessment.issues)
    if persona_issues:
        warnings.extend(persona_issues)

    hard_failure = (
        not execution_audit.valid
        or artifact_audit.readable is False
        or persona_audit.valid is False
    )
    pending_artifact = submitted and artifact_audit.readable is None
    quality_failure = artifact_audit.valid is False or not evidence_audit.valid
    if hard_failure:
        decision = "fail"
    elif repair.action in {"retry_step", "supplement_evidence", "readback"}:
        decision = "retry"
    elif pending_artifact or quality_failure:
        decision = "partial"
    else:
        decision = "pass"

    return VerificationReport(
        plan_compliance=execution_audit.valid,
        required_tools_satisfied=required_tools_satisfied,
        forbidden_tools_absent=forbidden_tools_absent,
        tool_order_valid=tool_order_valid,
        duplicate_submission_absent=duplicate_submission_absent,
        grounding_valid=grounding_valid,
        artifact_contract_valid=artifact_audit.valid is not False,
        artifact_readable=artifact_audit.readable,
        persona_valid=persona_audit.valid,
        execution_audit=execution_audit,
        evidence_audit=evidence_audit,
        artifact_audit=artifact_audit,
        persona_audit=persona_audit,
        repair_directive=repair,
        warnings=warnings,
        decision=decision,
    )


def _audit_artifacts(readback: dict | None) -> ArtifactAudit:
    if readback is None:
        return ArtifactAudit(valid=None, readable=None)
    readable = bool(readback.get("readable"))
    artifacts = [
        item for item in list(readback.get("artifacts") or [])
        if isinstance(item, dict)
    ]
    assessments = [
        verify_resource_quality(
            str(item.get("resource_type") or ""), item.get("artifact") or {}
        )
        for item in artifacts
    ]
    # A result reference without resolved content is readable as a job result,
    # but its resource contract remains unknown until storage readback succeeds.
    valid = all(item.valid for item in assessments) if assessments else None
    return ArtifactAudit(valid=valid, readable=readable, assessments=assessments)


def _repair_directive(
    *,
    steps: list[dict[str, Any]],
    execution: ExecutionAudit,
    evidence: EvidenceAudit,
    artifact: ArtifactAudit,
    persona: PersonaAudit,
    submitted: bool,
    successful_task_ids: list[str],
) -> RepairDirective:
    preserve = list(dict.fromkeys(successful_task_ids))
    if not execution.forbidden_tools_absent or not execution.duplicate_submission_absent:
        return RepairDirective(
            action="stop",
            reason="检测到越权工具调用或重复生成提交，必须停止而不是扩大重试范围",
            failed_audit="execution",
            preserve_successful_task_ids=preserve,
        )
    if execution.failed_tools:
        tool = execution.failed_tools[0]
        index = _step_index_for_tool(steps, tool)
        return RepairDirective(
            action="retry_step",
            reason=f"只重试失败工具 {tool} 所在步骤",
            failed_audit="execution",
            target_step_index=index,
            target_tool=tool,
            max_attempts=1,
            preserve_successful_task_ids=preserve,
        )
    if not evidence.valid:
        return RepairDirective(
            action="supplement_evidence",
            reason="只补充缺失证据，不重复生成已成功资源",
            failed_audit="evidence",
            target_step_index=_step_index_for_action(steps, "retrieve_context"),
            target_tool="rag_search",
            max_attempts=1,
            preserve_successful_task_ids=preserve,
        )
    if artifact.readable is False:
        return RepairDirective(
            action="readback",
            reason="任务标记成功但产物不可读，只重试读取，不重新提交生成",
            failed_audit="artifact",
            target_step_index=_step_index_for_action(steps, "status"),
            target_tool="query_generation_job_status",
            max_attempts=1,
            preserve_successful_task_ids=preserve,
        )
    if artifact.valid is False:
        return RepairDirective(
            action="stop",
            reason="产物质量契约不满足；创建新修订前需要用户确认，不能覆盖或重复提交",
            failed_audit="artifact",
            preserve_successful_task_ids=preserve,
            requires_user_confirmation=True,
        )
    if not persona.valid:
        return RepairDirective(
            action="stop",
            reason="表达不符合教师助手人格；不得用工具重跑掩盖表达问题",
            failed_audit="persona",
            preserve_successful_task_ids=preserve,
        )
    if submitted and artifact.readable is None:
        return RepairDirective(
            action="await_artifact",
            reason="等待已提交任务完成，禁止重复生成",
            failed_audit="artifact",
            preserve_successful_task_ids=preserve,
        )
    return RepairDirective(preserve_successful_task_ids=preserve)


def _step_index_for_tool(steps: list[dict[str, Any]], tool: str) -> int | None:
    for index, step in enumerate(steps):
        if tool in list(step.get("expected_tools") or []):
            return index
    return None


def _step_index_for_action(steps: list[dict[str, Any]], action: str) -> int | None:
    for index, step in enumerate(steps):
        if str(step.get("internal_action") or "") == action:
            return index
    return None
