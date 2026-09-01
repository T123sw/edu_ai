# AI Lecturer 实时讲解会话资源设计

## 背景

PPT 生成教学视频这条链路不能按单纯 `mp4` 文件播放来设计。`AI_Lecturer` 同时存在两种能力：

- 实时在线讲解：`LiveTalking` 通过 WebRTC 输出音视频流，业务网关通过在线接口控制逐句讲解、停止、打断问答。
- 离线整段导出：业务网关异步生成完整 `mp4` 文件，用于固定视频资产。

用户当前确认要走“实时生成、实时打断”的方向，因此前端不能只在课程资源中渲染一个 `<video>`。课程资源需要表达成一种新的复合资源：`AI 讲解会话资源`。它同时包含录播回看能力和继续互动能力。

## 当前判断

现有系统里有三个关键事实：

- 实时音视频不是文件 URL，而是 WebRTC 会话。`LiveTalking-main/web/client.js` 会向 `/offer` 发起 WebRTC 协商，并从返回值中取得真实 `sessionid`。
- 讲解控制接口在 `unified_gateway.py` 的 `/api/v1/online/*` 下，包括创建课程、生成脚本、逐句播报、停止讲解、打断问答。
- `LiveTalking` 已有录制雏形：`/record` 可以触发 `start_record` / `end_record`，底层 `BaseAvatar` 会通过 ffmpeg 写入音视频文件，但当前输出路径固定且未接入课程资源持久化。

这意味着：

- 实时讲解本身支持新的打断。
- 录播视频只能保留当时已经发生过的打断，不能在播放时产生新的实时打断。
- 如果课程资源需要继续支持新的打断，就必须保存会话快照，并允许用户从课程资源重新进入实时会话。

## 目标

1. 将 PPT 生成的 AI 讲解结果沉淀为课程资源。
2. 课程资源中既能回看录播，也能重新进入实时讲解继续互动。
3. 前端实时播放必须使用同一个 WebRTC `sessionid` 驱动播报、停止和打断，避免画面会话与控制会话错位。
4. 录制产物不能覆盖固定文件，必须按课程、资源、会话维度唯一持久化。
5. 保留离线 `mp4` 导出能力，但不把它当作实时互动的主路径。

## 非目标

- 不把 WebRTC 实时流伪装成普通 `video_url`。
- 不要求录播播放时支持新的打断。
- 不在本设计中实现复杂剪辑、字幕编辑、时间轴精修。
- 不把每次回看都重新触发大模型和头像渲染。

## 推荐方案

采用“实时讲解会话资源”模型：

- 实时页负责 WebRTC 接流、生成脚本、逐句讲解、打断问答、恢复讲解。
- 后端保存会话快照，包括 PPT 来源、脚本、提问、回答、页码、句子游标和时间点。
- 实时会话开始时可同步录制，结束后生成录播资产。
- 课程资源中展示同一个资源卡，但提供两个入口：
  - `回看录播`：播放这次会话沉淀出的录制文件。
  - `继续互动`：基于会话快照重新进入实时讲解页，继续支持新的打断。

## 资源模型

新增或扩展课程资源类型：

```json
{
  "material_id": "ai_session_20260420_001",
  "material_type": "ai_lecture_session",
  "title": "计算思维导论 - AI 实时讲解",
  "summary": "由 PPT 生成的 AI 讲解会话，包含录播回看和继续互动入口。",
  "content": {
    "source_ppt_material_id": "ppt_001",
    "session_snapshot_id": "snapshot_001",
    "recording_asset_id": "recording_001",
    "recording_url": "/api/courses/computational-thinking/lecture-sessions/ai_session_20260420_001/recording",
    "can_continue_interactive": true
  },
  "generation_state": {
    "status": "completed",
    "phase": "recording_ready",
    "message": "AI 讲解录播已生成，可继续互动"
  }
}
```

### 会话快照

会话快照保存用于恢复实时讲解的结构化状态：

