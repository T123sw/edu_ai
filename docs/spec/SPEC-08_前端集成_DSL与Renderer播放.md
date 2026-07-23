# SPEC-08 · 前端集成 @openmaic/dsl + renderer 播放（Phase 3 起步）

> **验收文档**：[`../acceptance/ACC-08_前端集成播放_验收.md`](../acceptance/ACC-08_前端集成播放_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 目标：edu_ai 前端引入 `@openmaic/dsl` + `@openmaic/renderer`，实现 slide 渲染、`actions[]` 播放、TTS 音频、spotlight/laser/zoom 聚焦、video 元素播放。
> **本 spec 只覆盖「迁移/引包/播放接通」这一层**；LessonTimeline 编译器与视频 A→B 的三接缝（ClockSource 注入 / effect `localTimeMs` / renderVideo 插槽）细节仍在 `../课件视频_统一时间线契约与AB演进预留设计_2026-06-30.md`，本文只标出「引包时就要留好的形状」。
> 上游（已核对）：`packages/@openmaic/{dsl,renderer,importer}`；`lib/playback/engine.ts`（`PlaybackEngine`）+ `lib/action/engine.ts`（`ActionEngine`）。
> 关联：SPEC-02（渲染的数据契约）、SPEC-04（数据来源）。

> **P3-1 进度（2026-07-24）**：引包+最小播放器+dev 冒烟样本已完成，详见 §7。
> `PlaybackEngine`/`ActionEngine` 已按 §3.1 port 完（speech+spotlight/laser 子集，
> 其余动作类型留白见 `actionEngine.ts` 顶部注释）；三接缝形状已落地（ClockSource
> 注入、renderVideo 强制插槽、effect-timing 归入 ClockSource/PlaybackEngine 层，
> 详见 `SlidePlayer.tsx` 注释里对 seam #2 的取舍说明）。**AC-08-3(真实课件播放)/
> AC-08-9(中文字体音色实测) 尚未做**——冒烟样本是手写夹具，没有接 SPEC-04 落库
> 的真实 classroom 数据；中文字体/TTS 只验证了机制存在（浏览器 TTS 兜底触发），
> 没有实测音色/字体渲染效果。

---

## 1. 引包（MIT，workspace/vendor）

| 包 | name | 用途 | 必要性 |
| --- | --- | --- | --- |
| dsl | `@openmaic/dsl` | 类型 + guards，纯 TS 零依赖 | **必引** |
| renderer | `@openmaic/renderer` | `SlideCanvas` + 元素渲染 + 聚焦效果 | **必引** |
| importer | `@openmaic/importer` | PPTX→DSL（用户导入课件）| 可后置 |
| pptxgenjs / mathml2omml | — | 导出 PPTX | Phase 4 |

引入方式（对齐 SPEC-01 §2）：起步用 pnpm workspace 指向 `openmaic-sidecar/packages/@openmaic/*` 或 vendor 复制为本地包；稳定后私有 registry 按版本。edu_ai 前端是 Vite/React，`@openmaic/*` 为 ESM/TS，配好 workspace 解析即可。

前端封装落点：`Edu_AI/src/openmaic/`（renderer 封装、播放器、聚焦 overlay 接线、进度组件）。

---

## 2. renderer 可用导出（已核对 `renderer/src/index.ts`）

```ts
SlideCanvas, SlideCanvasProps            // 一页幻灯渲染
SlideElement, SlideElementProps          // 单元素
SlideRendererProvider, useSlideContext   // 渲染上下文
HighlightOverlay / SpotlightOverlay / LaserOverlay / ZoomWrapper  // ★聚焦四件套
useViewportSize                          // 视口换算（对齐 viewportRatio, SPEC-02 §2.2）
findElementGeometry / getElementPercentageGeometry / PercentageGeometry  // 元素几何→百分比（聚焦寻址）
useSlideBackgroundStyle
```

- **聚焦实现是前端实时几何计算**（`document.getElementById('slide-element-'+id)` → DOM 矩形 → 0-100% → SVG mask + framer-motion），零 GPU、零后期。edu_ai 直接用。
- 元素 DOM id 约定 `slide-element-{element.id}` —— 依赖 SPEC-02 的 element.id 稳定不变。

---

## 3. 播放编排（PlaybackEngine + ActionEngine）

- `PlaybackEngine`（`lib/playback/engine.ts:52`）消费 `Scene.actions[]`，驱动：音频播放器 + canvas 状态 + 聚焦 overlay。上游注释：**No intermediate compile step — actions executed as-is**（实时态机）。
- `ActionEngine`（`lib/action/engine.ts`）逐动作执行。
- 并发语义按 SPEC-02 §3.2：SYNC 推进时钟串行，spotlight/laser fire-and-forget 叠在伴随 speech 时间窗。

### 3.1 迁移方式（★关键：不要原样照抄实时态机）

播放编排要**搬到前端，但按时间线文档改造成「ClockSource 注入 + 消费 LessonTimeline」的形状**，而不是照抄「等音频放完」的墙钟态机。原因：视频 A→B 要复用同一个播放器。

**引包/搭播放器时就要留好的三个接缝**（现在留形状，不接线；详见时间线文档 §5）：

1. **ClockSource 注入**：播放器只认 `currentTimeMs()`。A=墙钟（`performance.now`/rAF），B=虚拟帧钟。
   ```ts
   interface ClockSource { currentTimeMs(): number; }
   ```
2. **效果组件加可选 `localTimeMs` prop**（先加不接线）：fork/包 `SpotlightOverlay/LaserOverlay/ZoomWrapper` 时加 `localTimeMs?: number`；不传 → framer-motion 实时（A）；传 → 帧驱动（B）。
3. **视频元素走 `renderVideo` 插槽**：`BaseVideoElement` 自带该注入槽，**强制走它**，A 返回原生 `<video autoplay>`，B 返回 `<OffthreadVideo>`。永不走默认 `<video>`。

> Phase 3 只做「墙钟播放 + 聚焦 + 旁白同步」，三接缝**留好形状即可，不实现 B 分支**。这样 Phase 5/B 是「换实现」不是「重写」。

---

## 4. edu_ai 前端集成点

| 能力 | 组件/接线 |
| --- | --- |
| 取课件 | 调 edu_ai 后端取 `Stage + Scene[]`（落库数据，SPEC-04）|
| 渲染 | `SlideRendererProvider` + `SlideCanvas`（逐 Scene 的 slide）|
| 播放 | 前端 PlaybackEngine（改造版）消费 `Scene.actions[]` |
| 聚焦 | `SpotlightOverlay/LaserOverlay/ZoomWrapper`，elementId 寻址 |
| 旁白 | `SpeechAction.audioUrl`（edu_ai 地址，SPEC-04 §5）→ 音频播放；无则浏览器 TTS 兜底 |
| 视频元素 | `PPTVideoElement` + `play_video` 动作，走 renderVideo 插槽 |
| 进度/生成 | 复用统一 job 进度组件（SPEC-05 §3）|

- 路由/页面并入 `pages/teacher/*`（工作台预览）与学生端播放页。
- 状态管理沿用 Zustand（`store/`）；渲染上下文用 renderer 自带 `SlideRendererProvider`，不重复造。

---

## 5. 中文适配（Phase 3 专项实测）

- slide 字体：中文字体加载 + fallback（`configs/font.ts` 参考）。
- 公式：latex 元素中文环境渲染核对（导出走 mathml2omml，Phase 4）。
- TTS 音色/语速：`SpeechAction.voice/speed` 中文音色实测。
- `languageDirective` 已支持中文语义（SPEC-02 §1.1）。

---

## 6. 验收清单

- [x] `@openmaic/dsl+renderer` 在 edu_ai 前端构建通过（`file:` 依赖 + patch 002，非 workspace；`npm run build`/`vite dev` 均通过）
- [x] 喂一份手写 `Slide + [speech, spotlight]` → 前端能渲染 + 聚焦 + 旁白同步（`pages/_dev/PlayerSmoke.tsx`，浏览器验证：`#slide-element-el-formula` 命中、spotlight mask 出现、无未捕获异常）
- [ ] 用 SPEC-04 落库的真实课件完整播放一节课
- [x] 三接缝形状就位：`ClockSource`（`openmaic/clock.ts`）、renderVideo 强制插槽（`SlidePlayer.tsx`，永不落回默认 `<video>`）；`localTimeMs?` 的取舍见 `SlidePlayer.tsx` 顶部注释（用 `SlideCanvas.effects` 而非裸 overlay 组件，seam 落在 ClockSource/PlaybackEngine 层）
- [ ] 中文字体/音色实测通过（机制已接：浏览器 TTS 兜底、renderer fonts.css 已 import；未做真实中文渲染/音色效果验收）
