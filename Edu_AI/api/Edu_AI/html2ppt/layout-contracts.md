# 版式约束合同（Layout Contracts）

本文件定义模型生成 slide HTML 时可以使用的版式、组件层级和选择边界。它不是模板全文复制指南，而是“合法结构 + 版式选择”的规则源。

目标：
- 保持每页根节点、主要骨架和关键组件稳定。
- 允许模型在合同范围内组织内容。
- 避免因为重复规则、相似禁令或模板示例差异导致生成不稳定。

## 使用顺序

1. 根据 `content.md` 解析每页 `Role` 与 `Blocks`。
2. 按“版式选择表”决定候选版式。
3. 读取对应模板，只复用合同允许的 class 和层级。
4. 填入内容，并检查共享组件规则。
5. 相邻普通内容页尽量避免连续使用同一种文本版式。

如果模板示例和本合同冲突，始终以本合同为准。

## 教学表达

- 显示文案优先短句、标签、短动作和关键词；完整解释留给 Notes/讲稿，不直接塞进 slide。
- 每个输入 Block 至少有一个可见承载点，不能因为选择 comparison 或 process 版式而丢掉定义、对比标题或步骤标题。
- 常用表达 primitives：Definition（定义）、Compare（对比）、Process（流程）、Analogy（类比）、Takeaway（结论）。

## 共享组件规则

### Slide 根节点
- 每页必须以 `<div class="slide ...">...</div>` 作为根节点。
- 除 `card-layout` 外，推荐显式添加对应 `layout-*` class。
- 不允许在 slide 外再包业务容器。

### Brand Slot
品牌位由 `style/theme-brand-config.json` 决定：
- `brand.enabled = true` 时，非 thanks 页必须把品牌位放在 slide 根节点后的第一个业务子元素位置。
- 结构必须复用 `format/brand-slot-fragment.html`：

```html
<div class="slide-brand">
  <img class="slide-brand-image" src="{{BRAND_ASSET}}" alt="{{BRAND_ALT}}">
</div>
```

- `src` 使用主题配置中的 `brand.asset`。
- `alt` 使用主题配置中的 `brand.alt`。
- `layout-thanks` 不插入右上角 `slide-brand`，因为底部已经有放大的真实 logo。
- 品牌关闭时整块省略，不输出空节点。

### Header
凡是带标题区的版式，统一使用：

```html
<div class="header-area">
  <div class="title-en">...</div>
  <div class="title-main">...</div>
  <div class="title-divider"></div>
</div>
```

规则：
- `title-divider` 必须是独立真实节点，不能换成边框、伪元素或背景。
- `title-en` 可以是英文 kicker、主题标签或简短栏目名。
- `title-main` 保持原页标题含义，不要为版式强行改题。

### Quote Box
只要使用引言框，必须使用：

```html
<div class="quote-box">
  <div class="quote-accent"></div>
  <div class="quote-text">...</div>
</div>
```

不要把强调条写成 `border-left`、伪元素或其他装饰变体。

### Footer
标准文本类和媒体图文类页面可带页脚，但页脚只保留右下角页码：

```html
<div class="footer-area">
  <div class="footer-page">...</div>
</div>
```

不要输出 `footer-logo`、学校/学院署名或底部分隔线。

封面、目录、章节过渡、卡片、thanks 页默认不使用 `footer-area`。

### Media
媒体统一使用以下容器：
- `media-card`
- `media-stage`
- `media-element`
- `media-caption`

规则：
- 媒体内容必须是真实 `<img>` 或 `<video>`。
- 运行时内容中有 `Local-Path` / `Local-Poster-Path` 时优先使用本地路径。
- 媒体默认保持比例，使用居中自适应展示，不要强制拉伸。
- 每页最多一个主媒体。

### 系统后处理装饰
以下装饰由 PPT 服务后处理注入，模型不要手写：
- `slide-safe-decor`
- `thanks-safe-decor`
- `slide-top-rule`
- `slide-header-hairline`
- `slide-header-mark`
- `slide-header-mark-accent`
- `content-safe-accent`
- `thanks-safe-line`

