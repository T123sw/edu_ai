from __future__ import annotations

from typing import Any

import httpx


class Html2PptClient:
    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.http_client = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout_seconds,
            trust_env=False,
        )

    @staticmethod
    def _build_create_job_payload(*, content_markdown: str, theme_id: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "content_markdown": str(content_markdown or ""),
            "theme_id": str(theme_id or ""),
            "metadata": dict(metadata or {}),
        }

    def _absolutize_url(self, value: Any) -> Any:
        text = str(value or "").strip()
        if not text:
            return value
        if text.startswith(("http://", "https://")):
            return text
        if text.startswith("/"):
            return f"{self.base_url}{text}"
        return f"{self.base_url}/{text.lstrip('/')}"

    def _normalize_results_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})
        results = normalized.get("results")
        if not isinstance(results, dict):
            return normalized
        normalized_results = dict(results)
        for key in ("html_full_url", "html_url", "pptx_url", "manifest_url", "fragment_url"):
            if key in normalized_results:
                normalized_results[key] = self._absolutize_url(normalized_results.get(key))
        normalized["results"] = normalized_results
        return normalized

    def create_job(self, *, content_markdown: str, theme_id: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
        response = self.http_client.post(
            "/ppt/jobs",
            json=self._build_create_job_payload(
                content_markdown=content_markdown,
                theme_id=theme_id,
                metadata=metadata,
            ),
        )
        response.raise_for_status()
        return response.json()

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        response = self.http_client.get(f"/ppt/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    def get_job_results(self, job_id: str) -> dict[str, Any]:
        response = self.http_client.get(f"/ppt/jobs/{job_id}/results")
        response.raise_for_status()
        return self._normalize_results_payload(response.json())
