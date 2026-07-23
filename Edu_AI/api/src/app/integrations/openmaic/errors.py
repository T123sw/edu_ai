"""OpenMaicClient 错误映射 —— sidecar HTTP 错误 → edu_ai 异常。

见 docs/spec/SPEC-07 §4。映射以 **HTTP 状态码** 为主（sidecar 的
`errorCode` 在 400/404 两种情况下都可能是 `INVALID_REQUEST`，无法单独区分），
`sidecar_error`/`status_code` 保留原始信息供排查。
"""

from __future__ import annotations

from typing import Optional


class OpenMaicError(Exception):
    """OpenMaicClient 异常基类。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        sidecar_error: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.sidecar_error = sidecar_error


class OpenMaicBadRequest(OpenMaicError):
    """400 MISSING_REQUIRED_FIELD / INVALID_REQUEST（如缺 requirement、无效 jobId）。不重试。"""


class OpenMaicSSRFRejected(OpenMaicError):
    """403 INVALID_URL —— sidecar 的 SSRF 校验拒绝。不重试。"""


class OpenMaicJobNotFound(OpenMaicError):
    """404 —— job 不存在（可能已过期或 jobId 错误）。不重试。"""


class OpenMaicServerError(OpenMaicError):
    """5xx INTERNAL_ERROR —— sidecar 内部失败，可重试。"""


class OpenMaicUnavailable(OpenMaicError):
    """连接失败 / 超时 —— sidecar 不可达，可重试。"""


class OpenMaicPollTimeout(OpenMaicError):
    """wait_job 轮询总时长超过 max_poll_seconds 仍未 done。"""
