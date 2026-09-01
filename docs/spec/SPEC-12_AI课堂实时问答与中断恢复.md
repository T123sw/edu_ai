# SPEC-12 · AI 课堂实时问答与中断恢复

> **状态**：✅ 已完成并通过 ACC-12（2026-08-10）
> **验收文档**：[`../acceptance/ACC-12_AI课堂实时问答与中断恢复_验收.md`](../acceptance/ACC-12_AI课堂实时问答与中断恢复_验收.md)
> **实施计划**：[`../superpowers/plans/2026-08-10-ai-classroom-realtime-qa-implementation.md`](../superpowers/plans/2026-08-10-ai-classroom-realtime-qa-implementation.md)
> **关联规格**：SPEC-02（Stage/Scene/Action）、SPEC-06（Provider 安全边界）、SPEC-07（OpenMaicClient）、SPEC-08（前端播放）

## 1. 背景与当前基线

当前正式 AI 课堂主线为：

```text
课堂数据 Stage / Scene / Action / Slide
  → ClassroomPlayer
  → PlaybackEngine / ActionEngine
  → 预生成音频
  → 浏览器 SpeechSynthesis 降级
  → 阅读时长等待降级
```

现状已经支持按页播放、停止、重播、字幕、聚焦、互动场景和课堂 TTS 音频，但不支持句子级中断恢复：

- `PlaybackEngine` 只有 `idle | playing`，不公开当前 action 快照；
- 页面暂停通过销毁 renderer 实现，再播放会从当前页开头开始；
- `SceneActionPlayback` 私有持有播放引擎，课堂页无法请求句子级暂停；
- 没有课堂专用问答 Agent、学生级问答会话或即时回答 TTS 接口；
- 旧 LiveTalking/WebRTC 数字人链路已在 Phase 6 下线，不得作为本功能依赖。

2026-08-10 本机基线核查结果：

- 前端、后端、OpenMAIC sidecar 分别监听 5173、8001、3000；
- 后端 `/health` 返回 `status=ok`，知识库已就绪；
- sidecar `/api/health` 报告 `tts=true`；
- sidecar server provider 中 `qwen-tts` 已启用；
- 课堂播放核心 24 项定向测试通过。

## 2. 已确认的产品决策

1. 学生只使用文字提问，不接入麦克风、ASR、唤醒词或回声消除。
2. 学生打开提问框时立即暂停当前讲授，而不是等到点击发送。
3. 如果在一句话中途打断，回答后从该句开头重新讲；如果在两句之间打断，从下一句继续。
4. 问答历史按“课程 × 课堂 × 学生”隔离并持久化，刷新后仍可读取。
5. 问答不会修改原始课堂 `scenes/actions`，其他学生看不到该学生的历史。
6. Agent 生成回答后必须调用 Qwen TTS；浏览器 TTS 只作为服务端 TTS 失败后的运行时降级。
7. Agent 生成或回答音频播放期间锁定再次提交，不支持问题排队或打断回答。
8. 首版采用完整回答后一次性 TTS，不做 LLM/TTS 双流式播放。

## 3. 目标与非目标

### 3.1 目标

- 在课堂播放器内提供可随时打开的实时问答面板。
- 打开面板时可靠停止当前音频、视频和动作推进，并记录可恢复快照。
- Agent 基于当前讲授位置、课堂内容、该学生本课堂问答历史及课程知识库回答。
- 服务端调用 OpenMAIC sidecar 已配置的 Qwen TTS，返回受鉴权保护的回答音频。
- 回答音频包含“问题回答 + 自然衔接语”，播放完成后自动恢复讲授。
- 刷新页面后恢复问答历史，但不自动恢复刷新前正在进行的音频或处理中请求。
- 对重复提交、并发请求、过期快照和 TTS 失败提供可判定行为。

### 3.2 非目标

- 不恢复 LiveTalking、WebRTC、数字人、唇形同步或 GPU 服务。
- 不支持语音提问、多人抢答、教师审核队列或全班共享问答。
- 不在首版实现 token 级 LLM 流式输出、文本分句 TTS 流或音频分片队列。
- 不把学生问答写回课堂课件，也不改变 PPTX/MP4 导出内容。
- 不在本功能中迁移现有文件存储到 PostgreSQL；通过仓储接口保留未来替换能力。
- 不允许问答控制课堂翻页、修改课件或调用资源生成工作流。

