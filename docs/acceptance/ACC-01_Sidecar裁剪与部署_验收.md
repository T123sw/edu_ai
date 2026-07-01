# ACC-01 · Sidecar 裁剪与部署 · 验收文档

> 对应 spec：[`../spec/SPEC-01_Sidecar裁剪与部署.md`](../spec/SPEC-01_Sidecar裁剪与部署.md)
> 对应 Phase：0（打底）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §2 阶段路线
> 通用环境：见 [验收 README §2](README.md)
> 状态：✅ 核心已验证（2026-06-30 本机）；容器化 + `.env.example` + 就绪探测待补

---

## 1. 功能范围

**做**：把 OpenMAIC 裁剪成一个只提供后端能力的 Node sidecar，配好最小 `.env`，对 edu_ai 暴露 `health / parse-pdf / generate-classroom / verify-* / server-providers` 等端点，能容器化起服务。

**不做**：前端 UI（在 edu_ai 做）、本地模型权重/GPU、`tts` `media/video` 独立薄封装 route（后置）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定 |
| --- | --- | --- |
| AC-01-1 | sidecar 能启动，`GET /api/health` 返回 200 | ✅ 已过 |
| AC-01-2 | `POST /api/parse-pdf`（providerId=`mineru-cloud`）端到端解析一份真实教材 PDF 成功，返回非空 `text`，公式识别为 LaTeX | ✅ 已过 |
| AC-01-3 | 仓库存在 `.env.example`，键齐全、值留空/占位，真实 `.env` 已 gitignore | ⏳ |
| AC-01-4 | 目录裁剪后 `pnpm build` 通过；被裁目录经 grep 确认无 route 间接引用 | ⏳ |
| AC-01-5 | `docker-compose up` 起 sidecar + edu_ai 同网络，edu_ai 用服务名可访问 sidecar `/api/health` | ⏳ |
| AC-01-6 | sidecar 端口仅内网可达，未直接暴露公网 | ⏳ |
| AC-01-7 | `verify-model` 与 `verify-pdf-provider` 各通过一次 | ⏳ |
| AC-01-8 | 就绪探测：`/api/health` 200 + 1 个 LLM verify + MinerU verify 通过后判为「就绪」；失败时 edu_ai 主应用仍能启动（仅相关功能降级） | ⏳ |

---

## 3. 测试方法

### 3.1 环境准备
按 README §2 起 sidecar（`pnpm dev`），确认 `.env` 已配最小集（1 LLM + `PDF_MINERU_CLOUD_*`）。

### 3.2 用例

**T-01-A 健康检查（对应 AC-01-1）**
```bash
curl --noproxy "localhost,127.0.0.1" -s http://localhost:3000/api/health
# 预期：HTTP 200，JSON body（含 status/ok 语义）
```

**T-01-B 解析冒烟（对应 AC-01-2）**
```bash
curl --noproxy "localhost,127.0.0.1" -s -X POST http://localhost:3000/api/parse-pdf \
  -F "pdf=@./scratchpad/sample_textbook.pdf" \
  -F "providerId=mineru-cloud"
# 预期：200，data.text 非空；data.formulas[].latex 有 LaTeX；data.metadata.pageCount>0
# 注意：MinerU 云端可能耗时数分钟，curl 加 --max-time 1200
```

**T-01-C .env.example 完整性（对应 AC-01-3）**
- 检查仓库含 `openmaic-sidecar/.env.example`，逐键比对 SPEC-01 §4 最小集与扩展集；`git check-ignore openmaic-sidecar/.env` 命中。

**T-01-D 裁剪后构建（对应 AC-01-4）**
```bash
# 删任何目录前：确认无 route 引用
grep -rE "from '@/(<待删目录>)" app/api lib packages   # 预期：空
pnpm build                                             # 预期：构建成功
```

**T-01-E 容器互通（对应 AC-01-5/6）**
```bash
docker-compose up -d
# 在 edu_ai 后端容器内：
curl -s http://openmaic-sidecar:3000/api/health        # 预期 200
# 宿主机公网口探测 sidecar 端口：预期不可直接访问（仅内网）
```

**T-01-F provider 校验（对应 AC-01-7）**
```bash
curl --noproxy "localhost,127.0.0.1" -s -X POST http://localhost:3000/api/verify-model      -H 'Content-Type: application/json' -d '{...provider/model...}'   # 预期 通过
curl --noproxy "localhost,127.0.0.1" -s -X POST http://localhost:3000/api/verify-pdf-provider -H 'Content-Type: application/json' -d '{"providerId":"mineru-cloud"}'  # 预期 通过
```

**T-01-G 就绪探测降级（对应 AC-01-8）**
- 故意停 sidecar → 启 edu_ai 后端 → 预期：主应用正常起，解析/生成入口置灰并提示「解析服务不可用」，不崩溃。

---

## 4. 回归 / 边界 / 失败用例

| 用例 | 操作 | 预期 |
| --- | --- | --- |
| 代理拦截 | 不加 `--noproxy` 直连 localhost | 502（已知坑，证明必须 --noproxy）|
| 无 pdf | parse-pdf 不带 pdf 字段 | 400 MISSING_REQUIRED_FIELD |
| 非 multipart | parse-pdf 用 JSON | 400 INVALID_REQUEST |
| 错误 MinerU 前缀 | 只配 `PDF_MINERU_*` 不配 `PDF_MINERU_CLOUD_*` | 解析失败/走错 provider（证明前缀坑）|

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 | |
| 日期 | |
| 结论 | AC-01-1/2 已过（2026-06-30）；其余待补 |
| 遗留 | 容器化、.env.example、就绪探测 |
