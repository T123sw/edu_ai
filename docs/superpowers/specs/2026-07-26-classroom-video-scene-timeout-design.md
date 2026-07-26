# AI 课堂视频长场景超时设计

## 背景与根因

课堂视频导出在修正前端渲染地址后，已经可以连接 `http://127.0.0.1:5173/#video-render` 并连续录制前四个场景。真实任务 `job_6706f3673fcd` 在第五个可录制场景失败，错误为：

```text
page.waitForFunction: Timeout 120000ms exceeded
```

当前 `scripts/videoPipeline.ts` 把同一个 `120000ms` 同时用于页面导航、渲染根节点挂载和整段场景播放。该课件第五个可录制场景的真实旁白长度为 `144.72s`，第七个为 `124.56s`，均大于固定的 `120s`。因此失败原因不是页面不可达，而是连接超时和内容播放超时混用了同一个配置。

## 目标

- 页面连接及渲染根节点挂载仍保持 `120s` 上限，快速暴露服务未启动或页面无法加载的问题。
- 单个场景的播放完成等待改为独立的 `600s` 上限，允许合法的长旁白完成。
- 保持现有 `--timeout-ms` 参数兼容，并增加可单独覆盖的场景播放超时参数。
- 超过 `600s` 的异常场景仍明确失败，不允许导出任务无限挂起。

## 方案

`VideoExportOptions` 保留 `timeoutMs`，其语义继续表示页面导航和渲染根节点等待超时；新增 `sceneTimeoutMs`，表示等待 `data-export-status` 进入完成或失败状态的最长时间。

命令行增加：

```text
--scene-timeout-ms <正整数>
```

默认值：

```text
timeoutMs = 120000
sceneTimeoutMs = 600000
```

调用关系：

1. `page.goto()` 使用 `timeoutMs`。
2. 等待 `[data-video-render-root]` 使用 `timeoutMs`。
3. 等待单场景播放完成使用 `sceneTimeoutMs`。
4. 后续 WebM 合并、字幕和 MP4 转码流程不变。

## 错误处理

- `--scene-timeout-ms` 缺失、非数字、零或负数时，在启动录制前直接报参数错误。
- 页面不可达仍在约两分钟内失败，不因场景上限提高而延迟。
- 场景在十分钟内未完成时，保留 Playwright 超时错误并由现有任务状态转换为 `VIDEO_EXPORT_FAILED`。
- 导出失败时继续沿用现有临时目录清理机制，不发布半成品。

## 验证

自动化验证包括：

- 参数解析默认产生 `timeoutMs=120000` 和 `sceneTimeoutMs=600000`。
- `--scene-timeout-ms` 可覆盖默认值。
- 非法场景超时参数被拒绝。
- 场景完成等待使用 `sceneTimeoutMs`，页面连接继续使用 `timeoutMs`。
- 视频导出相关测试、完整前端测试、lint 和生产构建通过。

真实验证使用课程 `computational-thinking`、课堂 `Ii0-7a0bpN` 重新执行导出，要求：

- 顺利越过原先在第五个可录制场景发生的 `120000ms` 超时。
- 生成非空的 `classroom.mp4`、字幕和时间线文件。
- `ffprobe` 能读取 MP4 的视频、音频编码及有效时长。

## 范围边界

本次不改变可录制场景选择规则。MP4 仍只录制具备确定性时间线的 `slide` 场景；`interactive` 和 `quiz` 需要用户输入，将在课堂播放器中渲染，但不进入本轮自动视频。

## 验收结果（2026-07-26）

真实导出任务 `job_691e361aabb6` 已成功完成，并越过原先超过 120 秒的场景：

- 共录制 8 个 slide 场景。
- 总时长 `754500ms`（12 分 34.5 秒）。
- `classroom.mp4`：`23,881,142` 字节。
- `classroom.srt`：`12,505` 字节。
- `timeline.json`：`50,139` 字节。
- 视频流：H.264、1920×1080、30fps。
- 音频流：AAC、单声道、24kHz。
- `ffprobe` 读取的容器时长为 `754.5s`，音频时长为 `754.459s`。

产物位于：

```text
Edu_AI/api/course_data/courses/computational-thinking/generated_materials/classrooms/Ii0-7a0bpN_media/video/
```

因此 MP4 导出失败的两个根因均已关闭：渲染端口与实际 Vite 端口一致，长场景使用独立的 600 秒播放超时。