不要依赖 `.slide::before`、`.slide::after`、径向渐变、滤镜或复杂阴影来承载必须出现在 PPTX 中的视觉元素。

## 版式选择表

| 内容形态 | 推荐版式 |
|---|---|
| `Role = cover` | `cover` |
| `Role = toc` | `toc` |
| `Role = section` | `section` |
| `Role = thanks` | `thanks` |
| `Cards`，且是三点并列 / 三种特征 / 三类方案 | `card-layout` |
| `Comparison`，两个平级对象或视角 | `standard-text-comparison` |
| 强正反对比、旧架构 vs 新方案、痛点 vs 优势 | `comparison-vs-panels` |
| `Process` 3 步 | `standard-text-process` + `process-track` |
| 3 步工具调用、RPC、执行链路，且每步需要输入/代码/结果片段 | `execution-pipeline` |
| `Process` 4 步 | `standard-text-process` + `process-grid` |
| `Process` 5 步或更多 | `standard-text-process` + `process-list` |
| 高密度 bullets、嵌套说明、编号步骤、示例流程 | `standard-text-structured` |
| 左侧有 1 到 2 个完整 insight card，右侧有 quote + 3 条以上论证 | `standard-text-dual-panel` |
| 三大基石、三条原则、三项核心能力，并需要底部一句总结 | `pillar-cards-banner` |
| 一个总论点 + 5 到 6 个模块、能力、组件或支撑机制 | `capability-map-grid` |
| 媒体为主、文字辅助 | `media-left-text-right` 或 `media-focus` |
| 文字结论为主、媒体作例证 | `text-left-media-right` |
| 2 到 3 条低密度短要点 | `standard-text` |

## 合同 A：Cover

来源：
- `format/cover-body.html`

根节点：
- `div.slide.layout-cover`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `cover-hero`
3. `cover-meta`

结构：
- `cover-hero` 必须包含 `header-area`。
- `cover-hero` 可包含一个 `cover-subtitle`。
- `cover-subtitle` 包含 `cover-subtitle-accent`、`cover-subtitle-kicker`、`cover-subtitle-text`。
- `cover-meta` 包含 2 到 4 个 `meta-item`。

边界：
- 不加入 `content-area`。
- 不加入 `footer-area`。
- 不使用 `surface-card + quote-box` 充当封面副标题。

## 合同 B：TOC

来源：
- `format/toc-body.html`

根节点：
- `div.slide.layout-toc`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `toc-left`
3. `toc-right`

结构：
- `toc-left` 包含 `toc-title-en`、`toc-title-zh`、可选 `toc-summary`、`toc-divider`。
- `toc-summary` 只放一句很短的结构提示。
- `toc-right` 包含 3 到 5 个 `toc-item`。
- 每个 `toc-item` 包含 `tag-number` 和 `toc-content`。
- 每个 `toc-content` 包含 `toc-title` 和 `toc-subtitle`。

边界：
- 不把目录页写成普通卡片页。
- 不在 `toc-right` 直接堆段落。
- 不省略 `tag-number`。

## 合同 C：Section Break

来源：
- `format/section-body.html`

根节点：
- `div.slide.layout-section-break`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `section-left`
3. `section-right`

结构：
- `section-left` 包含一个 `section-number`。
- `section-right` 包含 `header-area` 等价标题结构，也可直接放 `title-en / title-main / title-divider`。
- `section-right` 可包含一个 `section-desc`。

边界：
- `section-number` 推荐两位数，如 `01`。
- `section-desc` 控制在 1 到 2 句。
- 不加入页脚、卡片阵列、流程或长列表。

## 合同 D：Standard Text / Classic

来源：
- `format/standard-text-body.html`

