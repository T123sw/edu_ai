# ACC-08 · 前端集成 DSL + Renderer 播放 · 验收文档

> 对应 spec：[`../spec/SPEC-08_前端集成_DSL与Renderer播放.md`](../spec/SPEC-08_前端集成_DSL与Renderer播放.md)
> 对应 Phase：3（交互课堂）· 地图：[`../../项目总览地图.md`](../../项目总览地图.md) §4.1 前端 / §5 视频接缝
> 相关：视频 A→B 三接缝细节见 [`../课件视频_统一时间线契约与AB演进预留设计_2026-06-30.md`](../课件视频_统一时间线契约与AB演进预留设计_2026-06-30.md)
> 通用环境：见 [验收 README §2](README.md)
> 状态：⏳ P3-1 已过 AC-08-1/2/4/7；**AC-08-3 已用真实生成的课件验证通过**（2026-07-24）。
> AC-08-9（中文字体/音色专项实测）与 AC-08-5/6/8（audioUrl/视频/并发的专项验证，
> 机制已实现但缺专项用例）仍待做。详见 SPEC-08 §0/§6。

---

## 1. 功能范围

**做**：edu_ai 前端引入 `@openmaic/dsl`+`@openmaic/renderer`，实现 slide 渲染、`actions[]` 播放、TTS 音频、spotlight/laser/zoom 聚焦、video 元素播放；播放器改造成「ClockSource 注入 + 消费 LessonTimeline」形状；**留好三接缝形状**（不实现 B 分支）。

**不做**：LessonTimeline 编译器完整实现与视频渲染（Phase 5/B）；PPTX 导出（Phase 4）；importer 导入（可后置）。

---

## 2. 验收标准（DoD）

| 编号 | 标准 | 判定 |
| --- | --- | --- |
| AC-08-1 | `@openmaic/dsl`+`renderer` 在 edu_ai 前端 workspace 解析并构建通过 | |
| AC-08-2 | 手写样本 `Slide + [speech, spotlight]` → 渲染正确 + 聚焦命中目标元素 + 旁白与聚焦同步 | |
| AC-08-3 | 用 ACC-04 落库的真实课件完整播放一节课，逐 scene、逐 action 正常 | |
| AC-08-4 | 聚焦 elementId 寻址正确（DOM id `slide-element-{id}`），空指时降级不崩 | |
| AC-08-5 | `speech.audioUrl`（edu_ai 地址）播放出声；无 audioUrl 时浏览器 TTS 兜底 | |
| AC-08-6 | video 元素经 `renderVideo` 插槽播放，`play_video` 动作控制时机；**不走默认 `<video>`** | |
| AC-08-7 | **三接缝形状就位**：①播放器只认 `ClockSource.currentTimeMs()`；②effect 组件有可选 `localTimeMs?` prop；③视频走 renderVideo 插槽（B 分支未实现但形状在，代码可见） | |
| AC-08-8 | 并发语义正确：spotlight/laser 叠在伴随 speech 时间窗，不推进时钟；SYNC 动作串行推进 | |
| AC-08-9 | 中文适配：字体加载/fallback、TTS 中文音色、latex 元素中文环境渲染通过实测 | |

---

## 3. 测试方法

### 3.1 构建（AC-08-1）
```bash
cd Edu_AI && npm run dev   # 预期：无 @openmaic/* 解析报错
npm run build              # 预期：构建通过
```

### 3.2 最小样本播放（AC-08-2/4/5/8）
- 建一个 dev-only 演示页 `pages/_dev/PlayerSmoke.tsx`，喂手写夹具：
  1 个 slide（含一个 text 元素 `id=el-formula`）+ actions `[speech("这是冒泡排序"), spotlight(elementId="el-formula")]`。
- 断言（人工 + 可加 Playwright）：
  - text 渲染在正确几何位置；
  - 播放到 speech 出声/字幕；
  - spotlight 高亮 `el-formula`（DOM 存在 `#slide-element-el-formula`，出现 SVG mask）；
  - spotlight 与 speech 时间窗重叠（不额外占时钟）。
  - 把 spotlight 指向不存在 id → 控制台告警、页面不崩（AC-08-4）。

### 3.3 真实课件（AC-08-3/6）
- 取 ACC-04 落库课件 → 学生端播放页完整播放；含 video 元素的 scene 走 renderVideo 出画，`play_video` 到点才播。

### 3.4 三接缝代码审查 + 冒烟（AC-08-7）——**关键**
- **代码审查**（可判定，不需运行 B）：
  - 播放器无硬编码 `performance.now()`/`Date.now()` 于时间推进处；统一经注入的 `ClockSource`（grep 断言）。
  - `SpotlightOverlay/LaserOverlay/ZoomWrapper` 封装 props 含可选 `localTimeMs?: number`。
  - 视频元素渲染仅经 `renderVideo` 插槽，无默认 `<video>` 直出（grep 断言）。
- 冒烟：注入一个「墙钟 ClockSource」正常播；替换成「假的定值 ClockSource」→ 播放停在该时刻（证明播放器确实只认注入时钟）。

### 3.5 中文实测（AC-08-9）
- 中文 slide 字体正确、无豆腐块；中文 TTS 音色自然；含中文说明的 latex 元素渲染正常。

---

## 4. 回归 / 边界

| 用例 | 预期 |
| --- | --- |
| 无 actions 的纯 slide | 静态展示，不报错 |
| discussion 等 live-only 动作 | 播放器可交互；（导出 MP4 时另按线性策略，属 Phase 5）|
| 音频加载失败 | 回退浏览器 TTS，不阻断播放 |
| 快速切 scene | 聚焦/音频正确清理，无残留 overlay |

---

## 5. 签收

| 项 | 内容 |
| --- | --- |
| 验收人 / 日期 | |
| 结论 | 三接缝形状（AC-08-7）是 Phase 5/B 的前置，务必审查通过 |
| 遗留 | LessonTimeline 编译器、视频渲染（Phase 5）|
