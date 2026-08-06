# Durable Job Execution and Resource Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax (`- [ ]`) for tracking.

**Goal:** 让教师端长耗时任务脱离页面和 API 请求生命周期，在后端重启后能够恢复；只有结果资源按当前用户成功回读后任务才显示成功，并让任务中心精确打开该资源。

**Architecture:** 继续以 `EduJob` 作为用户可见状态账本，以课程文件存储作为最终资源事实源；把现有 SQLite `TaskStore` 扩展成保存可序列化命令、租约和恢复元数据的执行队列。FastAPI lifespan 启动一个有界工作器，通过版本化处理器注册表重建业务依赖、领取任务、续租和执行。资源写入使用稳定资源 ID 和 `source_job_id` 实现幂等发布，完成协调器在 owner 范围内回读成功后才同时终结 `DurableTask` 与 `EduJob`。前端继续只轮询 `/api/jobs`，并通过完整的资源深链恢复结果。

**Tech Stack:** Python 3.11、FastAPI lifespan、SQLite 3、Pydantic v2、pytest；React 18、TypeScript、Vite、Node test runner。

---

## 范围与实施顺序

本计划落实已确认设计：

- `docs/superpowers/specs/2026-08-06-durable-job-execution-and-resource-recovery-design.md`
- `docs/superpowers/decisions/2026-08-06-teacher-p0-p1-decisions.md` 中 D-031

实施分为四个可独立回滚的小结，每个小结完成后提交并推送：

1. 立即恢复资源可见性和前端精确入口；
2. 建立 SQLite 持久任务内核；
3. 迁移所有已进入统一任务中心的长耗时任务；
4. 加入启动对账、故障注入和发布验收。

兼容边界：

- 保留 `/api/jobs`、旧聊天任务查询和现有前端轮询协议；
- 不引入 Redis、Celery、SSE 或 WebSocket；
- 不把 API key、Bearer token、用户密码、服务器绝对路径写入 `command_json`；
- 不承诺模型调用 exactly-once，只承诺命令 at-least-once、同一任务最多发布一个最终课程资源；
- 未迁移到持久处理器的旧任务不得被启动恢复器重新执行。

---

### Task 1: 修复历史资源清单兼容与单文件故障隔离

**Files:**

- Modify: `api/src/core/course_storage.py`
- Modify: `api/src/tests/core/test_course_material_manifest.py`
- Test: `api/src/tests/core/test_course_material_permissions.py`

- [ ] **Step 1: 写出历史 `version` 对象的失败测试**

在 `test_course_material_manifest.py` 增加一个旧报告，其中顶层 `version` 是正文版本对象，并同时写入一条合法资源：

```python
def test_legacy_artifact_version_does_not_hide_other_materials(storage, course_id):
    legacy_path = (
        storage.get_course_dir(course_id)
        / "generated_materials"
        / "reports"
        / "legacy-report.json"
    )
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(
        json.dumps(
            {
                "owner_user_id": "teacher",
                "title": "旧报告",
                "version": {"content": "正文 v2", "revision": 2},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert storage.save_generated_material(
        course_id,
        "quiz",
        "quiz-good",
        {"owner_user_id": "teacher", "title": "正常习题"},
    )

    materials = storage.list_generated_materials(
        course_id,
        owner_user_id="teacher",
    )

    assert {item["material_id"] for item in materials} == {
        "legacy-report",
        "quiz-good",
    }
    legacy = next(item for item in materials if item["material_id"] == "legacy-report")
    assert legacy["version"] == 1
    assert legacy["artifact_version"] == {"content": "正文 v2", "revision": 2}
```

- [ ] **Step 2: 运行测试并确认现状失败**

Run:

```powershell
Set-Location api
pytest src/tests/core/test_course_material_manifest.py -q
```

Expected: 新测试失败；现状会在 `int(dict)` 处抛出 `TypeError`，列表为空。

- [ ] **Step 3: 实现字段兼容和逐文件隔离**

在 `_normalize_material_manifest()` 中只把标量 `version` 解释为 manifest 版本；对象/列表迁移到 `artifact_version`：

```python
raw_version = normalized.get("version")
if isinstance(raw_version, (dict, list)):
    normalized.setdefault("artifact_version", raw_version)
    normalized["version"] = 1
else:
    try:
        normalized["version"] = int(raw_version or 1)
    except (TypeError, ValueError):
        normalized["version"] = 1
```

把 `list_generated_materials()` 的异常边界移动到单个 JSON 文件：

```python
for json_file in type_dir.glob("*.json"):
    try:
        material_data = self._read_json(json_file)
        # normalize, owner and scope checks
    except Exception as exc:
        log.warning(
            "skip invalid generated material",
            extra={"course_id": course_id, "path": str(json_file), "error": str(exc)},
        )
        continue
```

顶层只处理目录不可读等整体故障；不得因为单条资源失败而丢弃已经收集的资源。

- [ ] **Step 4: 验证清单和 owner 隔离**

Run:

```powershell
Set-Location api
pytest src/tests/core/test_course_material_manifest.py src/tests/core/test_course_material_permissions.py -q
```

Expected: 全部通过；无 owner 的历史资源仍不会泄露给认证用户。

- [ ] **Step 5: 提交并推送第一小结的后端修复**

