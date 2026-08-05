"""OpenMaicClient —— edu_ai 后端调用 OpenMAIC sidecar 的 httpx 客户端。

见 docs/spec/SPEC-07。本轮（Phase 2 P2-3）聚焦 `generate_classroom` /
`poll_job` / `wait_job` + 错误映射；`parse_pdf`（Phase 1 已用 Python 直连
绕过，SPEC-07 §3 D5）、`verify_*`/`server_providers`/`tts`/`generate_video`
（Phase 5/6 或按需）本轮不做，留出扩展位。
"""

from __future__ import annotations

import inspect
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Union

import anyio
import httpx

from .errors import (
    OpenMaicBadRequest,
    OpenMaicError,
    OpenMaicJobNotFound,
    OpenMaicPollTimeout,
    OpenMaicServerError,
    OpenMaicSSRFRejected,
    OpenMaicUnavailable,
)
from .types import JobEnvelope

log = logging.getLogger("openmaic.client")

OnProgress = Callable[[str, int, str], Union[None, Awaitable[None]]]


def _default_base_url() -> str:
    return os.getenv("OPENMAIC_BASE_URL", "http://localhost:3000")


@dataclass
class OpenMaicConfig:
    """见 SPEC-07 §1。所有超时单位秒。"""

    base_url: str = field(default_factory=_default_base_url)
    api_key: str = ""
    connect_timeout: float = 10.0
    request_timeout: float = 60.0
    parse_timeout: float = 20 * 60
    poll_interval: float = 5.0
    max_poll_seconds: float = 40 * 60
    retries: int = 2


def _map_http_error(status_code: int, error_code: Optional[str], message: str) -> OpenMaicError:
    """按 HTTP 状态码映射（sidecar 的 errorCode 在 400/404 都可能是
    INVALID_REQUEST，无法单独区分，见 errors.py 顶部说明）。"""
    if status_code == 404:
        return OpenMaicJobNotFound(message, status_code=status_code, sidecar_error=error_code)
    if status_code == 403:
        return OpenMaicSSRFRejected(message, status_code=status_code, sidecar_error=error_code)
    if status_code == 400:
        return OpenMaicBadRequest(message, status_code=status_code, sidecar_error=error_code)
    if status_code >= 500:
        return OpenMaicServerError(message, status_code=status_code, sidecar_error=error_code)
    return OpenMaicError(message, status_code=status_code, sidecar_error=error_code)


