import json
from typing import Any, List

from tiktoken import get_encoding
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage,ToolMessage

# ToolMessage 可能没被你导入，这里做个兜底导入


# 选用 gpt-4o 系列的分词器
ENC = get_encoding("o200k_base")


def _as_jsonable(x: Any) -> Any:
    """
    将任意 Python 对象转成“可 JSON 序列化”的值：
    - 原本就是 JSON 基本类型 -> 原样返回
    - dict/list 等复杂对象 -> 用 json.dumps 再 loads 一次，保持中文、不加空格
    - 兜底 str(x)
    """
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    try:
        # default=str 防止 datetime/Decimal 等导致失败
        return json.loads(json.dumps(x, ensure_ascii=False, separators=(",", ":"), default=str))
    except Exception:
        return str(x)


def _serialize_tool_calls(tool_calls: Any) -> list:
    """
    将 LangChain 的 AIMessage.tool_calls 统一转为 OpenAI Chat 的 tool_calls 结构。
    支持 list[dict] 或带属性的对象（.name/.args/.id）。
    """
    out = []
    if not tool_calls:
        return out

    for i, tc in enumerate(tool_calls, start=1):
        if isinstance(tc, dict):
            name = tc.get("name") or (tc.get("function") or {}).get("name") or "unknown"
            args = tc.get("args")
            tcid = tc.get("id") or tc.get("tool_call_id") or f"call_{i}"
        else:
            name = getattr(tc, "name", "unknown")
            args = getattr(tc, "args", None)
            tcid = getattr(tc, "id", None) or getattr(tc, "tool_call_id", None) or f"call_{i}"

        # OpenAI 要求 arguments 是 JSON 字符串
        if not isinstance(args, str):
            try:
                args = json.dumps(args, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                args = str(args)

        out.append({
            "id": tcid,
            "type": "function",
            "function": {"name": name, "arguments": args},
        })
    return out


def _to_openai_message(m: BaseMessage) -> dict:
    """
    把 LangChain 的消息对象映射到 OpenAI Chat 的单条 message dict。
    """
    # system
    if isinstance(m, SystemMessage):
        return {"role": "system", "content": _as_jsonable(m.content)}

    # user (human)
    if isinstance(m, HumanMessage):
        return {"role": "user", "content": _as_jsonable(m.content)}

    # assistant (+ tool_calls)
    if isinstance(m, AIMessage):
        msg = {"role": "assistant"}
        tcs = _serialize_tool_calls(getattr(m, "tool_calls", None))
        if tcs:
            msg["tool_calls"] = tcs
            if m.content not in (None, ""):
                msg["content"] = _as_jsonable(m.content)  # 有些模型会同时返回文字+tool_calls
        else:
            msg["content"] = _as_jsonable(m.content)
        return msg

    # tool
    if (ToolMessage is not None) and isinstance(m, ToolMessage):
        tool_call_id = getattr(m, "tool_call_id", None) or getattr(m, "id", None) or "call_1"
        name = getattr(m, "name", None)
        d = {"role": "tool", "tool_call_id": tool_call_id, "content": _as_jsonable(getattr(m, "content", ""))}
        if name:
            d["name"] = name  # OpenAI 可选字段
        return d

    # 兜底：当成 user
    return {"role": "user", "content": _as_jsonable(getattr(m, "content", ""))}


def serialize_messages_as_openai_json(messages: List[BaseMessage]) -> str:
    """
    把一组 LangChain 消息序列化成 OpenAI Chat 的消息 JSON（仅 messages 数组部分）。
    用紧凑分隔符保证计数稳定。
    """
    openai_msgs = [_to_openai_message(m) for m in messages]
    return json.dumps(openai_msgs, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def count_langchain_messages(messages: List[BaseMessage], enc=None) -> int:
    """
    主函数：返回 token 数。
    注意：这是“按最终要发的文本”估算；不同 API 还会有固定的报文开销，
    以服务端返回的 usage 为准。
    """
    encoder = enc or ENC
    payload = serialize_messages_as_openai_json(messages)
    # 允许“疑似特殊 token”通过，避免报错
    return len(encoder.encode(payload, disallowed_special=()))



