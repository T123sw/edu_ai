from __future__ import annotations

from app.chat.runtime.reflection.base import BaseReflector, ReflectVerdict

_MAX_IMAGES_TO_CHECK = 5


class VisionReflector(BaseReflector):
    """Vision-model check: are images in search results suitable for educational use?
    Only activates when step_constraints contains require_images=True."""

    priority = 20
    _APPLIES_TO = {"web_search", "rag_search"}

    def __init__(self, vision_gateway):
        self._gateway = vision_gateway

    def applies_to(self, tool_name: str) -> bool:
        return tool_name in self._APPLIES_TO

    def evaluate(self, tool_name, result, state, step_constraints) -> ReflectVerdict:
        if not result.get("ok"):
            return ReflectVerdict(verdict="pass")
        if not step_constraints.get("require_images", False):
            return ReflectVerdict(verdict="pass")

        payload = result.get("payload") or {}
        images: list[str] = payload.get("images") or []

        if not images:
            return ReflectVerdict(
                verdict="pass_with_warning",
                hint="搜索结果中未找到图片",
                severity="info",
            )

        plan = state.get("current_plan") or {}
        topic = plan.get("subject", "")
        resource_type = plan.get("resource_type", "")

        good_images: list[str] = []
        for img_url in images[:_MAX_IMAGES_TO_CHECK]:
            if self._is_image_suitable(img_url, topic, resource_type):
                good_images.append(img_url)

        if good_images:
            return ReflectVerdict(
                verdict="pass",
                filtered_data={"images": good_images},
            )

        return ReflectVerdict(
            verdict="retry",
            hint=f"未找到适合「{topic}」{resource_type or '教学'}的高质量配图，尝试换关键词重新搜索",
            severity="blocking",
        )

    def _is_image_suitable(self, img_url: str, topic: str, resource_type: str) -> bool:
        stream_fn = getattr(self._gateway, "stream_chat_with_tools", None)
        if not callable(stream_fn):
            return True  # fail-safe: pass when vision unavailable

        prompt = (
            f"这张图片是否适合用于《{topic}》的{resource_type or '教学材料'}？\n"
            "评估：1.内容相关性 2.清晰度 3.教育适用性\n"
            "只回答：合格 或 不合格，加一句理由（不超过20字）"
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": img_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        chunks: list[str] = []
        try:
            for e in stream_fn(messages, [], tool_choice="auto", temperature=0.0, max_tokens=50):
                if e.get("type") == "text_delta":
                    chunks.append(e.get("content", ""))
        except Exception:
            return True  # fail-safe on network/model errors

        text = "".join(chunks)
        # "合格" pass, "不合格" fail — handle ambiguous/empty as pass
        return "不合格" not in text
