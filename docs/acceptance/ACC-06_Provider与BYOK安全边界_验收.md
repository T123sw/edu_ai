# ACC-06 · Provider 配置与 BYOK 安全边界 · 验收文档

> 对应 spec：[`../spec/SPEC-06_Provider配置与BYOK安全边界.md`](../spec/SPEC-06_Provider配置与BYOK安全边界.md)
> 对应 Phase：横切（服务端随 Phase 0/1，前端配置页随 Phase 3）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §8（BYOK 混合 key 模型）
> 通用环境：见 [验收 README §2](README.md)
> 状态：⏳ 待做
> ⚠️ **安全验收**：本文的失败用例是安全边界，**必须全部通过**，不可跳过。

---

## 1. 功能范围

**做**：保留 OpenMAIC 的「托管优先 + 忽略客户端 key + SSRF 校验」三铁律；`server-providers` 声明托管；`verify-*` 连通性校验；前端配置页混合 key（托管灰掉、BYOK 可填）。

**不做**：本轮不强制开放全部 BYOK provider（按 SPEC-06 §7，MinerU/默认 LLM/TTS 走托管）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定 |
| --- | --- | --- |
| AC-06-1 | 托管场景：客户端传错/伪造 `apiKey`+`baseUrl`，被忽略，仍用服务端配置成功 | |
| AC-06-2 | **BYOK + 生产**：客户端传内网/非法 baseUrl（如 `http://169.254.169.254/`、`http://localhost/`）→ 403 INVALID_URL | |
| AC-06-3 | `GET /api/server-providers` 返回各 section 托管清单；前端据此灰掉已托管项 key 输入 | |
| AC-06-4 | `verify-model/verify-pdf-provider/verify-image-provider/verify-video-provider`：错误 key 失败、正确 key 通过 | |
| AC-06-5 | BYOK key **不出现在** edu_ai 日志、不明文久存（会话级/加密） | |
| AC-06-6 | 部署 `NODE_ENV=production`，SSRF 校验实际生效（非 dev 跳过） | |
| AC-06-7 | 托管 provider 的 key 永不下发到客户端（前端拿不到明文） | |

---

## 3. 测试方法

### 3.1 托管优先/忽略客户端 key（AC-06-1）
```bash
# MinerU 配为托管；客户端故意传假 key + 假 baseUrl
curl --noproxy "localhost,127.0.0.1" -s -X POST http://localhost:3000/api/parse-pdf \
  -F "pdf=@./scratchpad/sample.pdf" -F "providerId=mineru-cloud" \
  -F "apiKey=FAKE" -F "baseUrl=http://evil.example"
# 预期：解析仍成功（用服务端托管配置，假 key/baseUrl 被忽略）
```

### 3.2 SSRF（AC-06-2/6）——**安全必过**
```bash
# 前提：NODE_ENV=production，且该 provider 非托管（走 BYOK 分支）
for u in "http://169.254.169.254/latest/meta-data" "http://localhost:22" "http://127.0.0.1:3000"; do
  curl --noproxy "localhost,127.0.0.1" -s -o /dev/null -w "%{http_code}\n" -X POST \
    http://localhost:3000/api/parse-pdf -F "pdf=@./scratchpad/sample.pdf" \
    -F "providerId=<byok-provider>" -F "baseUrl=$u"
done
# 预期：全部 403（INVALID_URL）
```
- 反向：合法公网 baseUrl → 不被 SSRF 拦（正常进入调用）。

### 3.3 server-providers 前端联动（AC-06-3/7）
```bash
curl --noproxy "localhost,127.0.0.1" -s http://localhost:3000/api/server-providers
# 预期：JSON 含 providers/tts/asr/pdf/image/video/webSearch 各托管清单 + generation.parallelSceneConcurrency
# 前端：已托管项 key 输入框灰掉标"已托管"，且响应体不含托管 key 明文
```

### 3.4 verify-*（AC-06-4）
- 正确 key → 通过；改一位为错 → 失败。四个 route 各测一次。

### 3.5 日志脱敏（AC-06-5）
- BYOK 请求后 grep edu_ai 日志与 DB：断言不含明文 key（只允许脱敏形式如 `sk-***`）。

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| dev 环境（NODE_ENV≠production）| SSRF 跳过（已知）——**证明生产必须设 production** |
| provider 从托管改 BYOK | key 解析随之切换，SSRF 生效 |
| 缺 key 的托管声明 | verify 失败，就绪探测标记该 provider 不可用 |

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | |
| 结论 | **AC-06-2/6/7 为安全红线，未过不得上线** |
| 遗留 | 前端配置页随 Phase 3 |
