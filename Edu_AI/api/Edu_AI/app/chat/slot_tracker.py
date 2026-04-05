from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


SLOT_KEYS = ["topic", "audience", "objective"]
SLOT_PRIORITY = ["topic", "objective", "audience"]


SLOT_QUESTION_TEMPLATES: Dict[str, str] = {
    "topic": "我先对齐一下，你这次主要想讲哪个主题或知识点？",
    "objective": "我再确认一下，你希望学生通过这次内容重点达到什么目标？比如理解概念、会做题或能应用。",
    "audience": "你这次主要面向哪类学生？比如高中、大一或大二。",
}


SLOT_EXTRACT_PROMPT = """你是一个极其聪明的意图参数提取器。请从用户输入中提取槽位信息。
仅输出 JSON，字段固定如下：
{
  "topic": "",
  "audience": "",
  "objective": ""
}

规则：
1) 你必须进行“隐式代填”：只要用户的表达包含了对内容的期待、想讲的方向或希望达成的效果，就要总结为 objective（教学目标），绝对不要留空。
2) 若输入是明确术语/缩写（例如 TCP、HTTP、牛顿第二定律），优先识别为 topic。
3) 若用户回答很短（如“基础概念”“大一”“理解原理”），结合 expected_slot 判断并填写，但不要填无关内容。
4) 若用户说“直接开始讲/直接讲/别问了”，结合历史对话语境把 objective 总结为“了解当前主题的核心内容”。
5) 不要输出其他字段，输出必须是合法 JSON。
"""


