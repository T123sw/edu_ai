# 版式约束合同（Layout Contracts）
本文件用于定义当前项目里“允许被生成”的版式骨架、容器层级与可变范围。

目标不是把每一页都变成固定模板，而是给模型一个清晰的“合法边界”：
- 根节点和主要骨架必须稳定
- 组件层级必须稳定
- 内容组合可以在合同允许的范围内灵活变化
- 模板中的示例文案只是占位示意，不是必须保留的内容。

## Agent 使用方式

在生成任务中，按下面顺序使用本文件：

1. 先根据 `content.md` 判断当前页的内容形态。
2. 再选择最匹配的版式合同，而不是先自由写 HTML。
3. 只在该合同允许的根节点、容器层级和组件范围内组合内容。
4. 如果某页同时适配多种版式，再结合上一页避免重复。
5. 如果模板示例与合同不一致，始终以合同为准。

本文件负责回答三个问题：
- 这页应该用哪类骨架
- 该骨架的必需结构是什么
- 该骨架内部允许有多少灵活性

## 全局规则

### 1. 根节点规则
- 每一页都必须以 `<div class="slide ...">...</div>` 作为根节点。
- 除卡片页外，推荐为根节点显式添加对应的 `layout-*` class。
- 不允许在 slide 外层再包新的业务容器。

### 2. 品牌位规则
- 品牌位是否启用，只能由 `style/theme-brand-config.json` 决定。
- 如果当前主题 `brand.enabled` 为 `true`，则品牌位必须作为每一页 slide 根节点打开后的第一个子元素。
- 品牌位结构必须严格复用 `format/brand-slot-fragment.html`：

```html
<div class="slide-brand">
  <img class="slide-brand-image" src="{{BRAND_ASSET}}" alt="{{BRAND_ALT}}">
</div>
```

- `src` 必须替换为主题配置中的 `brand.asset`。
- `alt` 必须替换为主题配置中的 `brand.alt`。
- 如果品牌关闭，则整块省略，不输出空节点。

### 3. 标题规则
- 只要页面中出现页标题区域，就必须使用 `title-en`、`title-main`、`title-divider` 这一组现有结构。
- `title-divider` 必须作为独立元素存在，不能被替换成边框、伪元素或别的修饰结构。

### 4. 引言框规则
- 只要页面使用引言框，就必须严格使用以下结构：

```html
<div class="quote-box">
  <div class="quote-accent"></div>
  <div class="quote-text">...</div>
</div>
```

- 不允许改回 `border-left`、伪元素装饰条或其它变体。

### 5. 页脚规则
- 只有标准文本类页面默认带 `footer-area`。
- 卡片页、目录页、章节过渡页、封面页、致谢页不要求使用 `footer-area`，除非未来模板明确加入该结构。
- 如果使用 `footer-area`，内部应保持：
  - `footer-logo`
  - `footer-page`

### 6. 内容数量建议
- 合同中的“推荐数量”不是死规则，但若明显超出，页面很容易溢出或视觉失衡。
- 在不确定时，优先遵守结构稳定，其次再追求信息量。

### 7. 媒体骨架规则
- `layout.css` 中的 `layout-image-text`、`content-split-64`、`split-left-image`、`split-right-text`、`image-placeholder`、`text-list` 现已作为正式开放的媒体页骨架使用。
- 当前媒体页统一复用 `media-card`、`media-stage`、`media-element`、`media-caption` 作为媒体容器结构。
- 媒体内容可以是 `<img>` 或 `<video>`，但必须使用真实媒体标签。
- 媒体默认保持比例，必须使用自适应展示，不允许强制拉伸填满内容。

## 版式合同

### Contract A：Brand Slot Fragment

用途：
- 主题驱动的可选品牌位组件。

根节点签名：
- 不是独立 slide。

必须结构：
- `div.slide-brand`
- 其内部必须只有一个 `img.slide-brand-image`

禁止：
- 不允许改成背景图
- 不允许改成 SVG 内联占位
- 不允许加额外包裹层

### Contract B：Cover

对应来源：
- `format/cover-body.html`
- `format/layout.css` 中的 `.layout-cover`、`.cover-hero`、`.cover-meta`

适用场景：
- 封面页
- 报告首页
- 主题引入页

根节点签名：
- `div.slide.layout-cover`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `cover-hero`
3. `cover-meta`

`cover-hero` 必须包含：
- `header-area`

`header-area` 必须包含：
- `title-en`
- `title-main`
- `title-divider`

`cover-hero` 允许的可选内容：
- 一个 `surface-card`
- 该 `surface-card` 内允许放一个 `quote-box` 作为副标题、引导句或摘要语

