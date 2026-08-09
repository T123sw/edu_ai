"""Live chat-to-Agent-to-tool-to-material acceptance checks.

The script verifies actual Agent planning and resource tool calls.  It does not
call the direct generation endpoints used by the resource panel.
"""
from __future__ import annotations

import argparse
import os
from functools import partial
from typing import Any

try:
    from scripts.teacher_smoke_common import poll_job, request_json, request_sse_events
except ModuleNotFoundError:
    from teacher_smoke_common import poll_job, request_json, request_sse_events


def _result(events: list[dict[str, Any]]) -> dict[str, Any]:
    error = next((event for event in events if event.get("type") == "error"), None)
    if error:
        raise AssertionError(f"Agent stream error: {error.get('payload')}")
    event = next(
        (event for event in reversed(events) if event.get("type") == "result"),
        None,
    )
    if event is None:
        raise AssertionError("Agent stream returned no result event")
    return dict(event.get("payload") or {})


def _conversation_id(response: dict[str, Any]) -> str:
    return str(
        response.get("conversation_id")
        or (response.get("conversation") or {}).get("conversation_id")
        or ""
    ).strip()


def _successful_tools(response: dict[str, Any]) -> list[str]:
    return [
        str(step.get("tool") or "")
        for step in list((response.get("trace") or {}).get("agent_steps") or [])
        if isinstance(step, dict) and step.get("ok") is not False and step.get("tool")
    ]


def _task_id(events: list[dict[str, Any]], workflow_type: str) -> str:
    event = next(
        (
            event
            for event in events
            if event.get("type") == "task_submitted"
            and str((event.get("payload") or {}).get("workflow_type")) == workflow_type
        ),
        None,
    )
    if event is None:
        raise AssertionError(f"Agent submitted no {workflow_type} task")
    return str((event.get("payload") or {}).get("task_id") or "").strip()


