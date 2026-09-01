# Job Center Three-State Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将任务中心收敛为已完成、进行中、失败三种业务状态与唯一主操作，并保证重试请求只有在新任务真实进入执行链路后才返回成功。

**Architecture:** 前端把底层任务状态归一化为三类展示状态，由纯函数统一负责统计、可见性和主操作选择，抽屉只负责渲染和调用 API。后端继续保留“新建重试任务并关联原任务”的台账模型，在 API 边界验证重试任务确实处于可接受状态，并把入队或分发异常转换为明确的非 2xx 响应。

**Tech Stack:** React 18、TypeScript、Zustand、Node test runner、FastAPI、Pydantic、pytest。

---

## 文件结构

- `frontend/src/jobs/jobPresentation.ts`：新增任务中心可见性、三状态统计和唯一主操作的纯函数。
- `frontend/src/jobs/jobPresentation.test.ts`：以真实 `JobRecord` 验证状态映射、取消隐藏和操作选择。
- `frontend/src/jobs/JobCenterDrawer.tsx`：使用纯函数过滤、分组、渲染三个统计项，并显示后端重试错误。
- `backend/src/app/api/jobs.py`：校验新重试任务的接受状态，异常时终止“成功”响应并落失败状态。
- `backend/src/tests/test_jobs_api_v2.py`：验证真实入队成功、分发失败与异常时的 HTTP 语义和台账状态。
- `backend/src/tests/test_job_retry_service.py`：验证非持久化任务会调用原业务提交器并传回原始输入。

### Task 1: 建立前端三状态契约

**Files:**
- Modify: `frontend/src/jobs/jobPresentation.test.ts`
- Modify: `frontend/src/jobs/jobPresentation.ts`

- [ ] **Step 1: 写入失败测试**

在 `jobPresentation.test.ts` 中把旧质量指标断言替换为三状态断言，并加入可见性和唯一操作测试：

```ts
import {
  getJobPrimaryAction,
  isJobCenterVisible,
  presentJobDetail,
  presentJobError,
  summarizeJobs,
} from "./jobPresentation.ts";

test("summarizeJobs reports completed, active, and failed counts", () => {
  const jobs = [
    terminalJob("success", "succeeded", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z"),
    { ...terminalJob("queued", "queued", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z"), finished_at: null },
    { ...terminalJob("running", "running", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z"), finished_at: null },
    terminalJob("failed", "failed", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z"),
    terminalJob("partial", "partially_succeeded", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z"),
    terminalJob("canceled", "canceled", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z"),
  ];

  assert.deepEqual(summarizeJobs(jobs), {
    completedCount: 1,
    activeCount: 2,
    failedCount: 2,
  });
  assert.equal(isJobCenterVisible(jobs[5]), false);
});

test("getJobPrimaryAction returns only the action for the current state", () => {
  assert.equal(getJobPrimaryAction({ ...terminalJob("running", "running", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z"), cancelable: true }), "cancel");
  assert.equal(getJobPrimaryAction(terminalJob("failed", "failed", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z")), "retry");
  assert.equal(getJobPrimaryAction(terminalJob("success", "succeeded", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z"), "#/result"), "open-result");
  assert.equal(getJobPrimaryAction(terminalJob("success-no-result", "succeeded", "2026-08-06T10:00:00.000Z", "2026-08-06T10:00:02.000Z")), null);
});
```

- [ ] **Step 2: 运行测试并确认按预期失败**

Run: `pnpm test -- src/jobs/jobPresentation.test.ts`

Expected: FAIL，提示 `getJobPrimaryAction` 或 `isJobCenterVisible` 尚未导出，且旧 `summarizeJobs` 返回值不匹配。

- [ ] **Step 3: 实现最小纯函数**

在 `jobPresentation.ts` 中导入 `isActiveJob`，以以下契约替换旧质量指标：

