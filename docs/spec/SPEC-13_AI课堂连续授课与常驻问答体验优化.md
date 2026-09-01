# SPEC-13 AI 课堂连续授课与常驻问答体验优化

> **状态**：设计已确认，待实施并通过 ACC-13
> **日期**：2026-08-11
> **验收文档**：[ACC-13](../acceptance/ACC-13_AI课堂连续授课与常驻问答体验优化_验收.md)
> **实施计划**：[2026-08-11-ai-classroom-continuous-playback-and-persistent-qa.md](../superpowers/plans/2026-08-11-ai-classroom-continuous-playback-and-persistent-qa.md)
> **关联规格**：SPEC-02、SPEC-04、SPEC-06、SPEC-07、SPEC-08、SPEC-12

## 1. 背景与问题

SPEC-12 已交付文字提问、讲课中断、上下文回答、回答 TTS 和自然续讲。实际验收暴露出五类体验问题：

1. 实时问答同步执行课程 RAG、BM25 和 reranker，首字响应被检索链路显著拖慢；当前课堂讲稿和断点信息已经足以回答课堂内问题。
2. 学生问题只有服务端 turn 返回后才进入历史，造成“点击发送后消息消失”；学生和 AI 气泡也都按左侧头像布局。
3. 当前页播放完成只标记 `completed`，不会进入下一页继续授课。
4. 问答 TTS 固定使用 `qwen-tts / Cherry / 1.0`，课堂讲解却依赖 sidecar 的首个启用 provider 或 Python fallback 的 `alloy`，导致音色和表现不一致。
5. 问答面板使用浮层覆盖舞台，右侧原有“本页讲解提词”信息价值较低，且浮层在窄屏上遮挡更明显。

本规格是对已完成 SPEC-12 的增量修订，不重写其会话持久化、权限、幂等和音频鉴权协议。

## 2. 覆盖关系

以下决策自 SPEC-13 生效，并覆盖 SPEC-12 的对应描述：

| SPEC-12 原约定 | SPEC-13 新约定 |
| --- | --- |
| 打开提问框立即暂停 | 提问区常驻；输入不暂停，点击发送才捕获断点并暂停 |
| Agent 使用当前课堂上下文和课程 RAG | Agent 只使用服务端重建的本地可信课堂上下文，不调用 RAG、向量检索、BM25 或 reranker |
| 问答面板可打开、关闭并浮在舞台上 | 问答作为工作区右侧常驻栏，替换“本页讲解提词”区域 |
| 页面完成不自动导航 | 有下一页时自动进入并播放下一页；末页停留在完成态 |
| 讲解与问答 TTS 可走不同默认路径 | 二者使用同一服务端课堂语音配置档 |

SPEC-12 的以下约定保持不变：只接受文字提问；单次只处理一个问题；回答后按断点恢复；学生会话隔离；问答不改写课件；相同 `client_turn_id` 幂等；回答音频受鉴权保护；服务端 TTS 失败后允许浏览器 TTS 降级。

## 3. 目标与非目标

### 3.1 目标

- 学生在讲课过程中始终能看到问答历史和输入框。
- 学生提交问题后，问题在本地立即显示，随后才等待 LLM 和 TTS。
- 输入问题不打断授课；发送有效问题才原子地捕获断点、暂停课堂并提交请求。
- 问答只使用当前课程材料、当前页面讲稿、播放断点和最近问答，移除外部检索时延。
- 学生消息靠右、AI 消息靠左，状态和错误信息不破坏对话顺序。
- 当前页自然播放完后自动播放下一页，直到末页。
- 新生成或补生成的课堂讲解与实时回答使用相同的年轻女声配置档，默认 `qwen-tts / Cherry / 1.0`。
- 桌面、演示模式和窄屏均不遮挡舞台及核心播放控制。

### 3.2 非目标

- 不增加语音提问、ASR、唤醒词或数字人。
- 不实现问题队列、回答中插问或 LLM/TTS 双流式播放。
- 不保留“讲解提词”第二面板，也不新增其开关。
- 不让问答访问网页、课程知识库检索、向量库或其他 agent 工具。
- 不自动重生成已有课堂的历史音频，也不在本期提供批量换声 UI。
- 不为没有可播放 action 的空页面推断自动跳页规则。
- 不承诺情感风格指令；本期以固定年轻女声音色、统一 provider 和统一语速保证一致性。

## 4. 当前实现证据

### 4.1 问答检索

`backend/src/app/services/classroom_qa_service.py` 当前注入 `rag_search`，在 `submit_turn` 中同步执行检索并把 `rag_answer` 传入 prompt；日志含 `rag_ms` 和 `rag_degraded`。`classroom_qa_prompt.py` 明确拼接“课程知识库参考”。因此日志中会出现 VectorSearch、BM25 和 reranker，且请求必须等待检索结束。