```powershell
git add api/src/core/course_storage.py api/src/tests/core/test_course_material_manifest.py
git commit -m "fix(resources): isolate legacy manifest failures"
git push -u origin codex/durable-job-recovery
```

---

### Task 2: 修复任务中心卡片溢出并生成精确资源深链

**Files:**

- Create: `src/jobs/jobResultTarget.ts`
- Create: `src/jobs/jobResultTarget.test.ts`
- Modify: `src/jobs/JobCenterDrawer.tsx`
- Modify: `src/jobs/jobCenter.css`
- Modify: `src/stitch/teacherRoutes.ts`
- Modify: `src/stitch/teacherRoutes.test.ts`

- [ ] **Step 1: 写出结果链接的纯函数测试**

测试普通生成资源和 AI 课堂分别得到精确目标：

```typescript
test("builds an exact course material target", () => {
  assert.equal(
    getJobResultHash(Object.assign(makeJob(), {
      course_id: "course-a",
      result_ref: {
        resource_type: "course_material",
        course_id: "course-a",
        material_type: "report",
        material_id: "report-1",
      },
    })),
    "#resources?course_id=course-a&material_type=report&material_id=report-1",
  );
});

test("keeps classroom results on the classroom player", () => {
  assert.equal(
    getJobResultHash(Object.assign(makeJob(), {
      result_ref: {
        resource_type: "course_material",
        course_id: "course-a",
        material_type: "classroom",
        material_id: "stage-1",
      },
    })),
    "#classroom-player?course_id=course-a&classroom_id=stage-1",
  );
});
```

同时在 `teacherRoutes.test.ts` 验证可选参数编码：

```typescript
assert.equal(
  buildTeacherCourseHash("resources", "课程 1", {
    material_type: "report",
    material_id: "报告/1",
  }),
  "#resources?course_id=%E8%AF%BE%E7%A8%8B+1&material_type=report&material_id=%E6%8A%A5%E5%91%8A%2F1",
);
```

- [ ] **Step 2: 运行前端测试并确认失败**

Run:

```powershell
npm test -- --test-name-pattern="result|teacher course hash"
```

Expected: 因纯函数和可选查询参数尚不存在而失败。

- [ ] **Step 3: 提取结果目标函数**

`getJobResultHash()` 必须只依赖 `JobRecord`，规则如下：

```typescript
if (!courseId || !materialType || !materialId) return null;
if (materialType === "classroom") {
  return buildClassroomPlayerHash(courseId, materialId);
}
return buildTeacherCourseHash("resources", courseId, {
  material_type: materialType,
  material_id: materialId,
});
```

不能再把任意 `course_material` 只映射到课程资源首页。`JobCenterDrawer.tsx` 导入纯函数，不保留重复实现。

- [ ] **Step 4: 限制抽屉 Grid 和卡片内容宽度**

在 `jobCenter.css` 增加：

```css
.job-center-list {
  grid-template-columns: minmax(0, 1fr);
}

.job-card,
.job-card__top,
.job-card__detail,
.job-card__actions {
  min-width: 0;
  max-width: 100%;
}

.job-card__actions {
  flex-wrap: wrap;
}
```

抽屉内容不得产生横向滚动；长标题、课程 ID、错误信息用换行或省略处理。

- [ ] **Step 5: 运行结果链接与路由测试**

Run:

```powershell
npm test -- --test-name-pattern="result|teacher course hash"
```

Expected: 全部通过。

- [ ] **Step 6: 提交并推送第一小结的前端修复**

```powershell
git add src/jobs src/stitch/teacherRoutes.ts src/stitch/teacherRoutes.test.ts
git commit -m "fix(jobs): expose exact resource recovery links"
git push
```

---

### Task 3: 让课程资源页从深链恢复并选中指定资源

**Files:**

- Create: `src/stitch/api/courseMaterialTarget.ts`
- Create: `src/stitch/api/courseMaterialTarget.test.ts`
- Modify: `src/stitch/pages/CourseResources.tsx`
- Modify: `src/stitch/pages/courseResourcesManagement.test.ts`
- Verify: `src/stitch/api/courses.ts`

- [ ] **Step 1: 写出深链解析和类型过滤测试**

```typescript
test("reads an exact material target from the resources hash", () => {
  assert.deepEqual(
    readCourseMaterialTarget(
      "#resources?course_id=course-a&material_type=report&material_id=report-1",
    ),
    { materialType: "report", materialId: "report-1" },
  );
});

test("rejects incomplete targets", () => {
  assert.equal(
    readCourseMaterialTarget("#resources?course_id=course-a&material_id=report-1"),
    null,
  );
});
```

静态页面契约还要断言 `CourseResources.tsx` 使用解析器，不直接拿 `data[0]` 覆盖合法目标。

- [ ] **Step 2: 运行测试并确认失败**

```powershell
npm test -- --test-name-pattern="material target|resource management"
```

Expected: 新解析器不存在或页面未使用深链，测试失败。

- [ ] **Step 3: 实现深链优先选择**

加载列表时：

1. 解析 `window.location.hash`；
2. 先按 `material_type + material_id` 匹配；
3. 找到后同步选择对应筛选标签；
4. 找不到时调用现有详情接口
   `GET /api/courses/{course_id}/materials/{material_type}/{material_id}`；
