"""Offline deterministic runner for teacher-Agent contract and plan cases."""
from __future__ import annotations

import time
from types import SimpleNamespace

from app.chat.evals.dataset import AgentEvalCase
from app.chat.evals.evaluators import EvalResult, evaluate_case
from app.chat.runtime.planning.compiler import compile_plan
from app.chat.runtime.planning.task_contract_extractor import extract_task_contract


def run_offline_cases(cases: list[AgentEvalCase], *, repeat: int = 1) -> list[EvalResult]:
    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    results: list[EvalResult] = []
    for run_index in range(1, repeat + 1):
        for case in cases:
            started = time.perf_counter()
            capability = SimpleNamespace(**case.capability.model_dump(mode="python"))
            request = SimpleNamespace(
                question=case.question,
                course_id="eval-course",
                conversation_id=f"eval-{case.case_id}",
            )
            contract = extract_task_contract(request, capability, case.state)
            plan = compile_plan(contract, case.state)
            result = evaluate_case(
                case,
                actual_contract=contract,
                actual_plan=plan,
                run_index=run_index,
            )
            result.duration_ms = round((time.perf_counter() - started) * 1000, 3)
            results.append(result)
    return results
