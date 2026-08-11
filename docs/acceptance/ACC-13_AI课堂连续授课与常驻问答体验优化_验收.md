# ACC-13 AI 课堂连续授课与常驻问答体验优化验收

> **状态**：实施完成；自动化与核心真实 E2E 通过，人工听感/长链路签收待完成
> **日期**：2026-08-11
> **对应规格**：[SPEC-13](../spec/SPEC-13_AI课堂连续授课与常驻问答体验优化.md)
> **实施计划**：[2026-08-11-ai-classroom-continuous-playback-and-persistent-qa.md](../superpowers/plans/2026-08-11-ai-classroom-continuous-playback-and-persistent-qa.md)
> **基线关系**：ACC-12 已通过；本验收不得破坏其鉴权、幂等、历史隔离、中断恢复和 TTS 降级能力。

## 1. 验收目标

本验收判定以下五项产品反馈是否真实闭环：

1. 实时问答不调用 RAG/向量/BM25/reranker，只使用当前课堂可信上下文。
2. 学生问题发送后立即显示，学生消息在右、AI 消息在左。
3. 当前页完成后自动进入并播放下一页，末页停止。
4. 新生成讲解与实时回答使用相同的年轻女声配置档 `qwen-tts / Cherry / 1.0`。
5. 问答区常驻右侧并替换“讲解提词”，任何验收视口都不覆盖舞台和播放控制。

## 2. 验收环境与前置条件

- 使用包含 SPEC-13 实现的同一提交运行前端、FastAPI 后端和 OpenMAIC sidecar。
- 前端默认 `http://localhost:5173`，后端默认 `http://localhost:8001`，sidecar 默认 `http://localhost:3000`；实际端口不同时记录真实地址。
- 使用有课程读取权限的学生账号；另准备第二个学生账号验证会话隔离。
- 选用至少 3 个 scene、每页至少 2 条 speech action 的真实课堂。
- 配置并启用服务端 provider `qwen-tts`，环境档为 `Cherry / 1.0`。
- TTS 音色验收必须新建或显式重新生成课堂；已有 narration 缓存不作为失败或通过证据。
- 浏览器允许音频播放；开发者工具保留 Network 和 Console 记录。

## 3. 通过规则

- AC13-01～AC13-12 全部为强制项，任一失败则 ACC-13 不通过。
- 自动化命令必须返回 0；明确要求“无匹配”的 `rg` 命令应返回 1 且无输出。
- 人工端到端用例 B1～B8 必须全部执行；截图、日志、课堂 ID 和听感记录必须能追溯到同一待验收提交。
- 外部 LLM/TTS 短时不可用造成的失败应记录为环境阻塞，修复或恢复后重跑，不能跳过。
- “语音自然”不能只通过 provider 名称判断；既要证明配置一致，也要人工试听新生成讲解和回答。

## 4. 验收矩阵

| ID | 验收点 | 判定标准 | 证据 | 结果 |
| --- | --- | --- | --- | --- |
| AC13-01 | 问答无检索 | 代码无 live-Q&A RAG 符号；一次真实提问日志无 VectorSearch/BM25/reranker/RAG 阶段 | A1、B1 | 通过 |
| AC13-02 | 本地可信上下文 | prompt 含当前 scene、断点、前页尾部、最近 6 轮；无知识库参考；信息不足时说明边界 | A2、B2 | 自动化通过 |
| AC13-03 | 发送才打断 | 聚焦和输入期间授课继续；发送有效问题时才暂停；无效输入不暂停 | A3、B3 | 通过 |
| AC13-04 | 问题即时出现 | 延迟 POST 时，学生气泡在网络响应前可见；失败后保留并可用同一 ID 重试 | A3、A4、B3 | 通过 |
| AC13-05 | 对话方向与去重 | 学生气泡/头像在右，AI 在左；服务端返回后问题只出现一次 | A4、B3 | 通过 |
| AC13-06 | 常驻布局 | 无浮动入口/关闭/遮罩/讲解提词；宽屏、演示和窄屏不遮挡舞台或控制 | A4、A8、B4 | 通过（1366、1024、720） |
| AC13-07 | 自动下一页 | 连续 3 页按 1→2→3 自动进入并播放，不需人工点击 | A5、A8、B5 | 自动化通过；真实三页观察待签收 |
| AC13-08 | 完成边界 | 末页不循环；重复或 stale completion 不跳页；enter 失败不继续连跳 | A5、B5 | 自动化通过 |
| AC13-09 | 问答后连续授课 | 回答结束按原 checkpoint 恢复；本页完成后仍自动播放下一页 | A3、A5、B6 | 自动化与真实恢复通过 |
| AC13-10 | 统一新生成语音 | 新课堂 narration 与回答均记录 `qwen-tts / Cherry / 1.0`，人工听感一致且较原讲解自然 | A6、A7、B7 | 配置与回答 TTS 通过；人工试听待签收 |
| AC13-11 | 补全路径一致 | 缺失 narration 通过同一 OpenMAIC profile 补全，无 `/audio/speech` 或 `alloy` 课堂 fallback | A6、A7、B8 | 通过 |
| AC13-12 | 既有能力回归 | 鉴权、学生隔离、幂等、浏览器 TTS 降级、手动翻页、构建和 lint 均通过 | A6、A9、B8 | 通过（真实降级预制 turn 未执行） |

