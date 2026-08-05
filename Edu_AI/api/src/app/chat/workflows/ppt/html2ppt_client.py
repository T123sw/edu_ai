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
    ):
        self.base_url = str(base_url or "").rstrip("/")
        self.http_client = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout_seconds,
            trust_env=False,
        )

    def _absolute(self, value: Any) -> Any:
        text = str(value or "").strip()
        if not text or text.startswith(("http://", "https://")):
            return value
        return f"{self.base_url}/{text.lstrip('/')}"

    def create_job(
        self,
        *,
        content_markdown: str,
        theme_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.http_client.post(
            "/ppt/jobs",
            json={
                "content_markdown": content_markdown,
                "theme_id": theme_id,
                "metadata": metadata,
            },
        )
        response.raise_for_status()
        return dict(response.json())

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        response = self.http_client.get(f"/ppt/jobs/{job_id}")
        response.raise_for_status()
        return dict(response.json())

    def get_job_results(self, job_id: str) -> dict[str, Any]:
        response = self.http_client.get(f"/ppt/jobs/{job_id}/results")
        response.raise_for_status()
        payload = dict(response.json())
        results = dict(payload.get("results") or {})
        for key in (
            "html_full_url",
            "html_url",
            "pptx_url",
            "manifest_url",
            "fragment_url",
        ):
            if key in results:
                results[key] = self._absolute(results[key])
        payload["results"] = results
        return payload