## 4. 用户体验契约

### 4.1 正常路径

1. 课堂正在讲授，学生点击“提问”。
2. 当前音频立即停止，页面内容停留在当前场景；提问框获得焦点。
3. 学生输入 1～1000 个字符的问题并点击发送。
4. 页面显示“正在结合当前讲解生成语音回答”；后端分别记录 RAG、LLM 和 TTS 阶段耗时。
5. 回答文字进入问答历史，Qwen TTS 回答音频开始播放。
6. 回答音频结尾包含自然衔接语，例如“好，我们回到刚才关于快速排序基准值的说明。”
7. 音频结束后自动关闭本轮占用状态并恢复课堂：
   - `executing_action`：重播被打断的 action；
   - `between_actions`：播放下一条尚未执行的 action。
8. 问答面板可以保持打开；课堂恢复后学生可以关闭面板或提出下一问。

### 4.2 放弃本次提问

- 学生尚未发送问题时点击“取消提问”：不创建问答 turn，立即按原快照恢复。
- 输入为空时不得提交；课堂继续保持暂停，直到取消或输入有效问题。
- 页面退出、翻页或课堂资源 revision 变化时，丢弃本地恢复快照并取消回答音频。

### 4.3 回答期间控制

- Agent 生成、TTS 生成、回答播放期间，发送按钮禁用。
- 学生可以点击“停止回答并继续授课”；该动作取消回答音频，并按原快照恢复。
- 首版不允许回答期间再次提交问题，也不建立等待队列。

## 5. 总体架构

```text
ClassroomPlayer
  ├─ ManagedPagePlaybackController
  │    └─ PlaybackRuntimeHandle
  │         ├─ suspend() → PlaybackCheckpoint
  │         ├─ resume(checkpoint)
  │         └─ cancel()
  ├─ useClassroomInterruption
  │    ├─ 打开/取消提问
  │    ├─ 提交 turn
  │    ├─ 加载鉴权音频 blob
  │    └─ 播放完成后恢复
  └─ ClassroomQaPanel
       ├─ 问答历史
       ├─ 输入框
       └─ 状态与错误动作

POST classroom QA turn
  → ClassroomQaService
      ├─ ClassroomQaSessionStore
      ├─ 课堂 material + checkpoint 校验
      ├─ 课程 RAG
      ├─ 专用课堂问答 prompt + LLM
      └─ ClassroomQaTtsService
           └─ OpenMaicClient.synthesize_tts
                └─ OpenMAIC /api/generate/tts → qwen-tts
```

### 5.1 前端职责

- 播放器是恢复位置的事实源；后端不得控制前端 action 游标。
- 提问编排只通过 `PlaybackRuntimeHandle` 操作播放器，不直接操作 `speechSynthesis` 或 renderer 内部状态。
- 回答音频通过带 Authorization 的 fetch 转为 blob URL，沿用课堂预生成音频的鉴权模式。
- UI 状态与底层课堂播放状态分离，避免把 `generating_answer` 等业务状态塞进 OpenMAIC action 引擎。

### 5.2 后端职责

- 后端根据 `course_id/classroom_id/current_user` 重新读取课堂内容，不信任客户端提交的讲稿文本。
- 后端验证 checkpoint 的 `scene_id/action_id/action_index` 与已落库课堂一致。
- 后端只生成回答、衔接语、音频与历史记录，不修改课堂 material。
- 问答 API 使用课程 read 权限；会话和音频额外校验 `owner_user_id`。

## 6. 播放中断与恢复契约

### 6.1 类型

```ts
export type PlaybackCheckpointPhase =
  | "executing_action"
  | "between_actions";

export type PlaybackCheckpoint = {
  sceneId: string;
  sceneIndex: number;
  actionIndex: number;
  actionId: string | null;
  phase: PlaybackCheckpointPhase;
  pageRevision: number;
};

export interface PlaybackRuntimeHandle {
  play(): void;
  suspend(): PlaybackCheckpoint;
  resume(checkpoint: PlaybackCheckpoint): void;
  cancel(): void;
  dispose(): void;
}
```

### 6.2 action 游标语义

