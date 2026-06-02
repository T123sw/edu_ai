"""Diagnostic: call the planner gateway directly to see why create_plan isn't being invoked."""
import sys

sys.path.insert(0, r"D:\Edu_AI_1\Edu_AI\api\src")

from app.chat.runtime.model_registry import build_planner_gateway
from app.chat.runtime.planning.prompts import CREATE_PLAN_SCHEMA, PLANNER_SYSTEM_PROMPT

gw = build_planner_gateway()
print(f"Gateway model: {gw.model_name}")
print(f"Gateway base: {gw.api_base}")

messages = [
    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
    {"role": "user", "content": "用户请求：帮我写一份机器学习入门报告，3000字"},
]

print("\n=== 试 1：tool_choice=create_plan ===")
events = []
try:
    for event in gw.stream_chat_with_tools(
        messages,
        [CREATE_PLAN_SCHEMA],
        tool_choice={"type": "function", "function": {"name": "create_plan"}},
        temperature=0.1,
        max_tokens=1024,
    ):
        events.append(event)
        print(f"  → {event.get('type')}: {str(event)[:200]}")
except Exception as exc:
    print(f"  EXCEPTION: {exc}")

print(f"\n  事件总数: {len(events)}")
print(f"  事件类型分布: {sorted(set(e.get('type', '') for e in events))}")

tool_calls = [e for e in events if e.get("type") == "tool_calls"]
print(f"  tool_calls 事件数: {len(tool_calls)}")
if tool_calls:
    print(f"  第一个 tool_call: {tool_calls[0]}")

print("\n=== 试 2：tool_choice=auto ===")
events = []
try:
    for event in gw.stream_chat_with_tools(
        messages,
        [CREATE_PLAN_SCHEMA],
        tool_choice="auto",
        temperature=0.1,
        max_tokens=1024,
    ):
        events.append(event)
        if event.get("type") in ("tool_calls", "error", "unsupported"):
            print(f"  → {event.get('type')}: {str(event)[:300]}")
except Exception as exc:
    print(f"  EXCEPTION: {exc}")

print(f"\n  事件总数: {len(events)}")
tool_calls = [e for e in events if e.get("type") == "tool_calls"]
print(f"  tool_calls 事件数: {len(tool_calls)}")
if tool_calls:
    print(f"  第一个 tool_call: {tool_calls[0]}")
