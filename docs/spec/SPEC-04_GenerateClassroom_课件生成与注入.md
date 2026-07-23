# SPEC-04 · GenerateClassroom 课件生成与内容注入（Phase 2）

> **验收文档**：[`../acceptance/ACC-04_GenerateClassroom课件生成_验收.md`](../acceptance/ACC-04_GenerateClassroom课件生成_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 目标：edu_ai 调 sidecar `/api/generate-classroom`，**注入自己的 RAG/教材/知识图谱作为内容来源**，拿回 `Stage + Scene[]` 落库，正式取代 content_markdown。
> 这是主链路，也是「不照搬 OpenMAIC 流程」的关键点——骨架用它的，知识源用自己的。
> 上游实现（已核对）：`app/api/generate-classroom/route.ts`（72）→ `classroom-job-runner` → `lib/server/classroom-generation.ts`（574）→ `scene-generator.ts`（1746）；轮询 `app/api/generate-classroom/[jobId]/route.ts`。
> 关联：SPEC-02（产出契约）、SPEC-05（job/poll）、SPEC-06（provider/key）、SPEC-07（客户端）。

---

## 0. 本轮 MVP 范围（收窄，2026-07-01 用户拍板）

> 本轮只实现**最小生成闭环**：生成结构化课件并落库，打通 sidecar/客户端/job/校验主链路。媒体与前端后置。**决策（2026-07-01）**：sidecar=vendor 复制；知识源=**LLM 基座 + web search（主）+ RAG 领域补充（叠加，非替代）**；媒体/前端切割。

> **决策补充（2026-07-21，用户拍板）**：
> ① **sidecar 落地 = 方案 A「整体保留完整 OpenMAIC 项目」**——整个 OpenMAIC（Next.js 应用）原样 vendor 进 `edu_ai/openmaic-sidecar/` 子目录（纳入 edu_ai 统一版本管理），**不拆解吸收、不裁剪**；所有对上游的改动收敛到最少接缝（researchContext §4 三处 + env/配置），逐处以 patch 文件归档 `docs/spec/patches/`，保住「能追上游」这条命脉。定性理由：`generate-classroom` 背后是 `@openmaic/dsl` + `scene-generator`(1746) + `renderer` 一整套深度耦合 TS，整体当服务用 = 表面积最小、前端 renderer 白捡、追上游冲突面小；edu_ai(Python) 与 sidecar(Node) 通信**始终是 HTTP**，vendor 不增加运行时耦合，只决定源码归属。将来若需独立扩缩容 / 多产品共享，再把子目录拆成独立部署——因 `OpenMaicClient` 已用 HTTP 隔离，升级近零成本。
> ② **PBL（项目式学习，`app/api/pbl/**` + `lib/pbl/v2`）本轮不接入**——它是独立的多 agent 互动运行时（Instructor / Simulator 流式 SSE 对话 + `PBLProjectV2` 有状态推进 + evaluate 评估），与课件生成是两条产品线；但因 PBL 嵌在 `scene.content.projectV2`、与 DSL 深度耦合，**整包保留不裁**，未来单独立 SPEC 接入。见 §0.1 D9。

**本轮做（MVP）**：

- sidecar **整体保留完整项目（方案 A）** vendor 进 `edu_ai/openmaic-sidecar/` 子目录（补完 SPEC-01 的正式接入；**不拆解、不裁剪**，仅源码接缝改 + patch 归档，详见 §0 决策补充①）+ researchContext 注入补丁（§4）。
- `OpenMaicClient`（SPEC-07，聚焦 `generate_classroom` / `poll_job` / `wait_job` + 错误映射）。
- job 表衔接（SPEC-05，generate-classroom 的 job 化）。
- `classroom_service` 编排：researchContext = **web search（主外部源）+ RAG Top-K 领域补充（带出处）合并** → 生成 → 过 SPEC-02 §6 不变量校验 → 落库 `classrooms` / `classroom_scenes`（同 `Stage.id` 幂等 upsert）。
- 生成 flags：**`enableWebSearch=false`**——web 由 **edu_ai 侧独立 Web 检索层（SPEC-00，Phase 1.5 前置：Bocha 搜索 + Tavily Extract）** 产出并拼进 researchContext；sidecar 自带 web search **保留可用**（可选/兜底）。`enableTTS/Image/Video=false`（媒体后置）。**知识源分层 = LLM 基座 + web（edu_ai 侧 SPEC-00）+ RAG（领域补充，叠加非替代）**；researchContext 为空也应能靠 LLM 生成。Stage/Scene 结构（含 `speech.text`、`spotlight.elementId`）本轮须完整生成。

### 0.1 切割清单（Deferred —— 后续 Phase 必须回来补，不等于删除）

| # | 切割项 | 归属 | 触达的原 spec / AC |
| --- | --- | --- | --- |
| D1 | TTS 配音 + `audioUrl` 改写为 edu_ai 可达地址 | Phase 3 | §5、AC-04-6、SPEC-02 §6 不变量 5 |
| D2 | 图片/视频生成（`enableImage/Video`）+ 媒体落盘迁移 | Phase 5 | §5、SPEC-02 视频/媒体元素 |
| D3 | 前端 `renderer` 完整播放一节课 | Phase 3 | AC-04-8、SPEC-08 |
| D4 | researchContext 领域补充深度：**教材章节 + 知识图谱节点/关系 + 本地化图片说明**（本轮 web + RAG 第一路已接） | Phase 2.5 | §4.3 |
| D5 | 客户端 `parse_pdf` 方法接入（当前 Phase 1 用 Python 直连绕过） | 按需 | SPEC-07 §3 |
| D6 | parse-pdf 的 job 化（当前同步阻塞） | 可选 | SPEC-05 §6 |
| D7 | 旧 EduAgent **deepsearch+爬虫+SearxNG** 链路下线（已被 **SPEC-00 Web 检索层** 替换） | Phase 6 | SPEC-00 §11 |
| D8 | web search **图片**接入（sidecar 当前丢弃 Bocha `image_links` / Tavily images，`WebSearchResult` 无 images 字段）→ 真实配图来源，随媒体一起 | Phase 5 | §4.3、下方说明 |
| D9 | **PBL 项目式学习**（`pbl/v2` Instructor/Simulator 多 agent 互动运行时 + `PBLProjectV2`）接入——vendor 时整包保留不裁，本轮不接入 | 未定（单独立 SPEC） | OpenMAIC `app/api/pbl/**`、`lib/pbl/v2`、`scene.content.projectV2`（§0 决策补充②）|

> **web 层定稿（2026-07-01，用户实测后）**：web 检索独立为 **Phase 1.5 前置层 [SPEC-00](SPEC-00_Web检索层_Bocha搜索与Tavily抽取.md)**：edu_ai 侧 **Bocha 搜索 + Tavily Extract 全文**，替换旧 deepsearch+SearxNG+自建爬虫（用户实测慢/不稳/内容未审查/SearxNG 限流上线扛不住）。产物入 RAG / 供 researchContext。课件生成默认 `enableWebSearch=false`（web 由本层注入）；**sidecar 自带 web search 保留可用**（可选/兜底），web 功能独立于 sidecar。**图片**入库随 Phase 5 媒体（D8）。详见 SPEC-00。

> **D4 是"不照搬"的价值核心**：MVP 先证明注入链路生效（AC-04-1/2/3），拼装深度后补。收口每个后续 Phase 时回填对应切割项。

---

## 1. 端点契约（已核对源码）

### 1.1 提交

```
POST /api/generate-classroom
Content-Type: application/json
body: GenerateClassroomInput (见 §2)
→ 202 { jobId, status, step, message, pollUrl, pollIntervalMs:5000 }
错误：400 MISSING_REQUIRED_FIELD（无 requirement）/ 500 INTERNAL_ERROR
```

`route.ts` 立即 `after(() => runClassroomGenerationJob(...))` 后台跑，`jobId = nanoid(10)`。

### 1.2 轮询

```
GET {pollUrl}  (= /api/generate-classroom/{jobId})
→ 200 {
    jobId, status, step, progress, message, pollUrl, pollIntervalMs:5000,
    scenesGenerated, totalScenes,
    result?,          // 完成时含 GenerateClassroomResult
    error?,
    done: boolean     // status ∈ {succeeded, failed}
  }
错误：400 无效 jobId / 404 job 不存在
```

`status: 'queued'|'running'|'succeeded'|'failed'`；`step` 见 §3。

---

## 2. `GenerateClassroomInput`（已核对源码，行 40-51）

```ts
interface GenerateClassroomInput {
  requirement: string;                 // ★必填：需求文本
  pdfContent?: { text: string; images: string[] };   // 解析后的教材
  enableWebSearch?: boolean;           // edu_ai 默认 true（web 主力，与注入的 researchContext 合并叠加）
  webSearchProviderId?, webSearchApiKey?, baiduSubSources?;
  enableImageGeneration?: boolean;     // L? 媒体
  enableVideoGeneration?: boolean;
  enableTTS?: boolean;                 // L3 配音
  agentMode?: 'default' | 'generate';
  // ⚠️ researchContext ── 上游【没有】此字段，需迁移补丁（§4）
}
```

### 2.1 生成深度 = feature flags（同一条流水线、同一份数据）

| 深度 | flags | 产物 |
| --- | --- | --- |
| L1 只要课件 | 全关 | Slide DSL → 可导 PPTX |
| L2 要讲解 | +actions（默认含）| 互动播放（含聚焦）|
| L3 要成片 | `enableTTS` + `enableImageGeneration`/`enableVideoGeneration` | → 配音/媒体齐备 → MP4（Phase 5）|

---

## 3. 生成步骤与进度（`ClassroomGenerationStep`，已核对）

```
initializing(5) → researching(10) → generating_outlines(15→30)
→ generating_scenes(31→90, 逐 outline) → generating_media(90) → generating_tts(94)
→ persisting(98) → completed(100)
```

进度对象 `ClassroomGenerationProgress { step, progress, message, scenesGenerated, totalScenes? }`。edu_ai 前端进度组件直接吃这套（SPEC-05）。

内部管线（`classroom-generation.ts`）：
```
resolveModel → (可选 web search → researchContext)
→ generateSceneOutlinesFromRequirements(requirements, pdfText, ..., { researchContext, imageGenerationEnabled, videoGenerationEnabled })
→ 逐 outline: generateSceneContent → generateSceneActions → createSceneWithActions
→ (可选) generateMediaForClassroom → (可选) generateTTSForClassroom
→ persistClassroom → GenerateClassroomResult{ id,url,stage,scenes,scenesCount,createdAt }
```

---

## 4. ★内容注入补丁（researchContext）——迁移的核心改动

> **状态：✅ 已完成（2026-07-24，P2-2）**。3 处改动已落地并通过 `tsc --noEmit` + 4 条新增单测（`tests/server/classroom-generation-research-context.test.ts`：仅注入/都不传/web+注入合并/web 无 key 时回退注入）+ 既有 `classroom-generation-retry.test.ts` 4 条零回归。补丁说明见 [`docs/spec/patches/001-researchContext-injection.md`](patches/001-researchContext-injection.md)。

### 4.1 问题

上游 `researchContext` **只能由内部 web search 产生**（`classroom-generation.ts:275` `let researchContext; if (input.enableWebSearch) {...}`），`GenerateClassroomInput` 无 `researchContext` 字段。edu_ai 要注入自己的 RAG/教材/知识图谱，**必须打一个最小补丁**。

### 4.2 补丁（sidecar fork 上改，3 处）

1. `GenerateClassroomInput` 加字段：
   ```ts
   researchContext?: string;   // 外部注入的【领域补充】内容源（RAG/教材/图谱），与 web search 合并叠加，不替代
   ```
2. `route.ts` 透传：body 组装处加 `...(rawBody.researchContext ? { researchContext: rawBody.researchContext } : {})`。
3. `classroom-generation.ts:275` 附近改为「**合并叠加**」（web 主 + 注入补充，不互相短路）：
   ```ts
   let researchContext: string | undefined;
   if (input.enableWebSearch) { /* 原 web search 逻辑，产出 web 结果 */ }
   if (input.researchContext) {                    // ← 注入的领域补充（RAG/教材/图谱）
     researchContext = [researchContext, input.researchContext].filter(Boolean).join('\n\n');
   }
   ```
   下游 `generateSceneOutlinesFromRequirements(..., { researchContext })`（行 342）无需改，天然消费合并后的文本。

> 补丁记录在 `docs/spec/patches/`（SPEC-01 §2）。仅 3 处、非侵入，跟上游 diff 成本低。

### 4.3 知识源分层（§不照搬的关键：骨架用它的，知识源分层混合）

最终喂给生成的上下文 = 三层混合，**edu_ai 只负责拼「注入的领域补充」那一层，web 由 sidecar 内部产生并在 §4.2 合并**：

```
LLM 自身能力            ← 基座：生成主体，无任何外部资料也应能产出合理课件
  +
web（edu_ai 侧 SPEC-00 Web 检索层：Bocha 搜索 + Tavily Extract；不走 sidecar） ← 主外部源（时效/广度），由 edu_ai 拼进 researchContext
  +
researchContext（edu_ai 注入的领域补充，叠加非替代）=
    RAG 检索片段（按 requirement 检索本课程知识库，Top-K，带出处）   ← 本轮 MVP 只做这一路
  + 教材正文相关章节（来自 MinerU 解析入库，SPEC-03）                ┐
  + 知识图谱节点/关系（该主题的概念、先修、课时，见 计算思维知识图谱.md）├ §0.1 D4，Phase 2.5 补
  + 已本地化图片说明（Phase6A2，供 outline 引用）                    ┘
```

> **原则**：不把系统做成"只堆检索片段"。researchContext 是让课件贴合本课程/本教材的**补充**，不是唯一真相源；缺它时 LLM+web 仍应能生成。

- 拼装在 edu_ai `classroom_service.py`，格式为带来源标注的纯文本/markdown，长度受模型上下文预算约束（超限则先摘要）。
- **`pdfContent.text` 与 `researchContext` 分工**：`pdfContent` = 用户本次上传的原始教材；`researchContext` = edu_ai 检索/图谱拼出的背景。二者可同时传。
- `enableWebSearch` 默认 **true**（web 是主力外部源）；与注入的 RAG 补充在 sidecar 内合并（§4.2），不互相短路。

> **【本轮 MVP】接通 web + RAG 第一路**：web search（主）+ RAG 检索片段（领域补充，Top-K 带出处）合并注入。教材章节 / 知识图谱节点 / 本地化图片说明 = §0.1 D4，Phase 2.5 补。

---

## 5. 媒体落盘与回填（audioUrl / video src）

> **【本轮 MVP】本节整体 Deferred**（媒体/TTS flags 全关，见 §0.1 D1/D2）。因无配音，SPEC-02 §6 不变量 5（已配音则 audioUrl 须改写）本轮自然 N/A 通过。以下为后续 Phase 3/5 实现依据，保留不删。

- `enableTTS` → `generateTTSForClassroom` 预生成 mp3、`splitLongSpeechActions` 切句、回填 `SpeechAction.audioUrl`。
- `enableVideo/Image` → 在线 provider 异步生成、落盘、回填 `mediaRef/src`。
- **落盘位置问题**：sidecar 回填的是 **sidecar 本地/临时 URL**。edu_ai 落库前必须**把媒体迁到 edu_ai 存储**并改写 url（否则 SPEC-02 §6 不变量 5 失败）。两种做法：
  1. edu_ai 拉取 sidecar 产物 → 存自己对象存储 → 改写 `audioUrl/src` 为 edu_ai 可达地址（**推荐**）。
  2. edu_ai 反代 sidecar 媒体路径（临时，简单但耦合 sidecar 生命周期）。
- 共享卷（SPEC-01 §6）便于做法 1 的拉取。

---

## 6. 落库与校验（edu_ai 后端）

拿到 `result.stage / result.scenes` 后：

1. **校验不变量**（SPEC-02 §6）：id 齐全且同层唯一；`viewportRatio` 存在；`spotlight/laser/play_video.elementId` 指向存在且类型正确；已配音 `audioUrl` 已改写为 edu_ai 地址。任一失败 → 拒绝落库、标记 job 失败、保留原始 JSON 供排查。
2. **落库**（SPEC-02 §4）：`classrooms(stage_json)` + `classroom_scenes(scene_json)`，关联 `course_id / owner`。
3. **权限**：绑定教师账号；学生端只读。
4. **幂等**：同一 edu_ai 任务重试用同 `Stage.id`（upsert），不产生重复课件。

---

## 7. edu_ai 编排流程（classroom_service）

```
教师提需求/选教材
 → classroom_service 拼 researchContext（RAG+教材+图谱）
 → OpenMaicClient.generate_classroom(requirement, pdfContent?, researchContext, flags)  → jobId
 → 统一任务表登记（SPEC-05），前端轮询进度
 → 完成：拉媒体→改写url→校验→落库
 → 前端用 @openmaic/renderer 播放（SPEC-08）
```

---

## 8. 验收清单（对应 ACC-04；【MVP】=本轮硬性，【D/Phase】=切割后置）

- [ ] 【MVP】补丁生效：传 `researchContext` 后，生成大纲/内容明显采用注入知识（AC-04-1）
- [ ] 【MVP】不强依赖单一源：researchContext 为空靠 LLM+web 也能生成；web 不可用时纯 RAG 注入也能兜底（AC-04-2）
- [ ] 【MVP】合并叠加生效：web 结果与 RAG 注入都进入上下文，不互相短路（AC-04-3）
- [ ] 【MVP】job/poll 全程进度可见、推进到 `completed`，失败有 error 文案（AC-04-4/9）
- [ ] 【MVP】产出通过 SPEC-02 §6 全部不变量校验（AC-04-5）
- [ ] 【MVP】落库 + 同 `Stage.id` 幂等 upsert（AC-04-7）
- [ ] 【D1 / Phase 3】`enableTTS=true` 时 `audioUrl` 已改写为 edu_ai 可达地址且能播（AC-04-6）
- [ ] 【D3 / Phase 3】落库后前端 renderer 能完整播放一节课（AC-04-8）