5. 详情返回 404 时显示“结果资源不存在或无权访问”，不得静默选中第一条并伪装恢复成功；
6. 没有深链目标时才回退到当前选择或列表第一项。

为避免不同类型中同名 ID 冲突，把前端选择键改为：

```typescript
type MaterialSelection = {
  materialType: string;
  materialId: string;
};
```

- [ ] **Step 4: 验证筛选、置顶、重命名和删除不退化**

```powershell
npm test -- --test-name-pattern="material target|resource management|course material"
```

Expected: 深链测试及现有资源管理测试全部通过。

- [ ] **Step 5: 提交并推送资源恢复小结**

```powershell
git add src/stitch/api/courseMaterialTarget.ts src/stitch/api/courseMaterialTarget.test.ts src/stitch/pages/CourseResources.tsx src/stitch/pages/courseResourcesManagement.test.ts
git commit -m "fix(resources): restore exact generated material from job links"
git push
```

---

### Task 4: 把 `TaskStore` 升级为可迁移的持久执行队列

**Files:**

- Modify: `api/src/app/chat/tasks/task_store.py`
- Create: `api/src/tests/test_durable_task_store.py`
- Modify: `api/src/tests/test_job_store_v2.py`

- [ ] **Step 1: 写出幂等迁移测试**

使用一个只有旧字段的 SQLite 数据库实例，连续初始化两次 `TaskStore`：

```python
def test_schema_migration_is_idempotent_and_preserves_legacy_rows(tmp_path):
    db_path = tmp_path / "tasks.db"
    legacy = TaskStore(str(db_path))
    task_id = legacy.create(workflow_type="legacy", owner_user_id="teacher")
    legacy.close()

    first = TaskStore(str(db_path))
    first.close()
    second = TaskStore(str(db_path))

    assert second.get(task_id, owner_user_id="teacher")["status"] == "pending"
    assert {
        "command_json",
        "handler_version",
        "lease_owner",
        "lease_expires_at",
        "attempt_count",
    } <= second.column_names()
```

- [ ] **Step 2: 写出原子领取、租约和清理测试**

至少实现并完整断言以下测试：

- `test_two_store_instances_cannot_claim_the_same_task`
- `test_expired_lease_returns_to_pending_until_max_attempts`
- `test_expired_lease_fails_after_max_attempts`
- `test_heartbeat_only_extends_the_current_lease_owner`
- `test_terminal_cleanup_never_deletes_pending_or_leased_tasks`
- `test_idempotency_key_is_scoped_by_owner_and_workflow`
- `test_command_payload_rejects_secrets_and_absolute_paths`

两个 store 必须各自持有独立 SQLite 连接，验证数据库事务而不是进程锁。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
Set-Location api
pytest src/tests/test_durable_task_store.py src/tests/test_job_store_v2.py -q
```

Expected: 新 API/字段不存在，测试失败。

- [ ] **Step 4: 实现数据模型和可重复迁移**

在现有 `tasks` 表上追加设计文档字段，不破坏旧查询：

```python
@dataclass(frozen=True)
class DurableTask:
    task_id: str
    workflow_type: str
    handler_version: int
    owner_user_id: str
    course_id: str | None
    scope_type: str
    scope_id: str | None
    command: dict[str, Any] | None
    status: str
    attempt_count: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: float | None
    cancel_requested: bool
```

迁移使用 `PRAGMA table_info(tasks)` 加字段，再创建：

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_tasks_idempotency
ON tasks(owner_user_id, workflow_type, idempotency_key)
WHERE idempotency_key IS NOT NULL AND idempotency_key <> '';
CREATE INDEX IF NOT EXISTS ix_tasks_claim
ON tasks(status, available_at, created_at);
```

时间比较统一使用 UTC epoch float；对外 `created_at` 继续保留 ISO 字符串。

- [ ] **Step 5: 实现队列事务方法**

最低接口：

```python
enqueue(
    *,
    task_id,
    workflow_type,
    handler_version,
    owner_user_id,
    course_id,
    scope_type,
    scope_id,
    command,
    config_snapshot_id,
    idempotency_key,
    max_attempts,
) -> DurableTask
claim_next(*, lease_owner, lease_seconds) -> DurableTask | None
heartbeat(task_id, *, lease_owner, lease_seconds) -> bool
request_cancel(task_id, *, owner_user_id) -> bool
mark_succeeded(task_id, *, lease_owner, result, result_ref) -> bool
mark_partially_succeeded(task_id, *, lease_owner, result, result_ref, error_code, error) -> bool
mark_failed(task_id, *, lease_owner, error_code, error) -> bool
release_for_retry(task_id, *, lease_owner, available_at, error_code, error) -> bool
recover_expired_leases(*, now) -> RecoverySummary
close()
```

`claim_next()` 必须在 `BEGIN IMMEDIATE` 中选择并条件更新，只有提交成功后才返回命令。失败时显式 rollback。

- [ ] **Step 6: 保留旧聊天任务读取语义**

`create/mark_running/mark_complete/get` 仍可读取旧工作流结果；`_cleanup()` 只删除超过 TTL 的终态：

```sql
DELETE FROM tasks
WHERE status IN ('succeeded', 'partially_succeeded', 'failed', 'canceled', 'completed')
  AND updated_at < ?;
```

- [ ] **Step 7: 运行持久队列测试**

```powershell
pytest src/tests/test_durable_task_store.py src/tests/test_job_store_v2.py -q
```

