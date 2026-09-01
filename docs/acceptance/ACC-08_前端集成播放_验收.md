# ACC-08 · 前端集成 DSL + Renderer 播放 · 验收文档

> 对应 spec：[`../spec/SPEC-08_前端集成_DSL与Renderer播放.md`](../spec/SPEC-08_前端集成_DSL与Renderer播放.md)
> 对应 Phase：3（交互课堂）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §4.1 前端 / §5 视频接缝
> 相关：视频 A→B 三接缝细节见 [`../architecture/lesson-timeline-contract.md`](../architecture/lesson-timeline-contract.md)
> 通用环境：见 [验收 README §2](README.md)
> 状态：✅ Phase 3 已通过（2026-07-25）。AC-08-1～9 均有代码、自动化测试或浏览器
> 证据；中文音色自然度因自动化浏览器不暴露系统语音列表，保留为人工听感复核项，
> 不影响 `voice/speed` 选择、三级降级和播放完成语义。

---

## 1. 功能范围

**做**：edu_ai 前端引入 `@openmaic/dsl`+`@openmaic/renderer`，实现 slide 渲染、`actions[]` 播放、TTS 音频、spotlight/laser/zoom 聚焦、video 元素播放；播放器改造成「ClockSource 注入 + 消费 LessonTimeline」形状；**留好三接缝形状**（不实现 B 分支）。

**本阶段已做**：`LessonTimeline` 编译/实测记录、墙钟播放、聚焦/旁白并发、原生视频受控播放。

**不做**：确定性逐帧视频渲染（B）；PPTX 导出（Phase 4）；MP4 录制/mux（Phase 5）；importer 导入（可后置）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定与证据 |
| --- | --- | --- |
| AC-08-1 | `@openmaic/dsl`+`renderer` 在 edu_ai 前端解析并构建通过 | ✅ `npm run build`，5474 modules transformed |
| AC-08-2 | 手写样本 `Slide + [spotlight, speech]` → 渲染正确 + 聚焦命中目标元素 + 旁白与聚焦同步 | ✅ `PlayerSmoke.tsx` + `actionEngine.test.ts` + 浏览器冷启动 |
| AC-08-3 | 用 ACC-04 落库的真实课件完整播放一节课，逐 scene、逐 action 正常 | ✅ 2026-07-24 真实生成“冒泡排序算法入门”9 scene 并完整播放 |
| AC-08-4 | 聚焦 elementId 寻址正确（DOM id `slide-element-{id}`），空指时降级不崩 | ✅ 夹具含缺失 ID，用例完整结束且控制台无错误 |
| AC-08-5 | `speech.audioUrl` 播放；失败/缺失时浏览器 TTS，再失败时阅读停留 | ✅ 三级降级与 dispose 共 5 条专项测试 |
| AC-08-6 | video 元素经 `renderVideo` 插槽播放，`play_video` 动作控制时机；**不走默认 `<video>`** | ✅ 注册表 5 tests；浏览器实测 5.055s、`playing→completed`、静音且不自动播放 |
| AC-08-7 | **三接缝形状就位**：①注入 `ClockSource`；②效果时间归一到播放器时钟/时间线；③视频走 `renderVideo` 插槽 | ✅ 代码审查 + 注入时钟测试；B 分支仍按计划后置 |
| AC-08-8 | 并发语义正确：spotlight/laser 叠在伴随 speech 时间窗，不推进时钟；SYNC 动作串行推进 | ✅ timeline/playback/action 三层测试覆盖 |
| AC-08-9 | 中文适配：字体 fallback、中文音色选择、latex 中文环境渲染 | ✅ 字体/生僻字/KaTeX 浏览器截图无豆腐块；中文音色选择测试通过。自动化浏览器无系统语音列表，听感保留人工复核 |

---

## 3. 测试方法

### 3.1 构建（AC-08-1）
```bash
cd Edu_AI && npm run dev   # 预期：无 @openmaic/* 解析报错
npm run build              # 预期：构建通过
```