### 4.2 消息延迟与布局

`ClassroomQaPanel.tsx` 只渲染 `state.turns`。提交时的问题位于 `state.activeTurn`，直到服务端 `turn_received` 才追加到 `turns`，因此不能即时显示。现有 `.question` 和 `.answer` 共用头像在左的 grid 布局。

### 4.3 页面完成

`pagePlaybackController.ts` 的 `complete(sceneIndex, revision)` 只校验 revision 并把当前页标记为 `completed`；`ClassroomPlayer.tsx` 的 renderer `onComplete` 也只调用该方法，不导航、不播放下一页。

### 4.4 TTS 配置漂移

- 问答：`ClassroomQaTtsService` 显式使用 `OPENMAIC_LIVE_TTS_PROVIDER`、`OPENMAIC_LIVE_TTS_VOICE`、`OPENMAIC_LIVE_TTS_SPEED`，默认 `qwen-tts / Cherry / 1.0`。
- 课堂生成：Python `OpenMaicClient.generate_classroom` 只传 `enableTTS`；sidecar 从启用 provider 中自行选择并使用其默认 voice。
- 缺失音频补全：Python 路径可通过 OpenAI-compatible `/audio/speech` 和默认 `alloy` 生成。

这三条路径没有共享可验证的课堂语音配置档。

## 5. 总体设计

```text
ClassroomPlayer
  ├─ Catalog（普通桌面模式）
  ├─ Stage + ManagedPagePlaybackController
  │    └─ valid completion → enter(next) → play(next)
  └─ Persistent ClassroomQaPanel
       ├─ durable turns
       ├─ optimistic active turn
       └─ submit → checkpoint + suspend → API → answer TTS → resume

POST classroom QA turn
  → validate material/checkpoint/session
  → build trusted local classroom context
  → LLM answer + transition
  → shared OpenMAIC classroom speech profile
  → persist turn/audio

Generate classroom / fill missing narration
  → same shared OpenMAIC classroom speech profile
```

## 6. 无 RAG 的课堂问答上下文

### 6.1 可信上下文来源

后端必须从课程存储和会话存储重新读取并构造以下内容：

1. 课堂标题、课程 ID、当前 scene ID、标题和类型。
2. 当前 scene 的完整 speech 文本。
3. checkpoint 之前已经完成的当前 scene speech。
4. 被打断 action 的 speech 文本；如果位于 action 之间则为空。
5. 前一 scene 最后 3 条 speech，用于页面边界衔接。
6. 当前学生在本课堂最近 6 轮问答。
7. 学生原始问题。

客户端只提交 checkpoint 标识，不得提交或覆盖上述讲稿文本。

### 6.2 明确禁止的依赖

实时问答请求链路不得调用：

- `rag_search` 或 `_search_course_knowledge`；
- VectorSearch、embedding 或向量数据库；
- BM25、reranker 或混合检索；
- Web 搜索或其他 agent 工具。

`ClassroomQaContext` 删除 `rag_answer`；prompt 删除“课程知识库参考”和“知识库不足”等描述。模型遇到当前可信上下文不能支持的问题时，应简短说明“当前讲解信息不足”，再把话题引回当前知识点，不得编造。

### 6.3 API 与观测

GET/POST/audio API 契约、鉴权和持久化 schema 不变。结构化事件调整为：

```text
classroom_qa_turn
  session_id
  turn_id
  course_id
  classroom_id
  checkpoint_scene_id
  checkpoint_action_id
  context_ms
  llm_ms
  tts_ms
  total_ms
  tts_status
  result
  error_code
```

删除 `rag_ms` 和 `rag_degraded`。`context_ms` 只衡量本地材料/会话读取与 prompt 构造，不得包含外部网络检索。

## 7. 常驻问答与乐观消息

### 7.1 状态机

问答区常驻，因此状态不再表达打开/关闭：

```ts
export type ClassroomQaPhase =
  | "ready"
  | "submitting"
  | "loading_audio"
  | "playing_answer"
  | "resuming"
  | "error";
```

```text
ready → submitting → loading_audio → playing_answer → resuming → ready
                    └───────────────────────────────↑
submitting/loading_audio → error → submitting（重试同一 clientTurnId）
                               └→ resuming（放弃并继续授课）
```

移除 `isOpen`、`closed` 和 `drafting`。任一时刻仍最多只有一个未完成 turn。

### 7.2 发送时序

