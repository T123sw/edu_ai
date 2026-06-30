# 课件视频生成：统一时间线契约 与 A→B 演进预留设计

日期：2026-06-30

适用范围：edu_ai 复用 OpenMAIC 的课件/视频能力，放弃数字人。视频导出分两阶段：

- **A（先做，MVP）**：无头浏览器实时回放 + 录屏，音频用预生成 TTS 拼接。
- **B（后做，产品化）**：确定性逐帧渲染（Remotion 式）。

本设计只回答一个问题：**做 A 的时候，要事先给 B 预留什么，才能让 B 是「替换两个模块」而不是「重写」。**

---

## 0. 一条主线

A 和 B 唯一且必须的共享地基是一份数据结构：**LessonTimeline（课程时间线）**。

> A 阶段用「回放观测」**填充**它（边播边记每个动作的实际起止时间）；
> B 阶段用「ffprobe 量时长 + 规则预算」**填充**它。
> **契约不变，只换填充方式和渲染驱动。**

只要 A 的产出 = 一份合法的 LessonTimeline + 分段视频 + 音频，B 就站在它肩上。

---

## 1. LessonTimeline 契约（A、B 共享，现在就定）

```ts
// 课程级
interface LessonTimeline {
  version: number;               // 契约版本，B 不要破坏 A 的字段
  lessonId: string;
  durationMs: number;            // 总时长
  viewport: { width: number; height: number; ratio: number };  // 对齐 Slide.viewportRatio
  scenes: SceneSegment[];

  // —— 以下字段 A 不用、B 用；现在就占好位，避免日后改版本 ——
  render?: RenderConfig;         // 见 §2
}

// 场景级（= 分段渲染/分段录制的单位）
interface SceneSegment {
  sceneId: string;               // 稳定 id，来自 Scene
  sceneIndex: number;
  startMs: number;               // 在整课中的绝对偏移
  durationMs: number;
  slideRef: string;              // 指向要渲染的 Slide DSL（不内嵌，按引用）
  clips: TimelineClip[];
}

// 动作级（= 一个 Action 在时间轴上的落点）
interface TimelineClip {
  id: string;                    // 稳定，派生自 actionId
  actionId: string;              // 反向指回源 Action
  type:                          // 与 @openmaic/dsl 的 ActionType 对齐
    | 'speech' | 'spotlight' | 'laser' | 'play_video'
    | 'wb_draw_text' | 'wb_draw_shape' | 'wb_draw_latex' | 'wb_draw_chart'
    | 'wb_draw_table' | 'wb_draw_line' | 'wb_draw_code' | 'wb_edit_code'
    | 'wb_open' | 'wb_close' | 'wb_clear' | 'wb_delete'
    | 'widget_highlight' | 'widget_setState' | 'widget_annotation' | 'widget_reveal'
    | 'transition';
  track: 'narration' | 'focus' | 'visual' | 'media' | 'transition';
  startMs: number;               // 相对所属 SceneSegment 起点
  durationMs: number;
  durationSource: 'measured' | 'probed' | 'fixed' | 'media';  // 见 §3
  payload: Record<string, unknown>;  // 镜像源 Action 的类型专属字段
  concurrentWith?: string;       // 该 clip 与哪个 clip 并行（聚焦叠在讲解上），见 §4
}
```

设计要点（这些就是「预留」）：

1. **稳定 id 贯穿**：`sceneId / actionId / clipId / elementId` 全部稳定、可复现。B 的「只重渲改动那一页」和 A 的「按 scene 分段」都依赖它。**永远不要在编辑后重新生成 id；clipId 由 actionId 派生。**
2. **时间是「绝对可寻址」，不是「播到结束」**：契约里存显式 `startMs/durationMs`。A 虽然靠观测得到这些值，但**写进契约的就是 source of truth**——不是实时引擎的「等音频放完」。B 直接读这些值定位帧。
3. **slide 与音频都按引用，不内嵌**：`slideRef` 指向 Slide DSL，`payload.audioRef` 指向音频文件。时间线本身轻量，可单独持久化、diff、版本化。

---

## 2. RenderConfig（A 用子集，B 用全量，schema 现在占好）