```ts
import { isActiveJob, type JobRecord } from "./types";

export type JobStatusSummary = {
  completedCount: number;
  activeCount: number;
  failedCount: number;
};

export type JobPrimaryAction = "cancel" | "retry" | "open-result";

export function isJobCenterVisible(job: JobRecord): boolean {
  return job.status !== "canceled";
}

export function summarizeJobs(jobs: JobRecord[]): JobStatusSummary {
  return {
    completedCount: jobs.filter((job) => job.status === "succeeded").length,
    activeCount: jobs.filter(isActiveJob).length,
    failedCount: jobs.filter(
      (job) => job.status === "failed" || job.status === "partially_succeeded",
    ).length,
  };
}

export function getJobPrimaryAction(
  job: JobRecord,
  resultHash?: string | null,
): JobPrimaryAction | null {
  if (isActiveJob(job) && job.cancelable) return "cancel";
  if (
    (job.status === "failed" || job.status === "partially_succeeded") &&
    job.retryable
  ) return "retry";
  if (job.status === "succeeded" && resultHash) return "open-result";
  return null;
}
```

- [ ] **Step 4: 运行前端纯函数测试**

Run: `pnpm test -- src/jobs/jobPresentation.test.ts`

Expected: PASS，所有 `jobPresentation` 测试通过。

- [ ] **Step 5: 提交三状态契约**

```powershell
git add -- frontend/src/jobs/jobPresentation.ts frontend/src/jobs/jobPresentation.test.ts
git commit -m "test: define job center three-state contract"
```

### Task 2: 收敛任务中心界面与操作

**Files:**
- Modify: `frontend/src/jobs/JobCenterDrawer.tsx`
- Modify: `frontend/src/jobs/jobCenterPlacement.test.ts`

- [ ] **Step 1: 写入失败的界面结构测试**

在 `jobCenterPlacement.test.ts` 增加源码契约测试，防止旧指标和复制功能回归：

```ts
test("the task center renders three status totals and no task id copy action", async () => {
  const drawer = await readFile(new URL("./JobCenterDrawer.tsx", import.meta.url), "utf8");

  assert.match(drawer, /<span>已完成<\/span>/);
  assert.match(drawer, /<span>进行中<\/span>/);
  assert.match(drawer, /<span>失败<\/span>/);
  assert.doesNotMatch(drawer, /需关注率|平均耗时|复制任务 ID|navigator\.clipboard/);
  assert.match(drawer, /getJobPrimaryAction/);
  assert.match(drawer, /isJobCenterVisible/);
});
```

- [ ] **Step 2: 运行测试并确认旧界面导致失败**

Run: `pnpm test -- src/jobs/jobCenterPlacement.test.ts`

Expected: FAIL，命中“需关注率”“平均耗时”或“复制任务 ID”。

- [ ] **Step 3: 修改抽屉数据与统计渲染**

在 `JobCenterDrawer.tsx` 导入 `getJobPrimaryAction` 和 `isJobCenterVisible`，先过滤已取消任务，再分组和统计：

```tsx
const visibleJobs = useMemo(
  () => jobs.filter(isJobCenterVisible),
  [jobs],
);
const courseGroups = useMemo(
  () => buildJobCourseGroups(visibleJobs, {
    currentCourseId,
    currentCourseTitle,
    courseTitles,
  }),
  [courseTitles, currentCourseId, currentCourseTitle, visibleJobs],
);
const statusSummary = useMemo(() => summarizeJobs(visibleJobs), [visibleJobs]);
```

顶部统计无条件渲染三个格子：

```tsx
<section className="job-center-quality" aria-label="后台任务状态概览">
  <div><span>已完成</span><strong>{statusSummary.completedCount}</strong></div>
  <div><span>进行中</span><strong>{statusSummary.activeCount}</strong></div>
  <div><span>失败</span><strong>{statusSummary.failedCount}</strong></div>
</section>
```

课程分组改为 `active`、`failed`、`completed`，不再把取消任务放入完成组；标题依次为“进行中”“失败”“已完成”。删除 `formatDuration`。

- [ ] **Step 4: 只渲染唯一主操作并透传错误**

`runAction` 的异常分支改为：

```tsx
} catch (reason) {
  setActionError(
    reason instanceof Error ? reason.message : "任务操作失败，请稍后重试",
  );
}
```

`JobCard` 根据纯函数只渲染一个动作：