class SlotTracker:
    """槽位提取与追问选择器。"""

    def __init__(self, model_gateway):
        self.model_gateway = model_gateway

    @staticmethod
    def _clean_topic(topic: str) -> str:
        t = (topic or "").strip()
        if not t:
            return ""

        patterns = [
            r"^我想(?:了解|学习|知道|问下|问一问)?",
            r"^我想要(?:了解|学习)?",
            r"^帮我(?:讲解|介绍|说明|分析|看看)?",
            r"^请(?:你)?(?:讲解|介绍|说明|解释)?",
            r"^关于",
            r"^(?:能不能|可以)?(?:帮我)?(?:讲讲|说说)",
        ]
        for p in patterns:
            t = re.sub(p, "", t).strip()

        t = re.sub(r"(吧|吗|呢|一下|一下子|相关内容)$", "", t).strip()
        t = re.sub(r"^[，。,:：\s]+", "", t).strip()
        t = re.sub(r"[，。,:：\s]+$", "", t).strip()

        if len(re.findall(r"[，。；;！？!?]", t)) >= 1 and len(t) > 18:
            return ""
        return t

    @classmethod
    def _normalize_slots(cls, raw: Optional[Dict[str, Any]]) -> Dict[str, str]:
        result: Dict[str, str] = {k: "" for k in SLOT_KEYS}
        if not raw:
            return result
        for k in SLOT_KEYS:
            v = raw.get(k)
            result[k] = str(v).strip() if v else ""
        result["topic"] = cls._clean_topic(result.get("topic", ""))
        return result

    @staticmethod
    def merge_slots(old_slots: Dict[str, str], new_slots: Dict[str, str]) -> Dict[str, str]:
        merged = {k: str(old_slots.get(k, "") or "").strip() for k in SLOT_KEYS}
        for k in SLOT_KEYS:
            nv = str(new_slots.get(k, "") or "").strip()
            if nv:
                merged[k] = nv
        return merged

    @staticmethod
    def pick_next_missing_slot(slots: Dict[str, str]) -> Optional[str]:
        for key in SLOT_PRIORITY:
            if not str(slots.get(key, "") or "").strip():
                return key
        return None

    @staticmethod
    def build_slot_followup(slot_key: Optional[str]) -> str:
        if not slot_key:
            return ""
        return SLOT_QUESTION_TEMPLATES.get(slot_key, "你可以再补充一点关键背景信息吗？")

    @staticmethod
    def _extract_audience_marker(text: str) -> str:
        audience_markers = ["高一", "高二", "高三", "初一", "初二", "初三", "大一", "大二", "大三", "大四", "研究生", "小学", "初中", "高中"]
        for marker in audience_markers:
            if marker in text:
                return marker
        return ""

    @staticmethod
    def _has_objective_marker(text: str) -> bool:
        objective_markers = ["理解", "掌握", "学会", "会做", "应用", "复习", "入门", "讲清", "备考", "梳理"]
        return any(m in text for m in objective_markers)

    @classmethod
    def _detect_obvious_slot(cls, text: str) -> Tuple[Optional[str], float, str]:
        t = (text or "").strip()
        if not t:
            return None, 0.0, ""

        audience = cls._extract_audience_marker(t)
        if audience:
            return "audience", 0.95, audience

        if cls._has_objective_marker(t):
            return "objective", 0.88, t

        is_short_term = len(t) <= 24 and " " not in t and "，" not in t and "。" not in t
        looks_like_term = bool(re.fullmatch(r"[A-Za-z0-9_\-+#\.]+", t)) or (2 <= len(t) <= 12)
        not_generic = t not in {"这个", "那个", "不知道", "不会", "帮我", "看看", "怎么弄", "咋办"}
        if is_short_term and looks_like_term and not_generic:
            return "topic", 0.82, cls._clean_topic(t)

        m = re.search(r"(?:我想(?:了解|学习|知道)?|帮我(?:讲解|介绍|说明)?|请(?:你)?(?:讲解|介绍|说明|解释)?)(.+)$", t)
        if m:
            cand = cls._clean_topic(m.group(1).strip())
            if cand and len(cand) <= 20:
                return "topic", 0.78, cand

        return None, 0.0, ""

    @classmethod
    def _heuristic_extract_slots(cls, text: str, expected_slot: Optional[str] = None) -> Dict[str, str]:
        t = (text or "").strip()
        slots = {k: "" for k in SLOT_KEYS}
        if not t:
            return slots

        audience = cls._extract_audience_marker(t)
        if audience:
            slots["audience"] = audience

        if cls._has_objective_marker(t):
            slots["objective"] = t

        obvious_slot, obvious_conf, obvious_value = cls._detect_obvious_slot(t)
        if obvious_slot and obvious_value and obvious_conf >= 0.78 and not slots.get(obvious_slot):
            slots[obvious_slot] = obvious_value

        # expected_slot 作为弱引导，不覆盖明显特征
        if expected_slot in SLOT_KEYS:
            short_reply = len(t) <= 24 and "，" not in t and "。" not in t
            if short_reply and not any(slots.get(k) for k in SLOT_KEYS):
                if expected_slot == "topic":
                    slots["topic"] = cls._clean_topic(t)
                elif expected_slot == "objective":
                    slots["objective"] = t
                elif expected_slot == "audience":
                    slots["audience"] = t

        return slots

    def extract_slots_with_signal(self, text: str, expected_slot: Optional[str] = None) -> Dict[str, Any]:
        user_payload = {
            "text": text or "",
            "expected_slot": expected_slot or "",
        }
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SLOT_EXTRACT_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

        llm_slots = {k: "" for k in SLOT_KEYS}
        try:
            content = self.model_gateway.chat(messages=messages, temperature=0.0, max_tokens=200)
            payload = json.loads(content)
            llm_slots = self._normalize_slots(payload if isinstance(payload, dict) else None)
        except Exception:
            pass

        heuristic_slots = self._heuristic_extract_slots(text, expected_slot=expected_slot)
        merged_slots = self.merge_slots(llm_slots, heuristic_slots)

        obvious_slot, obvious_conf, obvious_value = self._detect_obvious_slot(text)
        correction_applied = False
        correction_from = expected_slot or ""
        correction_to = ""

        if expected_slot in SLOT_KEYS and obvious_slot and obvious_slot != expected_slot and obvious_conf >= 0.85:
            correction_applied = True
            correction_to = obvious_slot
            if obvious_value:
                merged_slots[obvious_slot] = obvious_value
            if str(merged_slots.get(expected_slot, "") or "").strip() == str(text or "").strip():
                merged_slots[expected_slot] = ""

        slot_confidence = {k: 0.0 for k in SLOT_KEYS}
        for k in SLOT_KEYS:
            if merged_slots.get(k):
                slot_confidence[k] = 0.65
        if obvious_slot and merged_slots.get(obvious_slot):
            slot_confidence[obvious_slot] = max(slot_confidence[obvious_slot], obvious_conf)
        if expected_slot in SLOT_KEYS and merged_slots.get(expected_slot):
            slot_confidence[expected_slot] = max(slot_confidence[expected_slot], 0.72)

        filled_slot = ""
        for k in SLOT_KEYS:
            if merged_slots.get(k):
                filled_slot = k
                break

        return {
            "slots": merged_slots,
            "slot_confidence": slot_confidence,
            "filled_slot": filled_slot,
            "expected_slot": expected_slot,
            "correction_applied": correction_applied,
            "correction_from": correction_from,
            "correction_to": correction_to,
        }

    def extract_slots(self, text: str, expected_slot: Optional[str] = None) -> Dict[str, str]:
        signal = self.extract_slots_with_signal(text=text, expected_slot=expected_slot)
        return signal.get("slots", {k: "" for k in SLOT_KEYS})
