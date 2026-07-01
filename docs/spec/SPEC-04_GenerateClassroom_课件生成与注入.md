# SPEC-04 · GenerateClassroom 课件生成与内容注入（Phase 2）

> **验收文档**：[`../acceptance/ACC-04_GenerateClassroom课件生成_验收.md`](../acceptance/ACC-04_GenerateClassroom课件生成_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 目标：edu_ai 调 sidecar `/api/generate-classroom`，**注入自己的 RAG/教材/知识图谱作为内容来源**，拿回 `Stage + Scene[]` 落库，正式取代 content_markdown。
> 这是主链路，也是「不照搬 OpenMAIC 流程」的关键点——骨架用它的，知识源用自己的。
> 上游实现（已核对）：`app/api/generate-classroom/route.ts`（72）→ `classroom-job-runner` → `lib/server/classroom-generation.ts`（574）→ `scene-generator.ts`（1746）；轮询 `app/api/generate-classroom/[jobId]/route.ts`。
> 关联：SPEC-02（产出契约）、SPEC-05（job/poll）、SPEC-06（provider/key）、SPEC-07（客户端）。

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
  enableWebSearch?: boolean;           // edu_ai 通常 false（用自己的注入）
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

### 4.1 问题

上游 `researchContext` **只能由内部 web search 产生**（`classroom-generation.ts:275` `let researchContext; if (input.enableWebSearch) {...}`），`GenerateClassroomInput` 无 `researchContext` 字段。edu_ai 要注入自己的 RAG/教材/知识图谱，**必须打一个最小补丁**。

### 4.2 补丁（sidecar fork 上改，3 处）

1. `GenerateClassroomInput` 加字段：
   ```ts
   researchContext?: string;   // 外部注入的内容来源，覆盖/替代 web search
   ```
2. `route.ts` 透传：body 组装处加 `...(rawBody.researchContext ? { researchContext: rawBody.researchContext } : {})`。
3. `classroom-generation.ts:275` 附近改为「注入优先」：
   ```ts
   let researchContext: string | undefined = input.researchContext;   // ← 注入优先
   if (!researchContext && input.enableWebSearch) { /* 原 web search 逻辑 */ }
   ```
   下游 `generateSceneOutlinesFromRequirements(..., { researchContext })`（行 342）无需改，天然消费。

> 补丁记录在 `docs/spec/patches/`（SPEC-01 §2）。仅 3 处、非侵入，跟上游 diff 成本低。

### 4.3 edu_ai 侧拼装 researchContext（§不照搬的关键）

```
researchContext =
    RAG 检索片段（按 requirement 检索本课程知识库，Top-K，带出处）
  + 教材正文相关章节（来自 MinerU 解析入库，SPEC-03）
  + 知识图谱节点/关系（该主题的概念、先修、课时，见 计算思维知识图谱.md）
  + 已本地化图片说明（Phase6A2，供 outline 引用）
```

- 拼装在 edu_ai `classroom_service.py`，格式为带来源标注的纯文本/markdown，长度受模型上下文预算约束（超限则先摘要）。
- **`pdfContent.text` 与 `researchContext` 分工**：`pdfContent` = 用户本次上传的原始教材；`researchContext` = edu_ai 检索/图谱拼出的背景。二者可同时传。
- `enableWebSearch` 默认 **false**（用自己的源；需要兜底时再开）。

---

## 5. 媒体落盘与回填（audioUrl / video src）

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

## 8. 验收清单

- [ ] 补丁生效：传 `researchContext` 后，生成大纲/内容明显采用注入知识（抽查引用点）
- [ ] `enableWebSearch=false` 且不传 key 时仍能生成（纯注入源）
- [ ] 产出通过 SPEC-02 §6 全部不变量校验
- [ ] `enableTTS=true` 时 `audioUrl` 已改写为 edu_ai 可达地址且能播
- [ ] job/poll 全程进度可见（SPEC-05），失败有 error 文案
- [ ] 落库后前端 renderer 能完整播放一节课