## 5. 自动化与静态验收

所有命令从仓库根目录运行，除非小节另有 `Set-Location`。

### A1. live Q&A 无 RAG 静态门禁

```powershell
rg -n "rag_search|rag_answer|_search_course_knowledge|课程知识库参考|rag_ms|rag_degraded" Edu_AI/api/src/app/services/classroom_qa_prompt.py Edu_AI/api/src/app/services/classroom_qa_service.py
```

预期：无输出，退出码 1。

再检查 live Q&A 服务没有间接导入检索组件：

```powershell
rg -n "VectorSearch|BM25|Reranker|hybrid_search|knowledge_base" Edu_AI/api/src/app/services/classroom_qa_service.py Edu_AI/api/src/app/services/classroom_qa_prompt.py
```

预期：无输出，退出码 1。

### A2. prompt 与服务单元测试

```powershell
Set-Location Edu_AI/api
python -m pytest src/tests/test_classroom_qa_prompt.py src/tests/test_classroom_qa_service.py -q
```

必须覆盖并通过：

- 当前 scene 完整讲稿、已完成讲稿、被打断 action、前一 scene 尾部和最近 6 轮问答。
- `ClassroomQaContext` 不存在 `rag_answer`。
- unsupported 问题明确上下文边界。
- 服务调用 LLM/TTS 前没有 retrieval dependency。
- 事件含 `context_ms/llm_ms/tts_ms/total_ms`，不含 RAG 字段。

### A3. 状态机与中断恢复

```powershell
Set-Location Edu_AI
npm test -- src/stitch/classroomQa/classroomQaState.test.ts src/stitch/classroomQa/useClassroomInterruption.test.ts
```

必须覆盖并通过：

- 初始状态为 `ready`，无 `isOpen/closed/drafting`。
- 输入不调用 `suspend`；有效发送按“断点/暂停—optimistic dispatch—HTTP”顺序执行。
- optimistic dispatch 不等待 HTTP promise。
- 失败保留问题和 `clientTurnId`；重试复用 ID；放弃只恢复一次。
- 回答音频结束后恢复；翻页/卸载后的旧回答不能恢复旧页。

### A4. 常驻面板组件

```powershell
Set-Location Edu_AI
npm test -- src/stitch/classroomQa/ClassroomQaPanel.test.ts
```

必须覆盖并通过：

- panel 是常驻 aside，不存在 dialog、浮动入口、关闭按钮和 overlay。
- active turn 在 durable turns 之前即可见，按 `clientTurnId` 去重。
- 学生与 AI 使用不同方向 class；pending/error 控件归属于 active turn。
- `ClassroomPlayer` 工作区内只有常驻问答，不再包含“讲解提词”或 transcript secondary panel。

### A5. 自动连续播放

```powershell
Set-Location Edu_AI
npm test -- src/openmaic/pagePlaybackController.test.ts src/stitch/classroomQa/classroomAutoplay.test.ts
```

必须覆盖并通过：

- 当前 playing scene/revision 首次完成返回 `true`。
- 重复、stale、非 playing 和已离开页面的完成返回 `false`。
- `true` 且存在下一页时严格执行 `enter(next)` 后 `play()`。
- 末页不调用 enter/play；enter 失败不递归进入更多页面。

### A6. Python TTS 与媒体回归

```powershell
Set-Location Edu_AI/api
python -m pytest src/tests/test_openmaic_client.py src/tests/test_openmaic_tts_service.py src/tests/test_classroom_media.py src/tests/test_classroom_qa_routes.py src/tests/test_classroom_qa_store.py -q
```

必须覆盖并通过：

- generate-classroom 请求显式发送 `ttsProviderId=qwen-tts`、`ttsVoice=Cherry`、`ttsSpeed=1.0`。
- 回答和缺失 narration 复用同一 OpenMAIC TTS service。
- base64/格式/大小/超时校验继续有效。
- 现有 narration URL 不被覆盖。
- session owner、音频鉴权、路径 containment、100 轮截断和幂等继续有效。

### A7. Sidecar 配置档

```powershell
Set-Location openmaic-sidecar
pnpm test -- tests/server/classroom-media-generation.test.ts tests/server/classroom-generation-tts-profile.test.ts
```

