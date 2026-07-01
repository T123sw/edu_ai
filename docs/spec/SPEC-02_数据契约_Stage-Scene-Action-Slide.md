# SPEC-02 · 数据契约 Stage / Scene / Action / Slide

> **验收文档**：[`../acceptance/ACC-02_数据契约_验收.md`](../acceptance/ACC-02_数据契约_验收.md) · **地图**：[`../../项目总览地图.md`](../../项目总览地图.md)
> 归属：全套 spec 的**地基**。所有其它 spec（生成、落库、播放、导出、视频）都消费这份契约。
> 上游事实源：`D:\github\OpenMAIC\packages\@openmaic\dsl\src\{stage,slides,action,guards}.ts`（纯类型零依赖，MIT）。
> **本 spec 的立场**：edu_ai **不重新定义**这套类型，只规定「如何消费、如何落库、哪些字段 edu_ai 关心、哪些约束必须守」。字段以上游 `.ts` 为准，本文出现的类型是**核对源码后的镜像摘录**，若与源码冲突以源码为准。
> 关联：SPEC-04（生成产出这份数据）、SPEC-07（Python 侧如何持有）、SPEC-08（前端如何渲染）。

---

## 1. 顶层结构（一节课）

```
Stage（一节课 / 一个课件）
 └─ Scene[]（一页 / 一个场景）
     ├─ type: 'slide' | 'quiz' | 'interactive' | 'pbl'
     ├─ content：随 type 变（slide → Slide DSL；quiz → QuizContent；interactive/pbl → app 自定义）
     └─ actions: Action[]（时间线动作：讲解/聚焦/播放/白板/互动）
```

- 源文件：`stage.ts` 定义 `Stage / Scene / SceneType / StageMode / VideoManifest / GeneratedAgentConfig / MultiAgentConfig`。
- `SceneType = 'slide' | 'quiz' | 'interactive' | 'pbl'`（已核对）。edu_ai 初期只需吃透 `slide`，其余原样透传落库、暂不特殊处理。
- `StageMode = 'autonomous' | 'playback' | 'edit'`。edu_ai 播放走 `playback`，编辑走 `edit`。

### 1.1 Stage（课程级）字段（edu_ai 关心的子集）

| 字段 | 说明 | edu_ai 处理 |
| --- | --- | --- |
| `id` | 稳定课程 id | **主键之一**，落库不可变 |
| `name` | 课程标题 | 展示 |
| `languageDirective` | 语言指令（中文适配关键）| 透传；中文场景确认为 `ch` 语义 |
| `videoManifest` | `Record<string, VideoManifestEntry{type:'video',prompt,aspectRatio?}>` | 视频元素生成清单，Phase 5 用 |
| `agents` / `GeneratedAgentConfig[]` | 多 Agent 讨论配置 | 透传落库；`interactive/pbl`/discussion 才用 |
| `style` | 全局样式 | 透传 |

> `Whiteboard = Omit<Slide, 'theme'|'turningMode'|'sectionTag'|'type'>`（白板是「去掉主画布字段」的 Slide）。

### 1.2 Scene（场景级）

| 字段 | 说明 |
| --- | --- |
| `id` | 稳定场景 id（**聚焦寻址、分段录制、局部重生成的锚**）|
| `type` | `SceneType` |
| `order` / `index` | 顺序 |
| `content` | 判别联合，`type==='slide'` 时为 `Slide` |
| `actions` | `Action[]`，默认用契约标准 `Action` 联合 |

---

## 2. Slide DSL（`slides.ts`，964 行，已核对）

一页幻灯 = 可编辑对象模型，**不是 markdown 副产物**。

```ts
interface Slide {
  id: string;
  viewportSize: number;          // 画布基准宽（px）
  viewportRatio: number;         // 视口宽高比（必填，渲染/导出/视频视口对齐用）
  theme: ...;                    // 主题
  elements: PPTElement[];        // ★ 元素集合
  background?: SlideBackground;  // 'solid'|'image'|'gradient'
  animations?: PPTAnimation[];
  script?: string;               // 演讲备注（导出 PPTX 备注、可作 speech 兜底）
  type?: SlideType;              // 'cover'|'contents'|'transition'|'content'|'end'
  turningMode?, sectionTag? ...
}
```

### 2.1 PPTElement 联合（10 种，均带稳定 id + 几何）

源：`slides.ts` `export type PPTElement = ...`（行 788）。所有元素继承 `PPTBaseElement`（行 154），带 `id / left / top / width / height / rotate` 等几何。

| 元素 | 接口 | 关键专属字段 |
| --- | --- | --- |
| 文本 | `PPTTextElement` | 富文本内容、行距 |
| 图片 | `PPTImageElement` | `src`、裁剪、滤镜 |
| 形状 | `PPTShapeElement` | 路径、填充 |
| 线条 | `PPTLineElement` | `Omit<PPTBaseElement,'height'|'rotate'>`（无高/无旋转）|
| 图表 | `PPTChartElement` | 图表数据 |
| 表格 | `PPTTableElement` | 单元格矩阵 |
| 公式 | `PPTLatexElement` | latex 源码（导出走 mathml2omml→OMML）|
| 视频 | `PPTVideoElement` | `src`、`mediaRef`（生成回填）、`poster` |
| 音频 | `PPTAudioElement` | `src` |
| 代码 | `PPTCodeElement` | 语言、高亮 |

> **edu_ai 迁移要点**：元素级稳定 `id` 让「聚焦第 3 页那个公式 / 让这句讲稿绑定那张图 / 只重生成这一页」全部成为可寻址操作。落库时**必须保留每个 element 的 id 原样**。

