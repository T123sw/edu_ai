# ACC-12 · AI 课堂实时问答与中断恢复 · 验收文档

> **对应规格**：[`../spec/SPEC-12_AI课堂实时问答与中断恢复.md`](../spec/SPEC-12_AI课堂实时问答与中断恢复.md)  
> **实施计划**：[`../superpowers/plans/2026-08-10-ai-classroom-realtime-qa-implementation.md`](../superpowers/plans/2026-08-10-ai-classroom-realtime-qa-implementation.md)  
> **状态**：待实施、待验收  
> **验收原则**：自动化证明状态与边界，真实浏览器和真实 Qwen TTS 证明声音与恢复体验。

## 1. 验收范围

本验收覆盖：

- 学生文字提问入口；
- 打开提问框立即暂停；
- 句子级 checkpoint、句中重讲和句间续讲；
- 课堂上下文 + 课程 RAG + 学生本课堂历史的 Agent 回答；
- OpenMAIC Qwen TTS 调用、鉴权音频和浏览器 TTS 降级；
- 学生级历史隔离、刷新持久化、幂等和并发保护；
- 失败重试、放弃回答、翻页和卸载清理；
- 现有课堂播放、PPTX、视频 A 回归。

不验收语音提问、数字人、WebRTC、多人共享问答、流式 TTS 或把问答写回导出课件。

## 2. 环境门槛

执行真实验收前必须满足：

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8001/health → status=ok
Sidecar:  http://127.0.0.1:3000/api/health → capabilities.tts=true
Provider: http://127.0.0.1:3000/api/server-providers → tts.qwen-tts 存在
```

测试课堂至少包含：

- 两个 scene；
- 当前测试 scene 至少三条 speech action；
- 至少一条有 `audioUrl` 的 speech；
- 可用的学生课程 read 权限；
- 可产生课程 RAG 结果的知识库内容。

## 3. 验收标准

| 编号 | 标准 | 自动化证据 | 人工/集成证据 | 当前状态 |
| --- | --- | --- | --- | --- |
| AC-12-1 | 学生打开提问框时立即取消当前课堂音频并冻结 scene/action checkpoint | playback controller + interruption hook tests | 听感确认点击后当前讲解立即停止 | 未实施 |
| AC-12-2 | action 执行中打断，回答后从被打断 action 开头重播 | playback engine tests | 在一句中间打断并听到该句完整重播 | 未实施 |
| AC-12-3 | action 之间打断，回答后从下一条 action 继续 | playback engine tests | 在两句间暂停并确认不重复上一句 | 未实施 |
| AC-12-4 | Agent 上下文来自可信课堂数据，包含当前页、被打断 action、近期问答和课程 RAG | backend context/prompt tests | 对当前页指代问题回答正确 | 未实施 |
| AC-12-5 | 回答与衔接语分字段生成，TTS 播放两者的拼接文本 | parser + TTS request tests | 听到回答后有自然回课话术 | 未实施 |
| AC-12-6 | 成功路径实际调用 OpenMAIC `/api/generate/tts`，provider 为 `qwen-tts` | OpenMaicClient mock transport test | sidecar 日志或网络记录 | 未实施 |
| AC-12-7 | Qwen TTS 音频保存到 edu_ai 课堂媒体目录，浏览器通过鉴权 blob 播放 | store/API/frontend audio tests | 浏览器 network 不直接暴露 sidecar 临时 URL | 未实施 |
| AC-12-8 | Qwen TTS 失败时先保留文字，再降级浏览器 TTS；双失败可手动继续 | service + hook tests | 断开 sidecar 后走降级 | 未实施 |
| AC-12-9 | 历史按课程、课堂、学生隔离，刷新后仍在，其他学生无法读取音频或历史 | store/API auth tests | 两个学生账号交叉验证 | 未实施 |
| AC-12-10 | 相同 clientTurnId 幂等，不重复调用 LLM/TTS；不同并发 turn 返回 409 | backend concurrency tests | 快速双击不产生重复回答 | 未实施 |
| AC-12-11 | Agent/TTS/回答播放期间再次提交被前后端共同阻止 | state machine + API tests | UI 按钮禁用且无问题队列 | 未实施 |
| AC-12-12 | 取消草稿不创建 turn 并恢复；停止回答可立即继续授课 | hook/store tests | 两个按钮路径人工验证 | 未实施 |
| AC-12-13 | 翻页、退出或 revision 变化使旧 checkpoint 失效，旧回答不得恢复旧页 | stale checkpoint tests | 生成期间翻页后不跳回 | 未实施 |
| AC-12-14 | 问题长度、路径穿越、课程权限、owner 和音频登记白名单均受保护 | schema/API security tests | 非 owner 请求返回 404 | 未实施 |
| AC-12-15 | 全屏和普通模式均可提问，面板不遮挡核心舞台与播放控制 | component/browser tests | 桌面宽屏与窄屏检查 | 未实施 |
| AC-12-16 | 现有课堂播放、PPTX、视频 A 测试、lint 和 build 不退化 | 全量前端门禁 + 后端定向门禁 | 正常课堂无问答时行为不变 | 未实施 |
| AC-12-17 | 活跃源码和部署配置未重新引入 LiveTalking、WebRTC、AI Lecturer | 静态 grep gate | 无 | 未实施 |

## 4. 自动化验收命令

### 4.1 前端定向测试

```powershell
Set-Location D:\github\edu_ai\Edu_AI
pnpm exec tsx --test `
  src/openmaic/actionEngine.test.ts `
  src/openmaic/playbackEngine.test.ts `
  src/openmaic/pagePlaybackController.test.ts `
  src/stitch/classroomQa/classroomQaState.test.ts `
  src/stitch/classroomQa/useClassroomInterruption.test.ts `
  src/stitch/api/classroomQa.test.ts
