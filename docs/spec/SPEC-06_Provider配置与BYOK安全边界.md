# SPEC-06 · Provider 配置与 BYOK 安全边界（横切）

> **验收文档**：[`../acceptance/ACC-06_Provider与BYOK安全边界_验收.md`](../acceptance/ACC-06_Provider与BYOK安全边界_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 目标：把 OpenMAIC 的 provider 配置 + key 解析 + 安全边界**整体保留**，贯穿所有能力（LLM/PDF/TTS/图片/视频/联网）。
> **一体不可拆**：保留前端配置页 = 一并保留「托管优先 + 忽略客户端 key + SSRF 校验」。只要页面不要边界 = 安全漏洞。
> 上游（已核对）：`lib/server/provider-config.ts`（`isServerConfiguredProvider` / `resolve*ApiKey` / `resolve*BaseUrl` / `getServer*Providers`）、`lib/server/ssrf-guard.ts`（`validateUrlForSSRF`）、`app/api/server-providers/route.ts`、`app/api/verify-*` 四个 route。
> 关联：SPEC-03（parse-pdf 用它）、SPEC-04（生成用它）、SPEC-01（.env / server-providers.yml）。

---

## 1. 混合 key 模型（edu_ai 采用）

两个来源，托管优先：

```
托管 provider（运营方在 .env / server-providers.yml 配）——服务端 key，客户端看不到
        ▲ 优先
BYOK（用户在前端配置页填自己的 key，按请求带给后端）——托管存在时被忽略
```

- **edu_ai 推荐**：运营方配默认（MinerU + 默认 LLM + 默认 TTS），用户可选覆盖/补充自己的 key。
- 两个极端按业务取舍：纯服务端（自营简单、key 不外泄）/ 纯 BYOK（多租户自助）。

---

## 2. 托管 provider 声明（服务端）

两种来源（`provider-config.ts` 已核对）：

1. **环境变量**：`<PREFIX>_API_KEY / <PREFIX>_BASE_URL / <PREFIX>_MODELS / <PREFIX>_ENABLED`（如 `DEEPSEEK_*`、`PDF_MINERU_CLOUD_*`、`TTS_<provider>_*`）。
2. **`server-providers.yml`**（`DEFAULT_FILENAME='server-providers.yml'`）：集中声明托管 provider，覆盖/补充 env。

`section` 维度（`ProviderSection`）：LLM providers / tts / asr / pdf / image / video / webSearch。

`GET /api/server-providers` 返回各 section 的托管 provider 列表（前端据此知道哪些已托管、无需用户填 key）+ `generation.parallelSceneConcurrency`。

---

## 3. key/baseUrl 解析规则（**安全边界核心**）

每次请求解析（`resolvePDFApiKey / resolvePDFBaseUrl / resolveTTSApiKey / resolveApiKey ...`）：

```
managed = isServerConfiguredProvider(section, providerId)
if managed:
    忽略客户端 apiKey / baseUrl，一律用服务端配置   # 防止客户端覆盖托管
else (BYOK):
    用客户端 apiKey / baseUrl
    if 客户端 baseUrl 且 NODE_ENV==='production':
        validateUrlForSSRF(baseUrl) 失败 → 403 INVALID_URL
```

三条铁律（迁移必须原样保留）：
1. **托管优先**：`managed` 时忽略客户端 key/baseUrl。
2. **忽略客户端 key**：托管 provider 的 key 永不来自客户端。
3. **SSRF 校验**：BYOK 且生产环境，客户端 baseUrl 必过 `validateUrlForSSRF`。

---

## 4. SSRF 校验（`ssrf-guard.ts`，已核对）

`validateUrlForSSRF(url): Promise<string|null>`（null=通过，字符串=拒绝原因）。用于任何**客户端可自配 baseUrl**的入口（parse-pdf、TTS、图片、视频的 BYOK 分支）。

- 触发条件：`clientBaseUrl && NODE_ENV==='production'`（`parse-pdf/route.ts` 已示范）。
- 拒绝 → 403 `INVALID_URL`。
- **edu_ai 部署务必 `NODE_ENV=production`**（SPEC-01 §4），否则 SSRF 校验被跳过。
- 若 edu_ai 走「后端代理调 sidecar」，且**不开放用户自配 baseUrl**，SSRF 面收窄，但仍应保留生产开关以防未来开 BYOK。

---

## 5. 连通性校验端点（verify-*）

四个 route 开箱可用：`verify-model` / `verify-pdf-provider` / `verify-image-provider` / `verify-video-provider`（POST）。

- 用途：前端配置页填完 key 实时校验；edu_ai 就绪探测（SPEC-01 §7）。
- edu_ai 前端配置页可直接复用其请求形态。
- （TTS/ASR/webSearch 若无独立 verify，用一次最小真实调用兜底或补 route。）

---

## 6. 前端配置页（保留 OpenMAIC 设计）

- 参考 OpenMAIC `components/settings/*-settings.tsx`（各 provider 分区）。
- edu_ai 前端移植时：读 `GET /api/server-providers` 判断哪些托管（灰掉 key 输入，标「已托管」）；BYOK provider 提供 key 输入 + verify 按钮。
- **key 传递**：BYOK key 按请求随调用带给 edu_ai 后端 → edu_ai 转发 sidecar（或前端→sidecar 经 edu_ai 代理）。key **不落 edu_ai 日志**、不明文久存（会话级/加密存储）。

---

## 7. edu_ai 落地决策清单

| 决策 | 建议默认 | 备注 |
| --- | --- | --- |
| MinerU | 托管 | 运营方统一 key，用户不填 |
| 默认 LLM | 托管 | `deepseek-v4-pro` 等 |
| TTS | 托管 | 中文音色实测后固定 |
| 用户自带 LLM/图片/视频 key | 开放 BYOK（可选）| 需保留 SSRF + verify |
| webSearch | **默认开（主力外部源）** | 与 edu_ai RAG 注入合并叠加、非二选一（SPEC-04 §4）|

---

## 8. 验收清单

- [ ] 托管 provider 场景：客户端传错 key/baseUrl 被忽略，仍用服务端配置成功
- [ ] BYOK 场景：生产环境传内网/非法 baseUrl → 403 INVALID_URL
- [ ] `GET /api/server-providers` 前端据此正确灰掉已托管项
- [ ] verify-* 对错误 key 返回失败、对正确 key 通过
- [ ] BYOK key 不出现在 edu_ai 日志/持久化明文中