- `actionIndex` 永远指向“下一次应该执行的 action”。
- action 开始时，引擎进入 `executing_action`，但在 action 成功结束前不增加 `actionIndex`。
- `suspend()` 在 action 执行期间触发：取消当前媒体，保留相同 `actionIndex/actionId`。
- `resume()` 收到 `executing_action` 快照：从该 action 开头重新执行。
- action 成功结束后增加 `actionIndex` 并进入 `between_actions`。
- `suspend()` 在两条 action 之间触发：保存下一条 action 的 index，恢复时直接执行下一条。
- 快照 `sceneId/pageRevision` 与当前页不匹配时，`resume()` 抛出 `StalePlaybackCheckpointError`，调用方不得强制恢复。

### 6.3 取消语义

- `ActionMediaAdapter` 增加公开的当前媒体取消能力，取消必须让等待中的 Promise 有界结束。
- `PlaybackEngine.suspend()` 增加 run token，旧异步 action 完成后不得发出 `onActionEnd` 或推进游标。
- 聚焦、激光、视频和 speech 在 suspend 时清理；恢复 action 时由 action 本身重新建立效果。
- 页面翻页、重播、卸载和回答“停止并继续”均必须撤销未使用的 blob URL。

## 7. 前端问答状态机

```ts
export type ClassroomQaPhase =
  | "closed"
  | "drafting"
  | "submitting"
  | "loading_audio"
  | "playing_answer"
  | "resuming"
  | "error";
```

允许的转换：

```text
closed → drafting
drafting → closed             取消并恢复
drafting → submitting         有效问题，服务端执行 RAG、LLM 和 Qwen TTS
submitting → loading_audio    回答已返回，正在获取鉴权音频 blob
loading_audio → playing_answer 音频可用
submitting → playing_answer   服务端 TTS 失败，浏览器 TTS 降级
playing_answer → resuming     回答结束或学生停止回答
resuming → drafting           面板保持打开
resuming → closed             面板已关闭
submitting/loading_audio → error
error → submitting            重试同一 clientTurnId
error → resuming              放弃本轮并继续授课
```

任一时刻最多存在一个未完成 turn；前端禁用重复提交，后端仍需执行幂等与冲突保护。

## 8. API 契约

### 8.1 读取当前学生会话

```http
GET /api/courses/{course_id}/classrooms/{classroom_id}/qa/session
Authorization: Bearer <token>
```

响应：

```json
{
  "session_id": "cqa_8b301e2eb4d94263",
  "course_id": "data-structures",
  "classroom_id": "0i5I9Nt7Aj",
  "owner_user_id": "student-a",
  "status": "ready",
  "turns": [
    {
      "turn_id": "turn_7df97ab92cff",
      "client_turn_id": "2f4559b8-ef53-48db-b184-e80dde655be4",
      "question": "基准值为什么通常选第一个元素？",
      "answer_text": "基准值不一定必须选第一个元素……",
      "transition_text": "好，我们回到刚才基准值划分的步骤。",
      "tts_status": "ready",
      "audio_url": "/api/courses/data-structures/classrooms/0i5I9Nt7Aj/qa/sessions/cqa_8b301e2eb4d94263/audio/turn_7df97ab92cff.mp3",
      "created_at": "2026-08-10T08:00:00Z"
    }
  ]
}
```

响应中的 `owner_user_id` 只返回当前登录用户自身标识。历史按 `created_at` 升序，首版最多返回最近 100 轮。尚未提过问题时返回确定性 `session_id` 和空 `turns`，但 GET 不创建文件；首次提交 turn 时才持久化会话。

### 8.2 提交问题

```http
POST /api/courses/{course_id}/classrooms/{classroom_id}/qa/turns
Authorization: Bearer <token>
Content-Type: application/json
```

请求：

```json
{
  "client_turn_id": "2f4559b8-ef53-48db-b184-e80dde655be4",
  "question": "基准值为什么通常选第一个元素？",
  "checkpoint": {
    "scene_id": "scene-quick-sort-partition",
    "scene_index": 2,
    "action_index": 4,
    "action_id": "speech-pivot-choice",
    "phase": "executing_action",
    "page_revision": 7
  }
}
```

成功响应：