1. 学生输入或聚焦输入框：授课继续，不捕获 checkpoint。
2. 学生点击发送或使用允许的键盘快捷键：校验 trim 后问题长度为 1～1000。
3. 同一同步事件中生成 `client_turn_id`、读取最新 runtime checkpoint、暂停当前播放、创建 optimistic active turn、清空输入框。
4. React 下一次渲染必须立即显示学生问题；不得等待 POST 返回。
5. 发送 API 请求；AI 一侧显示“正在结合当前讲解回答…”占位状态。
6. 返回 durable turn 后，用相同 `client_turn_id` 替换 active turn，不重复显示学生问题。
7. 播放回答音频并恢复课堂；状态回到 `ready`，历史仍可见。

如果在步骤 3 无法获得有效 checkpoint，不创建 active turn、不清空输入，显示确定性错误，授课状态保持原样。

### 7.3 可见消息投影

```ts
visibleTurns = durableTurns + activeTurnWhenNotDurable;
```

匹配键必须是 `client_turn_id`。服务端 turn 到达、会话刷新或重试返回同一 turn 时只能显示一次。错误状态保留学生问题和原 `client_turn_id`，提供“重试”和“放弃并继续授课”。

### 7.4 对话布局

- 学生行整体右对齐，学生头像在气泡右侧。
- AI 行整体左对齐，AI 头像在气泡左侧。
- 学生与 AI 气泡宽度不超过消息区的 82%，正文允许换行和长词断行。
- “思考中”、TTS 加载、恢复和错误提示附着于对应 active turn，不作为伪聊天消息写入持久历史。
- 新消息出现时仅在用户接近底部时自动滚动；查看旧消息时不得强制抢滚动位置。

## 8. 页面布局

`ClassroomQaPanel` 作为 `.classroom-console__workspace` 的固定布局子项，替换当前 `.classroom-console__assistant` 中的“本页讲解提词”。删除浮动入口、关闭按钮、遮罩和 `role=dialog`；保留明确的区域标题和可访问标签。

布局断点：

| 视口/模式 | 布局 |
| --- | --- |
| 桌面 `>= 1100px` | 课程目录 / 舞台 / 340～380px 问答栏 |
| 演示或全屏 | 舞台 / 340～380px 问答栏，课程目录隐藏 |
| 窄屏 `< 960px` | 问答区位于舞台下方，进入正常文档流；限制消息区高度，不覆盖舞台和播放控制 |

960～1099px 可压缩目录或问答栏，但问答区不得转成浮层。问答栏在课堂数据加载时即可见；没有历史时展示简短空状态，不能占据输入区域。

## 9. 自动连续授课

### 9.1 完成判定

`ManagedPagePlaybackController.complete(sceneIndex, revision)` 改为返回 `boolean`：

- 当前 scene、revision 和 `playing` 状态完全匹配时，标记完成并返回 `true`。
- 旧 renderer 的迟到回调、已翻页回调、重复完成回调返回 `false`，不得触发导航。

### 9.2 自动下一页

`ClassroomPlayer` 在收到 `true` 后执行：

```ts
if (currentIndex < scenes.length - 1) {
  await controller.enter(currentIndex + 1);
  await controller.play();
}
```

约束：

- 下一页只有在 `enter` 成功后才调用 `play`。
- 末页保持 `completed`，不循环、不跳回第一页。
- 自动切页失败时停留在当前可恢复状态并显示错误，不递归重试。
- 用户手动上一页/下一页仍按现有语义工作。
- 问答中断后先恢复当前 action；当前页正常完成时再进入同一自动下一页流程。
- 没有 playback handle/action 的页面不在本期自动跳过。

## 10. 统一课堂语音配置档

### 10.1 单一配置来源

沿用现有服务端配置，语义扩展为“课堂讲解与实时回答共享配置档”：

```text
OPENMAIC_LIVE_TTS_PROVIDER=qwen-tts
OPENMAIC_LIVE_TTS_VOICE=Cherry
OPENMAIC_LIVE_TTS_SPEED=1.0
```

变量名称为兼容既有部署暂不重命名。默认选用用户已认可的年轻女声 `Cherry`；语速固定 1.0。配置只允许来自后端环境，不接受浏览器传入 provider、voice、base URL 或密钥。

### 10.2 课堂生成链路

`OpenMaicClient.generate_classroom` 增加 `tts_provider_id`、`tts_voice`、`tts_speed`，并传给 sidecar generate-classroom 路由。sidecar：

- 只接受 provider ID、voice 和 speed，不接受 secret/base URL；
- provider 必须存在于 sidecar 服务端配置且已启用；
- `generateTTSForClassroom` 必须使用请求指定的配置档，禁止退回“第一个启用 provider”；
- 每个 speech action 仍可保留 DSL 明确给出的合法 speed；没有 action 覆盖时使用共享 speed。