根节点：
- `div.slide.layout-standard-text`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-area`
4. `footer-area`

结构：
- `content-area` 使用一个 `quote-box` 加一个 `surface-card text-details`，或只使用一个 `surface-card text-details`。
- `text-details` 内放 2 到 3 个扁平 `list-item`。

适用：
- 一个核心判断 + 2 到 3 条短解释。
- 概念定义、低密度结论、轻量摘要。

边界：
- 4 条以上要点、长解释、嵌套列表、编号步骤、示例流程不要用 classic。
- 不加入 `comparison-grid`、`process-track`、`process-grid`、`dual-panel-aside`、`sidebar-rail`。

## 合同 E：Standard Text / Dual Panel

来源：
- `format/standard-text-dual-panel-body.html`

根节点：
- `div.slide.layout-standard-text-dual-panel`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-area`
4. `footer-area`

结构：
- `content-area` 必须且只能包含 `dual-panel-aside` 和 `dual-panel-main`。
- `dual-panel-aside` 包含 1 到 2 个 `surface-card insight-card`。
- `dual-panel-main` 可包含一个 `quote-box` 和一个 `surface-card text-details`。

适用：
- 左侧有 1 到 2 个完整 insight card，右侧有 quote + 3 条以上论证。
- 原因分析、方法解读、优缺点说明。

边界：
- 对等比较应改用 comparison。
- 一个核心判断 + 3 到 4 条标签解释、短 bullets 或低密度概念拆解，应改用 `standard-text-structured` 或 `standard-text`。
- 不省略 `dual-panel-aside` 或 `dual-panel-main`。

## 合同 G：Standard Text / Structured

来源：
- `format/standard-text-structured-body.html`

根节点：
- `div.slide.layout-standard-text-structured`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-area`
4. `footer-area`

结构：
- `content-area` 包含 `structured-lead` 和一个 `surface-card structured-panel`。
- `structured-lead` 包含 `structured-kicker` 和 `structured-lead-text`。
- `structured-panel` 默认包含 3 到 4 个 `structured-section`；只有短内容才使用 5 个。
- 含 `structured-flow` 时最多 3 个 section。
- `structured-section` 包含 `structured-section-index` 与 `structured-section-body`。
- 示例流程使用 `structured-flow / structured-flow-step`，`structured-flow-step` 只写短动作短语。

适用：
- 高密度 bullets。
- 概念解释 + 示例流程 + 价值总结。
- 编号步骤、实践步骤、工作流说明。

边界：
- 不加入 `sidebar-card`、`sidebar-points`。
- 不使用 `structured-grid` 或多张 `structured-card`。
- 不嵌套原生 `ol` / `ul`。
- 不把 3 个或 5 个信息块做成独立卡片网格。

## 合同 H：Standard Text / Comparison

来源：
- `format/standard-text-comparison-body.html`

根节点：
- `div.slide.layout-standard-text-comparison`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-area`
4. `footer-area`

结构：
- `content-area` 包含一个 `comparison-grid`。
- `comparison-grid` 必须且只能包含两个 `surface-card comparison-card`。
- 每个 comparison card 包含 `insight-kicker`、`card-title`、`card-subtitle`、`comparison-details`。

适用：
- 两个平级对象、机制、方案或视角对照。

边界：
- 不承载三列或更多列内容。
- 上下级关系、流程关系不要误写成 comparison。

## 合同 I：Standard Text / Process

来源：
- `format/standard-text-process-body.html`
- `format/standard-text-process-grid-body.html`
- `format/standard-text-process-list-body.html`

