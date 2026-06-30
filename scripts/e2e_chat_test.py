"""E2E chat tester — drives the SSE stream endpoint and captures event timeline."""
import argparse
import json
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request


TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InRlYWNoZXIiLCJyb2xlIjoidGVhY2hlciIsImV4cCI6MTc4MDQ2NjA5MCwiaWF0IjoxNzgwMzc5NjkwfQ.vOQUvpQ4V99ArX1xfcFfOKFktrshk54t_EwWgH2XH7c"
BASE = "http://localhost:8001"


def stream_chat(question: str, conversation_id: str | None = None,
                allow_rag: bool = False, allow_web: bool = False,
                action_hint: str | None = None, timeout: int = 60):
    """Hit /api/chat/stream and yield parsed SSE events as dicts."""
    params = {"question": question, "token": TOKEN}
    if conversation_id:
        params["conversation_id"] = conversation_id
    if allow_rag:
        params["allow_rag"] = "true"
    if allow_web:
        params["allow_web"] = "true"
    if action_hint:
        params["action_hint"] = action_hint

    url = f"{BASE}/api/chat/stream?{urlencode(params)}"
    req = Request(url)

    event_type = None
    data_buffer = []

    with urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_buffer.append(line[5:].strip())
            elif line == "":  # event boundary
                if event_type and data_buffer:
                    data_str = "\n".join(data_buffer)
                    try:
                        data = json.loads(data_str) if data_str else {}
                    except json.JSONDecodeError:
                        data = {"_raw": data_str}
                    yield {"type": event_type, "data": data}
                event_type = None
                data_buffer = []


def run_case(name: str, question: str, conversation_id: str | None = None, **kwargs):
    print(f"\n{'=' * 80}")
    print(f"[{name}] 问：{question}")
    print(f"{'=' * 80}")

    events_by_type = {}
    deltas = []
    t0 = time.perf_counter()
    last_print = t0

    try:
        for event in stream_chat(question, conversation_id=conversation_id, **kwargs):
            etype = event["type"]
            events_by_type[etype] = events_by_type.get(etype, 0) + 1
            data = event["data"]
            now = time.perf_counter()

            if etype == "delta":
                # legacy SSE field is "delta", not "content"
                content = data.get("delta", "") or data.get("content", "")
                deltas.append(content)
                sys.stdout.write(content)
                sys.stdout.flush()
            elif etype == "meta":
                cid = data.get("conversation_id")
                print(f"\n[meta #{events_by_type['meta']}] conv_id={cid!r}  raw={json.dumps(data, ensure_ascii=False)[:160]}")
            elif etype == "result":
                msg = data.get("message", {}).get("content", "")[:80]
                action = data.get("action", {}).get("name", "")
                print(f"\n[result] action={action}  msg={msg!r}")
            elif etype == "tool_call":
                print(f"\n[tool_call] {data.get('tool')}  args={json.dumps(data.get('args'), ensure_ascii=False)[:120]}")
            elif etype == "tool_result":
                ok = data.get("ok")
                print(f"\n[tool_result] {data.get('tool')}  ok={ok}  summary={data.get('summary', '')[:60]}")
            elif etype == "plan":
                steps = data.get("steps", [])
                print(f"\n[plan] subject={data.get('subject')}  resource={data.get('resource_type')}  steps={len(steps)}")
                for s in steps:
                    print(f"    {s.get('index')}. {s.get('user_title')} → {s.get('expected_tools')}")
            elif etype == "plan_step_update":
                print(f"\n[plan_step_update] step={data.get('step_index')}  status={data.get('status')}  title={data.get('user_title', '')[:30]}")
            elif etype == "reflect":
                print(f"\n[reflect] {data.get('tool')}  verdict={data.get('verdict')}  severity={data.get('severity')}  issue={data.get('issue', '')[:60]}")
            elif etype == "task_submitted":
                print(f"\n[task_submitted] task_id={data.get('task_id')}  workflow={data.get('workflow_type')}")
            elif etype == "status":
                stage = data.get("stage")
                if stage in ("thinking", "fallback"):
                    print(f"\n[status] {stage}: {data.get('label', '')}")
            elif etype == "error":
                print(f"\n[error] {data}")
    except Exception as exc:
        print(f"\n[EXCEPTION] {exc}")

    elapsed = round((time.perf_counter() - t0) * 1000)
    print(f"\n\n--- 用例 {name} 完成 ({elapsed}ms) ---")
    print(f"事件统计: {dict(sorted(events_by_type.items()))}")
    print(f"delta 总字数: {sum(len(d) for d in deltas)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--conv", default=None)
    parser.add_argument("--rag", action="store_true")
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--action-hint", default=None)
    args = parser.parse_args()
    run_case(args.name, args.question, conversation_id=args.conv,
             allow_rag=args.rag, allow_web=args.web, action_hint=args.action_hint)