```json
{
  "session_id": "cqa_8b301e2eb4d94263",
  "turn": {
    "turn_id": "turn_7df97ab92cff",
    "client_turn_id": "2f4559b8-ef53-48db-b184-e80dde655be4",
    "question": "基准值为什么通常选第一个元素？",
    "answer_text": "基准值不一定必须选第一个元素……",
    "transition_text": "好，我们回到刚才基准值划分的步骤。",
    "tts_status": "ready",
    "audio_url": "/api/courses/data-structures/classrooms/0i5I9Nt7Aj/qa/sessions/cqa_8b301e2eb4d94263/audio/turn_7df97ab92cff.mp3",
    "created_at": "2026-08-10T08:00:00Z"
  }
}
```

规则：

- `question` trim 后长度为 1～1000；
- `client_turn_id` 必须是 UUID；
- 相同会话、相同 `client_turn_id` 在完成后的重复请求返回同一 turn，不重复调用 LLM/TTS；该 ID 仍在处理时返回 `CLASSROOM_QA_BUSY`，同样不得启动第二次调用；
- 同一会话已有不同的 turn 处于 `processing` 时返回 HTTP 409、错误码 `CLASSROOM_QA_BUSY`；
- checkpoint 不匹配当前课堂时返回 HTTP 409、错误码 `STALE_CLASSROOM_CHECKPOINT`；
- 课堂不存在或当前用户无权读取时统一返回 404，避免泄露资源存在性。

### 8.3 读取回答音频

```http
GET /api/courses/{course_id}/classrooms/{classroom_id}/qa/sessions/{session_id}/audio/{filename}
Authorization: Bearer <token>
```

- 必须校验课程 read 权限、课堂可见性、会话 owner 和文件路径穿越；
- 只允许读取该会话记录中已登记的音频文件；
- 返回正确 `Content-Type`，不得把 sidecar 临时 URL 暴露给浏览器。

## 9. Agent 上下文与输出

### 9.1 上下文构造

后端从可信数据构建以下上下文：

1. 课堂标题、课程 ID、当前场景标题与类型；
2. 当前场景完整 speech 文本；
3. checkpoint 前已经完成的当前场景 speech；
4. 被打断 action 的文本；
5. 前一场景最后 3 条 speech，避免页边界语义断裂；
6. 当前学生最近 6 轮本课堂问答；
7. 以学生问题为 query 的课程 RAG 结果，`top_k=5`；
8. 学生原始问题。

客户端只提交位置标识，不提交“已讲内容”“被打断文本”或 RAG 结果。

### 9.2 专用系统约束

课堂问答 Agent 必须：

- 优先回答当前问题，通常控制在 80～300 个中文字符；
- 先关联当前讲解，再使用课程知识库补充；
- 不把学生引导到资源生成、报告、PPT 或其他工作流；
- 知识库不足时明确边界，不编造课堂未提供的事实；
- 问题与课程无关时简短回应并引导回当前知识点；
- 输出独立的 `answer_text` 和不重复知识内容的 `transition_text`；
- `transition_text` 为一句自然口语，目标长度 10～40 个中文字符；
- 不在回答文本中输出 Markdown 表格、代码围栏或引用编号，保证 TTS 可读性。

### 9.3 结构化输出

模型目标输出：

```json
{
  "answer_text": "……",
  "transition_text": "好，我们回到刚才关于……的讲解。"
}
```

解析失败时：

- 将模型纯文本作为 `answer_text`；
- 使用确定性模板生成 `transition_text`：`好，我们回到刚才“{scene_title}”的讲解。`；
- 两个字段均执行长度上限和空白清洗后才进入 TTS。

## 10. Qwen TTS 契约

### 10.1 调用路径

`OpenMaicClient` 新增：

```python
async def synthesize_tts(
    self,
    *,
    text: str,
    audio_id: str,
    provider_id: str,
    voice: str,
    speed: float = 1.0,
) -> tuple[bytes, str]:
    ...
```

实际请求：

```http
POST {OPENMAIC_BASE_URL}/api/generate/tts
```

```json
{
  "text": "回答正文。好，我们回到刚才的讲解。",
  "audioId": "turn_7df97ab92cff",
  "ttsProviderId": "qwen-tts",
  "ttsVoice": "Cherry",
  "ttsSpeed": 1.0
}
```

配置默认值：

