from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional


class ReflectionEngine:
    """报告模块自反思引擎（outline/body）。"""

    def __init__(self, llm_factory: Callable[[], Any]):
        self._llm_factory = llm_factory
        self.enabled = os.getenv("REPORT_REFLECTION_ENABLED", "1").strip().lower() in {"1", "true", "yes"}
        self.outline_max_retries = int(os.getenv("REPORT_OUTLINE_REVIEW_MAX_RETRIES", "1"))
        self.body_max_retries = int(os.getenv("REPORT_BODY_REVIEW_MAX_RETRIES", "1"))
        self.timeout_sec = int(os.getenv("REPORT_REFLECTION_TIMEOUT_SEC", "20"))
        self.max_draft_chars = int(os.getenv("REPORT_REFLECTION_MAX_DRAFT_CHARS", "12000"))

    @staticmethod
    def _normalize_outline(raw_outline: Any) -> List[Dict[str, Any]]:
        """确保大纲结构稳定：[{title, points[]}]"""
        if isinstance(raw_outline, str):
            try:
                raw_outline = json.loads(raw_outline)
            except Exception:
                return []

        if not isinstance(raw_outline, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for item in raw_outline:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            points_raw = item.get("points")
            points: List[str] = []
            if isinstance(points_raw, list):
                points = [str(p).strip() for p in points_raw if str(p).strip()]
            elif isinstance(points_raw, str) and points_raw.strip():
                points = [points_raw.strip()]

            if title and points:
                normalized.append({"title": title, "points": points[:6]})

        return normalized

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            start_obj = text.find("{")
            end_obj = text.rfind("}")
            if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
                try:
                    return json.loads(text[start_obj : end_obj + 1])
                except Exception:
                    return {}
        return {}

    def review_text(
        self,
        *,
        stage: str,
        draft: str,
        context: Dict[str, Any],
        policy: str = "full",
        focus_instruction: str = "",
        max_retries: int = 1,
    ) -> Dict[str, Any]:
        """
        通用自反思入口。

        policy:
        - full: 全量审查
        - partial: 局部审查（依赖 focus_instruction）
        - skip: 跳过审查
        """
        normalized_policy = (policy or "full").strip().lower()
        if normalized_policy not in {"full", "partial", "skip"}:
            normalized_policy = "full"

        if not self.enabled:
            return {
                "passed": True,
                "final_text": draft,
                "review_applied": False,
                "policy": "disabled",
                "issues": [],
                "critique": "reflection disabled",
            }

        if normalized_policy == "skip":
            return {
                "passed": True,
                "final_text": draft,
                "review_applied": False,
                "policy": "skip",
                "issues": [],
                "critique": "skip review",
            }

        llm = self._llm_factory()
        if not llm:
            return {
                "passed": True,
                "final_text": draft,
                "review_applied": False,
                "policy": normalized_policy,
                "issues": [],
                "critique": "llm unavailable, bypass",
            }

        current = (draft or "")[: self.max_draft_chars]
        if len(draft or "") > self.max_draft_chars:
            truncated_issue = ["draft_truncated_for_review"]
        else:
            truncated_issue = []

        # 限制 context 体积，避免审查请求过大
        safe_context: Dict[str, Any] = {}
        for k, v in (context or {}).items():
            val = str(v)
            safe_context[k] = val[:1200] if len(val) > 1200 else val

        last_result: Dict[str, Any] = {}

        for _ in range(max(1, int(max_retries) + 1)):
            review_prompt = (
                "你是严苛的内容质量评审专家。请审查并在必要时修订草稿。"
                "必须输出严格 JSON，不要解释。"
            )

            policy_hint = ""
            if normalized_policy == "partial":
                policy_hint = (
                    "只做局部审查：仅检查并修订与用户修改指令相关的部分，"
                    "其他部分保持不变。"
                )
            else:
                policy_hint = "做全量审查：检查结构完整性、目标对齐、表达清晰度。"

            payload = {
                "stage": stage,
                "policy": normalized_policy,
                "focus_instruction": focus_instruction or "",
                "context": safe_context,
                "draft": current,
            }

            messages = [
                {"role": "system", "content": review_prompt},
                {
                    "role": "user",
                    "content": (
                        f"审查策略：{policy_hint}\n"
                        "检查要求：\n"
                        "1) 是否符合用户目标/受众\n"
                        "2) 结构是否完整\n"
                        "3) 表达是否专业且可执行\n"
                        "4) 若不通过，请给出 revised_text\n\n"
                        "输出格式（严格 JSON）：\n"
                        "{\"passed\": true/false, \"issues\": [\"...\"], \"critique\": \"...\", \"revised_text\": \"...\"}\n\n"
                        f"输入数据：\n{json.dumps(payload, ensure_ascii=False)}"
                    ),
                },
            ]

            try:
                # 不同后端 SDK 对 timeout 支持不一致，优先尝试带 timeout 调用
                try:
                    response = llm.invoke(messages, config={"timeout": self.timeout_sec})
                except Exception:
                    response = llm.invoke(messages)
                raw = str(getattr(response, "content", "") or "").strip()
                parsed = self._parse_json(raw)
            except Exception:
                parsed = {}

            passed = bool(parsed.get("passed", False))
            issues = parsed.get("issues") if isinstance(parsed.get("issues"), list) else []
            critique = str(parsed.get("critique") or "").strip()
            revised_text = str(parsed.get("revised_text") or "").strip()

            if passed:
                last_result = {
                    "passed": True,
                    "final_text": current,
                    "review_applied": False,
                    "policy": normalized_policy,
                    "issues": issues,
                    "critique": critique,
                }
                break

            if revised_text:
                current = revised_text
                last_result = {
                    "passed": True,
                    "final_text": current,
                    "review_applied": True,
                    "policy": normalized_policy,
                    "issues": issues,
                    "critique": critique,
                }
                break

            last_result = {
                "passed": False,
                "final_text": current,
                "review_applied": False,
                "policy": normalized_policy,
                "issues": issues,
                "critique": critique,
            }

        if not last_result:
            last_result = {
                "passed": True,
                "final_text": current,
                "review_applied": False,
                "policy": normalized_policy,
                "issues": [],
                "critique": "",
            }

        issues = last_result.get("issues") if isinstance(last_result.get("issues"), list) else []
        if truncated_issue:
            issues.extend(truncated_issue)
        last_result["issues"] = issues

        return last_result

    def review_outline(
        self,
        *,
        draft_outline_json: str,
        context: Dict[str, Any],
        policy: str,
        focus_instruction: str = "",
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        retries = self.outline_max_retries if max_retries is None else max_retries
        result = self.review_text(
            stage="outline",
            draft=draft_outline_json,
            context=context,
            policy=policy,
            focus_instruction=focus_instruction,
            max_retries=retries,
        )

        normalized = self._normalize_outline(result.get("final_text"))
        if not normalized:
            # 质量门控：审查输出非法时回退原始大纲
            fallback = self._normalize_outline(draft_outline_json)
            result["final_text"] = json.dumps(fallback, ensure_ascii=False)
            result["passed"] = True
            result["review_applied"] = False
            result["issues"] = list(result.get("issues") or []) + ["review_output_invalid_outline_fallback"]
            return result

        result["final_text"] = json.dumps(normalized, ensure_ascii=False)
        result["outline_section_count"] = len(normalized)
        return result

    def review_body(
        self,
        *,
        draft_markdown: str,
        context: Dict[str, Any],
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        retries = self.body_max_retries if max_retries is None else max_retries
        result = self.review_text(
            stage="body",
            draft=draft_markdown,
            context=context,
            policy="full",
            focus_instruction="",
            max_retries=retries,
        )

        # 质量门控：防止审查后正文过短/空
        final_text = str(result.get("final_text") or "").strip()
        original = (draft_markdown or "").strip()
        if not final_text or len(final_text) < max(80, int(len(original) * 0.2)):
            result["final_text"] = original
            result["passed"] = True
            result["review_applied"] = False
            result["issues"] = list(result.get("issues") or []) + ["review_output_too_short_fallback"]

        return result
