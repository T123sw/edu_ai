"""Preview or execute teacher Agent RAG/Web tool-call acceptance checks.

Examples:
  python src/scripts/smoke_teacher_agent_tools.py --course-id COURSE
  python src/scripts/smoke_teacher_agent_tools.py --course-id COURSE --selected-doc-id DOC --include-web --execute
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any

try:
    from scripts.teacher_smoke_common import request_json, request_sse_events
except ModuleNotFoundError:  # Direct execution: python src/scripts/...
    from teacher_smoke_common import request_json, request_sse_events


@dataclass(frozen=True)
class AgentCase:
    name: str
    payload: dict[str, Any]
    expected_source_mode: str
    expected_tools: set[str]


def build_cases(
    *, course_id: str, selected_doc_id: str | None, include_web: bool
) -> list[AgentCase]:
    base = {
        "question": "请用简洁步骤解释链表如何实现，并说明关键指针操作。",
        "course_id": course_id,
        "scope_type": "course",
    }
    cases = [
        AgentCase(
            "plain",
            {**base, "allow_rag": False, "allow_web": False, "source_mode": "none"},
            "none",
            set(),
        )
    ]
    if selected_doc_id:
        cases.append(
            AgentCase(
                "rag-selected",
                {
                    **base,
                    "allow_rag": True,
                    "allow_web": False,
                    "source_mode": "selected_documents",
                    "selected_doc_ids": [selected_doc_id],
                },
                "selected_documents",
                {"rag_search"},
            )
        )
    cases.append(
        AgentCase(
            "rag-course-auto",
            {
                **base,
                "allow_rag": True,
                "allow_web": False,
                "source_mode": "course_auto",
            },
            "course_auto",
            {"rag_search"},
        )
    )
    if include_web:
        cases.extend(
            [
                AgentCase(
                    "web",
                    {
                        **base,
                        "allow_rag": False,
                        "allow_web": True,
                        "source_mode": "none",
                    },
                    "none",
                    {"web_search"},
                ),
                AgentCase(
                    "rag-web",
                    {
                        **base,
                        "allow_rag": True,
                        "allow_web": True,
                        "source_mode": "course_auto",
                    },
                    "course_auto",
                    {"rag_search", "web_search"},
                ),
            ]
        )
    return cases


def _executed_tools(trace: dict[str, Any]) -> set[str]:
    tools: set[str] = set()
    for step in trace.get("agent_steps") or []:
        if not isinstance(step, dict) or step.get("ok") is False:
            continue
        name = str(step.get("tool") or step.get("tool_name") or "").strip()
        if name:
            tools.add(name)
    return tools


def validate_reply(
    response: dict[str, Any], *, expected_source_mode: str, expected_tools: set[str]
) -> None:
    message = response.get("message") or {}
    if not str(message.get("content") or "").strip():
        raise AssertionError("Agent returned no answer content")
    trace = response.get("trace") or {}
    actual_source_mode = trace.get("source_mode")
    # Plain chat may legitimately take the fast path, whose compact trace does
    # not carry Agent-only source metadata. Tool-backed cases must always prove
    # the exact source mode because that is part of their acceptance contract.
    source_mode_matches = actual_source_mode == expected_source_mode
    plain_fast_path = (
        not expected_tools
        and expected_source_mode == "none"
        and actual_source_mode is None
    )
    if not (source_mode_matches or plain_fast_path):
        raise AssertionError(
            f"source_mode mismatch: expected {expected_source_mode}, got {actual_source_mode}"
        )
    missing = expected_tools - _executed_tools(trace)
    if missing:
        raise AssertionError(
            "required tools were not executed successfully: "
            f"missing={sorted(missing)}, path={trace.get('path')}, "
            f"fallback={trace.get('fallback_reason')}, "
            f"steps={trace.get('agent_steps')}"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("EDU_AI_SMOKE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--course-id", default=os.getenv("EDU_AI_SMOKE_COURSE_ID"), required=False)
    parser.add_argument("--selected-doc-id", default=os.getenv("EDU_AI_SMOKE_DOCUMENT_ID"))
    parser.add_argument("--include-web", action="store_true", help="Call the configured live Web provider")
    parser.add_argument(
        "--cases",
        nargs="*",
        choices=["plain", "rag-selected", "rag-course-auto", "web", "rag-web"],
    )
    parser.add_argument("--execute", action="store_true", help="Perform authenticated requests")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.course_id:
        raise SystemExit("--course-id (or EDU_AI_SMOKE_COURSE_ID) is required")
    cases = build_cases(
        course_id=args.course_id,
        selected_doc_id=args.selected_doc_id,
        include_web=args.include_web,
    )
    if args.cases:
        requested = set(args.cases)
        cases = [case for case in cases if case.name in requested]
    if not args.execute:
        print(json.dumps({"mode": "preview", "cases": [case.name for case in cases]}, ensure_ascii=False, indent=2))
        return 0

    token = os.getenv("EDU_AI_SMOKE_TOKEN", "").strip()
    if not token:
        raise SystemExit("EDU_AI_SMOKE_TOKEN is required with --execute")
    for case in cases:
        if case.expected_tools & {"rag_search"}:
            preflight = request_json(
                args.base_url,
                "/api/chat/v2/generation/preflight",
                token,
                method="POST",
                payload={
                    "course_id": args.course_id,
                    "resource_type": "report",
                    "source_mode": case.payload["source_mode"],
                    "selected_doc_ids": case.payload.get("selected_doc_ids", []),
                },
            )
            if not preflight.get("valid"):
                raise AssertionError(f"{case.name}: generation source preflight failed")
        events = request_sse_events(
            args.base_url,
            "/api/chat/v2/stream",
            token,
            payload=case.payload,
        )
        stream_error = next(
            (event for event in events if event.get("type") == "error"),
            None,
        )
        if stream_error:
            raise AssertionError(
                f"{case.name}: stream failed: {(stream_error.get('payload') or {}).get('message')}"
            )
        result_event = next(
            (event for event in reversed(events) if event.get("type") == "result"),
            None,
        )
        if result_event is None:
            raise AssertionError(f"{case.name}: stream returned no result event")
        response = dict(result_event.get("payload") or {})
        validate_reply(
            response,
            expected_source_mode=case.expected_source_mode,
            expected_tools=case.expected_tools,
        )
        print(f"PASS {case.name}: tools={sorted(case.expected_tools)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