Expected: 全部通过。

- [ ] **Step 8: 提交并推送持久队列内核**

```powershell
git add api/src/app/chat/tasks/task_store.py api/src/tests/test_durable_task_store.py api/src/tests/test_job_store_v2.py
git commit -m "feat(jobs): add durable sqlite task leases"
git push
```

---

### Task 5: 建立版本化命令注册表、工作器和完成协调器

**Files:**

- Create: `api/src/app/services/durable_task_executor.py`
- Create: `api/src/app/services/durable_task_handlers.py`
- Create: `api/src/app/services/job_completion_service.py`
- Create: `api/src/tests/test_durable_task_executor.py`
- Create: `api/src/tests/test_job_completion_service.py`

- [ ] **Step 1: 写出注册表与未知命令测试**

```python
def test_registry_resolves_exact_workflow_and_version():
    registry = DurableTaskHandlerRegistry()
    registry.register("report_direct", 1, handler)
    assert registry.resolve("report_direct", 1) is handler
    with pytest.raises(UnsupportedTaskHandler):
        registry.resolve("report_direct", 2)
```

未知命令最终映射为 `UNSUPPORTED_HANDLER_VERSION`，不可无限重试。

- [ ] **Step 2: 写出工作器领取、心跳和重试测试**

使用短租约和 fake clock，验证：

- worker 只执行自己领取的任务；
- 业务执行超过一个心跳周期时租约仍有效；
- 可重试异常按 `min(2 ** attempt_count, 30)` 秒回退；
- 达到 `max_attempts` 后失败为 `MAX_ATTEMPTS_EXCEEDED`；
- `cancel_requested` 在执行前终结为 canceled；
- worker stop 后不领取新任务，当前任务不被误报失败。

- [ ] **Step 3: 写出资源回读门禁测试**

```python
def test_success_requires_owner_scoped_material_readback(
    coordinator, task, generated_result
):
    coordinator.finish(task, generated_result)
    assert get_job(task.task_id).status == JobStatus.SUCCEEDED

def test_missing_material_becomes_partial_success(
    coordinator, task, missing_ref
):
    coordinator.finish(task, {"saved": True, "result_ref": missing_ref})
    job = get_job(task.task_id)
    assert job.status == JobStatus.PARTIALLY_SUCCEEDED
    assert job.error_code == "RESOURCE_READBACK_FAILED"

def test_wrong_owner_cannot_pass_readback(
    coordinator, task, another_owner_result
):
    coordinator.finish(task, another_owner_result)
    assert get_job(task.task_id).status == JobStatus.PARTIALLY_SUCCEEDED
```

验收的 `result_ref` 必须包含：

```python
{
    "resource_type": "course_material",
    "course_id": "course-a",
    "material_type": "report",
    "material_id": "report-1",
}
```

- [ ] **Step 4: 运行测试并确认失败**

```powershell
pytest src/tests/test_durable_task_executor.py src/tests/test_job_completion_service.py -q
```

Expected: 模块尚不存在，测试失败。

- [ ] **Step 5: 实现命令上下文和注册表**

```python
@dataclass(frozen=True)
class DurableExecutionContext:
    task_id: str
    owner_user_id: str
    course_id: str | None
    config_snapshot_id: str | None
    progress: Callable[[int, str, str], None]
    is_cancel_requested: Callable[[], bool]

class DurableTaskHandler(Protocol):
    def __call__(
        self,
        command: Mapping[str, Any],
        context: DurableExecutionContext,
    ) -> Mapping[str, Any]:
        raise NotImplementedError
```

注册键是 `(workflow_type, handler_version)`；payload 只保存 JSON 基本类型。

- [ ] **Step 6: 实现单任务工作器**

首版默认 `concurrency=1`，避免模型、PPT 和无头浏览器在普通教师部署上争抢资源。工作器主循环：

```python
while not stop_event.is_set():
    task = store.claim_next(
        lease_owner=worker_id,
        lease_seconds=lease_seconds,
    )
    if task is None:
        stop_event.wait(poll_interval)
        continue
    execute_with_heartbeat(task)
```

心跳使用独立线程/定时器，不依赖处理器上报进度。处理器异常按明确的 retryable 分类决定重新排队或终结。

- [ ] **Step 7: 实现完成协调器**

完成顺序固定为：

1. 标准化处理器返回的 `result_ref`；
2. 用 `CourseStorageManager.get_generated_material(course_id, material_type, material_id, owner_user_id=owner)` 回读；
3. 验证 course/type/id/source_job_id；
4. 先保存 DurableTask 的结果引用；
5. 最后更新 `EduJob` 为用户可见终态。

如果内容已生成但资源缺失或不匹配，使用 `partially_succeeded/RESOURCE_READBACK_FAILED`。

- [ ] **Step 8: 运行内核测试**

```powershell
pytest src/tests/test_durable_task_executor.py src/tests/test_job_completion_service.py -q
```

Expected: 全部通过。

- [ ] **Step 9: 提交并推送执行器小结**

```powershell
git add api/src/app/services/durable_task_executor.py api/src/app/services/durable_task_handlers.py api/src/app/services/job_completion_service.py api/src/tests/test_durable_task_executor.py api/src/tests/test_job_completion_service.py
git commit -m "feat(jobs): execute durable commands with leases"
git push
```