### 2.2 视口与几何约定

- 坐标系：元素 `left/top/width/height` 相对 `viewportSize` 基准；聚焦 overlay 换算成 0–100 百分比（`PercentageGeometry`，见 `action.ts:285`）。
- 视频视口对齐 `Slide.viewportRatio`（LessonTimeline.viewport 也对齐它）。

---

## 3. Action 契约（`action.ts`，已核对）

`Scene.actions[]` 是时间线动作序列。所有动作继承 `ActionBase`（行 20，带稳定 `id`）。

### 3.1 全部动作类型（`ActionType = Action['type']`）

| 分类 | 动作 | 接口 | 关键字段 |
| --- | --- | --- | --- |
| 讲解 | `speech` | `SpeechAction` | `text, audioId, audioUrl, voice, speed` |
| 聚焦 | `spotlight` | `SpotlightAction` | `elementId, dimOpacity`（**无 duration**）|
| 指示 | `laser` | `LaserAction` | `elementId, color`（**无 duration**）|
| 视频 | `play_video` | `PlayVideoAction` | `elementId` |
| 白板 | `wb_open/close/clear/delete` | `WbOpen/Close/Clear/DeleteAction` | — |
| 白板 | `wb_draw_text/shape/chart/latex/table/line/code` | `WbDraw*Action` | 各自绘制载荷 |
| 白板 | `wb_edit_code` | `WbEditCodeAction` | 逐行改代码 |
| 讨论 | `discussion` | `DiscussionAction` | 多 Agent（**live-only**，MP4 跳过/固定时长）|
| 互动 | `widget_highlight/setState/annotation/reveal` | `Widget*Action` | 组件互动 |

### 3.2 并发语义（**A/B 视频与播放器必须一致**）

源码常量（已核对，`action.ts:251/257`）：

```ts
FIRE_AND_FORGET_ACTIONS = ['spotlight', 'laser'];   // 不推进时钟，叠加
SLIDE_ONLY_ACTIONS      = ['spotlight', 'laser'];   // 仅 slide 场景可用
SYNC_ACTIONS            = [ speech / play_video / wb_* / widget_* ... ];  // 推进时钟，串行
```

规则：
- **SYNC 动作**推进时间线时钟，串行排在 narration/visual 轨。
- **FIRE_AND_FORGET（spotlight/laser）**不推进时钟，叠加在 focus 轨，覆盖「其伴随的那个 speech」的时间窗。
- ⚠️ **源 DSL 的 spotlight/laser 没有 duration** → 「聚焦持续多久」是**时间线层派生**（A 观测 / B 绑定伴随 speech 时长）。此约束在 LessonTimeline 文档 §4 展开，edu_ai 落库 Action 时**不要臆造 duration 字段塞进源 Action**。

### 3.3 guards（判别守卫）

`guards.ts` 提供纯判别守卫（`isSpeechAction` 等）。前端/编译器判别动作类型走守卫，不手写 `action.type === 'x'` 散落各处。

---

## 4. edu_ai 落库映射（后端持久化约定）

原则：**结构化 JSON 原样落库 + 关系型索引旁挂**，不拆解 DSL 内部字段进关系表。

| edu_ai 存储 | 内容 |
| --- | --- |
| `classrooms` 表 | `id(=Stage.id)`、`name`、`owner`、`course_id`、`created_at`、`stage_json`（整个 Stage）|
| `classroom_scenes` 表 | `scene_id(=Scene.id)`、`classroom_id`、`order`、`type`、`scene_json`（整个 Scene，含 content + actions）|
| 媒体文件 | `audioUrl / video src / image src` 指向 edu_ai 存储（sidecar 落盘后由 edu_ai 拉取/代理，见 SPEC-04 §5）|

- **为什么整段 JSON 落库**：契约随上游演进，字段会增；拆表会频繁迁移。索引只抽稳定 id + 少量查询字段。
- **id 唯一性**：`(classroom_id, scene_id)`、`element.id` 在 slide 内唯一——落库前做一次唯一性校验（SPEC-04 §6 校验清单）。

---

## 5. 消费方一览（谁读这份契约）

| 消费方 | 读什么 | spec |
| --- | --- | --- |
| sidecar 生成流水线 | 产出 Stage/Scene | SPEC-04 |
| edu_ai 后端 | 落库/取库/权限 | SPEC-04/07 |
| 前端 renderer | Slide→canvas、Action→播放/聚焦 | SPEC-08 |
| PPTX 导出 | Slide.elements→pptxgenjs | 下一轮 SPEC-09 |
| LessonTimeline 编译器 | Scene.actions→多轨时间线 | 时间线文档 / SPEC-08 |

---

## 6. 不变量（写进校验，违反即拒绝落库）

1. `Stage.id / Scene.id / Action.id / element.id` 全部存在且稳定（非空、同层唯一）。
2. `Slide.viewportRatio` 存在（渲染/导出/视频视口对齐依赖它）。
3. `spotlight/laser.elementId` 必须能在同 Scene 的 `Slide.elements` 里找到对应 element（否则聚焦空指）。
4. `play_video.elementId` 指向的 element 必须是 `PPTVideoElement`。
5. `speech` 若已配音，`audioUrl` 指向 edu_ai 可达的存储（不是 sidecar 临时路径）。
6. 编辑不换 id（全局约定 §3.1）。

> 校验实现位置见 SPEC-04 §6。前端渲染前也可做一次软校验（缺失只降级告警不崩）。