`cover-meta` 必须包含：
- 2 到 4 个 `meta-item`

推荐内容承载方式：
- `title-main`：主标题
- `title-en`：英文副标题或主题标签
- `quote-box`：副标题、研究范围或一句导语
- `meta-item`：汇报人、导师、时间、单位等元信息

禁止：
- 不要把封面写成标准文本页
- 不要在封面中引入 `content-area`
- 不要在封面中使用 `footer-area`

说明：
- 当前 `format/cover-body.html` 更像示例片段，不足以单独表达完整封面骨架。
- 生成时应以本合同和 `layout.css` 中的 `layout-cover / cover-hero / cover-meta` 为准。

### Contract C：TOC

对应来源：
- `format/toc-body.html`
- `format/layout.css` 中 `.layout-toc`、`.toc-left`、`.toc-right`

适用场景：
- 目录页
- 全局结构总览页

根节点签名：
- `div.slide.layout-toc`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `toc-left`
3. `toc-right`

`toc-left` 必须包含：
- `toc-title-en`
- `toc-title-zh`
- `toc-divider`

`toc-right` 必须包含：
- 3 到 5 个 `toc-item`

每个 `toc-item` 必须包含：
- `tag-number`
- `toc-content`

每个 `toc-content` 必须包含：
- `toc-title`
- `toc-subtitle`

禁止：
- 不要把目录页写成普通卡片页
- 不要在 `toc-right` 中直接堆纯文本段落
- 不要省略 `tag-number`

### Contract D：Section Break

对应来源：
- `format/section-body.html`
- `format/layout.css` 中 `.layout-section-break`、`.section-left`、`.section-right`

适用场景：
- 章节过渡页
- Part 分隔页
- 大章节切换页

根节点签名：
- `div.slide.layout-section-break`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `section-left`
3. `section-right`

`section-left` 必须包含：
- 一个 `section-number`

`section-right` 必须包含：
- `title-en`
- `title-main`
- `title-divider`

`section-right` 可选包含：
- 一个 `section-desc`

推荐：
- `section-number` 使用两位数，例如 `01`、`02`
- `section-desc` 控制在 1 到 2 句内

禁止：
- 不要加入 `footer-area`
- 不要在章节过渡页中塞入大段列表、卡片阵列或流程结构

### Contract E：Standard Text / Classic

对应来源：
- `format/standard-text-body.html`
- `format/layout.css` 中 `.layout-standard-text`

适用场景：
- 一个核心判断 + 多条解释
- 概念定义页
- 结论摘要页

根节点签名：
- `div.slide.layout-standard-text`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `header-area`
3. `content-area`
4. `footer-area`

`header-area` 必须包含：
- `title-en`
- `title-main`
- `title-divider`

`content-area` 允许的直接子元素：
- 一个 `quote-box`
- 一个或两个 `surface-card text-details`

推荐组合：
- 方案 A：`quote-box` + 1 个 `surface-card text-details`
- 方案 B：仅 1 个 `surface-card text-details`

低内容密度优先策略：
- 当 classic 只有 2 到 4 条 bullets、没有天然的双栏/流程/对比结构时，优先使用方案 A
- 不要让页面退化成“一个很大的白色卡片 + 3 条很短的字”而缺少层次

`surface-card text-details` 内部应包含：
- 2 到 4 个 `list-item`

低密度呈现建议：
- 如果只有一个 `surface-card text-details`，其第一条 `list-item` 应尽量承担“主陈述”角色，后续条目再做支撑
- 不要让 3 条并列短句在视觉上完全同权，否则会放大页面空白感

`footer-area` 必须包含：
- `footer-logo`
- `footer-page`

禁止：
- 不要在 classic 中加入 `comparison-grid`
- 不要在 classic 中加入 `process-track`
- 不要在 classic 中用 `dual-panel-aside` 或 `sidebar-rail`

### Contract F：Standard Text / Dual Panel

对应来源：
- `format/standard-text-dual-panel-body.html`
- `format/layout.css` 中 `.layout-standard-text-dual-panel`

适用场景：
- 左侧核心判断，右侧详细论证
- 原因分析
- 方法解读
- 优缺点说明

根节点签名：
- `div.slide.layout-standard-text-dual-panel`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `header-area`
3. `content-area`
4. `footer-area`

`content-area` 必须且只能包含两个直接子元素：
- `dual-panel-aside`
- `dual-panel-main`

`dual-panel-aside` 允许包含：
- 1 到 2 个 `surface-card insight-card`

每个 `insight-card` 必须包含：
- 一个 `insight-kicker`
- 并且至少包含以下之一：
  - `insight-copy`
  - `mini-points`