必须覆盖并通过：

- 请求指定的 provider 即使不是启用列表第一项也会被使用。
- 未知/禁用 provider 明确失败，不暗中换 provider/voice。
- route 不接受或转发客户端 secret/base URL。
- voice/speed 被传递给每条新生成 speech audio。

静态补充检查：

```powershell
rg -n 'alloy|/audio/speech' Edu_AI/api/src/app/services/classroom_media.py
```

预期：无输出，退出码 1。

### A8. 确定性浏览器测试

```powershell
Set-Location Edu_AI
$env:PLAYWRIGHT_PORT='5187'
$env:VITE_API_BASE_URL='http://localhost:8001'
pnpm exec playwright test tests/e2e/classroom-persistent-qa.spec.ts --project=desktop1366 --project=compact1024
```

必须在 route stub/fixture 下覆盖：

- 延迟 POST 时问题立即显示。
- 左右消息位置通过 bounding box 判定，而非只检查 class 名。
- 1440×900、演示模式和 390×844 都不发生覆盖。
- 三页自动播放、末页停止、stale completion 不跳页。

### A9. 全量质量门禁

```powershell
Set-Location Edu_AI
npm test
npm run lint
npm run build
```

```powershell
Set-Location openmaic-sidecar
pnpm lint
pnpm build
```

预期：全部退出码为 0。若仓库既有、与本变更无关的失败存在，必须在本文件记录完整命令、失败项、基线提交复现结果和隔离结论；不能直接写“通过”。

## 6. 真实浏览器端到端验收

### B1. 无检索与时延阶段

1. 清空后端终端的旧日志标记，打开一节正在播放的真实课堂。
2. 输入与当前页直接相关的问题并发送，例如“这里为什么要选择第一个元素作为基准值？”
3. 保留从 POST 开始到返回的后端日志。

通过标准：

- 日志没有 VectorSearch、BM25、reranker、RAG 查询/降级记录。
- `classroom_qa_turn` 有 `context_ms/llm_ms/tts_ms/total_ms`，没有 `rag_ms/rag_degraded`。
- 回答引用当前讲稿内容且不需要课程知识库检索。

### B2. 上下文边界

1. 在当前讲稿覆盖范围内连续提出两个追问，第二问使用代词指代第一问内容。
2. 再问一个当前课堂材料不能支持的具体事实。

通过标准：最近问答能维持指代；超出材料的问题明确说明当前讲解信息不足并自然引回当前知识点，不伪造来源。

### B3. 发送时暂停与即时气泡

1. 课堂正在发声时聚焦输入框并输入至少 10 秒，不发送。
2. 确认讲解和页面 action 继续。
3. 在 Network 中启用慢速或用测试代理延迟 POST，点击发送。
4. 在响应前截图；再等待回答并截图。

通过标准：

- 输入阶段不暂停；发送瞬间暂停。
- 响应前学生问题已在右侧出现，头像在最右；AI pending 在左。
- 响应后 AI 回答在左，学生问题没有重复。
- 模拟一次 POST 失败，问题仍保留并能重试同一 turn。

### B4. 常驻布局与响应式

分别在以下模式截图并检查：

1. 1440×900 普通桌面：目录 / 舞台 / 问答栏。
2. 演示或全屏：舞台 / 问答栏，目录隐藏。
3. 390×844 窄屏：舞台在上、问答在下。

通过标准：问答始终可见；没有铃铛/浮动入口、关闭按钮、遮罩和“讲解提词”；问答不盖住舞台、字幕、上一页/下一页、播放或停止控制；消息区可滚动，输入区可操作。

### B5. 连续三页自动授课

1. 从三页课堂的第 1 页开始播放，不操作页面导航。
2. 观察第 1 页结束进入第 2 页并自动发声，第 2 页结束进入第 3 页并自动发声。
3. 等待第 3 页结束至少 5 秒。

通过标准：顺序严格为 1→2→3；每页进入后自动播放；末页停留在完成态，不回到第 1 页、不重复最后一页。随后手动上一页/下一页仍正常。

### B6. 问答恢复后继续翻页

1. 在第 1 页某条 speech 中途发送问题。
2. 听完回答和衔接语。
3. 确认被中断 speech 从头恢复，继续等待本页结束。

通过标准：不跳过被中断 action；回答结束只恢复一次；第 1 页完成后仍自动进入并播放第 2 页。

### B7. 讲解与回答音色

1. 记录验收提交和新生成课堂 ID。
2. 从日志或请求记录课堂生成 narration 的 provider、voice、speed。
3. 在同一课堂提问，记录回答 TTS 的 provider、voice、speed。
4. 同一验收人连续试听至少 30 秒讲解、一个完整回答和恢复后的讲解。