```ts
interface RenderConfig {
  fps: number;                   // B：逐帧帧率（30）。A：仅信息性
  resolution: { width: number; height: number };  // 1920x1080
  codec: 'h264';
  container: 'mp4';
  audioMix: {                    // A、B 都用
    narrationGain: number;       // 旁白增益
    duckOnClipAudio: boolean;    // 嵌入视频有声时是否压低旁白
    clipAudio: 'mute' | 'keep';  // 嵌入演示视频默认 mute
  };
  captions: 'none' | 'sidecar-srt' | 'burn-in';  // 见 §7，A 即可支持 sidecar-srt
  seed?: number;                 // B：随机性播种，保证可复现。A 忽略
}
```

> 现在把 `fps/seed` 这些「B 才用」的字段写进 schema 并留默认值，A 直接忽略。这样 B 上线不需要破坏性改版本。

---

## 3. 时长来源标记 `durationSource`（迁移的关键）

每个 clip 的 `durationMs` 标明怎么来的：

| 值 | 含义 | 谁产 |
| --- | --- | --- |
| `measured` | 回放时实测墙钟 | **A** |
| `probed` | ffprobe 量 TTS/视频文件 | B（音频/媒体）|
| `fixed` | 效果约定时长（如 spotlight 默认 4s、转场 0.5s）| A、B |
| `media` | 嵌入视频片段自身长度 | A、B |

价值：B 上线时可以**一条轨一条轨地迁移**（先把 narration 从 measured 换成 probed，验证和 A 的实测值对得上，再换下一轨），而不是一次性切换。`measured` 数据还能作为 B 预算规则的**校验基线**。

---

## 4. 并发语义现在就定死（A、B 必须一致）

依据 `@openmaic/dsl` 的两类动作（已核对源码）：

- `SYNC_ACTIONS`（speech / play_video / wb_* / widget_*）：**推进时钟**，串行排在 narration/visual 轨。
- `FIRE_AND_FORGET_ACTIONS`（spotlight / laser）：**不推进时钟**，叠加在 focus 轨，覆盖其「伴随的那个 speech」的时间窗。

落地规则（写进编译器）：

```
聚焦/激光 clip.startMs = 其伴随 speech clip.startMs
聚焦/激光 clip.durationMs = 其伴随 speech clip.durationMs（或显式 fixed）
聚焦/激光 clip.concurrentWith = 该 speech clip.id
```

> 注意：源 DSL 里 `SpotlightAction` **没有 duration 字段**（只有 elementId/dimOpacity）。所以「聚焦持续多久」是**时间线层新增的派生信息**，必须在这里定义。A 靠观测（聚焦持续到下个状态变化），B 靠规则（绑定伴随 speech 时长）。两者结果要一致。

---

## 5. 代码层的「接缝」——A 留好接口，B 只换实现

这几处是把 B 的工作从「重写」降到「替换」的关键。**A 阶段就按下面的形状写，即使 A 用不到 B 的分支。**

### 5.1 时钟源注入（最重要的一处）

播放器不要硬编码墙钟。让它从一个注入的 provider 拿当前时间：

```ts
interface ClockSource { currentTimeMs(): number; }
// A：真实墙钟（requestAnimationFrame / performance.now）
// B：虚拟帧钟（Remotion useCurrentFrame() * 1000 / fps）
```

播放器只认 `currentTimeMs()`。A→B = 换一个 ClockSource 实现，播放器主体不动。

### 5.2 效果组件的「局部时间」可选入参（B 最难那块的预留）

已核对：OpenMAIC 的 `SpotlightOverlay / LaserOverlay / ZoomWrapper / BaseCodeElement` 全用 framer-motion（墙钟驱动）。B 需要它们改由帧驱动。**预留方式**：fork/包这些组件时，加一个**可选** prop：

```ts
// localTimeMs 提供时（B）→ 用它驱动动画进度；不提供时（A）→ 回退 framer-motion 自动
interface EffectDriveProps { localTimeMs?: number; }
```

A 阶段不传这个 prop（让 framer-motion 实时跑，照样录得到）。B 阶段传入 `currentTimeMs - clip.startMs`。**这样 B 不用再回头逐个改组件——只是传入你早已加好的 prop。** 这一步把 B 最大的工作量从「改造每个动画」前置成「现在加一个可选入参」。

### 5.3 视频元素始终走 `renderVideo` 插槽（已有官方槽）

`BaseVideoElement` 自带 `renderVideo` 注入槽（已核对）。**A 阶段就强制走它**：

