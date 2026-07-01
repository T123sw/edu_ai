# ACC-05 · 异步任务协议 · 验收文档

> 对应 spec：[`../spec/SPEC-05_异步任务协议.md`](../spec/SPEC-05_异步任务协议.md)
> 对应 Phase：横切 · 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §8（统一异步任务协议）
> 通用环境：见 [验收 README §2](README.md)
> 状态：⏳ 待做

---

## 1. 功能范围

**做**：edu_ai 长任务（parse_pdf / generate_classroom / …）统一成 `{jobId,pollUrl,pollIntervalMs}`+`{status,step,progress,message,done}`；后端代理轮询 sidecar，前端只看 edu_ai job；一套进度组件；超时/重试/幂等。

**不做**：给 sidecar parse-pdf 加原生 job 协议（可选优化，非本轮）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定 |
| --- | --- | --- |
| AC-05-1 | edu_ai `jobs`/pipeline 表落地：`edu_job_id/kind/sidecar_job_id/status/step/progress/message/result_ref/error/owner` | |
| AC-05-2 | 前端全程只轮询 edu_ai（不直连 sidecar），权限校验生效 | |
| AC-05-3 | generate_classroom 进度经 edu_job 透出，step→中文映射正确显示 | |
| AC-05-4 | **完成语义正确**：sidecar succeeded 后 edu_ai 再做拉媒体+改写+校验+落库，全成功才置 edu_job=succeeded | |
| AC-05-5 | sidecar 成功但 edu_ai 后处理失败 → edu_job=failed（即便 sidecar 成功），error 明确 | |
| AC-05-6 | parse_pdf 以 job 呈现（做法1），前端无同步/异步差异感知 | |
| AC-05-7 | stale：running 30min 无进度 → failed；edu_ai 同步失败 | |
| AC-05-8 | 重试幂等：同任务重试不产生重复课件/重复入库 | |
| AC-05-9 | 轮询网络抖动带退避，不因单次失败立即判 failed | |
| AC-05-10 | 错误码归一：`SIDECAR_UNAVAILABLE/PERSIST_FAILED/VALIDATION_FAILED` + 透传 sidecar 码 | |

---

## 3. 测试方法

### 3.1 契约一致性（AC-05-1/3）
- 单测断言 edu_job 序列化字段与统一协议一致；step→中文映射表全覆盖（`initializing…completed/failed/queued`）。

### 3.2 完成语义（AC-05-4/5）——**重点**
- 集成测试：mock sidecar 返回 succeeded：
  - 后处理全成功 → edu_job=succeeded，`result_ref` 指向落库课件。
  - 后处理某步抛错（媒体拉取失败 / 校验失败）→ edu_job=**failed**，error∈{PERSIST_FAILED,VALIDATION_FAILED}，且**不**误报成功。

### 3.3 parse_pdf job 化（AC-05-6）
- 触发解析 → 前端看到 queued→running→succeeded，与生成任务体验一致。

### 3.4 stale / 超时（AC-05-7）
- mock sidecar 长时间不更新进度 → 30min 后（或调小阈值测试）edu_job 转 failed，message 含 stale 语义。

### 3.5 幂等与退避（AC-05-8/9）
- 同 payload 连续提交两次 → 只产 1 份课件（同 Stage.id upsert）。
- mock 轮询间歇 500/超时 → 客户端退避重试，最终成功；不中途误判 failed。

### 3.6 错误码（AC-05-10）
- 停 sidecar → 提交 → edu_job.error=SIDECAR_UNAVAILABLE。

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| 并发多任务 | 各自 jobId 隔离，进度互不串 |
| 前端刷新页面 | 用 edu_job_id 重新拉取，进度续上 |
| sidecar 重启丢内存 job | edu_ai 侧判定该 sidecar_job 失联→failed 可重试 |

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | |
| 结论 | |
| 遗留 | sidecar parse-pdf 原生 job 化（可选优化）|