- `OPENMAIC_LIVE_TTS_PROVIDER=qwen-tts`
- `OPENMAIC_LIVE_TTS_VOICE=Cherry`
- `OPENMAIC_LIVE_TTS_SPEED=1.0`

sidecar 返回 base64 后，后端解码、限制最大 10 MiB、按返回 format 确定扩展名，以临时文件 + `os.replace` 原子落盘。

### 10.2 状态与降级

- 成功：`tts_status=ready`，返回受鉴权音频 URL。
- sidecar 不可达、限流、超时或返回非法 base64：仍返回回答文字，`tts_status=failed`、`audio_url=null`。
- 前端收到 `failed` 后调用浏览器 `SpeechSynthesis` 朗读相同的 `answer_text + transition_text`。
- 浏览器 TTS 也不可用时，保持文字可读，显示“语音不可用”，学生点击“继续授课”后恢复。
- 无论成功或失败，服务端 TTS 都必须先被调用；不得直接跳过 Qwen TTS 使用浏览器语音。

## 11. 会话持久化

### 11.1 目录

```text
backend/course_data/courses/{course_id}/generated_materials/classrooms/
  {classroom_id}_media/qa/{owner_hash}/
    session.json
    audio/
      {turn_id}.mp3
```

`owner_hash = sha256(owner_user_id).hexdigest()[:24]`，路径中不使用原始用户名。

### 11.2 会话记录

```json
{
  "schema_version": 1,
  "session_id": "cqa_8b301e2eb4d94263",
  "course_id": "data-structures",
  "classroom_id": "0i5I9Nt7Aj",
  "owner_user_id": "student-a",
  "status": "ready",
  "active_client_turn_id": null,
  "created_at": "2026-08-10T08:00:00Z",
  "updated_at": "2026-08-10T08:00:06Z",
  "turns": []
}
```

写入规则：

- `ClassroomQaSessionStore` 提供仓储接口，文件实现使用进程内按 session 加锁、`O_CREAT|O_EXCL` 原子 claim 文件和 JSON 原子替换，避免多 worker 同时启动两个 turn；
- turn 开始前写入 `processing` 与 `active_client_turn_id`；
- LLM/TTS 完成后追加完整 turn 并清空 active 标识；
- 失败时保存 `failed` turn、稳定错误码和可重试标志，不保存 provider 原始响应或密钥；
- 会话最多保留最近 100 轮，清理历史 turn 时同步删除不再引用的回答音频；
- 日后切换 PostgreSQL 时保持 API、Pydantic schema 与 store port 不变。

claim 文件记录 `client_turn_id` 和创建时间；超过 120 秒时，下一次读取在持有同一路径进程锁后清理陈旧 claim，并把对应 turn 标为 `CLASSROOM_QA_INTERRUPTED`。完成或失败写入 session 后必须删除 claim。

## 12. 安全、隐私与资源限制

- 所有 API 必须登录并通过 `require_course_read`。
- session ID 不能替代 owner 校验；教师、管理员或其他学生也不能读取某学生问答，除非另立审计需求。
- 后端从课程存储读取课堂并检查当前用户可见性；不得只凭 URL 参数访问。
- 问题最大 1000 字符，模型上下文按 §9 截断，单次回答正文最大 1200 字符，衔接语最大 120 字符。
- TTS 输入为清洗后的回答和衔接语，总长度最大 1500 字符。
- sidecar base URL 和 TTS provider 配置只来自服务端环境，不接受客户端覆盖。
- 日志记录 `course_id/classroom_id/session_id/turn_id`、阶段、耗时和稳定错误码，不记录完整问题、回答、Authorization 或 provider 响应正文。
- 音频读取执行 resolved-path containment 检查和登记文件白名单检查。

## 13. 错误处理