---

### Task 6: 把生成工厂八类资源迁移为可序列化命令

**Files:**

- Modify: `api/src/app/services/generation_command.py`
- Create: `api/src/app/services/generation_task_handlers.py`
- Modify: `api/src/app/chat/api/routes_v2.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/report.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/lesson_plan.py`
- Modify: `api/src/app/chat/runtime/agent_tools/handlers/quiz.py`
- Modify: `api/src/app/chat/tasks/background_runner.py`
- Modify: `api/src/app/services/job_retry_service.py`
- Modify: `api/src/tests/test_unified_background_jobs.py`
- Create: `api/src/tests/test_generation_task_handlers.py`

- [ ] **Step 1: 写出“提交后没有进程内闭包”的测试**

对报告、教案、博客、习题、PPT、闪卡、图谱、小游戏参数化：

```python
@pytest.mark.parametrize(
    "resource_type,workflow_type",
    [
        ("report", "report_direct"),
        ("lesson_plan", "lesson_plan_direct"),
        ("blog", "blog_direct"),
        ("quiz", "quiz_direct"),
        ("ppt", "ppt_direct"),
        ("flashcard", "flashcard_direct"),
        ("graph", "graph_direct"),
        ("game", "game_direct"),
    ],
)
def test_generation_submit_persists_recoverable_command(
    service, store, generation_command, resource_type, workflow_type
):
    generation_command.resource_type = resource_type
    job = service.submit(generation_command)
    task = store.get_durable(job.edu_job_id)
    assert task.workflow_type == workflow_type
    assert task.command["resource_type"] == resource_type
    assert task.lease_owner is None
```

测试不得等待 daemon thread。

- [ ] **Step 2: 写出运行时配置快照脱敏测试**

`command_json` 保存配置 revision/snapshot ID 和非敏感运行参数，不能出现 key/token：

```python
serialized = json.dumps(task.command).lower()
assert "sk-" not in serialized
assert "api_key" not in serialized
assert "authorization" not in serialized
```

敏感配置继续由服务器端 `runtime_config_resolver` 按提交时冻结的 revision 解析。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
pytest src/tests/test_generation_task_handlers.py src/tests/test_unified_background_jobs.py -q
```

Expected: `GenerationCommandService.submit` 仍要求 handler 闭包并创建线程，测试失败。

- [ ] **Step 4: 改造 `GenerationCommandService.submit`**

新签名：

```python
def submit(
    self,
    command: GenerationCommand,
    *,
    existing_job: EduJob | None = None,
    retry_of_job_id: str | None = None,
) -> EduJob:
```

在同一提交锁内：

1. 查重；
2. 创建/接受 `EduJob`；
3. 调用 `TaskStore.enqueue`，其中 `task_id=job.edu_job_id`、`workflow_type` 来自资源类型映射、`command=command.model_dump(mode="json")`；
4. 入队失败则把 job 终结为 `TASK_ENQUEUE_FAILED`；
5. 立即返回 queued job，不创建线程。

- [ ] **Step 5: 实现八类处理器注册**

`generation_task_handlers.py` 在执行时按类型构建现有 service，并用 `SimpleNamespace` 重建旧请求契约。PPT 命令必须包含确认后的 outline 与 draft 所需参数；不得依赖浏览器内存中的 React 状态。

所有生成器必须返回标准 `result_ref`。对暂时仍返回 `artifacts` 的旧报告/教案/习题适配器，在处理器边界转换：

```python
{
    "resource_type": "course_material",
    "course_id": command["course_id"],
    "material_type": artifact["artifact_type"],
    "material_id": artifact["id"],
}
```

- [ ] **Step 6: 替换 HTTP 和 Agent 工具的闭包提交**

`routes_v2.py` 和三个 agent tool 只构造可序列化命令。`background_runner.submit_callable_task()` 不再用于课程资源生成；保留兼容读取，但对新的任意 callable 提交抛出明确错误，防止继续扩大不可恢复入口。

- [ ] **Step 7: 统一主动重试**

`POST /api/jobs/{id}/retry` 创建新 `EduJob` 和新 DurableTask：

- 新任务 `retry_of_job_id=旧 ID`；
- 复制脱敏命令快照；
- 使用新 task/job ID；
- 不直接调用旧 runner，不使用 `asyncio.create_task`。

- [ ] **Step 8: 验证八类任务契约**

```powershell
pytest src/tests/test_generation_task_handlers.py src/tests/test_unified_background_jobs.py src/tests/test_jobs_api_v2.py -q
```

Expected: 八类提交、owner 隔离、查重、重试和结果门禁通过。

- [ ] **Step 9: 提交并推送生成工厂迁移**

```powershell
git add api/src/app/services/generation_command.py api/src/app/services/generation_task_handlers.py api/src/app/chat/api/routes_v2.py api/src/app/chat/runtime/agent_tools/handlers api/src/app/chat/tasks/background_runner.py api/src/app/services/job_retry_service.py api/src/tests/test_generation_task_handlers.py api/src/tests/test_unified_background_jobs.py
git commit -m "refactor(generation): enqueue recoverable resource commands"
git push
```

---

### Task 7: 迁移 AI 课堂、视频导出、RAG 文档和视频入库

**Files:**

- Modify: `api/src/app/services/classroom_service.py`
- Modify: `api/src/app/services/classroom_video_export.py`
- Modify: `api/src/app/services/knowledge_document_service.py`
- Modify: `api/src/app/services/video_service.py`
- Create: `api/src/app/services/platform_task_handlers.py`
- Modify: `api/src/app/api/courses.py`
- Modify: `api/src/app/api/video.py`
- Modify: `api/src/app/services/job_retry_service.py`
- Create: `api/src/tests/test_platform_durable_tasks.py`
- Modify: `api/src/tests/test_course_material_jobs.py`

- [ ] **Step 1: 写出四类平台任务快照测试**

参数化断言：

| workflow_type | 必需可序列化字段 | 禁止字段 |
|---|---|---|
| `classroom_generate` | course、requirement、scope、web/TTS 开关 | client、storage manager、auth token |
| `classroom_video_export` | course、classroom ID、内部短期凭据引用 | Bearer token、current_user 对象 |
| `rag_document_index` | course、document ID、pending version、force | rag_system、文件绝对路径 |
| `video_ingest` | course、document/job ID、受控相对文件标识、切片参数 | 上传流、服务器绝对路径 |

测试提交函数返回 queued job，且刷新/请求结束无需保留 event-loop task。

- [ ] **Step 2: 写出任务处理器重建依赖测试**

处理器通过工厂获取：

- `CourseStorageManager`；
- owner 对应的 OpenMAIC、RAG 或 embedding 配置；
- 受控课程目录内的源文件；
- 视频导出所需的服务器侧服务凭据。

对相对路径执行 `resolve()` 和 `relative_to(course_root)`，越界返回 `INVALID_SOURCE_REFERENCE`。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
pytest src/tests/test_platform_durable_tasks.py src/tests/test_course_material_jobs.py -q
```