### 3.2 最小样本播放（AC-08-2/4/5/8）
- 建一个 dev-only 演示页 `pages/_dev/PlayerSmoke.tsx`，喂手写夹具：
  1 个 slide（含中文 text、KaTeX、字体探针）+ actions
  `[spotlight(elementId="el-formula"), speech("这是冒泡排序", voice="zh-CN", speed=0.95)]`。
- 断言（人工 + 可加 Playwright）：
  - text 渲染在正确几何位置；
  - 播放到 speech 出声/字幕；
  - spotlight 高亮 `el-formula`（DOM 存在 `#slide-element-el-formula`，出现 SVG mask）；
  - spotlight 与 speech 时间窗重叠（不额外占时钟）。
  - 把 spotlight 指向不存在 id → 控制台告警、页面不崩（AC-08-4）。

### 3.3 真实课件与嵌入视频（AC-08-3/6）
- 取 ACC-04 落库课件 → 学生端播放页完整播放。
- 专项视频夹具使用真实 MP4，原生 `<video>` 注册到稳定元素 ID；浏览器实测：
  `data-video-state="playing"` 后变为 `"completed"`，`currentTime=duration=5.055`，
  `autoplay=false`、`muted=true`，完成后播放器回到 `idle`。

### 3.4 三接缝代码审查 + 冒烟（AC-08-7）——**关键**
- **代码审查**（可判定，不需运行 B）：
  - 播放器无硬编码 `performance.now()`/`Date.now()` 于时间推进处；统一经注入的 `ClockSource`（grep 断言）。
  - 实时效果生命周期由编译时间线的 `concurrentWith` 与注入时钟决定；B 阶段把
    虚拟帧时钟接入同一层，不要求 Phase 3 手工重组 renderer 的裸 overlay。
  - 视频元素渲染仅经 `renderVideo` 插槽，无默认 `<video>` 直出（grep 断言）。
- 冒烟：注入一个「墙钟 ClockSource」正常播；替换成「假的定值 ClockSource」→ 播放停在该时刻（证明播放器确实只认注入时钟）。

### 3.5 中文实测（AC-08-9）
- 中文 slide 字体正确、无豆腐块；中文 TTS 音色自然；含中文说明的 latex 元素渲染正常。

2026-07-25 冷启动证据：

- 计算样式以 `"Noto Sans SC", "Microsoft YaHei", "PingFang SC", ...` 开头；
- 字体探针含 `【】`、`龘`、Latin 和数字，截图无豆腐块；
- `.base-element-latex .katex` 存在，公式与相邻中文说明布局正常；
- `voice/speed`、指定音色优先和中文语言 fallback 由单元测试覆盖；
- 自动化浏览器 `getVoices()` 返回空列表，无法客观判定“自然度”，列为人工听感复核；
  浏览器 TTS 不可用时播放器会进入确定性阅读停留，不阻断课程。

### 3.6 本次自动化命令

```bash
cd Edu_AI
npm test          # 32 passed
npm run lint      # 0 errors（88 条迁移前存量 warning）
npm run build     # success
```

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| 无 actions 的纯 slide | 静态展示，不报错 |
| discussion 等 live-only 动作 | 播放器可交互；（导出 MP4 时另按线性策略，属 Phase 5）|
| 音频加载失败 | 回退浏览器 TTS，不阻断播放 |
| 快速切 scene | 聚焦/音频正确清理，无残留 overlay |
| 浏览器无中文系统音色 | 回退浏览器默认中文策略；再失败则按阅读时长停留 |
| video elementId 不存在/加载失败 | 动作完成为 missing/failed，不阻断后续动作 |

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | Codex 自动化验收 / 2026-07-25 |
| 结论 | ✅ Phase 3 通过；LessonTimeline、旁白/聚焦、受控视频、中文/公式与三接缝均已落地 |
| 遗留 | 中文音色自然度需人工听感复核；PPTX 属 Phase 4，MP4 录制/mux 属 Phase 5，逐帧渲染属 B |