```

预期：退出码 0，所有新增和原有定向用例通过。

### 4.2 后端定向测试

```powershell
Set-Location D:\github\edu_ai\Edu_AI\api\src
python -m pytest `
  tests/test_openmaic_client.py `
  tests/test_classroom_qa_store.py `
  tests/test_classroom_qa_prompt.py `
  tests/test_classroom_qa_service.py `
  tests/test_classroom_qa_routes.py `
  -q
```

预期：退出码 0；幂等、并发、owner、checkpoint、TTS 成功与降级全部通过。

### 4.3 前端全量门禁

```powershell
Set-Location D:\github\edu_ai\Edu_AI
pnpm test
pnpm run lint
pnpm run build
```

预期：

- test 退出码 0；
- lint 为 0 errors，既有 warning 数量不得因本功能增加；
- build 成功，无 TypeScript 或 Vite 解析错误。

### 4.4 后端相关回归

```powershell
Set-Location D:\github\edu_ai\Edu_AI\api\src
python -m pytest `
  tests/app/test_legacy_services_retired.py `
  tests/test_classroom_media.py `
  tests/test_classroom_persistence.py `
  tests/test_student_classroom_permissions.py `
  -q
```

如果真实测试文件名与计划执行期间仓库现状不一致，实施者必须在 ACC-12 中记录实际存在且覆盖同一边界的命令；不得删除回归类别。

### 4.5 旧链路静态门禁

```powershell
Set-Location D:\github\edu_ai
rg -n -S "LiveTalking|teaching_video_bridge|ai_lecturer_bridge|RTCPeerConnection" `
  Edu_AI/src `
  Edu_AI/api/src/app `
  Edu_AI/.env.example `
  Edu_AI/api/src/.env.example
```

预期：无本功能新增的运行时代码命中；历史注释或退休断言必须逐条说明，不得构成 import、路由、环境依赖或启动项。

## 5. 真实浏览器验收脚本

### 5.1 句中打断

1. 用学生账号打开一份包含至少三条旁白的 AI 课堂。
2. 播放当前页，在第二条旁白说到一半时点击“提问”。
3. 确认课堂音频立即停止，舞台保持当前页，输入框获得焦点。
4. 输入与当前句有关的问题并发送。
5. 确认只出现一个处理中状态，不能再次发送。
6. 确认回答文字出现，并听到 Qwen TTS 朗读回答和衔接语。
7. 确认第二条旁白从头重播，然后继续第三条。

### 5.2 句间续讲

1. 使用可控测试时钟或在两条旁白之间打开提问框。
2. 完成一轮问答。
3. 确认恢复时直接开始下一条旁白，不重复已完整结束的上一条。

### 5.3 历史隔离

1. 学生 A 完成两轮问答并刷新页面，确认两轮历史仍在。
2. 学生 B 打开同一课堂，确认看不到学生 A 的历史。
3. 使用学生 B 的 token 请求学生 A 的 session 或音频 URL。
4. 确认返回 404，响应不透露 owner 或资源路径。

### 5.4 TTS 降级

1. 保持前后端运行，临时停止 sidecar 或使用测试注入让 TTS 返回错误。
2. 提交问题，确认回答文字仍出现。
3. 有浏览器语音时确认自动降级朗读；无浏览器语音时显示“语音不可用”。
4. 点击“继续授课”，确认按 checkpoint 恢复且不重复提交该问题。

### 5.5 过期快照

1. 提交问题后，在回答返回前切换到下一页。
2. 确认旧回答结果不得让页面跳回上一页或播放上一页旁白。
3. 确认旧回答 blob URL 被撤销，控制台无未处理 Promise rejection。

### 5.6 布局

在普通模式、全屏演示、宽度 1280px 和窄屏布局分别检查：

- 提问入口可触达；
- 面板不会覆盖“上一页/播放/下一页”核心控制；
- 历史可滚动，输入框和取消/发送按钮始终可见；
- 焦点顺序、Escape 行为和 `aria-live` 状态可用。

## 6. TTS 调用证据

成功签收必须至少保存以下一种证据：

- sidecar 结构化日志，含 `provider=qwen-tts`、`audioId=turn_*`，不含密钥；
- 测试 mock transport 捕获的完整请求字段；
- 浏览器/后端 trace 关联同一 `turn_id` 的 `tts_status=ready` 与受鉴权音频请求。

证据必须证明调用的是服务端 Qwen TTS，而不是只证明浏览器 `SpeechSynthesis` 出声。

## 7. 验收记录规则

实施完成后在本节追加一次带日期的签收记录，内容必须包括：

- Git commit hash；
- §4 每条实际命令、退出码和通过数量；
- 使用的课堂 ID、scene ID、action ID；
- Qwen TTS 证据类型；
- 句中、句间、隔离、降级和布局的人工结论；
- 已知但不阻塞本规格的限制。

在上述证据齐全前，本文状态保持“待实施、待验收”，不得提前标记通过。