class OpenMaicClient:
    """封装 sidecar 调用；单例连接池由调用方持有（见 `__init__.py` 的
    `get_openmaic_client()`），也可直接实例化（测试用 `transport=` 注入
    `httpx.MockTransport`）。"""

    def __init__(
        self,
        config: Optional[OpenMaicConfig] = None,
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.config = config or OpenMaicConfig()
        # trust_env=False：本机常见 HTTP 代理会拦截对 localhost 的请求
        # （见 openmaic-sidecar-run-notes），sidecar 只在内网/本机访问，不需要代理。
        self._client = httpx.AsyncClient(trust_env=False, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OpenMaicClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def health(self) -> bool:
        try:
            resp = await self._client.get(
                f"{self.config.base_url.rstrip('/')}/api/health",
                timeout=self.config.connect_timeout,
            )
            return resp.status_code == 200
        except (httpx.TransportError, httpx.TimeoutException):
            return False

    async def generate_classroom(
        self,
        *,
        requirement: str,
        research_context: Optional[str] = None,
        pdf_content: Optional[dict[str, Any]] = None,
        enable_web_search: bool = False,
        enable_image: bool = False,
        enable_video: bool = False,
        enable_tts: bool = False,
        agent_mode: str = "default",
    ) -> JobEnvelope:
        """POST /api/generate-classroom —— 只提交，返回 202 信封（含
        jobId/pollUrl）；等待完成用 `wait_job`（SPEC-05 §6）。"""
        body: dict[str, Any] = {
            "requirement": requirement,
            "enableWebSearch": enable_web_search,
            "enableImageGeneration": enable_image,
            "enableVideoGeneration": enable_video,
            "enableTTS": enable_tts,
            "agentMode": agent_mode,
        }
        if research_context:
            # 依赖 SPEC-04 §4 sidecar 补丁（docs/spec/patches/001）。
            body["researchContext"] = research_context
        if pdf_content is not None:
            body["pdfContent"] = pdf_content

        data = await self._request_json(
            "POST",
            "/api/generate-classroom",
            json=body,
            timeout=self.config.request_timeout,
            retryable=True,
            kind="generate_classroom",
        )
        return data  # type: ignore[return-value]

    async def poll_job(self, poll_url: str) -> JobEnvelope:
        """GET {pollUrl}，单次轮询。"""
        data = await self._request_json(
            "GET",
            poll_url,
            timeout=self.config.request_timeout,
            retryable=True,
            absolute=True,
            kind="poll_job",
        )
        return data  # type: ignore[return-value]

    async def get_classroom(self, classroom_id: str) -> dict[str, Any]:
        """GET /api/classroom?id={classroom_id} —— 取完整 `{id, stage, scenes,
        createdAt}`。**必须在 job 成功后单独调用**：job 信封的 `result` 字段
        只有 `{classroomId, url, scenesCount}`（sidecar
        `lib/server/classroom-job-store.ts` 的
        `markClassroomGenerationJobSucceeded` 只存这三个字段）——SPEC-04 §1.2
        写的"完成时 result 含完整 GenerateClassroomResult"跟这份真实源码不
        一致，已按源码实测结果订正（真实生成一份课件、核对 job 文件内容
        后确认），见 SPEC-04 §1.2 的更新说明与 SPEC-07 §3 的方法列表。
        """
        data = await self._request_json(
            "GET",
            f"/api/classroom?id={classroom_id}",
            timeout=self.config.request_timeout,
            retryable=True,
            kind="get_classroom",
        )
        classroom = data.get("classroom") if isinstance(data, dict) else None
        if not isinstance(classroom, dict):
            raise OpenMaicServerError(f"GET /api/classroom returned no classroom for id={classroom_id}")
        return classroom

    async def download_media(self, url: str) -> tuple[bytes, Optional[str]]:
        """下载 sidecar 生成的媒体文件（目前只用于配音 audioUrl 迁移，见
        `classroom_media.migrate_classroom_speech_audio`）。`url` 必须是
        `self.config.base_url` 下的地址——调用方负责这个前置判断，这里只管下载。
        返回 `(内容字节, content-type)`。"""
        try:
            resp = await self._client.get(url, timeout=self.config.request_timeout)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise OpenMaicUnavailable(f"sidecar media unreachable: {exc}") from exc

        if not (200 <= resp.status_code < 300):
            raise OpenMaicServerError(
                f"failed to download media from sidecar: HTTP {resp.status_code} url={url}",
                status_code=resp.status_code,
            )
        return resp.content, resp.headers.get("content-type")

    async def wait_job(
        self,
        poll_url: str,
        *,
        on_progress: Optional[OnProgress] = None,
    ) -> JobEnvelope:
        """循环轮询至 `done`；每次回调 `on_progress(step, progress, message)`
        供调用方写回 edu_ai 任务表。超过 `max_poll_seconds` 未完成则抛
        `OpenMaicPollTimeout`。"""
        deadline = time.monotonic() + self.config.max_poll_seconds
        interval = self.config.poll_interval

        while True:
            envelope = await self.poll_job(poll_url)
            step = envelope.get("step", "")
            progress = envelope.get("progress", 0)
            message = envelope.get("message", "")

            if on_progress is not None:
                maybe_awaitable = on_progress(step, progress, message)
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable

            if envelope.get("done"):
                return envelope

            if time.monotonic() >= deadline:
                raise OpenMaicPollTimeout(
                    f"generate-classroom job did not complete within "
                    f"{self.config.max_poll_seconds:.0f}s (last step={step!r}, progress={progress})"
                )

            poll_interval_ms = envelope.get("pollIntervalMs")
            interval = (poll_interval_ms / 1000) if poll_interval_ms else interval
            await anyio.sleep(interval)

    async def _request_json(
        self,
        method: str,
        url_or_path: str,
        *,
        timeout: float,
        retryable: bool,
        kind: str,
        json: Optional[dict[str, Any]] = None,
        absolute: bool = False,
    ) -> dict[str, Any]:
        url = url_or_path if absolute else f"{self.config.base_url.rstrip('/')}{url_or_path}"
        attempts = (self.config.retries + 1) if retryable else 1
        last_error: Optional[OpenMaicError] = None

        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                headers = (
                    {"Authorization": f"Bearer {self.config.api_key}"}
                    if self.config.api_key
                    else None
                )
                resp = await self._client.request(
                    method, url, json=json, headers=headers, timeout=timeout
                )
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                elapsed = time.monotonic() - started
                last_error = OpenMaicUnavailable(f"sidecar unreachable: {exc}")
                log.warning(
                    "openmaic_client_call kind=%s attempt=%s/%s status=unavailable elapsed=%.2fs",
                    kind,
                    attempt,
                    attempts,
                    elapsed,
                )
                if attempt < attempts:
                    await anyio.sleep(0.5 * attempt)
                    continue
                raise last_error from exc

            elapsed = time.monotonic() - started

            if 200 <= resp.status_code < 300:
                data = resp.json()
                job_id = data.get("jobId") if isinstance(data, dict) else None
                log.info(
                    "openmaic_client_call kind=%s attempt=%s/%s status=%s job_id=%s elapsed=%.2fs",
                    kind,
                    attempt,
                    attempts,
                    resp.status_code,
                    job_id,
                    elapsed,
                )
                return data

            try:
                payload = resp.json()
            except ValueError:
                payload = {}
            error_code = payload.get("errorCode") if isinstance(payload, dict) else None
            message = (
                (payload.get("error") if isinstance(payload, dict) else None)
                or resp.text[:300]
                or f"HTTP {resp.status_code}"
            )
            mapped = _map_http_error(resp.status_code, error_code, message)
            log.warning(
                "openmaic_client_call kind=%s attempt=%s/%s status=%s errorCode=%s elapsed=%.2fs",
                kind,
                attempt,
                attempts,
                resp.status_code,
                error_code,
                elapsed,
            )

            if isinstance(mapped, OpenMaicServerError) and attempt < attempts:
                last_error = mapped
                await anyio.sleep(0.5 * attempt)
                continue
            raise mapped

        assert last_error is not None  # pragma: no cover — 循环要么 return 要么 raise
        raise last_error