```tsx
const primaryAction = getJobPrimaryAction(job, resultHash);

<div className="job-card__actions">
  {primaryAction === "cancel" ? (
    <button type="button" disabled={busy} onClick={() => void onAction(job, "cancel")}>
      {busy ? "处理中…" : "取消"}
    </button>
  ) : primaryAction === "retry" ? (
    <button type="button" disabled={busy} onClick={() => void onAction(job, "retry")}>
      {busy ? "处理中…" : "重试"}
    </button>
  ) : primaryAction === "open-result" && resultHash ? (
    <a href={resultHash}>打开结果</a>
  ) : null}
</div>
```

- [ ] **Step 5: 运行任务中心前端测试**

Run: `pnpm test -- src/jobs/jobPresentation.test.ts src/jobs/jobCenterPlacement.test.ts`

Expected: PASS，两份测试文件全部通过。

- [ ] **Step 6: 提交界面修改**

```powershell
git add -- frontend/src/jobs/JobCenterDrawer.tsx frontend/src/jobs/jobCenterPlacement.test.ts
git commit -m "feat: simplify job center states and actions"
```

### Task 3: 阻止后端返回假重试成功

**Files:**
- Modify: `backend/src/tests/test_jobs_api_v2.py`
- Modify: `backend/src/app/api/jobs.py`

- [ ] **Step 1: 写入失败响应测试**

在 `test_jobs_api_v2.py` 增加返回失败任务和抛出分发异常两种测试：

```py
def test_retry_rejects_a_job_that_did_not_enter_execution(client, monkeypatch):
    active_client, _ = client
    failed = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"requirement": "重试课堂"},
    )
    job_store.update_job(failed.edu_job_id, status=JobStatus.FAILED)

    async def reject_dispatch(job, **kwargs):
        return job_store.update_job(
            job.edu_job_id,
            status=JobStatus.FAILED,
            message="当前任务未能重新提交",
            error_message="当前任务未能重新提交",
        )

    monkeypatch.setattr(jobs_api, "dispatch_retry_job", reject_dispatch)
    response = active_client.post(f"/api/jobs/{failed.edu_job_id}/retry")

    assert response.status_code == 409
    assert response.json()["detail"] == "当前任务未能重新提交"


def test_retry_marks_new_job_failed_when_dispatch_raises(client, monkeypatch):
    active_client, _ = client
    failed = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={"requirement": "重试课堂"},
    )
    job_store.update_job(failed.edu_job_id, status=JobStatus.FAILED)

    async def broken_dispatch(job, **kwargs):
        raise RuntimeError("worker unavailable")

    monkeypatch.setattr(jobs_api, "dispatch_retry_job", broken_dispatch)
    response = active_client.post(f"/api/jobs/{failed.edu_job_id}/retry")
    listed = active_client.get("/api/jobs").json()["items"]
    retry = next(item for item in listed if item.get("retry_of_job_id") == failed.edu_job_id)

    assert response.status_code == 503
    assert response.json()["detail"] == "重试任务未能提交，请稍后再试"
    assert retry["status"] == "failed"
    assert retry["error_code"] == "RETRY_DISPATCH_FAILED"
```

- [ ] **Step 2: 运行测试并确认当前 API 错误地返回 202 或遗留排队任务**

Run: `backend/src/.venv/Scripts/python.exe -m pytest backend/src/tests/test_jobs_api_v2.py -q`

Expected: FAIL；第一例得到 202，第二例虽得到 500 但新任务仍是 `queued`。

- [ ] **Step 3: 增加接受状态校验与异常落账**

在 `jobs.py` 增加：

```py
RETRY_ACCEPTED_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.SUCCEEDED,
}


def _accepted_retry(job: EduJob) -> dict:
    if job.status not in RETRY_ACCEPTED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=job.message or job.error_message or "重试任务未能进入执行队列",
        )
    return _public_job(job)
```

重写端点主体，使持久化和业务分发路径都经过 `_accepted_retry`，并在异常时落失败状态：

```py
    retried: EduJob | None = None
    try:
        durable_retried = retry_durable_job(
            original,
            owner_user_id=owner,
            task_store=get_task_store(),
        )
        if durable_retried is not None:
            return _accepted_retry(durable_retried)
        retried = retry_job(edu_job_id, owner_user_id=owner)
        dispatched = await dispatch_retry_job(
            retried,
            auth_token=credentials.credentials if credentials else "",
            current_user=current_user,
            course_storage_manager=courses_api._svc._get_manager(),
        )
        return _accepted_retry(dispatched)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        if retried is not None:
            update_job(
                retried.edu_job_id,
                status=JobStatus.FAILED,
                step="retry_dispatch_failed",
                progress=100,
                message="重试任务未能提交，请稍后再试",
                error_code="RETRY_DISPATCH_FAILED",
                error_message=str(exc),
            )
        raise HTTPException(
            status_code=503,
            detail="重试任务未能提交，请稍后再试",
        ) from exc
```