Expected: 现有实现仍调用 `asyncio.create_task` 或进程线程，测试失败。

- [ ] **Step 4: 迁移 AI 课堂生成**

把 `_build_research_context` 纳入 worker 处理器，使 HTTP 提交不等待 RAG。命令保存 requirement、scope、开关和冻结配置 revision；执行时调用现有 `run_generate_classroom_job` 的核心逻辑。

AI 课堂结果仍发布到 `material_type=classroom`，成功前由完成协调器 owner 回读。

- [ ] **Step 5: 迁移课堂视频导出**

不能把前端 Bearer token 持久化。视频导出脚本访问本地课堂页面时，使用后端签发的短时、单用途导出会话：

```python
export_session_id = export_session_store.issue(
    owner_user_id=owner,
    course_id=course_id,
    classroom_id=classroom_id,
)
```

命令只存 `export_session_id`；恢复时若会话过期，由处理器为同一 owner/course/classroom 重新签发。最终 `result_ref` 指向课堂资源并包含视频附件信息。

- [ ] **Step 6: 迁移 RAG 文档索引**

上传请求只完成受控文件落盘和文档 manifest；索引命令保存 document ID。处理器执行现有 `run_index_job`，进度回调通过 execution context 同步到 DurableTask/EduJob。

- [ ] **Step 7: 迁移视频入库**

保留旧 `/api/video/jobs/{id}` 只读兼容适配器，但事实状态来自 `EduJob`。删除新的进程内任务字典写入和 `asyncio.to_thread` 提交。

- [ ] **Step 8: 替换重试分发**

`job_retry_service.py` 不再按类型启动协程或线程，只调用统一的 `retry_durable_job()`。所有四类任务的旧 job 如果缺少恢复命令，明确返回 `LEGACY_TASK_NOT_RECOVERABLE`。

- [ ] **Step 9: 验证四类任务**

```powershell
pytest src/tests/test_platform_durable_tasks.py src/tests/test_course_material_jobs.py src/tests/test_jobs_api_v2.py -q
```

Expected: 提交、恢复参数、owner 隔离、取消和重试测试全部通过。

- [ ] **Step 10: 提交并推送平台任务迁移**

```powershell
git add api/src/app/services/classroom_service.py api/src/app/services/classroom_video_export.py api/src/app/services/knowledge_document_service.py api/src/app/services/video_service.py api/src/app/services/platform_task_handlers.py api/src/app/api/courses.py api/src/app/api/video.py api/src/app/services/job_retry_service.py api/src/tests/test_platform_durable_tasks.py api/src/tests/test_course_material_jobs.py
git commit -m "refactor(jobs): persist classroom rag and video commands"
git push
```

---

### Task 8: 接入 FastAPI lifespan、启动恢复与双账本对账

**Files:**

- Modify: `api/src/app/bootstrap.py`
- Create: `api/src/app/services/job_reconciliation_service.py`
- Create: `api/src/tests/test_job_worker_lifespan.py`
- Create: `api/src/tests/test_job_reconciliation_service.py`

- [ ] **Step 1: 写出 lifespan 启停测试**

```python
def test_app_lifespan_starts_and_stops_one_worker(monkeypatch):
    worker = FakeWorker()
    app = create_app(worker_factory=lambda: worker)
    with TestClient(app):
        assert worker.started == 1
    assert worker.stopped == 1
```

重复构建 app 不得共享已停止 worker。

- [ ] **Step 2: 写出启动恢复矩阵**

覆盖：