```json
{
  "snapshot_id": "snapshot_001",
  "course_id": "computational-thinking",
  "source_ppt_material_id": "ppt_001",
  "ai_lecturer_course_id": "1001",
  "outline": [
    {
      "title": "什么是计算思维",
      "content": "本页讲解内容"
    }
  ],
  "script": [
    {
      "page_index": 0,
      "sentences": ["第一句讲稿", "第二句讲稿"]
    }
  ],
  "events": [
    {
      "type": "speak",
      "page_index": 0,
      "sentence_index": 0,
      "text": "第一句讲稿",
      "timestamp_ms": 1200
    },
    {
      "type": "interrupt_question",
      "question": "学生问题",
      "page_index": 0,
      "sentence_index": 1,
      "timestamp_ms": 8200
    },
    {
      "type": "interrupt_answer",
      "answer": "AI 回答",
      "timestamp_ms": 9800
    }
  ],
  "last_position": {
    "page_index": 0,
    "sentence_index": 1
  }
}
```

## 前端设计

### 实时讲解页

实时讲解页采用 React 原生接管 WebRTC，不再把 `webrtcapi.html` 当黑盒 `iframe` 使用。

页面职责：

- 创建 `RTCPeerConnection`。
- 向 `LiveTalking` 的 `/offer` 发起协商。
- 保存返回的真实 `sessionid`。
- 将远端 `audio` / `video` track 绑定到页面播放器。
- 用同一个 `sessionid` 调用业务网关的 `speak_sentence`、`stop_speaking`、`interrupt_and_ask`。
- 在讲解过程中追加事件日志。
- 结束时触发录制收尾和课程资源入库。

推荐组件拆分：

- `AiLecturerLivePlayer`：只负责 WebRTC 连接、远端流展示、连接状态。
- `AiLecturerSessionController`：负责课程大纲、脚本生成、逐句播报、停止、恢复。
- `AiLecturerInterruptPanel`：负责学生提问、打断、回答展示。
- `AiLectureSessionRecorder`：负责开始录制、结束录制、录制状态展示。

### 课程资源页

课程资源页识别 `material_type === "ai_lecture_session"` 后展示复合资源卡。

详情区展示：

- 资源标题、来源 PPT、生成状态。
- `回看录播` 按钮：有 `recording_url` 时可播放录播。
- `继续互动` 按钮：有 `session_snapshot_id` 时跳转到实时讲解页，并携带 `courseId`、`materialId`、`snapshotId`。
- 最近一次打断问题摘要。
- 录制生成失败时的错误信息和重试入口。

### 工作台右侧文件列表

工作台生成成功后，右侧文件列表里的条目应展示为 `AI 讲解会话`，而不是普通视频。

点击行为：

- `status=processing`：提示正在生成或录制，不跳转。
- `status=completed` 且有 `recording_url`：跳转课程资源并选中该会话资源。
- 用户需要互动时，从课程资源详情点击 `继续互动`。

## 后端设计

### 业务接口

新增课程侧会话接口：

- `POST /api/courses/{course_id}/lecture-sessions`
  - 从已完成 PPT 创建 AI 讲解会话资源。
  - 初始化会话快照。

- `POST /api/courses/{course_id}/lecture-sessions/{session_id}/recording/start`
  - 转发到 LiveTalking `/record` 的 `start_record`。
  - 保存录制状态。

- `POST /api/courses/{course_id}/lecture-sessions/{session_id}/recording/stop`
  - 转发到 LiveTalking `/record` 的 `end_record`。
  - 将录制文件移动到课程资源目录。
  - 更新 `recording_url`。

- `PATCH /api/courses/{course_id}/lecture-sessions/{session_id}/snapshot`
  - 增量保存脚本和事件日志。

- `GET /api/courses/{course_id}/lecture-sessions/{session_id}`
  - 返回资源、快照、录播状态。

### 录制产物

当前 `LiveTalking` 录制输出固定为 `data/record.mp4`，需要改成按会话唯一命名。

推荐目录：

```text
backend/course_data/courses/{course_id}/generated_materials/lecture_sessions/{session_id}/
  snapshot.json
  recording.mp4
  metadata.json
```

`metadata.json` 保存：

```json
{
  "session_id": "ai_session_20260420_001",
  "source_ppt_material_id": "ppt_001",
  "recording_status": "completed",
  "recording_url": "/api/courses/computational-thinking/lecture-sessions/ai_session_20260420_001/recording",
  "created_at": "2026-04-20T00:00:00Z",
  "updated_at": "2026-04-20T00:00:00Z"
}
```

## 数据流

### 创建会话

1. 用户在工作台选择已完成 PPT 并发起 AI 讲解。
2. 后端创建 `ai_lecture_session` 课程资源。
3. 后端保存初始快照。
4. 前端跳转实时讲解页。

### 开始实时讲解