根节点：
- `div.slide.layout-standard-text-process`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-area`
4. `footer-area`

三种结构：
- 3 步：`process-track`，相邻 `process-step` 之间插入 `process-divider`。
- 4 步：`process-grid`，必须有 4 个 `surface-card process-step`，不要插入 `process-divider`。
- 5 步或更多：`surface-card process-list`，每一步使用 `process-list-item`。

共同结构：
- 每个 `process-step` 或 `process-list-item` 包含 `process-index` 和 `process-copy`。
- `process-copy` 包含 `card-title` 与 `card-subtitle`。

边界：
- `process-index` 已经承担序号，`card-title` 不要重复写 `Step 1`、`01`。
- 5 步不要使用 `process-grid` 或 `process-step-wide`。
- 不要把流程页退化成普通 bullet 列表。
- 不要把 5 步 Process 改成普通三卡或低密度文本页。

## 合同 J：Card Layout

来源：
- `format/card-layout-body.html`

根节点：
- `div.slide`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `cards-grid`

结构：
- `cards-grid` 包含 3 个左右 `surface-card`。
- 每张卡片至少包含 `card-title` 和 `card-desc`。
- 推荐加入 `card-subtitle` 增强层次；旧内容里的 `card-icon` 仍可保留。
- 每张卡片必须包含真实 `card-top-accent` 和 `card-ghost-number` 节点；`card-ghost-number` 使用 `01`、`02`、`03` 这类两位序号。
- 标题分隔线由 CSS 提供，顶部色条和右下角淡色序号不要依赖 CSS 伪元素或 counter。

适用：
- 三点并列、三种特征、三类方案、三类画像、三个关键词与标签解释。

边界：
- 不加入 `footer-area`。
- 不把流程或对比误写成卡片阵列。
- 短卡片不要只保留“标题 + 一句短句”。

## 合同 J2：Comparison VS Panels

来源：
- `format/comparison-vs-panels-body.html`

根节点：
- `div.slide.layout-comparison-vs-panels`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-area`

结构：
- `content-area` 包含一个 `vs-comparison-grid`。
- `vs-comparison-grid` 必须包含左侧 `surface-card vs-panel vs-panel-negative`、中间 `vs-center`、右侧 `surface-card vs-panel vs-panel-positive`。
- `vs-center` 只包含真实节点 `vs-badge`。
- 每侧 `vs-panel` 包含 `vs-panel-heading`、2 到 3 个 `vs-point`、1 个 `vs-summary`。

适用：
- 旧架构 vs 新方案、痛点 vs 优势、风险路径 vs 推荐路径。

边界：
- 普通平级比较用 `standard-text-comparison`。
- 不要连续使用 `comparison-vs-panels`。
- 不加入页脚、流程轨道或第三列。

## 合同 J3：Execution Pipeline

来源：
- `format/execution-pipeline-body.html`

根节点：
- `div.slide.layout-execution-pipeline`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-area`

结构：
- `content-area` 包含 `pipeline-track`。
- `pipeline-track` 必须包含 3 个 `surface-card pipeline-card`，相邻卡片之间使用真实 `pipeline-arrow` 节点。
- `pipeline-arrow` 必须包含 `pipeline-arrow-svg`，不要使用 `▶` 等 emoji 或纯文本箭头。
- 每张卡片包含 `pipeline-number`、`pipeline-card-title`、`pipeline-card-text`，可选 `pipeline-code`。

适用：
- 3 步工具调用、RPC、执行链路、上下文回传。

边界：
- 普通 3 步短流程用 `standard-text-process` + `process-track`。
- `pipeline-code` 只放短输入、短 JSON、命令结果或模型输出摘要。
- 不要连续使用 `execution-pipeline`。

## 合同 J4：Pillar Cards Banner

来源：
- `format/pillar-cards-banner-body.html`

根节点：
- `div.slide.layout-pillar-cards-banner`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-area`

结构：
- `content-area` 包含 `pillar-card-grid` 和 `pillar-summary-bar`。
- `pillar-card-grid` 必须包含 3 个 `surface-card pillar-card`。
- 每张卡片包含 `pillar-icon-box`、`card-title`、`card-desc` 和 1 到 3 个 `pillar-tag`。

适用：
- 三大原则、三大基石、三类优势、三项能力。

边界：
- 4 个以上模块不要用本版式。
- 强对比不用本版式。
- 不要连续使用 `pillar-cards-banner`。

## 合同 J5：Capability Map Grid

来源：
- `format/capability-map-grid-body.html`