`mini-points` 内应包含：
- 2 到 4 个 `mini-point`

`dual-panel-main` 允许包含：
- 0 到 1 个 `quote-box`
- 1 个 `surface-card text-details`

`text-details` 内推荐：
- 2 到 4 个 `list-item`

禁止：
- 不要把左右两栏做成对等比较；对等比较应改用 comparison
- 不要省略 `dual-panel-aside` 或 `dual-panel-main`

### Contract G：Standard Text / Sidebar

对应来源：
- `format/standard-text-sidebar-body.html`
- `format/layout.css` 中 `.layout-standard-text-sidebar`

适用场景：
- 左侧摘要导航，右侧主体说明
- 研究计划页
- 问题拆解页
- 阶段总结页

根节点签名：
- `div.slide.layout-standard-text-sidebar`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `header-area`
3. `content-area`
4. `footer-area`

`content-area` 必须且只能包含两个直接子元素：
- `sidebar-rail`
- `sidebar-main`

`sidebar-rail` 必须包含：
- 一个 `sidebar-card`

`sidebar-card` 推荐包含：
- 一个 `title-en`
- 一个 `sidebar-title`
- 一个 `sidebar-points`

`sidebar-points` 内应包含：
- 2 到 4 个 `sidebar-point`

`sidebar-main` 允许包含：
- 0 到 1 个 `quote-box`
- 1 个 `surface-card text-details`

`text-details` 内推荐：
- 2 到 4 个 `list-item`

禁止：
- 不要把左栏写成普通段落堆叠
- 不要在 sidebar 中改用 `dual-panel-aside`
- 不要把 sidebar 做成平级双对象对比

### Contract H：Standard Text / Comparison

对应来源：
- `format/standard-text-comparison-body.html`
- `format/layout.css` 中 `.layout-standard-text-comparison`

适用场景：
- 两种方案对比
- 两类机制对照
- 现象 vs 机理
- A / B 分析

根节点签名：
- `div.slide.layout-standard-text-comparison`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `header-area`
3. `content-area`
4. `footer-area`

`content-area` 必须包含：
- 一个 `comparison-grid`

`comparison-grid` 必须且只能包含：
- 2 个 `surface-card comparison-card`

每个 `comparison-card` 应包含：
- 一个 `insight-kicker`
- 一个 `card-title`
- 0 到 1 个 `card-subtitle`
- 一个 `comparison-details`

`comparison-details` 内推荐：
- 2 到 4 个 `list-item`

禁止：
- 不要把三列甚至更多列内容塞进 comparison
- 不要把上下级关系页面误写成 comparison
- 不要省略任意一侧卡片

### Contract I：Standard Text / Process

对应来源：
- `format/standard-text-process-body.html`
- `format/layout.css` 中 `.layout-standard-text-process`

适用场景：
- 阶段推进
- 方法流程
- 研究路线
- 时间顺序
- 三阶段训练

根节点签名：
- `div.slide.layout-standard-text-process`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `header-area`
3. `content-area`
4. `footer-area`

`content-area` 推荐包含以下顺序：
1. `process-track`
2. `quote-box`（可选）
3. `surface-card text-details`（可选但强烈推荐）

`process-track` 必须由以下结构组成：
- 3 到 5 个 `surface-card process-step`
- 相邻 `process-step` 之间必须插入一个 `process-divider`
- `process-divider` 不能出现在开头或结尾

每个 `process-step` 必须包含：
- `process-index`
- `process-copy`

每个 `process-copy` 必须包含：
- `card-title`
- 0 到 1 个 `card-subtitle`

`text-details` 内推荐：
- 2 到 4 个 `list-item`

禁止：
- 不要把流程页退化成普通项目符号列表
- 不要让 `process-track` 只剩 2 个步骤
- 不要在流程轨道中混入 comparison 或 sidebar 容器

### Contract J：Card Layout

对应来源：
- `format/card-layout-body.html`
- `format/layout.css` 中 `.cards-grid`

适用场景：
- 三点并列
- 三种特征
- 三类方案
- 多列并列信息页

根节点签名：
- `div.slide`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `header-area`
3. `cards-grid`

`header-area` 必须包含：
- `title-en`
- `title-main`
- `title-divider`

`cards-grid` 必须包含：
- 2 到 4 个 `surface-card`

每个 `surface-card` 推荐包含：
- 0 到 1 个 `card-icon`
- 1 个 `card-title`
- 0 到 1 个 `card-subtitle`
- 1 个 `card-desc`