1. pending DurableTask + queued EduJob：保持排队；
2. 过期 leased 且未超次数：恢复 pending，EduJob 显示 queued/正在恢复；
3. 过期 leased 且超次数：双方失败 `WORKER_LOST`；
4. active EduJob 无可恢复命令：失败 `LEGACY_TASK_NOT_RECOVERABLE`；
5. DurableTask 有 result_ref 且 owner 回读成功：直接补齐 succeeded，不调用处理器；
6. EduJob succeeded 但资源回读失败：审计降级为 partially_succeeded；
7. 另一个 owner 的资源不能用于修复任务。

- [ ] **Step 3: 运行测试并确认失败**

```powershell
pytest src/tests/test_job_worker_lifespan.py src/tests/test_job_reconciliation_service.py -q
```

Expected: lifespan 工作者和对账服务尚不存在，测试失败。

- [ ] **Step 4: 实现启动对账**

对账顺序：

```python
store.migrate()
reconciler.finish_published_results()
reconciler.recover_expired_leases()
reconciler.fail_unrecoverable_legacy_jobs()
worker.start()
```

对账修改历史 succeeded 时必须在 `input_summary` 或错误字段保存
`reconciled_from=succeeded`，只允许成功降级，禁止失败升级。

- [ ] **Step 5: 接入 lifespan**

使用 `asynccontextmanager`：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = build_durable_job_runtime()
    runtime.reconcile()
    runtime.start()
    app.state.durable_job_runtime = runtime
    try:
        yield
    finally:
        runtime.stop(grace_seconds=10)
```

测试可注入 worker factory；生产 `create_app()` 使用默认 runtime。

- [ ] **Step 6: 验证生命周期和对账**

```powershell
pytest src/tests/test_job_worker_lifespan.py src/tests/test_job_reconciliation_service.py -q
```

Expected: 全部通过，无未关闭 SQLite 连接或线程警告。

- [ ] **Step 7: 提交并推送启动恢复**

```powershell
git add api/src/app/bootstrap.py api/src/app/services/job_reconciliation_service.py api/src/tests/test_job_worker_lifespan.py api/src/tests/test_job_reconciliation_service.py
git commit -m "feat(jobs): recover durable work on api startup"
git push
```

---

### Task 9: 统一取消、重试和任务中心公开状态

**Files:**

- Modify: `api/src/app/api/jobs.py`
- Modify: `api/src/app/services/job_retry_service.py`
- Modify: `api/src/app/services/job_store.py`
- Modify: `api/src/tests/test_jobs_api_v2.py`
- Modify: `src/jobs/jobStore.test.ts`

- [ ] **Step 1: 写出取消一致性测试**

验证：

- 只能取消本人任务；
- queued 任务立即取消，不再被领取；
- leased 任务设置 cancel_requested，worker 在阶段边界观察；
- 资源已经成功发布后迟到的取消不删除资源、不把 succeeded 改成 canceled；
- DurableTask 和 EduJob 的终态一致。

- [ ] **Step 2: 写出主动重试审计测试**

重试成功返回新 ID，且：

```python
assert retried.retry_of_job_id == original.edu_job_id
assert durable.command == original_durable.command
assert durable.task_id == retried.edu_job_id
assert original.status in TERMINAL_JOB_STATUSES
```

- [ ] **Step 3: 实现 API 协调**

`DELETE/POST cancel` 先 owner 校验，再请求 DurableTask 取消，最后反映到 EduJob；`retry` 从 DurableTask 的脱敏命令复制，不再从可能丢字段的 `input_summary` 猜测。

公开 API 继续只返回 `EduJob`，不暴露 lease owner、command JSON 或内部路径。

- [ ] **Step 4: 运行前后端任务状态测试**

```powershell
Set-Location api
pytest src/tests/test_jobs_api_v2.py src/tests/test_job_store_v2.py -q
Set-Location ..
npm test -- --test-name-pattern="job"
```

Expected: 全部通过。

- [ ] **Step 5: 提交并推送状态协调**

```powershell
git add api/src/app/api/jobs.py api/src/app/services/job_retry_service.py api/src/app/services/job_store.py api/src/tests/test_jobs_api_v2.py src/jobs/jobStore.test.ts
git commit -m "fix(jobs): coordinate durable cancel and retry state"
git push
```

---

### Task 10: 故障注入、全量验证与验收记录

**Files:**

- Create: `api/src/tests/test_durable_job_recovery_e2e.py`
- Modify: `docs/superpowers/decisions/2026-08-06-teacher-p0-p1-decisions.md`
- Create: `docs/superpowers/verification/2026-08-06-durable-job-recovery-verification.md`

- [ ] **Step 1: 实现三处确定性故障注入**

测试使用 hook/event，不使用随机 sleep，并完整实现：

- `test_request_end_does_not_cancel_generation`
- `test_expired_lease_is_recovered_after_worker_restart`
- `test_restart_after_publish_reconciles_without_second_model_call`

第三个测试在“资源已保存、job 尚未终结”处停止 worker；新 runtime 启动后应按 `source_job_id` 找到资源并补齐成功，fake model 调用次数仍为 1。

- [ ] **Step 2: 加入损坏历史资源和精确打开的回归链**

端到端数据：

1. 写入四条 `version=dict` 历史报告；
2. 提交并完成一条新报告；
3. `/api/courses/{id}/materials` 返回新报告，不为零；
4. `/api/jobs/{id}` 返回完整 result_ref；
5. 前端目标 hash 带 type/id；
6. 资源页选择该报告。

- [ ] **Step 3: 运行定向后端套件**

```powershell
Set-Location api
pytest `
  src/tests/test_durable_task_store.py `
  src/tests/test_durable_task_executor.py `
  src/tests/test_job_completion_service.py `
  src/tests/test_generation_task_handlers.py `
  src/tests/test_platform_durable_tasks.py `
  src/tests/test_job_worker_lifespan.py `
  src/tests/test_job_reconciliation_service.py `
  src/tests/test_durable_job_recovery_e2e.py `
  src/tests/test_unified_background_jobs.py `
  src/tests/test_job_store_v2.py `
  src/tests/test_jobs_api_v2.py `
  src/tests/core/test_course_material_manifest.py `
  src/tests/core/test_course_material_permissions.py -q
```