| 场景 | 后端行为 | 前端行为 | 是否恢复课堂 |
| --- | --- | --- | --- |
| 问题为空/过长 | 422 | 保留输入并提示 | 否 |
| 会话已有处理中 turn | 409 `CLASSROOM_QA_BUSY` | 禁止重复提交并刷新会话 | 否 |
| checkpoint 过期 | 409 `STALE_CLASSROOM_CHECKPOINT` | 提示课堂位置已变化 | 不按旧位置恢复；保持当前页停止 |
| RAG 失败 | 继续仅用课堂上下文回答，记录 `rag_degraded` | 不打断正常流程 | 回答后恢复 |
| LLM 失败 | turn 标为 failed | 显示重试/放弃 | 放弃后恢复 |
| Qwen TTS 失败 | 返回文字与 `tts_status=failed` | 浏览器 TTS 降级 | 降级播放后恢复 |
| Qwen 与浏览器 TTS 都失败 | 返回文字 | 显示语音不可用和继续按钮 | 学生确认后恢复 |
| 回答音频 401/404 | 不改变 turn | 尝试浏览器 TTS | 降级播放后恢复 |
| 学生翻页/退出 | 取消本地请求结果消费 | 清理回答音频与快照 | 不恢复旧页 |
| 页面刷新时存在 processing | GET 将超时的 processing 转为 failed | 展示该轮失败，可重新提问 | 不自动播放或恢复 |

服务端 `processing` 超过 120 秒视为可恢复的陈旧状态；下一次读取会话时转为 `failed`，错误码 `CLASSROOM_QA_INTERRUPTED`。

## 14. 可观测性

每轮生成记录结构化事件：

```text
classroom_qa_turn
  session_id
  turn_id
  course_id
  classroom_id
  checkpoint_scene_id
  checkpoint_action_id
  rag_ms
  llm_ms
  tts_ms
  total_ms
  tts_status
  result=success|failed|degraded
  error_code
```

目标指标：

- API 去重命中不产生第二次 LLM/TTS 调用；
- Qwen TTS 成功时，回答文字返回到回答音频可播放的总耗时可被独立测量；
- 任何失败均有稳定错误码，日志不得依赖解析自然语言异常。

首版不承诺固定网络延迟 SLA；验收要求本地已配置服务下功能正确且阶段耗时可见。

## 15. 测试策略

### 15.1 前端单元测试

- action 执行中 suspend 不推进 actionIndex，resume 重播该 action；
- action 间 suspend 恢复下一 action；
- stale checkpoint 拒绝恢复；
- suspend 取消音频、视频和效果，旧异步完成不产生 action end；
- 问答状态机禁止重复提交；
- 打开面板立即暂停，取消空白草稿恢复；
- TTS ready 使用鉴权 blob 音频；failed 使用浏览器语音；双失败等待手动继续；
- 回答结束恢复一次且只恢复一次；翻页后旧回答不得恢复旧页；
- blob URL 在完成、取消、翻页和卸载时撤销。

### 15.2 后端单元测试

- session ID 与 owner 目录隔离；同一学生/课堂 get-or-create 幂等；
- 原子写入、100 轮截断、processing 超时恢复；
- checkpoint 可信重建与越界拒绝；
- prompt 包含当前场景、被打断 action、前序讲解、历史问答和 RAG 摘要；
- 模型 JSON、纯文本和非法输出均产生稳定 answer/transition；
- OpenMaicClient TTS 请求字段、base64 解码、格式、超时与错误映射；
- 相同 clientTurnId 不重复调用 LLM/TTS；不同并发 turn 返回 409；
- TTS 失败返回文字而非使整轮失败；
- 音频 owner、课程权限和路径穿越检查。

### 15.3 集成与浏览器验收

- 用真实含多条 speech action 的课堂，在一句中间打开提问并发送；
- 听到 Qwen TTS 回答和衔接语后，被打断句从头重播；
- 在两句间暂停时从下一句继续；
- 刷新后历史仍在，其他学生不可见；
- 全屏演示下提问入口可用且不遮挡核心舞台；
- TTS 服务断开时验证浏览器语音降级和文字兜底。

## 16. 完成定义

只有同时满足以下条件才能把本规格标记为完成：

1. ACC-12 所有自动化必过项通过；
2. 使用真实课堂完成句中和句间两种人工验收；
3. 网络记录证明成功路径调用 `/api/generate/tts` 且 provider 为 `qwen-tts`；
4. 两个学生账号的问答历史相互不可见；
5. 现有课堂播放、PPTX 和视频 A 回归测试不退化；
6. 活跃运行时代码不新增 LiveTalking、WebRTC 或 AI Lecturer 依赖；
7. ACC-12 记录最终命令、结果和人工证据后签收。
