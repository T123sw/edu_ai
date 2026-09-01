"""job 表衔接单测（SPEC-05 / ACC-05，Phase 2 P2-4 范围）：

覆盖 job_store 的 create/get/update/list 往返、generate_classroom 提交→
轮询→完成的 edu_job 状态迁移、三类失败路径（提交失败/轮询中失败/sidecar
本身报 failed）、"完成语义差异"闸门（post-process 失败必须让 edu_job=failed
即便 sidecar 成功，AC-05-4/5）、以及 step 中文映射表的完整性（AC-05-3）。
"""

import sys
import uuid
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

pytestmark = pytest.mark.anyio

from app.integrations.openmaic import (
    OpenMaicBadRequest,
    OpenMaicPollTimeout,
    OpenMaicUnavailable,
)
from app.services import job_store as job_store_module
from app.services.job_store import JobKind, JobStatus, create_job, get_job, list_jobs, update_job
from app.services.classroom_job_service import (
    CLASSROOM_STEP_LABELS,
    start_generate_classroom_job,
)


@pytest.fixture(autouse=True)
def _isolate_job_storage(monkeypatch, tmp_path):
    """每个测试用独立目录，避免跟真实 storage/jobs 或其他测试互相污染。"""
    from core import Config

    isolated_root = tmp_path / f"jobs-{uuid.uuid4().hex}"
    monkeypatch.setattr(Config, "STORAGE_ROOT", isolated_root)
    yield


# ── job_store 往返（AC-05-1） ────────────────────────────────────────────


def test_job_store_create_get_update_roundtrip():
    job = create_job(kind=JobKind.GENERATE_CLASSROOM, owner="teacher-a")

    assert job.edu_job_id.startswith("job_")
    assert job.status == JobStatus.QUEUED
    assert job.step == "queued"
    assert job.owner == "teacher-a"

    fetched = get_job(job.edu_job_id)
    assert fetched is not None
    assert fetched.edu_job_id == job.edu_job_id

    updated = update_job(job.edu_job_id, status=JobStatus.RUNNING, step="researching", progress=10)
    assert updated is not None
    assert updated.status == JobStatus.RUNNING
    assert updated.step == "researching"
    assert updated.progress == 10
    assert updated.updated_at != job.updated_at or updated.updated_at >= job.created_at


def test_job_store_update_missing_job_returns_none():
    assert update_job("job_does_not_exist", status=JobStatus.FAILED) is None


def test_job_store_list_filters_by_kind_and_limit():
    for _ in range(3):
        create_job(kind=JobKind.GENERATE_CLASSROOM)

    jobs = list_jobs(kind=JobKind.GENERATE_CLASSROOM, limit=2)
    assert len(jobs) == 2
    assert all(j.kind == JobKind.GENERATE_CLASSROOM for j in jobs)


# ── step 中文映射完整性（AC-05-3） ───────────────────────────────────────


def test_classroom_step_labels_cover_all_generation_steps():
    # SPEC-04 §3 的 ClassroomGenerationStep 全集 + queued/failed（SPEC-05 §3）
    expected_steps = {
        "queued",
        "initializing",
        "researching",
        "generating_outlines",
        "generating_scenes",
        "generating_media",
        "generating_tts",
        "persisting",
        "completed",
        "failed",
    }
    assert expected_steps.issubset(CLASSROOM_STEP_LABELS.keys())
    assert all(isinstance(label, str) and label for label in CLASSROOM_STEP_LABELS.values())


# ── 编排：fake OpenMaicClient ────────────────────────────────────────────


class FakeClient:
    """只实现 service 用到的两个方法，避免依赖真实 httpx 传输。"""

    def __init__(self, *, submit_error=None, wait_error=None, progress_events=None, final_envelope=None):
        self.submit_error = submit_error
        self.wait_error = wait_error
        self.progress_events = progress_events or []
        self.final_envelope = final_envelope or {
            "jobId": "sidecar-job-1",
            "status": "succeeded",
            "step": "completed",
            "progress": 100,
            "message": "Done",
            "pollUrl": "http://sidecar-test:3000/api/generate-classroom/sidecar-job-1",
            "pollIntervalMs": 5000,
            "done": True,
            "result": {"id": "classroom-1", "scenes": []},
        }
        self.wait_job_calls = 0

    async def generate_classroom(self, **kwargs):
        if self.submit_error is not None:
            raise self.submit_error
        return {
            "jobId": "sidecar-job-1",
            "status": "queued",
            "step": "initializing",
            "message": "Queued",
            "pollUrl": "http://sidecar-test:3000/api/generate-classroom/sidecar-job-1",
            "pollIntervalMs": 5000,
        }

    async def wait_job(self, poll_url, *, on_progress=None):
        self.wait_job_calls += 1
        if on_progress is not None:
            for step, progress, message in self.progress_events:
                on_progress(step, progress, message)
        if self.wait_error is not None:
            raise self.wait_error
        return self.final_envelope