1. 前端向 `LiveTalking /offer` 发起 WebRTC 协商。
2. `LiveTalking` 返回 `sessionid`。
3. 前端保存 `sessionid`。
4. 前端调用业务网关生成脚本。
5. 前端用真实 `sessionid` 逐句调用 `speak_sentence`。

### 实时打断

1. 用户输入问题。
2. 前端调用 `stop_speaking(sessionid)`。
3. 前端调用 `interrupt_and_ask(sessionid, question, slide_context, interrupted_sentence)`。
4. 后端生成回答并转发给 `LiveTalking` 播报。
5. 前端将问题和回答写入会话快照。
6. 回答完成后继续原讲解队列。

### 结束并入库

1. 用户结束讲解。
2. 前端调用录制停止接口。
3. 后端移动录制文件到课程目录。
4. 后端更新课程资源 `recording_url` 和 `generation_state`。
5. 课程资源页展示 `回看录播` 和 `继续互动`。

### 继续互动

1. 用户在课程资源页点击 `继续互动`。
2. 前端打开实时讲解页并加载 `session_snapshot_id`。
3. 前端恢复大纲、脚本、事件日志和最近进度。
4. 前端重新建立新的 WebRTC 会话，获得新的实时 `sessionid`。
5. 后续打断继续写入同一个会话快照或派生一个新的会话版本。

## 状态机

`ai_lecture_session` 的推荐状态：

- `created`：资源已创建，尚未开始实时会话。
- `live_ready`：WebRTC 会话已建立。
- `speaking`：正在讲解。
- `interrupted`：正在处理用户打断。
- `recording`：录制进行中。
- `recording_processing`：录制已结束，正在转存。
- `completed`：录播和快照均已可用。
- `failed`：会话或录制失败。

## 错误处理

- WebRTC 协商失败：提示实时连接失败，允许重试连接。
- `sessionid` 丢失：禁止播报、停止和打断按钮，提示重新连接。
- 录制开始失败：允许继续实时讲解，但课程资源标记为“无录播，仅可继续互动”。
- 录制停止失败：保留会话快照，标记录播失败，提供重试转存。
- 快照保存失败：前端保留本地事件队列，下一次成功请求时补写。
- 录播文件不存在：课程资源隐藏回看按钮，保留继续互动按钮。

## 测试计划

### 前端

- WebRTC `/offer` 返回 `sessionid` 后，控制接口使用该真实 `sessionid`。
- 没有 `sessionid` 时，播报、停止、打断按钮不可用。
- `ai_lecture_session` 资源在课程资源页展示两个入口。
- `recording_url` 缺失时只展示继续互动入口。
- 点击继续互动能携带 `courseId`、`materialId`、`snapshotId` 进入实时讲解页。

### 后端

- 创建 AI 讲解会话时生成课程资源和快照文件。
- 开始录制会正确转发到 LiveTalking `/record`。
- 停止录制后将文件移动到唯一会话目录。
- 同一课程下多个会话不会互相覆盖录制文件。
- 快照增量保存能追加脚本和打断事件。
- 课程材料列表能返回 `material_type=ai_lecture_session`。

### 集成

- 从工作台选择 PPT 创建 AI 讲解会话。
- 实时页建立 WebRTC 连接并取得真实 `sessionid`。
- 逐句讲解、停止、打断问答都命中同一个 `sessionid`。
- 结束后课程资源中出现该 AI 讲解会话。
- 回看录播可以播放历史课。
- 继续互动可以重新建立实时会话并支持新的打断。

## 验收标准

1. 课程资源中不再把实时 AI 讲解误展示为普通 `mp4` 视频。
2. 已完成的 AI 讲解资源至少能展示 `回看录播` 或 `继续互动` 其中一种可用入口。
3. 实时讲解页所有控制动作都使用 WebRTC 协商返回的真实 `sessionid`。
4. 一次讲解中的历史打断能出现在录播和会话快照中。
5. 回看录播不支持新的打断；继续互动支持新的打断。
6. 多次生成或录制不会覆盖已有课程资源。

## 迁移说明

之前的“课程资源直接播放教学视频”设计只适用于离线 `mp4` 资产。对于实时可打断的 AI Lecturer，本设计取代单纯 `video` 资源模型。

后续实现时可以保留离线 `video` 类型，用于完整导出的视频；新增 `ai_lecture_session` 类型，用于实时讲解和录播双态资源。