通过标准：三段均为 `qwen-tts / Cherry / 1.0`；讲解与回答听感为同一年轻女声音色，语速一致，无明显机械断句、突变音色或回答后切回死板旧音色。记录试听人、时间和一句具体评价。

### B8. 缺失音频、降级与隔离

1. 构造或选择一条 narration URL 缺失但其他已存在的测试课堂，触发补全。
2. 证明缺失项用共享 profile 生成，已有项没有被重写。
3. 临时让服务端 TTS 返回失败，提问并验证浏览器 TTS/文字兜底后恢复。
4. 用第二个学生账号打开同一课堂。

通过标准：补全不走 `alloy`；既有文件 hash/mtime 不变；降级路径可继续授课；第二个学生看不到第一个学生的问答历史。

## 7. 证据记录

实施验收时在本节追加一次记录，字段必须完整：

```text
验收提交：
验收日期与时区：
验收人：
前端/后端/sidecar 地址：
学生账号标识（脱敏）：
课程 ID / 课堂 ID：
新生成音频目录或资源标识：
A1～A9 命令结果：
B1～B8 截图/日志路径：
讲解 TTS provider/voice/speed：
回答 TTS provider/voice/speed：
试听结论：
失败、隔离项与重跑结果：
最终结论：通过 / 不通过
```

### 2026-08-11 实施验收记录

```text
验收提交：9dae8af（功能代码基线 5b27415）
验收日期与时区：2026-08-11，Asia/Shanghai
验收人：Codex 自动化与浏览器技术验收；最终听感验收人待产品方填写
前端/后端/sidecar 地址：http://127.0.0.1:5190 / http://127.0.0.1:8001 / http://localhost:3000
学生账号标识（脱敏）：student；隔离账号由真实 E2E 动态注册
课程 ID / 课堂 ID：computational-thinking / IwhZs0-46W
新生成音频资源标识：turn_3ae2427f13666aa6，tts_status=ready
讲解 TTS provider/voice/speed：服务端共享配置 qwen-tts / Cherry / 1.0；本轮使用历史课堂音频，不作为新讲解听感证据
回答 TTS provider/voice/speed：qwen-tts / Cherry / 1.0
试听结论：自动播放与完整回答音频均成功结束；“年轻、有感情、与讲解一致”的主观评价待产品方签收
最终结论：代码与核心真实 E2E 通过；ACC-13 暂不签为最终通过
```

自动化证据：

- 后端全量：`python -m pytest src/tests -q`，1548 passed、3 skipped、0 failed，202.75 秒。
- 前端全量：`npm test`，304 passed、0 failed。
- sidecar 全量：`pnpm test`，1766 passed、0 failed。
- lint：前端 0 errors / 46 个既有 warnings；sidecar 0 errors / 15 个既有 warnings。
- 构建：前端 `npm run build` 成功；sidecar 在 worktree 补齐 workspace 依赖后以 `next build --webpack` 成功。默认 Turbopack 因 `node_modules` junction 指向 worktree 外而拒绝运行，属于隔离环境限制。
- 确定性浏览器：`classroom-persistent-qa.spec.ts` 在 `desktop1366`、`compact1024` 共 4 个场景通过。
- 真实浏览器：`classroom-realtime-qa.real.spec.ts --project=desktop1366`，1 passed、1 skipped；通过项覆盖 checkpoint 中断、响应前 optimistic 气泡、真实 LLM、受保护 TTS 音频、恢复、持久化、演示/720 布局、第二用户隔离和跨用户音频 404。
- 真实日志：LLM `qwen3.5-plus` 用时 4281ms；QA POST 200；回答音频 GET 200；本次请求日志无 VectorSearch、BM25、reranker 或 RAG 阶段。

尚需产品方完成后才能把本文状态改为“通过”：

1. 用本提交新生成或显式重生成的课堂，连续观察至少 3 页真实 narration 自动播放至末页。
2. 同一验收人试听至少 30 秒新讲解、一个完整回答和恢复后讲解，并记录对年轻女声、情感和断句的主观评价。
3. 如需严格覆盖 B8 的真实降级分支，提供一个预制 `tts_status=failed` turn 后重跑脚本第二用例；单元/集成测试中的浏览器 TTS 降级已通过。

## 8. 签收规则

当且仅当 AC13-01～AC13-12 及 B1～B8 全部通过：

1. 将本文状态改为“通过”，并写入真实验收提交与证据。
2. 将 SPEC-13 状态改为“已完成并通过 ACC-13”。
3. 更新 `docs/spec/README.md`、`docs/acceptance/README.md` 和 `项目总览地图.md`。
4. 若仍有已知限制，明确写为非阻塞限制；不得用限制掩盖强制项失败。