- [ ] **Step 4: 运行后端重试 API 测试**

Run: `backend/src/.venv/Scripts/python.exe -m pytest backend/src/tests/test_jobs_api_v2.py -q`

Expected: PASS，所有重试、取消和权限测试通过。

- [ ] **Step 5: 提交后端重试契约**

```powershell
git add -- backend/src/app/api/jobs.py backend/src/tests/test_jobs_api_v2.py
git commit -m "fix: reject job retries that are not dispatched"
```

### Task 4: 验证非持久化任务的真实业务分发

**Files:**
- Create: `backend/src/tests/test_job_retry_service.py`

- [ ] **Step 1: 写入业务分发测试**

新建 `test_job_retry_service.py`，直接调用重试分发器并替换业务提交器以记录真实参数：

```py
import pytest

from app.services import job_retry_service, job_store
from app.services.job_store import JobKind


@pytest.mark.asyncio
async def test_classroom_retry_calls_original_business_submitter(monkeypatch, tmp_path):
    from core import Config

    monkeypatch.setattr(Config, "STORAGE_ROOT", tmp_path)
    retried = job_store.create_job(
        kind=JobKind.GENERATE_CLASSROOM,
        owner_user_id="teacher-a",
        course_id="course-1",
        input_summary={
            "requirement": "围绕勾股定理生成课堂",
            "enable_web_search": True,
            "enable_tts": False,
        },
    )
    captured = {}

    async def fake_submit(**kwargs):
        captured.update(kwargs)
        return kwargs["existing_job"]

    monkeypatch.setattr(
        job_retry_service,
        "submit_classroom_generation_job",
        fake_submit,
    )

    dispatched = await job_retry_service.dispatch_retry_job(
        retried,
        auth_token="token",
        current_user={"username": "teacher-a"},
        course_storage_manager=object(),
    )

    assert dispatched.edu_job_id == retried.edu_job_id
    assert captured["course_id"] == "course-1"
    assert captured["requirement"] == "围绕勾股定理生成课堂"
    assert captured["enable_web_search"] is True
    assert captured["enable_tts"] is False
    assert captured["existing_job"].edu_job_id == retried.edu_job_id
```

- [ ] **Step 2: 运行真实业务分发契约测试**

Run: `backend/src/.venv/Scripts/python.exe -m pytest backend/src/tests/test_job_retry_service.py -q`

Expected: PASS，说明非持久化课堂任务确实调用原业务提交器，而不是只创建台账记录。

- [ ] **Step 3: 提交业务分发测试**

```powershell
git add -- backend/src/tests/test_job_retry_service.py
git commit -m "test: verify job retry business dispatch"
```

### Task 5: 完整验证

**Files:**
- Verify: `frontend/src/jobs/*`
- Verify: `backend/src/app/api/jobs.py`
- Verify: `backend/src/tests/test_jobs_api_v2.py`

- [ ] **Step 1: 运行前端完整单元测试**

Run: `pnpm test`

Working directory: `Edu_AI`

Expected: PASS，0 failed。

- [ ] **Step 2: 运行前端检查与生产构建**

Run: `pnpm lint`

Working directory: `Edu_AI`

Expected: exit 0。

Run: `pnpm build`

Working directory: `Edu_AI`

Expected: exit 0，Vite 生成生产资源。

- [ ] **Step 3: 运行后端相关测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_jobs_api_v2.py -q`

Working directory: `backend/src`

Expected: PASS，0 failed。

- [ ] **Step 4: 检查差异与需求覆盖**

Run: `git diff --check`

Expected: exit 0，无空白错误。

逐项确认：顶部仅三个数字；取消任务隐藏；每条任务最多一个操作；不存在复制任务 ID；失败分发不返回 202；真实重试任务具有新的 ID 和 `retry_of_job_id`。