### 10.3 缺失讲解音频补全

`synthesize_classroom_speech_audio` 不再使用 OpenAI-compatible `/audio/speech` 和默认 `alloy`。它必须通过 OpenMAIC `/api/generate/tts` 调用同一配置档。实现应提取共享 OpenMAIC TTS helper，使问答和讲解复用请求校验、base64 解码、格式识别、大小限制与错误映射，避免再次漂移。

### 10.4 兼容性

- 现有课堂中已经落盘的 narration URL 和音频不被静默覆盖。
- 新建课堂、显式重新生成课堂、缺失 narration 补全使用新配置档。
- 问答音频行为与 API 保持兼容。
- 验收音色时必须新建或重新生成一个测试课堂，不能拿历史缓存音频判定失败。

## 11. 错误处理

| 场景 | UI/播放行为 |
| --- | --- |
| 空问题或超长 | 不暂停、不清空输入、不发送 |
| 捕获 checkpoint 失败 | 不创建 optimistic turn，保留输入并提示 |
| POST 失败 | 保留 optimistic 问题，显示重试/放弃；课堂保持暂停 |
| 重试成功 | 用相同 `client_turn_id` 去重并继续回答播放 |
| TTS 失败 | 按 SPEC-12 使用浏览器 TTS；仍从相同断点恢复 |
| stale checkpoint | 不按旧断点恢复；保留问题并提示课堂位置已变化 |
| 自动进入下一页失败 | 不跳过更多页面；显示错误并允许手动播放 |
| 迟到的页面完成回调 | `complete=false`，无 UI 跳转 |
| 共享 provider 不可用 | 课堂生成/补全明确失败并记录稳定错误码，不暗中换音色 |

## 12. 安全、性能与可访问性

- 沿用 SPEC-12 的课程 read、session owner、路径 containment 和音频白名单校验。
- prompt 内容全部来自服务端可信材料和当前用户会话，学生问题仍视为不可信文本，不得改变系统约束。
- 移除 RAG 后，不得以浏览器提交讲稿全文作为性能捷径。
- 问答 POST 的 `total_ms` 必须能被拆分为 context、LLM、TTS；验收不设置与外部模型波动冲突的绝对 SLA，但 `context_ms` 不得包含外部检索。
- 问答区域有可访问名称；消息列表使用日志语义或等价可读结构；发送、重试、放弃均可通过键盘操作。
- 回答播放时禁用发送，但输入框内容不丢失；状态不能只依赖颜色表达。

## 13. 验收准则映射

| ID | 可判定结果 |
| --- | --- |
| AC13-01 | 实时问答代码和运行日志均无 RAG、VectorSearch、BM25、reranker 调用 |
| AC13-02 | prompt 只含本规格列出的本地可信课堂上下文，信息不足时明确边界 |
| AC13-03 | 输入/聚焦不暂停；发送有效问题才暂停并捕获 checkpoint |
| AC13-04 | POST 未返回时学生问题已经显示，失败后仍保留且可重试 |
| AC13-05 | 学生头像/气泡在右，AI 头像/气泡在左，无重复 turn |
| AC13-06 | 问答常驻并替换讲解提词，桌面、演示和窄屏均不遮挡舞台/控制 |
| AC13-07 | 有下一页时当前页完成后自动进入并播放下一页 |
| AC13-08 | 末页不循环，迟到/重复完成回调不跳页 |
| AC13-09 | 问答恢复当前 action 后，页面完成仍自动连续授课 |
| AC13-10 | 新生成课堂与实时回答都显式使用 `qwen-tts / Cherry / 1.0` |
| AC13-11 | 缺失 narration 补全也使用同一配置档，不调用 `alloy` 路径 |
| AC13-12 | 既有问答鉴权、幂等、历史隔离、TTS 降级和手动翻页回归通过 |

## 14. 完成定义

只有同时满足以下条件，SPEC-13 才能标记为完成：

1. ACC-13 的自动化、静态检查和人工端到端用例全部通过并记录证据。
2. 使用真实新生成课堂验证连续至少 3 页自动播放。
3. 在真实模型和 Qwen TTS 环境完成一次“发送问题—即时显示—语音回答—恢复—自动下一页”。
4. 运行证据证明问答没有检索阶段，讲解和回答使用相同 provider、voice、speed。
5. 宽屏、演示模式和窄屏截图证明常驻问答不覆盖舞台和控制条。
6. SPEC-12 保留的权限、幂等、会话隔离和降级用例没有回归。
7. ACC-13 从“待验收”更新为“通过”，规格索引和项目地图同步更新。
