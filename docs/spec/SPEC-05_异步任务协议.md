# SPEC-05 · 异步任务协议（横切）

> **验收文档**：[`../acceptance/ACC-05_异步任务协议_验收.md`](../acceptance/ACC-05_异步任务协议_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 目标：把 sidecar 的 `{jobId, pollUrl, pollIntervalMs}` + `{status, step, progress, message, done}` 收成 **edu_ai 全系统统一的长任务协议**，前端只有一套进度组件。
> 上游（已核对）：`app/api/generate-classroom/route.ts`（提交 202）、`[jobId]/route.ts`（轮询）、`lib/server/classroom-job-store.ts`（job 状态机）。
> 关联：SPEC-03（parse-pdf 是同步，见 §6）、SPEC-04（generate-classroom 是 job）、`Edu_AI/api/src/app/pipeline/`（承接方，已存在）。

---

## 1. 统一协议（sidecar 已实现，edu_ai 对齐）

### 1.1 提交响应（202）

```json
{ "jobId": "<id>", "status": "queued", "step": "queued",
  "message": "...", "pollUrl": "<abs url>", "pollIntervalMs": 5000 }
```

### 1.2 轮询响应（200）

```json
{ "jobId","status","step","progress","message","pollUrl","pollIntervalMs":5000,
  "scenesGenerated","totalScenes","result?","error?","done": true|false }
```

- `status: 'queued' | 'running' | 'succeeded' | 'failed'`（`ClassroomGenerationJobStatus`，已核对）。
- `step`：业务步骤枚举（generate-classroom 为 `ClassroomGenerationStep | 'queued' | 'failed'`，SPEC-04 §3）。
- `progress`: 0-100。
- `done = status ∈ {succeeded, failed}`（轮询终止条件）。
- 完成时 `result` 携带业务产物（generate-classroom 为 `GenerateClassroomResult`）。

### 1.3 job 状态机（`classroom-job-store.ts`，已核对）

```
queued → running →(onProgress 多次更新 step/progress/message)→ succeeded(step=completed,progress=100)
                                                             ↘ failed(step=failed, error)
超时保护：running 且 30min 无进度更新 → 判定 stale → failed
```

---

## 2. edu_ai 承接设计

### 2.1 任务表（edu_ai 统一 `jobs` / 复用 `pipeline` 任务模型）

| 列 | 说明 |
| --- | --- |
| `edu_job_id` | edu_ai 自己的任务 id（对前端暴露的稳定 id）|
| `kind` | `parse_pdf` / `generate_classroom` / `export_pptx` / `render_video` / `kg_build` ... |
| `sidecar_job_id` | 若委托 sidecar，存其 jobId；否则空 |
| `status/step/progress/message` | 镜像统一协议 |
| `result_ref` / `error` | 产物引用 / 错误 |
| `owner / created_at / updated_at` | 归属与时间 |

### 2.2 适配（sidecar job ↔ edu_ai job）

- edu_ai 提交生成 → 建 `edu_job`(status=queued) → 调 sidecar 得 `sidecar_job_id` → 存映射。
- **轮询由 edu_ai 后端做**（不让前端直连 sidecar，保权限/隐藏 sidecar）：edu_ai 后台/或前端轮 edu_ai → edu_ai 轮 sidecar `pollUrl` → 更新 `edu_job` → 完成时执行落库（SPEC-04 §5/6）后置 `succeeded`。
- **完成语义差异**：sidecar `succeeded` ≠ edu_ai `succeeded`。edu_ai 要在 sidecar 完成后**再做拉媒体+改写url+校验+落库**，全部成功才对前端置 `succeeded`；这一步失败则 edu_ai job=failed（即便 sidecar 成功）。

---

## 3. 前端进度组件（统一一套）

- 输入：edu_ai job 的 `{status, step, progress, message}`。
- 展示：阶段名（step→中文文案映射表）+ 进度条 + `scenesGenerated/totalScenes`（生成类）。
- 轮询：按 `pollIntervalMs`（默认 5000ms），`done` 为真停止。
- 失败：显示 `error`，提供「重试」（重试复用同产物 id，SPEC-04 §6 幂等）。

step→中文映射（generate-classroom）：
```
initializing→初始化 · researching→检索资料 · generating_outlines→生成大纲
generating_scenes→生成场景 · generating_media→生成媒体 · generating_tts→合成配音
persisting→保存 · completed→完成 · failed→失败 · queued→排队中
```

---

## 4. 超时、重试、幂等

| 项 | 规则 |
| --- | --- |
| sidecar stale | 30min 无进度 → sidecar 自判 failed；edu_ai 同步为 failed |
| edu_ai 轮询超时 | 设总超时（生成类 ≥30min），超时置 failed 并可重试 |
| 重试 | 生成类用同 `Stage.id` upsert；解析类幂等按文档哈希去重 |
| 网络抖动 | 轮询失败重试带退避，不立即判 failed |

---

## 5. 错误码约定（edu_ai 对前端）

沿用 sidecar 语义并归一：`MISSING_REQUIRED_FIELD / INVALID_REQUEST / INVALID_URL(SSRF) / INTERNAL_ERROR`，edu_ai 另加 `SIDECAR_UNAVAILABLE / PERSIST_FAILED / VALIDATION_FAILED`（落库校验失败，SPEC-02 §6）。

---

## 6. parse-pdf 的特例（同步 vs job）

- 当前 sidecar `/api/parse-pdf` 是**同步阻塞** route（非 job/poll），可能耗时数分钟（SPEC-03 §3）。
- edu_ai 处理二选一：
  1. **edu_ai 侧包成 job**：edu_ai 建 `edu_job(kind=parse_pdf)`，后台线程/任务里同步调 sidecar（长超时），完成写回 job。前端体验统一。（**推荐**）
  2. 直接长超时同步调用（仅内部批处理场景）。
- 若后续给 sidecar parse-pdf 也套 job 协议，则与 generate-classroom 完全一致——列为可选优化，非本轮必须。

---

## 7. 验收清单

- [ ] generate-classroom 全程通过 edu_ai job 暴露给前端，进度/失败/重试都走统一组件
- [ ] sidecar 成功但 edu_ai 落库失败时，edu_ai job=failed 且有明确 error
- [ ] parse-pdf 以 job 形式呈现（做法 1），前端无需感知同步/异步差异
- [ ] 重试幂等：不产生重复课件/重复入库
