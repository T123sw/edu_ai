from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.chat.runtime.reflection.base import BaseReflector, ReflectVerdict

_MAX_IMAGES_TO_CHECK = 5


class VisionReflector(BaseReflector):
    """Vision-model check: are images in search results suitable for educational use?
    Only activates when step_constraints contains require_images=True."""

    priority = 20
    _APPLIES_TO = {"image_search", "web_search", "rag_search"}

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
        # image_search payload returns list[dict] with url/source_page/...;
        # legacy web_search / rag_search inject_images_into_report path uses list[str].
        # Accept both, but always preserve the original item shape in filtered_data
        # so downstream consumers see what they expect.
        images = payload.get("images") or []

        if not images:
            # Always pass_with_warning on 0 candidates — let the step advance.
            # When a parallel batch contains some 0-image calls and some good
            # ones, returning "retry" here forced every retry per call and
            # blew the agent's time budget. strict mode + accumulated_images
            # already ensure that generate_resource runs next regardless of
            # whether this particular call found anything.
            return ReflectVerdict(
                verdict="pass_with_warning",
                hint="搜索结果中未找到图片",
                severity="info",
            )

        plan = state.get("current_plan") or {}
        topic = plan.get("subject", "")
        resource_type = plan.get("resource_type", "")

        # Parallel vision calls — each can take 1-3s, so 5 images sequential ≈ 10s.
        candidate_imgs = images[:_MAX_IMAGES_TO_CHECK]
        with ThreadPoolExecutor(max_workers=min(len(candidate_imgs), 5)) as pool:
            verdicts = list(pool.map(
                lambda item: (item, self._is_image_suitable(_extract_url(item), topic, resource_type)),
                candidate_imgs,
            ))
        good_images = [item for item, ok in verdicts if ok]

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
            # When vision is entirely unconfigured we pass — heuristics in the
            # handler already filtered low-quality candidates.
            return True

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
        had_error = False
        try:
            for e in stream_fn(messages, [], tool_choice="auto", temperature=0.0, max_tokens=50):
                etype = e.get("type")
                if etype == "text_delta":
                    chunks.append(e.get("content", ""))
                elif etype in ("error", "unsupported"):
                    # Provider-level failure: image download timeout, geo-block,
                    # auth/cookie wall, NSFW filter, model rejection, etc.
                    had_error = True
                    break
        except Exception:
            had_error = True

        text = "".join(chunks).strip()

        # Reject when VLM couldn't render a verdict — being permissive here
        # silently lets through irrelevant or unreachable images.
        if had_error or not text:
            return False
        # Explicit reject signal from the model.
        if "不合格" in text:
            return False
        # Require an explicit pass signal — defends against ambiguous replies
        # like apologies or refusals that happen to omit "不合格".
        return "合格" in text


def _extract_url(item) -> str:
    """Accept both list[str] (legacy web_search/rag_search) and list[dict] (image_search)."""
    if isinstance(item, dict):
        return str(item.get("url") or "")
    return str(item or "")
