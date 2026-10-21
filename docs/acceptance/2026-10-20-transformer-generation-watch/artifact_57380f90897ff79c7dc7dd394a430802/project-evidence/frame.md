# frame.md — design truth

**concept:** 把这场取舍写成一张账本。三列衡量角度（复杂度 / 顺序操作数 / 路径长度），三行层类型（自注意力 / 循环 / 卷积），逐列填入数字；最后用一条分界线把「训练」与「生成」切开。所有画面都是这份账本的翻阅过程，不做营销式渲染。

## Canvas

- size: 1920 × 1080 (16:9), 视频课程统一契约
- safe content: 全部内容在 `y ≤ 900`（底部 180px 为字幕带保留）；左右安全边距 120px
- ground: 深色底加极淡网格（24px / 96px 两级），网格只作纸面质感，对比度极低
- 场景以硬切/短交叉淡入衔接；每个场景自带完整背景层（满屏 `class="clip"`），不依赖根节点底色

## colors

    canvas: "#0f172a"
    ink: "#f8fafc"
    accent: "#38bdf8"
    accent-soft: "#7dd3fc"
    muted: "#94a3b8"
    panel: "#16233b"
    line: "#334155"
    positive: "#34d399"
    warning: "#fbbf24"

用法：`accent` 只用于「当前正在讲的那一列/那一项」的边框、下划线与关键公式；`muted` 承载未聚焦的列、注释与出处；`positive` 标优势；`warning` 标代价；绝不把彩色当装饰铺满画面。

## typography

    display: { fontFamily: "Noto Sans SC", fontSize: "84px", fontWeight: 800, letterSpacing: "-0.02em" }
    title: { fontFamily: "Noto Sans SC", fontSize: "56px", fontWeight: 700, letterSpacing: "-0.01em" }
    body: { fontFamily: "Noto Sans SC", fontSize: "38px", fontWeight: 400, lineHeight: 1.55 }
    label: { fontFamily: "Noto Sans SC", fontSize: "30px", fontWeight: 500, letterSpacing: "0.04em" }
    mono: { fontFamily: "Noto Sans SC", fontSize: "40px", fontWeight: 700, letterSpacing: "0" }

字号下限：标题 ≥ 48px，正文 ≥ 32px，图示标签 ≥ 28px。公式与斜体记号（O(n²·d)、h_t、d_model）用 `font-style: italic` 区分，不用外部数学字体。

```css
@font-face{font-family:"Noto Sans SC";font-style:normal;font-weight:100 900;font-display:block;src:url("assets/fonts/NotoSansSC-Variable.ttf") format("truetype");}
```

拉丁字母与数字也一律使用 Noto Sans SC（已含拉丁字形），不要另外命名系统字体。帧文件是 `compositions/frames/` 下的模板片段，但 `@font-face` 的路径以**装配后的项目根**为准：始终写 `assets/fonts/NotoSansSC-Variable.ttf`。

## 版面骨架（每帧一致）

1. **页眉**（top 64px 起）：左侧 `Transformer · 取舍判断` 30px muted；右侧场景编号 `03 / 09` 30px muted。页眉不参与入场动画，常驻。
2. **标题区**（top 132–250px）：一行标题 56–84px，可以是问句或判断句；标题下一条 4px accent 短线（宽 96px）。
3. **主体区**（top 280–860px）：一列主视觉（表格 / 链路图 / 分屏对比 / 曲线），支持元素可以放在右下角，但不得挤占主视觉。
4. **页脚**（bottom 约 930–1010px，仍在 900 安全线下方留白内只放极短标注）：只允许一行 28px muted 的出处/备注，例如 `Attention Is All You Need · §4 Table 1`。不放字幕正文。

## 组件

- **账本表格**：三列（每层计算复杂度 / 最少顺序操作数 / 最大路径长度）+ 左侧行标签列。行高 120px；表头 30px muted 小字；单元格数值 44–52px、`font-style: italic`；行标签 40px。表格几何在所有出现表格的场景中保持完全一致（同样的列 x 位置、同样的行 y 位置），只改变「点亮哪一列」。
- **列聚焦**：未讲的列整体 `opacity: 0.28`，当前列 `opacity: 1` 并获得 2px accent 边框 + 顶部 accent 短线；切换聚焦时用 0.3s 交叉淡入即可，不做横向滑动。
- **数值胶囊**：`panel` 底、1px `line` 边框、圆角 14px、内边距 18px 32px，28–40px 文字。
- **链路节点**：96×96 圆角方框，`panel` 底、1px line 边框；已激活时边框变 accent、内部数字 accent。连接线为 3px `line`，激活段为 accent。
- **分屏**：左右各 780px 宽，中间 40px 缝隙；两侧各有 44px 标题和一条 2px 分隔线。左右标题分别用 accent 与 warning 标记「能做 / 不能做」。
- **出处 chip**：24–28px muted 文字前加一个 6px accent 圆点。

## 动效语气

克制、以「填入」为主：淡入 + 8–16px 上移、数值胶囊轻微 scale 0.94→1、链路逐节点点亮、表格逐行逐列填入。禁止持续漂浮、旋转、发光呼吸、粒子。每个场景的入场应当是「讲解者把这一项填进表格」的动作感，而不是演示动画。所有元素在场景内按旁白推进依次出现，末尾 1–2 秒保持静止可读。

## 禁止项

- 不在画面上重复旁白整句：只写关键词、公式、数字、标签。
- 不引用任何图片/图标素材：无附件，全部由排版与 CSS/SVG 图元构成。
- 不使用系统 CJK 字体名；只使用本文件的 Noto Sans SC。
- 不使用练习题、提问作答、答案核对等课堂练习画面。
