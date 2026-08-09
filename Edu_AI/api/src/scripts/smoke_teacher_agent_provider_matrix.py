"""Exercise the same minimal teacher-Agent contract on independent providers.

The report intentionally records only provider host/model identifiers and
sanitised outcomes.  API keys, prompts containing private course data, raw
provider responses, and hidden reasoning are never persisted.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    from app.chat.model_gateway import ChatModelGateway
    from app.chat.runtime.model_registry import build_agent_gateway
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.chat.model_gateway import ChatModelGateway
    from app.chat.runtime.model_registry import build_agent_gateway


_TOOL = {
    "type": "function",
    "function": {
        "name": "record_teaching_topic",
        "description": "记录教师当前要备课的主题",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "audience": {"type": "string"},
            },
            "required": ["topic", "audience"],
            "additionalProperties": False,
        },
    },
}


def _provider_id(candidate: dict) -> str:
    host = urlparse(str(candidate.get("api_base") or "")).hostname or "unknown"
    return f"{host}/{candidate.get('model_name') or 'unknown'}"


def _single_candidate_gateway(candidate: dict) -> ChatModelGateway:
    return ChatModelGateway(
        api_base=str(candidate.get("api_base") or ""),
        api_key=candidate.get("api_key"),
        model_name=str(candidate.get("model_name") or ""),
    )


def _run_text_case(gateway: ChatModelGateway) -> tuple[bool, str]:
    answer = gateway.chat(
        [{
            "role": "system",
            "content": "你是教师备课助手。不要解释，只回复 TEACHER_AGENT_OK。",
        }],
        temperature=0,
        max_tokens=32,
    )
    return "TEACHER_AGENT_OK" in answer, "nonempty_teacher_reply" if answer else "empty_reply"


def _run_tool_case(gateway: ChatModelGateway) -> tuple[bool, str]:
    calls: list[dict] = []
    errors: list[str] = []
    for event in gateway.stream_chat_with_tools(
        [{
            "role": "user",
            "content": "为高一学生准备快速排序课程，请调用工具记录主题。",
        }],
        [_TOOL],
        tool_choice="required",
        temperature=0,
        max_tokens=128,
    ):
        if event.get("type") == "tool_calls":
            calls.extend(event.get("calls") or [])
        elif event.get("type") in {"error", "unsupported"}:
            errors.append(str(event.get("message") or event.get("type")))
    matched = [call for call in calls if call.get("name") == "record_teaching_topic"]
    if not matched:
        return False, "missing_required_tool" if not errors else "provider_tool_error"
    args = dict(matched[0].get("args") or {})
    passed = bool(str(args.get("topic") or "").strip()) and bool(
        str(args.get("audience") or "").strip()
    )
    return passed, "required_tool_with_arguments" if passed else "invalid_tool_arguments"


def run_matrix(provider_limit: int = 2) -> dict:
    configured = build_agent_gateway().candidates
    unique: list[dict] = []
    seen: set[str] = set()
    for candidate in configured:
        identifier = _provider_id(candidate)
        if identifier in seen or not candidate.get("api_key"):
            continue
        seen.add(identifier)
        unique.append(candidate)
        if len(unique) >= provider_limit:
            break
    if len(unique) < provider_limit:
        raise RuntimeError(f"需要 {provider_limit} 个独立 Provider，当前仅配置 {len(unique)} 个")

    results: list[dict] = []
    for candidate in unique:
        gateway = _single_candidate_gateway(candidate)
        for case_id, runner in (
            ("teacher_text_contract", _run_text_case),
            ("required_tool_contract", _run_tool_case),
        ):
            started = time.perf_counter()
            try:
                passed, observation = runner(gateway)
            except Exception as exc:  # provider failures belong in the matrix
                passed = False
                observation = f"{type(exc).__name__}: provider_case_failed"
            results.append({
                "provider": _provider_id(candidate),
                "case_id": case_id,
                "passed": passed,
                "observation": observation,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            })

    passed_count = sum(1 for item in results if item["passed"])
    return {
        "schema_version": "2026-08-09.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider_count": len(unique),
        "case_count": len(results),
        "passed_count": passed_count,
        "pass_rate": passed_count / len(results) if results else 0.0,
        "results": results,
    }


def _markdown(payload: dict) -> str:
    lines = [
        "# Teacher Agent Provider Matrix",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Providers: {payload['provider_count']}",
        f"- Pass rate: {payload['pass_rate']:.2%}",
        "",
        "| Provider | Case | Result | Observation | Duration |",
        "|---|---|---|---|---:|",
    ]
    for item in payload["results"]:
        lines.append(
            f"| `{item['provider']}` | `{item['case_id']}` | "
            f"{'PASS' if item['passed'] else 'FAIL'} | {item['observation']} | "
            f"{item['duration_ms']} ms |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", type=int, default=2)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--fail-under", type=float, default=0.95)
    args = parser.parse_args()
    payload = run_matrix(provider_limit=args.providers)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in (
        "provider_count", "case_count", "passed_count", "pass_rate"
    )}, ensure_ascii=False))
    return 0 if payload["pass_rate"] >= args.fail_under else 1


if __name__ == "__main__":
    raise SystemExit(main())
