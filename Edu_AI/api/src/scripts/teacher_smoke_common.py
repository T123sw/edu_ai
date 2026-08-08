"""Shared helpers for opt-in teacher-platform live smoke checks."""

from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TERMINAL_STATUSES = {"succeeded", "partially_succeeded", "failed", "canceled"}


def request_json(
    base_url: str,
    path: str,
    token: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 600,
) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {path} returned HTTP {exc.code}: {response_body[:1000]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc


def poll_job(
    job_id: str,
    *,
    request_json: Callable[..., dict[str, Any]],
    timeout_seconds: float,
    interval_seconds: float = 2,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        job = request_json("GET", f"/api/jobs/{job_id}")
        if str(job.get("status") or "") in TERMINAL_STATUSES:
            return job
        if time.monotonic() >= deadline:
            raise TimeoutError(f"job {job_id} did not finish within {timeout_seconds:g}s")
        time.sleep(interval_seconds)


def source_fields(source_mode: str, selected_doc_ids: list[str]) -> dict[str, Any]:
    if source_mode == "selected_documents" and not selected_doc_ids:
        raise ValueError("selected_documents requires --selected-doc-id")
    if source_mode != "selected_documents" and selected_doc_ids:
        raise ValueError("selected document ids are only valid in selected_documents mode")
    return {
        "source_mode": source_mode,
        "selected_doc_ids": list(selected_doc_ids),
    }