def _turn(
    *,
    base_url: str,
    token: str,
    course_id: str,
    question: str,
    conversation_id: str = "",
    allow_web: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = {
        "question": question,
        "course_id": course_id,
        "scope_type": "course",
        "source_mode": "none",
        "allow_rag": False,
        "allow_web": allow_web,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    events = request_sse_events(
        base_url,
        "/api/chat/v2/stream",
        token,
        payload=payload,
    )
    return events, _result(events)


def _assert_job_succeeded(call, task_id: str, timeout: float) -> dict[str, Any]:
    job = poll_job(
        task_id,
        request_json=lambda method, path: call(path, method=method),
        timeout_seconds=timeout,
    )
    if job.get("status") != "succeeded" or not job.get("result_ref"):
        raise AssertionError(
            f"job {task_id} status={job.get('status')} error={job.get('error_message')}"
        )
    return job


def _run_confirmed_resource(
    *,
    base_url: str,
    token: str,
    course_id: str,
    prompt: str,
    workflow_type: str,
    timeout: float,
) -> tuple[str, dict[str, Any]]:
    first_events, first = _turn(
        base_url=base_url,
        token=token,
        course_id=course_id,
        question=prompt,
    )
    if "draft_outline" not in _successful_tools(first):
        raise AssertionError(f"{workflow_type}: Agent did not draft an outline")
    conversation_id = _conversation_id(first)
    if not conversation_id:
        raise AssertionError(f"{workflow_type}: missing conversation id")
    second_events, second = _turn(
        base_url=base_url,
        token=token,
        course_id=course_id,
        question="确认生成",
        conversation_id=conversation_id,
    )
    expected_tool = f"generate_{workflow_type}"
    if expected_tool not in _successful_tools(second):
        raise AssertionError(f"{workflow_type}: Agent did not call {expected_tool}")
    task_id = _task_id(second_events, workflow_type)
    call = partial(request_json, base_url, token=token)
    return task_id, _assert_job_succeeded(call, task_id, timeout)


def run_report(base_url: str, token: str, course_id: str, timeout: float) -> None:
    task_id, job = _run_confirmed_resource(
        base_url=base_url,
        token=token,
        course_id=course_id,
        prompt="帮我生成一份快速排序的教学报告",
        workflow_type="report",
        timeout=timeout,
    )
    material_id = str((job.get("result_ref") or {}).get("material_id") or "")
    print(f"PASS agent-report: job={task_id}, material={material_id}")


def run_web_report(base_url: str, token: str, course_id: str, timeout: float) -> None:
    first_events, first = _turn(
        base_url=base_url,
        token=token,
        course_id=course_id,
        question="请先查找网络资料，然后生成一份快速排序的教学报告",
        allow_web=True,
    )
    first_tools = _successful_tools(first)
    if not {"web_search", "draft_outline"}.issubset(first_tools):
        raise AssertionError(f"web-report first turn tools={first_tools}")
    if "generate_report" in first_tools:
        raise AssertionError(
            f"web-report submitted before outline confirmation: {first_tools}"
        )
    conversation_id = _conversation_id(first)
    second_events, second = _turn(
        base_url=base_url,
        token=token,
        course_id=course_id,
        question="确认生成",
        conversation_id=conversation_id,
        allow_web=True,
    )
    second_tools = _successful_tools(second)
    if not {"web_search", "generate_report"}.issubset(second_tools):
        raise AssertionError(f"web-report confirm tools={second_tools}")
    if second_tools.index("web_search") > second_tools.index("generate_report"):
        raise AssertionError(f"web-report confirm order={second_tools}")
    task_id = _task_id(second_events, "report")
    call = partial(request_json, base_url, token=token)
    # The global Job ledger is the public durable snapshot used by the teacher
    # task center.  /api/chat/tasks is a legacy compact status view and does not
    # expose the generation command config.
    submitted_job = call(f"/api/jobs/{task_id}")
    config = dict((submitted_job.get("input_summary") or {}).get("config") or {})
    if not str(config.get("research_context") or "").strip():
        raise AssertionError("web-report task has no retrieval context")
    if not list(config.get("research_sources") or []):
        raise AssertionError("web-report task has no research sources")
    job = _assert_job_succeeded(call, task_id, timeout)
    material_id = str((job.get("result_ref") or {}).get("material_id") or "")
    materials = call(
        f"/api/courses/{course_id}/materials?material_type=report&space=mine"
    )
    material = next(
        (
            item
            for item in list(materials or [])
            if str(item.get("material_id") or item.get("id") or "") == material_id
        ),
        None,
    )
    if material is None:
        raise AssertionError(f"web-report material {material_id} was not found")
    grounding = dict((material.get("generation_state") or {}).get("grounding") or {})
    if grounding.get("retrieval_context_used") is not True:
        raise AssertionError(f"web-report grounding state={grounding}")
    if int(grounding.get("research_source_count") or 0) < 1:
        raise AssertionError(f"web-report source count state={grounding}")
    print(
        f"PASS agent-web-report: order={second_tools}, "
        f"sources={len(config['research_sources'])}, job={task_id}, material={material_id}"
    )


def run_direct_resource(
    base_url: str,
    token: str,
    course_id: str,
    timeout: float,
    *,
    name: str,
    prompt: str,
) -> None:
    events, response = _turn(
        base_url=base_url,
        token=token,
        course_id=course_id,
        question=prompt,
    )
    tool = f"generate_{name}"
    tools = _successful_tools(response)
    if tool not in tools:
        raise AssertionError(f"{name}: expected {tool}, got {tools}")
    task_id = _task_id(events, name)
    call = partial(request_json, base_url, token=token)
    job = _assert_job_succeeded(call, task_id, timeout)
    material_id = str((job.get("result_ref") or {}).get("material_id") or "")
    print(f"PASS agent-{name}: job={task_id}, material={material_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--course-id", default=os.getenv("EDU_AI_SMOKE_COURSE_ID"))
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument(
        "--cases",
        nargs="*",
        choices=["report", "web-report", "lesson-plan", "quiz", "blog", "flashcard", "graph", "game", "classroom"],
    )
    args = parser.parse_args()
    token = os.getenv("EDU_AI_SMOKE_TOKEN", "").strip()
    if not token or not args.course_id:
        raise SystemExit("EDU_AI_SMOKE_TOKEN and --course-id are required")
    cases = args.cases or [
        "report",
        "web-report",
        "lesson-plan",
        "quiz",
        "blog",
        "flashcard",
        "graph",
        "game",
        "classroom",
    ]
    if "report" in cases:
        run_report(args.base_url, token, args.course_id, args.timeout)
    if "web-report" in cases:
        run_web_report(args.base_url, token, args.course_id, args.timeout)
    if "lesson-plan" in cases:
        task_id, job = _run_confirmed_resource(
            base_url=args.base_url,
            token=token,
            course_id=args.course_id,
            prompt="帮我生成一份快速排序的教案",
            workflow_type="lesson_plan",
            timeout=args.timeout,
        )
        print(
            f"PASS agent-lesson-plan: job={task_id}, "
            f"material={(job.get('result_ref') or {}).get('material_id', '')}"
        )
    direct_cases = {
        "quiz": "帮我生成5道快速排序练习题",
        "blog": "帮我生成一篇快速排序的教学博客",
        "flashcard": "帮我生成10张快速排序复习闪卡",
        "graph": "帮我生成快速排序的思维导图",
        "game": "帮我生成一个快速排序课堂小游戏",
        "classroom": "帮我生成一个快速排序 AI 课堂",
    }
    for name, prompt in direct_cases.items():
        if name in cases:
            run_direct_resource(
                args.base_url,
                token,
                args.course_id,
                args.timeout,
                name=name,
                prompt=prompt,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
