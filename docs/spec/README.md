# edu_ai · OpenMAIC 迁移 · 规格文档（SPEC）索引

> 本目录是 **OpenMAIC 迁移**的规格层文档（spec），回答「**具体怎么落地、每个接口/字段/文件长什么样**」。
> 上层文档（不在本目录）：`../../项目总览地图.md`（全貌地图）、`../OpenMAIC复用_实施总纲_2026-06-30.md`（照着干的主计划）、`../OpenMAIC_对比分析与替换方案_v2_2026-06-30.md`（为什么换）、`../课件视频_统一时间线契约与AB演进预留设计_2026-06-30.md`（视频 A→B）。
> **验收层**：每份 `SPEC-0x` 都有对应的 `../acceptance/ACC-0x`（实现什么/验收标准/怎么测）。索引见 [`../acceptance/README.md`](../acceptance/README.md)。三层指针：**地图 ↔ spec ↔ 验收** 互通。
> **spec 与总纲的分工**：总纲说「搬什么、路线」；spec 说「一行行怎么接、字段叫什么、错误怎么处理、验收脚本是什么」。总纲变则 spec 跟。
> 最近更新：2026-07-01 · 状态：草案 v0.1（本轮聚焦「把 OpenMAIC 迁进来」的核心面）

---

## 0. 文档结构（分总分）

```
README.md (本文 = 总)                     ← 范围/术语/约定/横切原则/交叉引用
  ├─ SPEC-00  Web 检索层（Bocha+Tavily）  ← Phase 1.5 前置：Bocha 搜索+Tavily Extract 替换旧 deepsearch+SearxNG+爬虫（先于 Phase 2）
  ├─ SPEC-01  Sidecar 裁剪与部署          ← Phase 0：sidecar 形态、目录裁剪、.env、容器、暴露端点
  ├─ SPEC-02  数据契约 Stage/Scene/Action/Slide   ← 所有阶段共享的地基（分-地基）
  ├─ SPEC-03  ParsePDF 解析迁移           ← Phase 1：/api/parse-pdf 契约 + 替换 scripts/mineru.py
  ├─ SPEC-04  GenerateClassroom 课件生成与内容注入  ← Phase 2：生成入口 + researchContext 注入补丁
  ├─ SPEC-05  异步任务协议                ← 横切：jobId/pollUrl 统一到 edu_ai 任务表
  ├─ SPEC-06  Provider 配置与 BYOK 安全边界  ← 横切：托管优先/忽略客户端 key/SSRF
  ├─ SPEC-07  OpenMaicClient（Python 客户端）  ← edu_ai 侧 httpx 客户端的完整规格
  └─ SPEC-08  前端集成 @openmaic/dsl + renderer  ← Phase 3 起步：引包、播放、聚焦（LessonTimeline 编译器细节仍在时间线文档）
```

> **本轮范围（聚焦「迁移」）**：SPEC-01 ~ SPEC-08。
> **本轮暂不展开**（迁移完成后再补，避免过度设计）：PPTX 导出（Phase 4，见总纲 §5.2 use-export-pptx）、视频 A/B（Phase 5/B，细节已在时间线文档）、旧模块下线执行单（Phase 6，见总纲 §5.1）。这三块在下一轮 spec 补 `SPEC-09 / SPEC-10 / SPEC-11`。

---

## 1. 目标与非目标

**目标**：把 OpenMAIC（`D:\github\OpenMAIC`，Next.js/TS，MIT）的能力迁进 edu_ai（FastAPI + Vite/React），形成：

- 后端一个裁剪版 **Node sidecar**，对 edu_ai 暴露 `parse-pdf / generate-classroom / tts / media/video / verify-*`。
- 前端引入 **`@openmaic/dsl` + `@openmaic/renderer`** 做课件播放与聚焦。
- edu_ai 用 OpenMAIC 的 **`Stage/Scene/Action/Slide`** 作为课件源数据，注入自己的 RAG/教材/知识图谱作为内容来源。

**非目标（本迁移不做）**：数字人/唇形同步；自造一套等价 DSL；把 TS 逻辑重写进 Python；一次性删除旧链路（先影子验证，Phase 6 再删）。

---

## 2. 术语表（全套 spec 通用）