根节点：
- `div.slide.layout-capability-map-grid`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-area`

结构：
- `content-area` 包含 `capability-map`。
- `capability-map` 包含左侧 `capability-hero` 和右侧 `capability-grid`。
- `capability-grid` 推荐 6 个 `surface-card capability-card`；内容天然为 5 项时允许 5 个。
- 每张小卡包含 `capability-index`、`capability-card-title`、`capability-card-text`，可选 `capability-chip`。

适用：
- 一个核心论点拆解为 5 到 6 个模块、能力、组件或支撑机制。

边界：
- 每个模块说明控制在 1 到 2 行。
- 3 项并列用 `pillar-cards-banner` 或 `card-layout`。
- 不要连续使用 `capability-map-grid`。

## 合同 K：Media Left / Text Right

来源：
- `format/media-left-text-right-body.html`

根节点：
- `div.slide.layout-image-text`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-split-64`
4. `footer-area`

结构：
- `content-split-64` 包含 `split-left-image` 和 `split-right-text`。
- `split-left-image` 包含一个 `surface-card media-card`。
- `split-right-text` 放 `quote-box` 和 `surface-card text-details text-list`。

适用：
- 媒体为主，右侧放解释、结论或阅读提示。

边界：
- 不裸放媒体标签。
- 不让右侧正文变成 comparison 或 process。

## 合同 L：Text Left / Media Right

来源：
- `format/text-left-media-right-body.html`

根节点：
- `div.slide.layout-text-media`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `header-area`
3. `content-split-46`
4. `footer-area`

结构：
- `content-split-46` 包含 `split-left-text` 和 `split-right-media`。
- `split-left-text` 放 `quote-box` 和 `surface-card text-details text-list`。
- `split-right-media` 包含一个 `surface-card media-card`。

适用：
- 先给结论，再用右侧媒体展示案例或证据。

边界：
- 不在右侧放多个主媒体。
- 左侧不要改成流程轨道或卡片阵列。

## 合同 M：Media Focus

来源：
- `format/media-focus-body.html`

根节点：
- `div.slide.layout-media-focus`

直接子元素顺序：
1. `slide-brand`（按主题配置，可选）
2. `media-focus-image-panel`
3. `media-focus-content-panel`

结构：
- `media-focus-image-panel` 包含 `media-stage`、`media-element` 和可选 `media-focus-caption`。
- `media-focus-content-panel` 包含 `header-area`、一个重点说明 `quote-box` 和一个短 `text-details text-list`。
- 左侧图片使用 cover 裁切语义：保持原比例填满左侧区域，超出部分允许裁掉。
- 版式必须是绝对定位左右分栏，左侧约 60% 全高媒体，右侧约 40% 短文本说明；根节点必须无 padding，避免主题 `.slide` padding 影响 full-bleed 图片。

适用：
- 关键架构图、实验效果、视频演示等视觉主角页面。

边界：
- 禁止横幅式媒体结构或 banner 图；不要生成上方长条媒体 + 下方文本的旧结构。
- 不再输出下方总结区。
- 右侧文字控制在 2 到 3 条短要点。
- 不在一页放多个主媒体。

## 合同 N：Thanks

来源：
- `format/thanks-body.html`

根节点：
- `div.slide.layout-thanks`

直接子元素顺序：
1. `thanks-content`
2. `footer-decoration`

结构：
- `thanks-content` 包含 `title-en`、`title-main`、`title-divider center-divider`、`thanks-note`。
- `title-main` 推荐 `Q&A`，必须单行。
- `footer-decoration` 包含真实 `<img class="thanks-logo-image" src="/assets/HEU/heu-logo.png" ...>`。

边界：
- 不加入 `slide-brand`。
- 不加入 `header-area` 或 `footer-area`。
- 不输出 `thanks-orbit`、`thanks-accent-line`、`thanks-safe-decor`。
- 不输出 `logo-placeholder`、`HEU LOGO`、`contact-info`、`info-item`。
- 不承载总结卡片、核心回顾或未来展望。
