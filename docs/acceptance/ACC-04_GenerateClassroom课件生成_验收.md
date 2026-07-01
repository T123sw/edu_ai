# ACC-04 · GenerateClassroom 课件生成与注入 · 验收文档

> 对应 spec：[`../spec/SPEC-04_GenerateClassroom_课件生成与注入.md`](../spec/SPEC-04_GenerateClassroom_课件生成与注入.md)
> 对应 Phase：2（课件生成）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §2 / §8
> 通用环境：见 [验收 README §2](README.md)
> 状态：⏳ MVP 待实现（本轮范围见 §1；切割清单见 [SPEC-04 §0.1](../spec/SPEC-04_GenerateClassroom_课件生成与注入.md)）

---

## 1. 功能范围

**做**：edu_ai 调 `/api/generate-classroom`，注入自己的 `researchContext`，拿回 `Stage+Scene[]`，校验→落库，取代 content_markdown。含 sidecar 的 3 处注入补丁。

> **本轮 MVP 收窄（2026-07-01 用户拍板）**：知识源=**LLM 基座 + web search（主）+ RAG 领域补充（叠加，非替代）**，`enableWebSearch=true`；媒体 flags（TTS/图片/视频）关；**不含前端播放**。sidecar 用 vendor 复制接入。切割项见 [SPEC-04 §0.1](../spec/SPEC-04_GenerateClassroom_课件生成与注入.md)，后续 Phase 回填。

**不做（本轮，Deferred）**：TTS 配音与 `audioUrl` 改写（→Phase 3）；图片/视频生成（→Phase 5）；前端 renderer 播放（→Phase 3）；researchContext 的教材章节/知识图谱/本地化图片深度（→Phase 2.5）；PPTX 导出（Phase 4）；成片视频（Phase 5）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 本轮 | 判定 |
| --- | --- | --- | --- |
| AC-04-1 | **注入补丁生效**：body 传 `researchContext` 后，生成大纲/内容明显采用注入知识（可抽查引用点/术语） | ✅ MVP | |
| AC-04-2 | 不强依赖单一源：`researchContext` 为空靠 LLM+web 也能生成；反之 web 不可用时纯 RAG 注入也能兜底 | ✅ MVP | |
| AC-04-3 | 补丁「合并叠加」：web search 结果与注入的 `researchContext` **共同进入上下文**（不互相短路），抽查两源都被采用 | ✅ MVP | |
| AC-04-4 | 提交返回 202 `{jobId,pollUrl,pollIntervalMs:5000}`；轮询按 SPEC-04 §3 步骤推进到 `completed` | ✅ MVP | |
| AC-04-5 | 产出通过 ACC-02 全部不变量校验 | ✅ MVP | |
| AC-04-6 | `enableTTS=true`：`speech.audioUrl` 已改写为 edu_ai 可达地址且能播放 | ⏭ D1 / Phase 3 | |
| AC-04-7 | 落库 `classrooms`+`classroom_scenes`，绑定 `course_id/owner`；重试用同 `Stage.id` upsert 不重复 | ✅ MVP | |
| AC-04-8 | 前端用 renderer 能完整播放这节课（衔接 ACC-08） | ⏭ D3 / Phase 3 | |
| AC-04-9 | 失败路径：sidecar 成功但 edu_ai 落库/校验失败 → edu_ai job=failed 且 error 明确（ACC-05） | ✅ MVP | |

> 本轮硬性 = AC-04-1/2/3/4/5/7/9（7 条）。AC-04-6/8 随媒体与前端后置（切割 D1/D3），本轮 §3.4/§3.5 的 TTS 用例与 §2 AC-04-8 暂不作为通过条件。

---

## 3. 测试方法

### 3.1 sidecar 注入补丁单测（AC-04-1/3）
- 在 sidecar fork 加测试：构造带 `researchContext` 的输入，断言 `classroom-generation.ts` 里 `researchContext = input.researchContext` 生效、`enableWebSearch` 分支被短路。
- 端到端：
```bash
curl --noproxy "localhost,127.0.0.1" -s -X POST http://localhost:3000/api/generate-classroom \
  -H 'Content-Type: application/json' \
  -d '{"requirement":"讲解冒泡排序","researchContext":"【教材】冒泡排序：相邻比较交换……【知识图谱】先修:数组;时间复杂度O(n^2)","enableTTS":false}'
# 预期 202 {jobId,pollUrl,...}
curl --noproxy "localhost,127.0.0.1" -s http://localhost:3000/api/generate-classroom/<jobId>
# 轮询到 step=completed，result.stage/scenes 存在；抽查 scene 文本含注入术语（如"相邻比较交换/O(n^2)"）
```

### 3.2 单源可用性兜底（AC-04-2）
- 兜底A：`enableWebSearch=false`、仅传 RAG `researchContext` → 生成成功（web 不可用不阻断）。
- 兜底B：`researchContext` 为空、`enableWebSearch=true` → 靠 LLM+web 也能生成（不强依赖 RAG）。

### 3.3 落库 + 校验 + 幂等（AC-04-5/7）
- edu_ai `classroom_service` 走完整流程（pytest 集成测试）：断言落库行数、id 稳定；重复提交同任务 → upsert 不新增课件。

### 3.4 配音改写（AC-04-6）
- `enableTTS=true` 生成 → 断言每个 `speech.audioUrl` 前缀是 edu_ai 存储域名（非 sidecar 临时路径）→ 前端播放该 url 出声。

### 3.5 失败注入（AC-04-9）
- Mock 落库阶段抛错（如唯一约束冲突）→ 断言 edu_ai job=failed、`error=PERSIST_FAILED`、原始产出保留。

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| researchContext 超上下文预算 | edu_ai 先摘要再注入，不超模型限制 |
| requirement 为空 | 400 MISSING_REQUIRED_FIELD |
| 生成中途某 scene 失败 | 流水线分阶段可重试/降级，不整单崩（观察 message）|
| 长任务 30min 无进度 | sidecar 判 stale=failed，edu_ai 同步失败（ACC-05）|

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | |
| 结论 | |
| 遗留 | 图片/视频生成、PPTX、成片视频另阶段验收 |