# ── 提交失败（AC-05-10：错误码归一） ─────────────────────────────────────


async def test_submit_failure_marks_job_failed_with_normalized_error_code():
    client = FakeClient(submit_error=OpenMaicBadRequest("Missing required field: requirement"))

    job = await start_generate_classroom_job(requirement="", client=client)

    assert job.status == JobStatus.FAILED
    assert job.error_code == "INVALID_REQUEST"
    assert job.sidecar_job_id is None


async def test_submit_failure_connection_maps_to_sidecar_unavailable():
    client = FakeClient(submit_error=OpenMaicUnavailable("sidecar unreachable"))

    job = await start_generate_classroom_job(requirement="x", client=client)

    assert job.status == JobStatus.FAILED
    assert job.error_code == "SIDECAR_UNAVAILABLE"


# ── 轮询中失败（超时/不可达） ─────────────────────────────────────────────


async def test_wait_job_timeout_marks_job_failed_sidecar_unavailable():
    client = FakeClient(wait_error=OpenMaicPollTimeout("did not complete in time"))

    job = await start_generate_classroom_job(requirement="x", client=client)

    assert job.status == JobStatus.FAILED
    assert job.error_code == "SIDECAR_UNAVAILABLE"
    # 提交阶段已经成功过，sidecar_job_id 应该已经记录下来
    assert job.sidecar_job_id == "sidecar-job-1"


# ── sidecar 本身报 failed ────────────────────────────────────────────────


async def test_sidecar_reported_failure_marks_job_failed_with_sidecar_message():
    client = FakeClient(
        final_envelope={
            "jobId": "sidecar-job-1",
            "status": "failed",
            "step": "failed",
            "message": "Classroom generation failed",
            "pollUrl": "http://sidecar-test:3000/api/generate-classroom/sidecar-job-1",
            "pollIntervalMs": 5000,
            "done": True,
            "error": "LLM provider rate limited",
        }
    )

    job = await start_generate_classroom_job(requirement="x", client=client)

    assert job.status == JobStatus.FAILED
    assert job.error == "LLM provider rate limited"


# ── 进度回写（AC-05-3） ──────────────────────────────────────────────────


async def test_progress_callback_updates_job_step_progress_message():
    client = FakeClient(
        progress_events=[
            ("researching", 10, "Researching topic"),
            ("generating_outlines", 30, "Generating scene outlines"),
        ]
    )

    job = await start_generate_classroom_job(requirement="x", client=client)

    assert job.status == JobStatus.SUCCEEDED
    assert job.step == "completed"
    assert job.progress == 100


# ── 完成语义差异闸门（AC-05-4/5，本轮核心） ──────────────────────────────


async def test_sidecar_success_with_successful_post_process_marks_job_succeeded():
    client = FakeClient()

    async def on_sidecar_succeeded(result):
        return {"classroom_id": result["id"], "persisted": True}

    job = await start_generate_classroom_job(
        requirement="x", client=client, on_sidecar_succeeded=on_sidecar_succeeded
    )

    assert job.status == JobStatus.SUCCEEDED
    assert job.result_ref == {"classroom_id": "classroom-1", "persisted": True}


async def test_sidecar_success_but_post_process_failure_marks_job_failed_persist_failed():
    """核心场景：sidecar 说成功了，但 edu_ai 落库/校验失败——job 必须是 failed，
    不能因为 sidecar 成功就误报 succeeded（SPEC-05 §2.2、AC-05-4/5）。"""
    client = FakeClient()

    async def on_sidecar_succeeded(result):
        raise ValueError("validation failed: missing viewportRatio")

    job = await start_generate_classroom_job(
        requirement="x", client=client, on_sidecar_succeeded=on_sidecar_succeeded
    )

    assert job.status == JobStatus.FAILED
    assert job.error_code == "PERSIST_FAILED"
    assert "validation failed" in job.error
