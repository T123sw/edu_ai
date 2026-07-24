# SPEC-07 · OpenMaicClient（Python 客户端）

> **验收文档**：[`../acceptance/ACC-07_OpenMaicClient客户端_验收.md`](../acceptance/ACC-07_OpenMaicClient客户端_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 目标：edu_ai 后端一个 httpx 客户端，封装所有 sidecar 调用，统一超时/重试/错误映射，把 sidecar job 适配到 edu_ai 任务表。
> 落点：`Edu_AI/api/src/app/integrations/openmaic/`（`client.py` + `types.py` + `errors.py`）。
> 关联：SPEC-01（端点）、SPEC-03/04（契约）、SPEC-05（job/poll）、SPEC-06（key）。

---

## 1. 配置

```python
class OpenMaicConfig:
    base_url: str            # http://openmaic-sidecar:3000（容器内网）
    connect_timeout: float = 10.0
    request_timeout: float = 60.0        # 一般请求
    parse_timeout: float = 20 * 60       # parse-pdf 同步阻塞，长超时（SPEC-03 §3）
    poll_interval: float = 5.0           # 遵循 sidecar pollIntervalMs
    max_poll_seconds: float = 40 * 60    # 生成类总超时
    retries: int = 2                     # 幂等 GET/提交的网络重试
```

- 从 edu_ai 配置读取，`base_url` 环境相关。
- **单例/连接池**：复用一个 `httpx.AsyncClient`（keep-alive）。

---

## 2. 类型 stub（`types.py`）

**不重定义 DSL 字段语义**（SPEC-02 §约定）。只建「够用」的 dataclass / TypedDict：

```python
# 解析
class ParsedPdf(TypedDict):
    text: str
    images: list[str]
    tables: NotRequired[list]; formulas: NotRequired[list]; layout: NotRequired[list]
    metadata: NotRequired[dict]      # pageCount / imageMapping / pdfImages ...

# 生成——Stage/Scene 原样透传（dict），只强类型 job 信封
class JobEnvelope(TypedDict):
    jobId: str; status: str; step: str; progress: NotRequired[int]
    message: str; pollUrl: str; pollIntervalMs: int
    scenesGenerated: NotRequired[int]; totalScenes: NotRequired[int]
    result: NotRequired[dict]        # GenerateClassroomResult: {id,url,stage,scenes,...}
    error: NotRequired[str]; done: NotRequired[bool]
```

> `stage/scenes` 保持 `dict`（原样落库 SPEC-02 §4），不拆成 Pydantic 字段，避免跟上游契约漂移。

---

## 3. 方法（异步）

```python
class OpenMaicClient:
    async def health(self) -> bool: ...

    # SPEC-03
    async def parse_pdf(self, *, file: bytes, filename: str,
                        provider_id: str = "mineru-cloud",
                        api_key: str | None = None,
                        base_url: str | None = None) -> ParsedPdf: ...
        # multipart: pdf/providerId/apiKey?/baseUrl? ; 长超时同步调用

    # SPEC-04
    async def generate_classroom(self, *, requirement: str,
                        research_context: str | None = None,      # ← 注入补丁字段
                        pdf_content: dict | None = None,
                        enable_web_search: bool = False,
                        enable_image: bool = False,
                        enable_video: bool = False,
                        enable_tts: bool = False,
                        agent_mode: str = "default") -> JobEnvelope: ...
        # POST /api/generate-classroom → 202 信封（含 jobId/pollUrl）

    # SPEC-05
    async def poll_job(self, poll_url: str) -> JobEnvelope: ...   # 单次 GET
    async def wait_job(self, poll_url: str, *, on_progress=None) -> JobEnvelope: ...
        # 循环 poll 至 done；回调 on_progress(step,progress,message) 供写回 edu_job

    # SPEC-04（补：job 成功后取完整产物）
    async def get_classroom(self, classroom_id: str) -> dict: ...
        # GET /api/classroom?id={classroom_id} → {id,stage,scenes,createdAt}
        # 必须在 wait_job 成功后调用——job 信封的 result 只有
        # {classroomId,url,scenesCount}，不含 stage/scenes（见 SPEC-04 §1.2 订正）

    # SPEC-06
    async def verify_model(self, ...) -> bool: ...
    async def verify_pdf_provider(self, ...) -> bool: ...
    async def server_providers(self) -> dict: ...   # GET /api/server-providers

    # Phase 5（薄封装，后置）
    async def tts(self, ...) -> ...: ...
    async def generate_video(self, ...) -> ...: ...
```

- `generate_classroom` **只提交**，返回信封；等待交给 `wait_job`（可放后台任务，SPEC-05 §6 做法 1）。
- `research_context` → body `researchContext`（依赖 SPEC-04 §4 sidecar 补丁）。

---

## 4. 错误映射（`errors.py`）

sidecar 错误码 → edu_ai 异常：

| sidecar | 触发 | edu_ai 异常 |
| --- | --- | --- |
| 400 MISSING_REQUIRED_FIELD | 缺 requirement/pdf | `OpenMaicBadRequest` |
| 400 INVALID_REQUEST | 无效 jobId / Content-Type | `OpenMaicBadRequest` |
| 403 INVALID_URL | SSRF | `OpenMaicSSRFRejected` |
| 404 | job 不存在 | `OpenMaicJobNotFound` |
| 5xx INTERNAL_ERROR | 解析/生成失败 | `OpenMaicServerError`（可重试）|
| 连接失败/超时 | sidecar 不可达 | `OpenMaicUnavailable` → 上层置 job=failed(SIDECAR_UNAVAILABLE) |

- 重试仅对幂等 + 瞬时错误（连接、5xx、超时），带指数退避；`4xx` 不重试。
- 所有异常携带 sidecar 原始 `error` 文案，供 job.error 展示。

---

## 5. 与 edu_ai 任务表衔接（SPEC-05）

```python
# classroom_service 内
env = await client.generate_classroom(requirement=..., research_context=ctx, enable_tts=True)
edu_job.sidecar_job_id = env["jobId"]
await client.wait_job(env["pollUrl"], on_progress=lambda s,p,m: edu_job.update(step=s, progress=p, message=m))
# 完成后：拉媒体→改写url→校验(SPEC-02§6)→落库(SPEC-04§6)→edu_job=succeeded
```

- **轮询在 edu_ai 后端**，前端只看 edu_job（不直连 sidecar，保权限、隐藏 sidecar）。
- key 传递（BYOK）：上层把用户 key 作为参数传入方法 → 客户端放进 body/form；**客户端不落日志**（SPEC-06 §6）。

---

## 6. 可观测

- 每次调用记 `kind / sidecar_job_id / 耗时 / status`，key 脱敏。
- health 定时探测喂就绪判定（SPEC-01 §7）。

---

## 7. 验收清单

- [ ] `parse_pdf` 长超时下稳定返回，短暂网络抖动自动重试
- [ ] `generate_classroom` + `wait_job` 全程回写 edu_job 进度
- [ ] 各错误码正确映射为对应异常；4xx 不重试、5xx/超时重试
- [ ] BYOK key 不出现在日志
- [ ] sidecar 宕机时上层 job=failed 且文案清晰
