# SPEC-10 · 视频 A 导出

> 状态：✅ 已实现并通过验收（2026-07-25）  
> 对应验收：[`../acceptance/ACC-10_视频A导出_验收.md`](../acceptance/ACC-10_视频A导出_验收.md)  
> 上游契约：[`SPEC-02_数据契约_Stage-Scene-Action-Slide.md`](SPEC-02_数据契约_Stage-Scene-Action-Slide.md)、[`SPEC-08_前端集成_DSL与Renderer播放.md`](SPEC-08_前端集成_DSL与Renderer播放.md)

## 1. 目标与边界

视频 A 复用交互课堂的 `Stage / Scene / Action / Slide` 与 `LessonTimeline`，在无头
Chromium 中按场景回放画面，再用 FFmpeg 生成 1080p MP4、SRT 和实测时间线。导出由
edu_ai 统一异步任务驱动，教师不需要离开课堂页。

本阶段不做逐帧虚拟时钟、动画 `localTimeMs` 驱动、`OffthreadVideo` 或渲染农场；
这些属于可选的视频 B。A 的输出契约必须能作为 B 的稳定输入。

## 2. 导出产物

每次成功导出原子发布三个固定文件：

| 文件 | 契约 |
| --- | --- |
| `classroom.mp4` | H.264 视频 + AAC 音频，1920×1080，30 fps |
| `classroom.srt` | UTF-8 字幕，序号与有效场景顺序一致，时间单调且不重叠 |
| `timeline.json` | 合并后的实测 `LessonTimeline`；场景起点按累计时长平移 |

`timeline.json` 不持久化浏览器生成的临时 `audioUrl`，旁白条目标记
`audioMixed: true`。没有可播放内容的场景不进入导出清单，也不产生空字幕。

## 3. 前端无头渲染入口

内部路由为：

```text
/#video-render?course_id=<course>&classroom_id=<classroom>&scene_index=<n>
```

- 真实课堂必须携带正常登录态；只有显式 `fixture=1` 的测试夹具可绕过登录。
- 页面使用与交互课堂相同的 `ClassroomPlayer`、动作编译器和受控视频插槽。
- 渲染根节点固定 1920×1080，并暴露稳定的
  `data-render-status`、`data-scene-id`、`data-scene-count` 与时间线 JSON。
- 录制器只在 `data-render-status="completed"` 后收口；失败或超时必须终止任务，
  不发布半成品。

## 4. Playwright / FFmpeg 流水线

`frontend/scripts/videoPipeline.ts` 按下列顺序运行：

1. Playwright Chromium 逐场景打开渲染路由并录制 WebM。
2. 等待播放器报告完成，读取该场景实测时间线。
3. FFmpeg 将场景转为 H.264 1920×1080/30 fps，并按时间线裁切。
4. 提取所有旁白音轨，按动作起点延迟后混音；没有旁白时保留合法静音轨。
5. 按场景顺序 concat，mux AAC 音频，生成 SRT 与合并时间线。
6. 用临时目录完成全部工作，只有完整成功后才替换正式产物。

命令行入口：

```powershell
cd Edu_AI
npm run export:classroom-video -- -- --base-url=http://127.0.0.1:5173 `
  --output-dir=<绝对目录> --course-id=<course> --classroom-id=<classroom> `
  --auth-json=<临时登录态文件> --ffmpeg=<ffmpeg路径> --overwrite
```

进程调用使用参数数组，不经过 shell。输出目录必须落在调用方指定的安全根目录内。

## 5. 后端任务与接口

任务种类为 `render_video`，复用 `EduJob` 的排队、进度、失败和结果协议。

| 接口 | 说明 |
| --- | --- |
| `POST /api/courses/{course_id}/classrooms/{classroom_id}/video/export` | 提交导出任务，返回统一 job/poll 数据 |
| `GET /api/courses/{course_id}/classrooms/{classroom_id}/video/artifacts/{filename}` | 登录后下载固定白名单产物 |

后端为每个任务创建 `.job-<jobId>` staging 目录，Node 导出成功后再原子发布，防止并发
任务覆盖或 Windows 文件锁导致旧 WebM 复用。认证信息只通过
`EDU_AI_EXPORT_AUTH_JSON` 环境变量传给子进程，不能出现在命令行、日志或结果对象中。

任务成功结果包含：

```json
{
  "videoUrl": ".../artifacts/classroom.mp4",
  "subtitleUrl": ".../artifacts/classroom.srt",
  "timelineUrl": ".../artifacts/timeline.json"
}
```

产物接口只接受 `classroom.mp4`、`classroom.srt`、`timeline.json`，并沿用课程/课堂
访问控制；路径穿越、未登录下载和不存在文件均不得泄露本地路径。

## 6. 前端产品交互

课堂页提供“导出视频”动作：

- 单次点击提交一个任务并轮询进度；
- 执行中禁用重复提交，展示后端进度和失败信息；
- 成功后下载 MP4，并提供 SRT 下载；
- 轮询终止、组件卸载和失败时清理定时器与本地状态。

导出不阻塞当前课堂播放，也不改变课堂的 scene/action 数据。

## 7. 配置与部署

| 配置 | 用途 |
| --- | --- |
| `CLASSROOM_VIDEO_FRONTEND_URL` | 后端导出进程访问的前端基址 |
| `CLASSROOM_VIDEO_NODE_BIN` | Node 可执行文件，默认从 PATH 解析 |
| `CLASSROOM_VIDEO_FFMPEG_BIN` | FFmpeg 可执行文件，默认从 PATH 解析 |

部署机必须按 `pnpm-lock.yaml` 安装 Node 依赖，并执行
`pnpm exec playwright install chromium`；同时提供 FFmpeg/ffprobe。生产前端必须允许后端
导出进程访问内部渲染路由。

## 8. 代码落点

| 位置 | 职责 |
| --- | --- |
| `frontend/src/openmaic/videoExport.ts` | 时间线合并与 SRT |
| `frontend/src/openmaic/ClassroomVideoRender.tsx` | 无头渲染路由 |
| `frontend/scripts/videoPipeline.ts` | Playwright 录制与 FFmpeg 合成 |
| `frontend/scripts/export-classroom-video.ts` | CLI |
| `backend/src/app/services/classroom_video_export.py` | 后端任务编排与原子发布 |
| `frontend/src/openmaic/ClassroomVideoExportButton.tsx` | 提交、轮询与下载 |

