# SPEC-01 · Sidecar 裁剪与部署

> **验收文档**：[`../acceptance/ACC-01_Sidecar裁剪与部署_验收.md`](../acceptance/ACC-01_Sidecar裁剪与部署_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 归属：Phase 0（**已验证可行 2026-06-30**）。本 spec 规定 sidecar 的**形态、目录裁剪、.env、容器化、暴露端点、运行方式**。
> 上游：`D:\github\OpenMAIC`（Next.js 16 + Turbopack，pnpm workspace，Node 22）。
> 关联：SPEC-03/04（用它的 route）、SPEC-06（配置/安全）、SPEC-07（Python 客户端调它）。

---

## 1. 形态决策

- **sidecar = 独立 Node 服务**，与 edu_ai FastAPI 通过 HTTP 通信。**不塞进 Python 进程**（TS/Next.js 不可能零成本内嵌）。
- **只保留 API 能力，去掉重叠 UI**：前端在 edu_ai 自己做（引 `@openmaic/dsl+renderer`），sidecar 只当后端能力提供者。
- **全在线 API，无本地权重**：所有能力都是 `XXX_API_KEY + XXX_BASE_URL` 的 provider 对，部署不需要 GPU。

---

## 2. 引入方式（演进两步）

| 阶段 | 方式 | 说明 |
| --- | --- | --- |
| 起步（现在）| **git submodule** 或 vendor 复制到 `edu_ai/openmaic-sidecar/` | 最快能用；前端包用 workspace 路径引用 |
| 稳定后 | fork → 私有 registry 按版本消费 | 便于跟上游 diff、按版本升级 |

> 迁移改动（如 SPEC-04 的 researchContext 注入补丁）必须落在 fork 上并记录 patch，避免 submodule 更新覆盖。建议 patch 用独立 commit + `docs/spec/patches/` 存补丁说明。

---

## 3. 目录裁剪清单

以 `D:\github\OpenMAIC` 顶层为基准（已核对结构）：

| 目录 | 处置 | 理由 |
| --- | --- | --- |
| `app/api/*` | **保留** | 对外端点：`generate-classroom / parse-pdf / classroom / classroom-media / tts(见§5) / verify-* / health / server-providers` |
| `lib/*` | **保留** | 全部生成/解析/provider 逻辑 |
| `packages/@openmaic/*` | **保留** | 前端也要引（dsl/renderer/importer），保持 workspace 完整 |
| `packages/pptxgenjs`、`packages/mathml2omml` | **保留** | Phase 4 导出用 |
| `app/(页面路由，非 api)` | **可裁/保留** | edu_ai 不用其页面 UI；保留不碍事，裁剪减体积。首轮建议保留以免破坏构建，后续按需删 |
| `components/`、`public/`（纯 UI）| 可裁 | 同上，非 API 依赖的可删；**注意 route 可能间接 import，删前 grep** |
| `e2e/`、`eval/`、`tests/`、`community/`、`skills/`、`docs/` | 可删 | 与运行无关 |
| `middleware.ts` | **核对保留** | 可能含 access-code / 安全逻辑（SPEC-06），删前读 |

> **裁剪铁律**：删任何目录前 `grep -r "from '@/<目标>'" app/api lib packages` 确认无被 route 间接引用。首轮以「能起服务 + 端点通」为准，宁保守勿激进。

---

## 4. .env 规格（最小闭环 → 按需扩展）

> 完整变量名对照见 v2 文档 §2.1。**MinerU 云端用前缀 `PDF_MINERU_CLOUD_*`**（不是 `PDF_MINERU_*`，后者是自部署版——本机 Phase 0 已踩过）。

### 4.1 最小启动集（1 个 LLM + MinerU Cloud + 1 个 TTS）

```dotenv
# —— LLM（1 个即可启动）——
DEFAULT_MODEL=deepseek:deepseek-v4-pro     # 注意模型名（Phase 0 坑③）
DEEPSEEK_MODELS=deepseek-v4-pro
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=...

# —— PDF：MinerU Cloud —— （前缀是 CLOUD，别配成自部署版）
PDF_MINERU_CLOUD_API_KEY=...
PDF_MINERU_CLOUD_BASE_URL=...              # 默认 MINERU_CLOUD_DEFAULT_BASE，可留空走默认

# —— TTS（1 个在线，最小闭环可后置到 Phase 2）——
TTS_<provider>_API_KEY=...
TTS_<provider>_BASE_URL=...

NODE_ENV=production                         # 生产开 SSRF 校验（SPEC-06）
```

### 4.2 按需扩展（后续 Phase 开）

- 图片：`IMAGE_<provider>_API_KEY/BASE_URL`（OpenAI/Grok/MiniMax/NanoBanana/Qwen-Image/Seedream）
- 视频：`VIDEO_<provider>_*`（Seedance/Kling/Veo/Sora/MiniMax-Video/Grok-Video/HappyHorse）
- 联网：`WEB_SEARCH_<provider>_*`（Tavily/Brave/Baidu/Bocha/MiniMax）——edu_ai 通常**不开**（用自己的 researchContext，SPEC-04）
- 托管 provider 声明：`server-providers.yml`（SPEC-06）

### 4.3 约定

- `.env` **gitignore**，仓库放 `.env.example`（键齐全、值留空/占位）。
- 托管 key 只放服务端 `.env`；BYOK key 由前端按请求传（SPEC-06）。

---

## 5. 对外暴露端点（edu_ai 调用面）

| 端点 | 方法 | 状态 | 实现 | spec |
| --- | --- | --- | --- | --- |
| `/api/health` | GET | ✅ 开箱 | — | 本文 §7 |
| `/api/parse-pdf` | POST multipart | ✅ 开箱 | `lib/document` + `lib/pdf/*` | SPEC-03 |
| `/api/generate-classroom` | POST | ✅ 开箱（+researchContext 补丁）| `lib/server/classroom-generation.ts` 等 | SPEC-04 |
| `/api/generate-classroom/{jobId}` | GET | ✅ 开箱 | `classroom-job-store` | SPEC-05 |
| `/api/verify-model` `/verify-pdf-provider` `/verify-image-provider` `/verify-video-provider` | POST | ✅ 开箱 | — | SPEC-06 |
| `/api/server-providers` | — | ✅ 开箱 | 托管 provider 声明 | SPEC-06 |
| `/api/tts`（薄封装）| POST | ⚠️ 需包 route | `lib/audio/tts-providers.ts` `generateTTS` | SPEC-04（TTS 由生成流水线内部触发，独立 route 可后置）|
| `/api/media/video`（薄封装）| POST | ⚠️ 需包 route | `lib/media/video-providers.ts` `generateVideo` | Phase 5 |

> `tts` / `media/video` 独立 route 是「薄封装」——首轮**不必单独做**，因为配音/媒体已由 `generate-classroom` 流水线内部完成（`enableTTS/enableImageGeneration/enableVideoGeneration` flag）。独立 route 仅在需要「对已有课件补配音/补视频」时才加。

---

## 6. 容器化

- 用仓库自带 `Dockerfile` + `docker-compose.yml`。
- compose 里 sidecar 与 edu_ai 后端同网络；edu_ai 用服务名（如 `http://openmaic-sidecar:3000`）访问。
- 暴露端口 3000（Next 默认）。**只对 edu_ai 后端内网可达，不直接对公网**（生成/解析是特权能力）。
- 无 GPU、无卷挂大模型权重；仅挂一个媒体产物落盘卷（配音 mp3、生成视频），供 edu_ai 拉取（SPEC-04 §5）。

---

## 7. 健康检查与就绪判定

- `GET /api/health` → 200 视为存活。
- **就绪判定**（edu_ai 启动时探测）：`/api/health` 200 + 至少 1 个 LLM provider `verify-model` 通过 + MinerU `verify-pdf-provider` 通过（SPEC-06）。
- 探测失败：edu_ai 相关功能降级（解析/生成入口置灰），不阻断主应用启动。

---

## 8. 本机运行（Windows + conda，Phase 0 已验证）

- conda env `openmaic`（nodejs 22 + pnpm 10），项目 `D:\github\OpenMAIC`。
- 起服务：`conda run -n openmaic --no-capture-output pnpm dev`（Next 16 Turbopack，:3000）。
- **三个坑**（均已解决，写进部署清单）：
  1. **pnpm postinstall 失败**：vendored 包 build 用 `rm -rf dist`，cmd 无 `rm` → 把 `C:\Program Files\Git\usr\bin` 加进 PATH 再 `pnpm install`。
  2. **本机代理 `127.0.0.1:7897` 拦 localhost**：curl 测试加 `--noproxy "localhost,127.0.0.1"`；PowerShell `Invoke-WebRequest` 不受影响；服务出网调 mineru.net 直连即可。
  3. **DeepSeek 模型名 `deepseek-v4-pro`**：`DEFAULT_MODEL=deepseek:deepseek-v4-pro`，别按旧知识改成 `deepseek-chat`。

---

## 9. 验收清单（Phase 0 Done 的定义）

- [x] sidecar 起，`/api/health` 200
- [x] `/api/parse-pdf`（providerId=`mineru-cloud`）端到端解析一份真实教材 PDF 成功（公式识别为 LaTeX）
- [ ] `.env.example` 键齐全并提交
- [ ] docker-compose 起 sidecar + edu_ai 同网络互通（本机 conda 已通，容器待补）
- [ ] `verify-model` / `verify-pdf-provider` 各通过一次

> 前两项 2026-06-30 本机已过（记忆 `openmaic-sidecar-run-notes`）；后三项在正式接 edu_ai 时补。