| 术语 | 含义 |
| --- | --- |
| **sidecar** | 裁剪后的 OpenMAIC Node 服务（Next.js），与 edu_ai FastAPI 通过 HTTP 通信。 |
| **Stage / Scene / Action / Slide** | OpenMAIC `@openmaic/dsl` 的课件数据契约。详见 SPEC-02。 |
| **researchContext** | edu_ai 拼装并注入生成流水线的内容来源文本（RAG 片段 + 教材正文 + 知识图谱节点）。上游默认由 web search 产出，**edu_ai 用它做覆盖注入**（SPEC-04）。 |
| **job / poll** | 统一异步任务协议：提交返回 `{jobId, pollUrl, pollIntervalMs}`，轮询返回 `{status, step, progress, message, done, result}`。详见 SPEC-05。 |
| **managed provider** | 运营方在 sidecar `.env` 配好的托管 provider；此时**忽略客户端传入的 key/baseUrl**。详见 SPEC-06。 |
| **BYOK** | Bring Your Own Key，用户在前端配置页自带 provider key。 |
| **LessonTimeline** | 由 `Scene.actions[]` 编译出的显式多轨时间线，视频 A/B 的共享地基（本轮不展开，见时间线文档）。 |

---

## 3. 全局约定（所有 spec 必须遵守）

1. **id 不可变**：`stageId / sceneId / actionId / elementId` 一旦生成即稳定，编辑课件只改内容不换 id。这是聚焦寻址、局部重生成、视频分段/增量重渲的共同前提。
2. **契约以上游为准**：`@openmaic/dsl` 是单一事实源，edu_ai **不复制一份类型定义**，通过引包/生成 stub 消费；后端 Python 侧只做「透传 + 落库」，不重建等价 Pydantic 模型的字段语义（只做最小校验）。
3. **一切长任务走统一 job/poll 协议**（SPEC-05），前端只有一套进度组件。
4. **安全边界与配置页一体**：保留 OpenMAIC 前端配置页 = 一并保留「托管优先 + 忽略客户端 key + SSRF 校验」（SPEC-06），不能只要页面不要边界。
5. **先影子后下线**：新链路验收前，旧 html2ppt / AI_Lecturer 保留不删。
6. **中文默认**：MinerU `language:'ch'`、`languageDirective`、TTS 音色/字体按中文实测。

---

## 4. 迁移与阶段（Phase）对照

| Phase | 主 spec | 验收锚点 |
| --- | --- | --- |
| 0 打底 | SPEC-01 | sidecar 起、`/api/health` 200、`/api/parse-pdf` 解析成功（**已验证 2026-06-30**）|
| 1.5 Web 检索前置 | **SPEC-00** | Bocha 搜索 + Tavily Extract 替换旧 web，入 RAG（Phase 2 前置）|
| 1 解析替换 | SPEC-03（依赖 SPEC-06/07）| RAG 入库改走 MinerU Cloud，结果对齐 |
| 2 课件生成 | SPEC-04（依赖 SPEC-02/05/07）| 用 edu_ai 知识源生成一节结构化课件并落库 |
| 3 交互课堂 | SPEC-08（依赖 SPEC-02）| 前端播一节课，聚焦+旁白同步 |
| 横切 | SPEC-05 / SPEC-06 | 任务协议统一、provider 边界就位 |

依赖关系：**SPEC-02（数据契约）与 SPEC-06/07（客户端/配置）是地基**，其余都依赖它们。建议阅读顺序：`README → 02 → 01 → 06 → 07 → 05 → 03 → 04 → 08`。

---

## 5. 代码落点（edu_ai 侧新增目录约定）

| 位置 | 放什么 | 关联 spec |
| --- | --- | --- |
| `openmaic-sidecar/`（仓库根，fork/submodule）| 裁剪版 OpenMAIC | SPEC-01 |
| `Edu_AI/api/src/app/integrations/openmaic/` | `OpenMaicClient` + 类型 stub + 错误映射 | SPEC-07 |
| `Edu_AI/api/src/app/services/classroom_service.py` | 课件生成编排（拼 researchContext、落库 Stage/Scene）| SPEC-04 |
| `Edu_AI/api/src/app/pipeline/`（已存在）| 承接统一 job/poll 任务模型 | SPEC-05 |
| `Edu_AI/src/openmaic/`（前端）| 引入的 dsl/renderer 封装 + 播放器 | SPEC-08 |

> 具体文件清单在各 spec 内。以上为总览，避免各 spec 各说各话。

---

## 6. 变更记录

| 日期 | 版本 | 变更 |
| --- | --- | --- |
| 2026-07-01 | v0.1 | 建立 spec 目录，写 README(总) + SPEC-01~08(分)，聚焦迁移核心面 |