Expected: 全部通过。

- [ ] **Step 4: 运行正式前端测试、lint 和构建**

如果本地 file dependency 尚未构建，先在以下包分别执行其仓库自带构建脚本：

- `../openmaic-sidecar/packages/@openmaic/dsl`
- `../openmaic-sidecar/packages/@openmaic/renderer`
- `../openmaic-sidecar/packages/mathml2omml`
- `../openmaic-sidecar/packages/pptxgenjs`

然后：

```powershell
Set-Location ..
npm test
npm run lint
npm run build
```

Expected:

- 正式前端测试全部通过；
- lint 无 error；
- Vite production build 成功。

- [ ] **Step 5: 运行后端完整测试并诚实记录历史失败**

```powershell
Set-Location api
pytest src/tests -q
```

Expected: 本轮新增/相关测试全绿；若仍有与本轮无关的历史失败，在验收文档记录用例名、基线状态和判定，不为迎合旧断言回退产品决策。

- [ ] **Step 6: 真实浏览器验收**

在 1280、1366、1440、1600、1920px 宽度验证：

- 任务中心抽屉 `scrollWidth <= clientWidth`；
- 每张成功任务卡可见“打开结果”；
- 提交报告后立即刷新页面，任务仍为 queued/running，完成后可精确打开；
- 打开结果后 URL 包含 course/type/id，详情区选中对应资源；
- 后端重启后 queued 任务继续，失租任务显示“正在恢复”；
- 历史坏报告不隐藏新资源；
- 当前用户无法打开其他 owner 的任务或资源。

- [ ] **Step 7: 记录实现中的自主决策**

把实际实现中与原设计存在的细化选择追加到 D-032 起，包括：

- worker 默认并发数与配置方式；
- lease、heartbeat、最大次数；
- 视频导出内部会话策略；
- 旧 active job 的恢复/失败规则；
- 处理器返回兼容策略。

验收文档列出提交、测试输出摘要、浏览器尺寸、已知限制和回滚点。

- [ ] **Step 8: 最终提交并推送**

```powershell
git add api/src/tests/test_durable_job_recovery_e2e.py docs/superpowers/decisions/2026-08-06-teacher-p0-p1-decisions.md docs/superpowers/verification/2026-08-06-durable-job-recovery-verification.md
git commit -m "test(jobs): verify restart-safe resource recovery"
git push
```

- [ ] **Step 9: 最终提交前检查**

```powershell
git status --short
git log --oneline --decorate -12
git diff --check origin/main HEAD
rg -n "TODO|TBD|FIXME|coming soon" `
  api/src/app/services `
  api/src/app/chat/tasks `
  src/jobs `
  src/stitch/pages/CourseResources.tsx `
  docs/superpowers/verification/2026-08-06-durable-job-recovery-verification.md
```

Expected:

- 工作区只剩明确说明的忽略构建产物；
- 每个小结都有独立提交且已推送；
- diff 无空白错误；
- 没有本轮遗留占位符。

---

## 最终验收标准

功能验收：

- 浏览器刷新、路由切换、继续普通对话、关闭任务中心均不会终止后端任务；
- API 进程重启后，pending 自动继续，过期 leased 按最大次数恢复或明确失败；
- 任一生成任务只有在 owner 范围内回读 course/type/id/source_job_id 一致的资源后才是 succeeded；
- 崩溃发生在资源发布之后时，启动对账不会重复调用模型或重复创建资源；
- 一条损坏历史 manifest 不会隐藏同课程其他资源；
- 任务中心能在窄抽屉中看到操作按钮，并精确打开相应资源；
- 主动取消和主动重试具有明确、owner 隔离且可审计的状态。

架构验收：

- 新长耗时任务不持久化 Python closure、请求对象、服务实例、数据库连接、Bearer token、API key 或绝对路径；
- `DurableTask`、`EduJob`、Course Storage 通过同一个 `edu_job_id/source_job_id` 可对账；
- 原子领取在两个独立 SQLite 连接下仍保证单次 claim；
- 心跳不依赖业务进度上报；
- 所有已展示在统一任务中心的长耗时类型都已注册版本化处理器，或明确返回不可恢复错误而不作虚假承诺。

发布门槛：

- 定向后端套件全绿；
- 正式 `npm test`、lint、production build 通过；
- 1280–1920px 真实浏览器验收通过；
- 完整后端测试中的任何非绿项均有基线证据和独立治理记录；
- 决策日志和验收报告已更新，分阶段提交均已推送。
