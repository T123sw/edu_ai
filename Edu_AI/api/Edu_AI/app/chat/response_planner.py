from __future__ import annotations

import json
from typing import Any, Dict, List


AnswerMode = str

PLANNER_PROMPT = """你是教学对话中的回答计划器。
任务：根据用户问题与已知槽位，选择最合适的回答模式，并给出一句风格提示。

仅输出 JSON：
{
  "answer_mode": "explain|compare|steps|example|qa",
  "style_hint": "一句简短提示"
}

规则：
1) explain：概念讲解、原理说明。
2) compare：对比/区别/优缺点。
3) steps：流程、步骤、方法。
4) example：要求举例、案例、类比。
5) qa：一般问答。
6) 输出必须为合法 JSON，不要输出其他内容。
"""


class ResponsePlanner:
    def __init__(self, model_gateway):
        self.model_gateway = model_gateway

    @staticmethod
    def _extract_json_payload(raw: Any) -> Dict[str, Any]:
        print(f"[response_planner] raw_type={type(raw)}")
        if isinstance(raw, dict):
            print(f"[response_planner] raw is dict keys={list(raw.keys())}")
            return raw

        text = str(raw or "").strip()
        print(f"[response_planner] raw_text_preview={text[:200]}")
        if not text:
            return {}

        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _fallback(question: str) -> Dict[str, str]:
        q = (question or "").lower()
        if any(k in q for k in ["区别", "对比", "优缺点", "vs", "compare"]):
            return {"answer_mode": "compare", "style_hint": "先给结论，再用要点对比。"}
        if any(k in q for k in ["步骤", "流程", "怎么做", "如何", "step"]):
            return {"answer_mode": "steps", "style_hint": "按步骤给出，尽量可执行。"}
        if any(k in q for k in ["举例", "案例", "类比", "example"]):
            return {"answer_mode": "example", "style_hint": "用一个贴近课堂的例子解释。"}
        if any(k in q for k in ["原理", "是什么", "解释", "讲解", "理解"]):
            return {"answer_mode": "explain", "style_hint": "先定义，再讲核心机制。"}
        return {"answer_mode": "qa", "style_hint": "简洁直接回答，必要时补充要点。"}

    def plan(self, question: str, slots: Dict[str, str]) -> Dict[str, Any]:
        payload = {
            "question": question or "",
            "slots": slots or {},
        }
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            raw = self.model_gateway.chat(messages=messages, temperature=0.0, max_tokens=120)
            data = self._extract_json_payload(raw)
            print(f"[response_planner] parsed_payload={data}")
            mode = str(data.get("answer_mode") or "").strip()
            hint = str(data.get("style_hint") or "").strip()
            if mode in {"explain", "compare", "steps", "example", "qa"}:
                return {
                    "answer_mode": mode,
                    "style_hint": hint or self._fallback(question)["style_hint"],
                    "source": "llm_json",
                }
        except Exception as exc:
            print(f"[response_planner_error] type={type(exc)} detail={exc}")

        fb = self._fallback(question)
        return {"answer_mode": fb["answer_mode"], "style_hint": fb["style_hint"], "source": "fallback"}
