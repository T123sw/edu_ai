from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.chat.runtime.reflection.base import BaseReflector, ReflectVerdict

_MAX_IMAGES_TO_CHECK = 5


class VisionReflector(BaseReflector):
    """Vision-model check: are images in search results suitable for educational use?
    Only activates when step_constraints contains require_images=True.

    Phase 6-A.2 重构：对 image_search 结果，先把图片下载到本地，再把本地图以
    base64 data URI 形式发给 VLM 审查。这样 Qwen/DashScope 无需联网下载境外图，
    根治"无法下载多模态内容"的失败。通过审查的图已在本地，generate_report
    直接使用，不再重复下载。
    """

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

        plan = state.get("current_plan") or {}
        topic = plan.get("subject", "")
        resource_type = plan.get("resource_type", "")
        payload = result.get("payload") or {}

        if tool_name == "image_search":
            if not _vlm_review_enabled():
                # VLM off → trust heuristic filtering; reflect_node accumulates
                # the raw filtered images and generate_report localizes them.
                return ReflectVerdict(verdict="pass")
            return self._evaluate_image_search(payload, topic, resource_type, state)

        # Legacy web_search / rag_search path — list[str] URLs reviewed as-is.
        images = payload.get("images") or []
        if not images:
            return ReflectVerdict(
                verdict="pass_with_warning",
                hint="搜索结果中未找到图片",
                severity="info",
            )
        candidate_imgs = images[:_MAX_IMAGES_TO_CHECK]
        with ThreadPoolExecutor(max_workers=min(len(candidate_imgs), 5)) as pool:
            verdicts = list(pool.map(
                lambda item: (item, self._is_image_suitable(_extract_url(item), topic, resource_type)),
                candidate_imgs,
            ))
        good_images = [item for item, ok in verdicts if ok]
        if good_images:
            return ReflectVerdict(verdict="pass", filtered_data={"images": good_images})
        return ReflectVerdict(
            verdict="pass_with_warning",
            hint="未找到适合的高质量配图，将使用现有素材继续",
            severity="info",
        )

    # ── image_search: download locally then review via base64 ────────────────

    def _evaluate_image_search(self, payload, topic, resource_type, state) -> ReflectVerdict:
        images = payload.get("images") or []  # list[dict]
        if not images:
            return ReflectVerdict(
                verdict="pass_with_warning",
                hint="搜索结果中未找到图片",
                severity="info",
            )

        owner = state.get("_owner")
        course_id = state.get("_course_id")

        candidate_imgs = images[:_MAX_IMAGES_TO_CHECK]
        with ThreadPoolExecutor(max_workers=min(len(candidate_imgs), 5)) as pool:
            results = list(pool.map(
                lambda img: self._localize_and_review(img, topic, resource_type, owner, course_id),
                candidate_imgs,
            ))
        good = [loc for ok, loc in results if ok and loc]

        if good:
            return ReflectVerdict(verdict="pass", filtered_data={"images": good})
        # No image passed review (download failures or all rejected). Don't block
        # the run — pass_with_warning lets the step advance; the report is still
        # generated, just possibly without these images.
        return ReflectVerdict(
            verdict="pass_with_warning",
            hint=f"未找到适合「{topic}」{resource_type or '教学'}的高质量配图，将继续生成",
            severity="info",
        )

    def _localize_and_review(self, img_dict, topic, resource_type, owner, course_id):
        """Download → base64 → VLM review. Returns (ok, localized_dict_or_None)."""
        try:
            from app.chat.workflows.report.image_downloader import (
                LocalizedAsset,
                localize_image,
            )
        except Exception:
            return (False, None)

        asset = localize_image(img_dict, owner=owner, course_id=course_id)
        if not isinstance(asset, LocalizedAsset):
            return (False, None)  # download failed → drop

        data_uri = _to_data_uri(asset.local_path, asset.content_type)
        if data_uri is None:
            return (False, None)

        if not self._is_image_suitable(data_uri, topic, resource_type):
            return (False, None)

        localized = {
            "url": asset.local_url,            # /api/images/searched/{hash}.{ext}
            "source_url": asset.source_url,
            "source_page": asset.source_page,
            "local_path": str(asset.local_path),
            "title": asset.title,
            "alt": str(img_dict.get("alt") or asset.title or "图片"),
            "thumbnail": asset.local_url,
            "license": img_dict.get("license"),
            "_localized": True,
        }
        return (True, localized)

    def _is_image_suitable(self, image_ref: str, topic: str, resource_type: str) -> bool:
        """image_ref is either an http(s) URL (legacy) or a base64 data URI."""
        stream_fn = getattr(self._gateway, "stream_chat_with_tools", None)
        if not callable(stream_fn):
            return True  # vision unconfigured → trust heuristics

        prompt = (
            f"这张图片是否适合用于《{topic}》的{resource_type or '教学材料'}？\n"
            "评估：1.内容相关性 2.清晰度 3.教育适用性\n"
            "只回答：合格 或 不合格，加一句理由（不超过20字）"
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_ref}},
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
                    had_error = True
                    break
        except Exception:
            had_error = True

        text = "".join(chunks).strip()
        if had_error or not text:
            return False
        if "不合格" in text:
            return False
        return "合格" in text


def _vlm_review_enabled() -> bool:
    try:
        from core import Config
        return bool(getattr(Config, "IMAGE_SEARCH_VLM_REVIEW", False))
    except Exception:
        return False


def _to_data_uri(local_path, content_type: str) -> str | None:
    try:
        data = Path(local_path).read_bytes()
    except Exception:
        return None
    b64 = base64.b64encode(data).decode("ascii")
    mime = content_type or "image/png"
    return f"data:{mime};base64,{b64}"


def _extract_url(item) -> str:
    """Accept both list[str] (legacy web_search/rag_search) and list[dict] (image_search)."""
    if isinstance(item, dict):
        return str(item.get("url") or "")
    return str(item or "")
