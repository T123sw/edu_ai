# frame.md — 设计真源（本课程「位置编码与逐位置前馈网络」节点视频）

**概念角度**：把 Transformer 的一层画成一张带刻度的工程实验台 —— 深海军蓝的场、细网格、青色主强调，
位置轴用琥珀色标记（顺序），前馈子层用紫罗兰标记（逐位置非线性）；所有公式、维度数字与位置索引都按
工程笔记的排法摆出来，像在读一张画出来的论文图，而不是看幻灯片。

本文件是**样式真源**：色板、字体阶梯、组件形状、构图规则。它不含场景内容；每一帧的画面与讲解在
`STORYBOARD.md` 的 `## Frame N` 块里。

---

## 色板（课程视觉约定，必须原样使用）

colors:
  canvas: "#0f172a"
  ink: "#f8fafc"
  ink-dim: "#cbd5e1"
  ink-mute: "#94a3b8"
  accent: "#38bdf8"
  accent-deep: "#0284c7"
  pos: "#fbbf24"
  pos-deep: "#b45309"
  ffn: "#a78bfa"
  ffn-deep: "#6d28d9"
  surface: "#16213a"
  surface-2: "#1e2c48"
  line: "#334155"
  line-soft: "#243247"

角色分工（不要混用）：

- `canvas` 场底色；`ink` 主文字；`ink-dim` 正文次级与图注；`ink-mute` 仅用于刻度/轴标注（≥28px）。
- `accent` 青色 = 结构、箭头、当前讲述的焦点、公式里的关键词。
- `pos` 琥珀 = 位置相关的一切（pos 轴、位置码、PE 公式、顺序示意）。
- `ffn` 紫罗兰 = 前馈子层相关的一切（FFN 公式、W1/W2、逐位置列、维度 2048）。
- 大面积填充只用 `surface` / `surface-2`；`line` 2px、`line-soft` 2px 做分隔。禁止整屏线性渐变。

## 字体

```
@font-face{font-family:"Noto Sans SC";font-style:normal;font-weight:100 900;font-display:block;src:url("assets/fonts/NotoSansSC-Variable.ttf") format("truetype");}
```

唯一字体族：`Noto Sans SC`（拉丁字母、数字、公式符号都用它）。不要写其他 font-family，不要用系统字体。
数字一律 `font-variant-numeric: tabular-nums;`，公式整体加 `letter-spacing: .01em`。

## 字号阶梯（px，1920×1080 画布）

| 角色 | 字号 / 字重 | 用途 |
| --- | --- | --- |
| hero | 132 / 700 | 一帧的主判断句（≤ 8 字，最多两行） |
| title | 76 / 700 | 场景标题、公式块标题 |
| subhead | 50 / 600 | 小节提示、公式前的引导语 |
| body | 40 / 400 · line-height 1.55 | 说明文字，最大宽度 1100px |
| formula | 54 / 500 | 公式主行；`tabular-nums`；关键词用 accent/pos/ffn 上色 |
| formula-sm | 40 / 500 | 公式的符号注释行 |
| label | 30 / 600 · letter-spacing .10em | 图注、轴标注、列标题、卡片标签（**不低于 28**） |
| meta | 28 / 500 | 页眉元信息、来源标注（仅此一处可用 28） |

正文最小 32px，图示标签最小 28px，标题最小 48px。密集图示**分步出现**，不缩小字号。

## 构图规则

- 画布 1920×1080。**内容全部落在 0–900px**（底部 900–1080 留空作为字幕安全区），页眉在 0–140。
- 页眉：左侧 `01 / 09` 形式的章节序号（label，`ink-mute`），右侧本节主题短标签（label，`accent`），
  下方 2px `line-soft` 通栏横线（可用 `scaleX` 0→1 入场）。
- 主内容用网格/弹性布局锚定：左对齐起始 x=120，右侧留到 1800；不要居中漂浮。
- 每帧至少两个焦点：一个主视觉（公式块 / 矩阵 / 图）＋ 一个辅助说明（要点列 / 轴标 / 图例）。
- 背景层（每帧都有，作为最低轨道的全屏 `class="clip"`，**不要**画在 `#root` 上）：
  1) 60px 细网格（`line-soft`，opacity .07）；
  2) 右上或左下的柔和径向青色辉光（radial-gradient，opacity .16–.20）；
  3) 一个 3–8% 透明度的超大字幽灵字（如 `PE`、`FFN`），缓慢漂移。
  三者共享一段缓慢的环境动效（呼吸/漂移），不要静止。

## 组件

- **chip（词元/位置标记）**：`background: surface`，2px `line` 描边，radius 14，padding 16px 28px，
  字号 34/600；被强调时描边换成 `accent` 或 `pos`，并加 `box-shadow: 0 0 0 3px rgba(56,189,248,.18)`。
- **formula-card**：`background: surface`，2px `line` 描边，radius 20，padding 44px 56px；
  上方 4px 高 120px 宽的强调条（accent 或 pos 或 ffn），公式 54px。符号释义行用 `formula-sm` + `ink-dim`。
- **matrix（PE 热力图）**：cell 44×44，gap 4，radius 6；取值用 5 档静态色（canvas→accent 之间：
  `#12203a` `#164e63` `#0e7490` `#0891b2` `#38bdf8`），奇数维用 pos 系（`#3a2f14` `#78350f` `#b45309` `#f59e0b` `#fbbf24`）
  区分 sin/cos 行；行列标签 label 字号。
- **wave（正弦曲线）**：SVG path，`stroke: accent`（sin）与 `pos`（cos），3px；
  可用 `stroke-dasharray/offset` 自绘；坐标轴线 `line`。
- **arrow**：SVG 2.5–3px 线 + 三角头，`accent`；向量箭头用 `pos` 或 `ffn`。
- **dimension-bar**：横向条，`scaleX` 入场；条高 40–56，标签在条内左端（ink），维度数字在条右端（tabular-nums）。
- **badge**：pill，1.5px 描边，字号 28/600，用于「共享参数」「逐位置」「N=6」这类短注。
- **step-rail**：`01 02 03` 序号，label 字号，当前步 accent，其余 `ink-mute`。

## 动效纪律

- 每帧一个 `gsap.timeline({ paused: true })`，注册在 `window.__timelines["<frame_id>"]`；
  所有入场用 `fromTo` + 显式 from 值；只动画 transform / opacity / 颜色、`strokeDashoffset`、`clip-path`。
- 入场节奏：0.45–0.7s，`power3.out` / `back.out(1.6)` / `power2.inOut` 混用；
  同组 stagger ≤ 0.12s，整组不超过 0.5s。
- 每帧的揭示按 `voiceover` 的推进次序铺满整段（最后一拍不要早于时长的 70%），不要在前 25% 摊完再静止。
- 环境动效（网格漂移、辉光呼吸、幽灵字漂移）用有限次数的 `yoyo` 或按 `tl.time()` 计算，
  不能有 `Math.random()` / `Date.now()`。

## 禁止

- 不在 `#root` 上画背景色，也不给 `#root` 加 class（用 `#root {}` 选择器）。
- 不用 `transform` 做居中（用 flex / inset）；不在 GSAP 会动的元素上写 CSS `transform`。
- 不在 `.clip` 元素上动画 `opacity` 之外的进出（`visibility`/`autoAlpha`/`display` 一律禁止）。
- 不出现 `<br>`；不把旁白整句写成画面文字（画面只放关键词、公式、数字、图注）。
- 不引入外部字体、外链图片、音视频；`<audio>` 由根合成负责，帧内不得出现。