低内容密度优先策略：
- 如果单张卡片只有一句短描述，优先补足层次，例如加入 `card-subtitle`、`card-icon`，或让 `card-desc` 形成两层表达
- 不要把 card-layout 做成“每张卡都只有标题 + 一句很短的句子”且留出大面积无意义空白
- 卡片之间可以共享统一的轻量层次，例如序号、英文 kicker 或同构副标题，以增强结构感

说明：
- 当前模板示例展示的是 3 列，但从结构上允许 2 到 4 列。
- 所有卡片字段不必完全一致，但整体层级应尽量统一。

禁止：
- 不要在 card-layout 中加入 `footer-area`
- 不要把卡片页写成流程页或对比页
- 不要把 `cards-grid` 内元素换成非 `surface-card`

### Contract K：Thanks / Q&A

对应来源：
- `format/thanks-body.html`
- `format/layout.css` 中 `.layout-thanks`

适用场景：
- Q&A
- 致谢页
- 汇报结束页

根节点签名：
- `div.slide.layout-thanks`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `thanks-content`
3. `footer-decoration`

`thanks-content` 必须包含：
- `title-en`
- `title-main`
- `title-divider center-divider`
- `contact-info`

`contact-info` 必须包含：
- 2 到 4 个 `info-item`

`footer-decoration` 必须包含：
- 一个 `logo-placeholder`

禁止：
- 不要在致谢页加入 `header-area`
- 不要加入 `footer-area`
- 不要把结束页改写成普通文本页

### Contract L：Media / Left Media Right Text

对应来源：
- `format/media-left-text-right-body.html`
- `format/layout.css` 中 `.layout-image-text`、`.content-split-64`

适用场景：
- 左侧放图片，右侧放解释
- 左侧放视频，右侧放要点
- 图示解读页

根节点签名：
- `div.slide.layout-image-text`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `header-area`
3. `content-split-64`
4. `footer-area`

`content-split-64` 必须且只能包含：
- `split-left-image`
- `split-right-text`

`split-left-image` 必须包含：
- 一个 `surface-card media-card`

`media-card` 必须包含：
- 一个 `image-placeholder media-stage`
- 0 到 1 个 `media-caption`

`media-stage` 内必须包含以下之一：
- 一个 `img.media-element`
- 一个 `video.media-element`

`split-right-text` 推荐包含：
- 0 到 1 个 `quote-box`
- 1 个 `surface-card text-details`

禁止：
- 不要省略媒体容器直接裸放媒体标签
- 不要让媒体脱离 `media-stage`
- 不要把右侧正文写成 comparison 或 process 结构

### Contract M：Media / Left Text Right Media

对应来源：
- `format/text-left-media-right-body.html`
- `format/layout.css` 中 `.layout-text-media`、`.content-split-46`

适用场景：
- 左侧结论，右侧媒体
- 左侧分析，右侧案例
- 文本结论 + 视觉证据

根节点签名：
- `div.slide.layout-text-media`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `header-area`
3. `content-split-46`
4. `footer-area`

`content-split-46` 必须且只能包含：
- `split-left-text`
- `split-right-media`

`split-left-text` 推荐包含：
- 0 到 1 个 `quote-box`
- 1 个 `surface-card text-details`

`split-right-media` 必须包含：
- 一个 `surface-card media-card`

`media-card` 必须包含：
- 一个 `image-placeholder media-stage`
- 0 到 1 个 `media-caption`

`media-stage` 内必须包含以下之一：
- 一个 `img.media-element`
- 一个 `video.media-element`

禁止：
- 不要把左侧写成流程轨道或卡片阵列
- 不要在右侧放多个主媒体

### Contract N：Media / Focus

对应来源：
- `format/media-focus-body.html`
- `format/layout.css` 中 `.layout-media-focus`

适用场景：
- 大图重点展示
- 视频演示页
- 视觉焦点页

根节点签名：
- `div.slide.layout-media-focus`

根节点允许的直接子元素顺序：
1. `slide-brand`（仅在品牌开启时）
2. `header-area`
3. `media-focus-stage`
4. `media-focus-summary`

`media-focus-stage` 必须包含：
- 一个 `surface-card media-card media-card-focus`

`media-card-focus` 必须包含：
- 一个 `image-placeholder media-stage`
- 0 到 1 个 `media-caption`

`media-stage` 内必须包含以下之一：
- 一个 `img.media-element`
- 一个 `video.media-element`

`media-focus-summary` 推荐包含：
- 0 到 1 个 `quote-box`
- 0 到 1 个 `surface-card text-details`

说明：
- 该版式不是“纯媒体页”，下方应保留少量总结文字。
- 总结文字推荐压缩为 1 条结论句，或最多 1 到 2 条极短要点。

禁止：
- 不要把 `media-focus-summary` 堆成大段正文或大文本卡片
- 不要在一页里放多个主媒体