```
A：renderVideo = 返回原生 <video autoplay>（实时播放，录屏抓得到）
B：renderVideo = 返回 <OffthreadVideo seekTo={localTimeMs}>（按帧 seek）
```

**永远不要走默认 `<video>` 路径。** 这样 A→B 只换 renderVideo 的返回值。

### 5.4 分段/合成针对 SceneSegment

A（按 scene 录片段）和 B（按 scene 渲片段）都以 `SceneSegment` 为单位，产出后 ffmpeg concat + 音轨 mux。**现在就把 concat/mux 步骤写成「吃 SceneSegment 列表」**，A、B 共用这一段。

### 5.5 字幕从 narration 轨纯函数导出

speech clip 有 text + startMs + durationMs → SRT/VTT 是时间线的纯函数，A、B 完全一致。**A 阶段就实现 `timeline → srt`**，立刻可用，B 免费继承。

---

## 6. A 的「时间线录制器」产出 = B 的输入

A 的实现里，PlaybackEngine 回放时发事件：

```ts
onActionStart(actionId, wallClockMs)
onActionEnd(actionId, wallClockMs)
```

一个 **TimelineRecorder** 消费这些事件，填充 `startMs/durationMs/durationSource='measured'`，输出一份**完整的 LessonTimeline 并持久化**（和课程存一起）。

> 关键认知：**A 的副产物不是「一个视频」，而是「视频 + 这份时间线」。** 这份时间线就是 B 要吃的东西。所以 A 做完，B 的输入数据天然就有了。

---

## 7. 必须现在拍板的几条策略（A、B 要一致）

1. **音频永远「拼」不「录」**：TTS 阶段每个 speech 产出稳定 `audioRef`；视频只录画面，音轨由 audioRef 按 startMs 拼接后 mux。A、B 同。
2. **MP4 是线性讲课版**：`discussion` 等 live-only 动作，统一策略 = 跳过 或 用预生成内容给固定时长。现在定，A、B 同。
3. **嵌入演示视频默认 mute**（`clipAudio:'mute'`），旁白承载讲解。需要时再按 `duckOnClipAudio` 处理。
4. **id 不可变**：编辑课件不重生成 id，只改内容；保证 B 的增量重渲和 A 的分段都稳定。

---

## 8. A 明确「不做」的事（避免过度设计）

- ❌ 不建确定性帧驱动（ClockSource 先只实现墙钟版）。
- ❌ 不把 framer-motion 动画帧化（只加好 §5.2 的可选 prop，不接线）。
- ❌ 不接 OffthreadVideo（renderVideo 先返回原生 video）。
- ❌ 不做超实时/并行渲染农场。

A 就是：无头实时回放 + 按 scene 录屏 + 事件时间戳填时间线 + TTS 音轨拼接 mux + SRT。够发版。

---

## 9. A 建 / B 加 —— 一张对照表

| 能力 | A 阶段 | B 阶段（替换/新增）|
| --- | --- | --- |
| LessonTimeline 契约 | ✅ 定义 + 观测填充 | 复用，改预算填充 |
| 播放器 / renderer / 聚焦 | ✅ 共享 | 共享 |
| ClockSource | 墙钟实现 | + 虚拟帧钟实现 |
| 效果动画 | framer-motion 实时（加好可选 prop 不接线）| 接 `localTimeMs` 驱动 |
| 视频元素 | renderVideo → 原生 video | renderVideo → OffthreadVideo |
| 资源就绪 | 浏览器原生等待 | + delayRender/continueRender |
| 分段 concat + 音轨 mux | ✅ 按 SceneSegment | 共享 |
| 字幕 timeline→SRT | ✅ | 共享 |
| 时长来源 | measured | probed/fixed/media |
| 渲染方式 | 实时录屏 | 逐帧渲染 |

---

## 10. 结论

把 A 做成「**回放 + 录屏 + 顺手产出一份 LessonTimeline**」，并在播放器/效果/视频三处留好 **ClockSource 注入、effect 的 localTimeMs 可选 prop、renderVideo 插槽** 这三个接缝——B 的上线就退化为：换时钟、传入早已加好的 prop、把 renderVideo 指向 OffthreadVideo。**播放器、契约、分段、字幕、音轨全部原样复用。**

这就是「以 B 为目标、先落地 A」在工程上的具体兑现方式。
</content>
