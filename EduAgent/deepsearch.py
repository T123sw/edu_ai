import tomllib
from pathlib import Path

from langchain_core.messages import HumanMessage

from o_agent import get_agent, get_llm_by_type
from tools import scan_page, web_search
from define import *

import ast
import json
import re
from typing import Any, Optional

# ```json ... ``` 代码块
_CODEBLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
# 粗略抓可能的 JSON 起点
_JSON_START_RE = re.compile(r"[\{\[]")

def parse_json_from_text(
    text: str,
    *,
    allow_python_literal: bool = True,
    return_first: bool = True,
) -> Any:
    """
    从任意字符串中提取并解析 JSON（object/array）。

    参数:
      - allow_python_literal: 允许用 ast.literal_eval 兜底解析单引号/Python dict 风格
      - return_first: 若存在多个 JSON，返回第一个；否则抛错（目前实现默认第一个）

    返回:
      - 解析后的 Python 对象（dict/list/str/number/...）

    失败:
      - ValueError（包含原因）
    """
    if not isinstance(text, str):
        raise ValueError(f"text must be str, got {type(text)}")

    s = text.strip()
    if not s:
        raise ValueError("empty text")

    # 1) 优先解析 ```json ... ``` 代码块
    m = _CODEBLOCK_RE.search(s)
    if m:
        candidate = m.group(1).strip()
        obj = _try_json_then_literal(candidate, allow_python_literal)
        if obj is not None:
            return obj

    # 2) 如果整个字符串就是 JSON，直接 parse
    obj = _try_json_then_literal(s, allow_python_literal)
    if obj is not None:
        return obj

    # 3) 从文本中扫描：找第一个完整的 {...} 或 [...]
    start_match = _JSON_START_RE.search(s)
    if not start_match:
        raise ValueError("no JSON start token '{' or '[' found")

    start = start_match.start()
    extracted = _extract_first_balanced_json(s, start)
    if extracted is None:
        raise ValueError("found JSON start but could not extract a balanced JSON block")

    obj = _try_json_then_literal(extracted, allow_python_literal)
    if obj is None:
        # 给出更清晰的提示
        preview = extracted[:200].replace("\n", "\\n")
        raise ValueError(f"extracted JSON candidate but parse failed. candidate preview: {preview}")

    return obj


def _try_json_then_literal(candidate: str, allow_python_literal: bool) -> Optional[Any]:
    candidate = candidate.strip()
    if not candidate:
        return None

    # 先 json.loads
    try:
        return json.loads(candidate)
    except Exception:
        pass

    if not allow_python_literal:
        return None

    # 再 ast.literal_eval（支持 {'a':1} / True / None 等）
    try:
        obj = ast.literal_eval(candidate)
        # literal_eval 可能返回 set/tuple 等非 JSON 类型，这里你可按需限制
        return obj
    except Exception:
        return None


def _extract_first_balanced_json(s: str, start: int) -> Optional[str]:
    """
    从 s[start] 开始提取第一个括号配平的 JSON 块（支持 {} 或 []），
    会正确跳过字符串中的括号/转义。

    返回提取的子串，失败返回 None。
    """
    if start < 0 or start >= len(s):
        return None

    opening = s[start]
    if opening not in "{[":
        return None
    closing = "}" if opening == "{" else "]"

    depth = 0
    in_str = False
    escape = False
    quote_char = ""

    for i in range(start, len(s)):
        ch = s[i]

        if in_str:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == quote_char:
                in_str = False
                quote_char = ""
            continue

        # 不在字符串内
        if ch in ('"', "'"):
            in_str = True
            quote_char = ch
            continue

        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return s[start : i + 1]

        # 注意：嵌套时可能出现另一种括号（{}里出现[]），不影响 depth；
        # 真正的 JSON 配平只关心最外层 opening/closing。
        # 如果你想更严格可扩展为栈，但通常够用了。

    return None




def deepsearch_large_llm(query: str)->dict|None:

    from o_agent import get_llm_from_config
    
    # 从配置文件获取 LLM（使用默认配置，temperature=0.2）
    llm = get_llm_from_config(temperature=0.2)

    max_retries = 3
    while max_retries > 0:

        print(f"[deepsearch] start query={query!r} retries_left={max_retries}")
        agent = get_agent(
            name='search',
            tools=[scan_page, web_search],
            llm=llm,
        )

        # 优化prompt让Agent更快完成任务，并在获得足够结果后立即返回
        resp = agent.invoke(
            input=[
                HumanMessage(content='我需要你将我的话题（topic）分解为一些子查询，使用工具进行搜索，最后将搜索到的与我的话题相关的链接以JSON的形式通过chat工具返回给我。重要：一旦获得5条或更多链接，立即使用chat工具返回结果，不要继续搜索。'),
                HumanMessage(content=f'我想查询的话题：{query}\n请至少返回5条链接，如果不足如实返回，查询不到返回一个JSON空列表。\n重要：最多搜索2-3次，一旦获得足够链接，立即使用chat工具返回JSON格式的链接列表。'),
                HumanMessage(content=f'最终通过chat工具返回的结果应为如下样例（纯JSON数组，不要有其他文字）:\n'
                                    f'["link1", "link2", "link3"]\n'
                                    f'重要：当你已经搜索了2-3次或获得了5条以上链接时，必须立即使用chat工具返回结果，不要再继续搜索。')
            ],
            config={
                "recursion_limit": 15  # 增加到15，给Agent足够的步骤完成任务
            }
        )
        try:
            if not isinstance(resp, dict) or 'response' not in resp:
                print(f"[deepsearch] unexpected agent response keys={list(resp.keys()) if isinstance(resp, dict) else type(resp)}")
                max_retries -= 1
                continue
            output = parse_json_from_text(resp['response'])
            if not isinstance(output, list):
               max_retries -= 1
               continue

            return {'links': output}

        except Exception:
            max_retries -= 1
            continue

    return None


def deepsearch_local_llm(query: str)->dict|None:



    pass









