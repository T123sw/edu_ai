# ACC-07 · OpenMaicClient（Python 客户端）· 验收文档

> 对应 spec：[`../spec/SPEC-07_OpenMaicClient_Python客户端.md`](../spec/SPEC-07_OpenMaicClient_Python客户端.md)
> 对应 Phase：横切（Phase 1 起用）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §4.2 后端
> 通用环境：见 [验收 README §2](README.md)
> 状态：⏳ 待做

---

## 1. 功能范围

**做**：`backend/src/app/integrations/openmaic/` 下 httpx 客户端，封装 `health/parse_pdf/generate_classroom/poll_job/wait_job/verify_*/server_providers`，统一超时/重试/错误映射，把 sidecar job 适配到 edu_ai 任务表。

**不做**：`tts/generate_video` 薄封装（后置到 Phase 5）；不重定义 DSL 字段语义（stage/scenes 保持 dict 透传）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定 |
| --- | --- | --- |
| AC-07-1 | 单例 `AsyncClient` 复用连接池；超时按 SPEC-07 §1（parse 20min、生成总 40min、一般 60s） | |
| AC-07-2 | `parse_pdf` 默认 `provider_id='mineru-cloud'`，长超时下稳定返回 | |
| AC-07-3 | `generate_classroom` 提交返回 JobEnvelope（含 jobId/pollUrl），`research_context` 映射到 body `researchContext` | |
| AC-07-4 | `wait_job` 循环轮询至 `done`，`on_progress` 回调回写 edu_job 的 step/progress/message | |
| AC-07-5 | 错误映射正确：400→BadRequest、403→SSRFRejected、404→JobNotFound、5xx→ServerError、连接失败→Unavailable | |
| AC-07-6 | 重试策略：4xx 不重试；5xx/超时/连接失败带指数退避重试（≤配置次数） | |
| AC-07-7 | BYOK key 作为参数传入时进 body/form，且**不落日志**（脱敏） | |
| AC-07-8 | 可观测：每次调用记 `kind/sidecar_job_id/耗时/status`，key 脱敏 | |
| AC-07-9 | stage/scenes 以 dict 透传，不因上游新增字段而报错 | |

---

## 3. 测试方法

落点建议 `backend/tests/test_openmaic_client.py`（pytest-asyncio + `respx`/`httpx.MockTransport` mock sidecar）。

### 3.1 契约与默认值（AC-07-2/3/9）
```python
# mock POST /api/generate-classroom → 202 信封
env = await client.generate_classroom(requirement="x", research_context="CTX")
assert env["jobId"] and env["pollUrl"]
# 断言发出的请求 body 含 "researchContext":"CTX"
# parse_pdf 不传 provider → 请求 form 里 providerId == "mineru-cloud"
```

### 3.2 wait_job 回调（AC-07-4）
```python
# mock 轮询序列：running(30)→running(60)→succeeded(100,done)
seen=[]
await client.wait_job(poll_url, on_progress=lambda s,p,m: seen.append((s,p)))
assert seen[-1][1]==100 and 轮询在 done 处停止
```

### 3.3 错误映射矩阵（AC-07-5/6）
| mock 响应 | 断言异常 | 是否重试 |
| --- | --- | --- |
| 400 MISSING_REQUIRED_FIELD | OpenMaicBadRequest | 否 |
| 403 INVALID_URL | OpenMaicSSRFRejected | 否 |
| 404 | OpenMaicJobNotFound | 否 |
| 500 INTERNAL_ERROR | OpenMaicServerError | 是（退避后成功/最终失败）|
| 连接拒绝/超时 | OpenMaicUnavailable | 是 |

- 用可控 mock 制造「前 2 次 500，第 3 次 200」验证重试成功；「持续 500」验证达上限后抛出。

### 3.4 超时（AC-07-1）
- 断言不同方法采用不同 timeout 配置（parse 长、生成总超时长、一般短）。

### 3.5 脱敏（AC-07-7/8）
- 传入 `api_key="sk-secret"` → 断言日志/记录中只出现脱敏形式，无明文。

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| sidecar 返回未知新字段 | 客户端忽略，不崩（TypedDict total=False / dict）|
| pollUrl 跨主机（容器名）| 客户端按返回的绝对 pollUrl 请求 |
| 并发调用 | 连接池复用，无句柄泄漏 |

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | |
| 结论 | |
| 遗留 | tts/generate_video 封装待 Phase 5 |
