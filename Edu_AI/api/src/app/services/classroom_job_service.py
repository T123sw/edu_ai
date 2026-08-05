"""generate_classroom 的 job 化衔接（SPEC-05 §2.2，Phase 2 P2-4）。

把 `OpenMaicClient` 对 sidecar 的提交/轮询适配成 edu_ai 自己的 `EduJob`：
edu_ai 提交 → 建 edu_job(queued) → 调 sidecar 拿 sidecar_job_id → 轮询回写
edu_job 的 step/progress/message → sidecar 完成后再判定 edu_ai 是否成功
（"完成语义差异"，SPEC-05 §2.2、AC-05-4/5：sidecar succeeded ≠ edu_ai
succeeded，还要后处理全部成功才行）。

**本轮范围边界**：`on_sidecar_succeeded` 默认实现只是把 sidecar 原始产物
原样挂到 `result_ref`，还没做「拉媒体→改写url→校验(SPEC-02§6)→落库」——
那是 P2-5 `classroom_service` 的活。这里把「后处理必须成功才能置
succeeded」这条完成语义的**流程闸门**先搭好、连同错误路径(SIDECAR_UNAVAILABLE/
PERSIST_FAILED)一起测好，P2-5 只需要把 `on_sidecar_succeeded` 换成真正的
落库实现，不需要改这层的控制流。
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from app.integrations.openmaic import (
    OpenMaicBadRequest,
    OpenMaicClient,
    OpenMaicError,
    OpenMaicJobNotFound,
    OpenMaicPollTimeout,
    OpenMaicServerError,
    OpenMaicSSRFRejected,
    OpenMaicUnavailable,
    get_openmaic_client,
)
from app.services.job_store import (
    EduJob,
    JobKind,
    JobStatus,
    create_job,
    get_job,
    update_job,
)

log = logging.getLogger("classroom_job_service")

# SPEC-05 §3：sidecar step → 中文文案（供前端进度组件用）。
CLASSROOM_STEP_LABELS: dict[str, str] = {
    "queued": "排队中",
    "initializing": "初始化",
    "researching": "检索资料",
    "generating_outlines": "生成大纲",
    "generating_scenes": "生成场景",
    "generating_media": "生成媒体",
    "generating_tts": "合成配音",
    "persisting": "保存",
    "completed": "完成",
    "failed": "失败",
}

OnSidecarSucceeded = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def _default_on_sidecar_succeeded(result: dict[str, Any]) -> dict[str, Any]:
    return {"sidecar_result": result}


def _error_code_for(exc: OpenMaicError) -> str:
    """SPEC-05 §5：沿用 sidecar 语义并归一，连接类失败统一为 SIDECAR_UNAVAILABLE。"""
    if isinstance(exc, (OpenMaicUnavailable, OpenMaicPollTimeout)):
        return "SIDECAR_UNAVAILABLE"
    if isinstance(exc, OpenMaicBadRequest):
        return exc.sidecar_error or "INVALID_REQUEST"
    if isinstance(exc, OpenMaicSSRFRejected):
        return exc.sidecar_error or "INVALID_URL"
    if isinstance(exc, OpenMaicJobNotFound):
        return exc.sidecar_error or "INVALID_REQUEST"
    if isinstance(exc, OpenMaicServerError):
        return exc.sidecar_error or "INTERNAL_ERROR"
    return exc.sidecar_error or "SIDECAR_UNAVAILABLE"


def _fail(edu_job_id: str, *, step: str, message: str, error: str, error_code: str) -> EduJob:
    updated = update_job(
        edu_job_id,
        status=JobStatus.FAILED,
        step=step,
        message=message,
        error=error,
        error_code=error_code,
    )
    assert updated is not None  # 刚创建的 job，理论上一定存在
    return updated


def create_classroom_job(
    *,
    owner: Optional[str] = None,
    course_id: Optional[str] = None,
    scope_type: str = "course",
    scope_id: Optional[str] = None,
    input_summary: Optional[dict[str, Any]] = None,
) -> EduJob:
    """只建 job（queued），不提交给 sidecar。给需要"立即拿到 edu_job_id 再
    在后台跑生成"的调用方用（P3-2 异步提交），见
    `classroom_service.submit_classroom_generation_job`。"""
    return create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id=owner,
        course_id=course_id,
        scope_type=scope_type,
        scope_id=scope_id,
        input_summary=input_summary,
    )


async def run_generate_classroom_job(
    job: EduJob,
    *,
    requirement: str,
    research_context: Optional[str] = None,
    pdf_content: Optional[dict[str, Any]] = None,
    enable_web_search: bool = False,
    enable_image: bool = False,
    enable_video: bool = False,
    enable_tts: bool = False,
    agent_mode: str = "default",
    client: Optional[OpenMaicClient] = None,
    on_sidecar_succeeded: OnSidecarSucceeded = _default_on_sidecar_succeeded,
) -> EduJob:
    """跑完一份**已存在**的 job（阻塞至 done）：提交 sidecar → 轮询回写 →
    完成语义判定。`start_generate_classroom_job` 是"建 job + 跑"的便捷封装
    （同步等待场景，如测试）；异步提交场景（HTTP 路由 fire-and-forget 一个
    `asyncio.create_task`）应该先 `create_classroom_job()` 拿到 job_id
    立即返回给调用方，再用这个函数在后台跑。
    """
    active_client = client or get_openmaic_client()

    try:
        envelope = await active_client.generate_classroom(
            requirement=requirement,
            research_context=research_context,
            pdf_content=pdf_content,
            enable_web_search=enable_web_search,
            enable_image=enable_image,
            enable_video=enable_video,
            enable_tts=enable_tts,
            agent_mode=agent_mode,
        )
    except OpenMaicError as exc:
        log.warning("generate_classroom submit failed for edu_job=%s: %s", job.edu_job_id, exc)
        return _fail(
            job.edu_job_id,
            step="failed",
            message="Failed to submit classroom generation job",
            error=str(exc),
            error_code=_error_code_for(exc),
        )

    updated = update_job(
        job.edu_job_id,
        sidecar_job_id=envelope.get("jobId"),
        status=JobStatus.RUNNING,
        step=envelope.get("step", "queued"),
        progress=envelope.get("progress", 0),
        message=envelope.get("message", ""),
    )
    assert updated is not None

    def _on_progress(step: str, progress: int, message: str) -> None:
        update_job(
            job.edu_job_id,
            status=JobStatus.RUNNING,
            step=step,
            progress=progress,
            message=message,
        )

    try:
        final_envelope = await active_client.wait_job(envelope["pollUrl"], on_progress=_on_progress)
    except OpenMaicError as exc:
        log.warning("generate_classroom wait_job failed for edu_job=%s: %s", job.edu_job_id, exc)
        return _fail(
            job.edu_job_id,
            step="failed",
            message="Failed while waiting for classroom generation to complete",
            error=str(exc),
            error_code=_error_code_for(exc),
        )

    if final_envelope.get("status") != "succeeded":
        return _fail(
            job.edu_job_id,
            step=final_envelope.get("step") or "failed",
            message=final_envelope.get("message") or "Classroom generation failed",
            error=final_envelope.get("error") or "sidecar reported failure",
            error_code="INTERNAL_ERROR",
        )

    current = get_job(job.edu_job_id)
    if current and current.status == JobStatus.CANCEL_REQUESTED:
        canceled = update_job(
            job.edu_job_id,
            status=JobStatus.CANCELED,
            step="canceled",
            message="任务已取消",
            result_ref=None,
        )
        assert canceled is not None
        return canceled

    # 完成语义差异（SPEC-05 §2.2、AC-05-4/5）：sidecar succeeded 只是前置条件，
    # 还要后处理（P2-5 起=拉媒体+改写url+校验+落库）全部成功才置 edu_job=succeeded；
    # 后处理失败则 edu_job=failed，即便 sidecar 本身成功了。
    try:
        result_ref = await on_sidecar_succeeded(final_envelope.get("result") or {})
    except Exception as exc:  # noqa: BLE001 — 后处理任何异常都必须落 edu_job=failed
        log.exception("post-process after sidecar success failed for edu_job=%s", job.edu_job_id)
        # 鸭子类型而非 import ClassroomValidationError：这层不应依赖具体的落库实现
        # （P2-5 换钩子时这层代码不用动），只看异常是否带 `violations`（SPEC-02 §6
        # 校验失败的标记）来决定归入 VALIDATION_FAILED 还是 PERSIST_FAILED（SPEC-05 §5）。
        error_code = "VALIDATION_FAILED" if getattr(exc, "violations", None) else "PERSIST_FAILED"
        return _fail(
            job.edu_job_id,
            step="failed",
            message="Post-processing failed after sidecar generation succeeded",
            error=str(exc),
            error_code=error_code,
        )

    updated = update_job(
        job.edu_job_id,
        status=JobStatus.SUCCEEDED,
        step="completed",
        progress=100,
        message="Classroom generation completed",
        result_ref=result_ref,
    )
    assert updated is not None
    return updated


async def start_generate_classroom_job(
    *,
    requirement: str,
    research_context: Optional[str] = None,
    pdf_content: Optional[dict[str, Any]] = None,
    enable_web_search: bool = False,
    enable_image: bool = False,
    enable_video: bool = False,
    enable_tts: bool = False,
    agent_mode: str = "default",
    owner: Optional[str] = None,
    client: Optional[OpenMaicClient] = None,
    on_sidecar_succeeded: OnSidecarSucceeded = _default_on_sidecar_succeeded,
) -> EduJob:
    """建 job + 跑完（阻塞至 done）的便捷封装——同步等待场景（测试、手动
    脚本）用这个。HTTP 路由的异步提交场景请用
    `create_classroom_job()` + `run_generate_classroom_job()` 分两步。
    """
    job = create_classroom_job(owner=owner)
    return await run_generate_classroom_job(
        job,
        requirement=requirement,
        research_context=research_context,
        pdf_content=pdf_content,
        enable_web_search=enable_web_search,
        enable_image=enable_image,
        enable_video=enable_video,
        enable_tts=enable_tts,
        agent_mode=agent_mode,
        client=client,
        on_sidecar_succeeded=on_sidecar_succeeded,
    )
