# PPT Content Pipeline Redesign

**日期：** 2026-04-09

**范围：** 仅覆盖 `outline -> slide_plan -> content_markdown -> html2ppt` 这条 PPT 内容生成链路，不修改 `html2ppt` 渲染引擎本身，不涉及前端交互改造。

**设计目标：** 让 PPT 中间表示从“方便大模型输出”转为“方便 PPT 排版与教学表达”，分阶段解决目录膨胀、正文溢出、页面僵硬、占位词泛滥等问题。

**本次设计结论：**

- 目录问题的根因是缺少稳定的 `chapter` 层，不能再从 `slides` 反推目录。
- 溢出问题的根因是 `content_markdown` 生成前没有版式容量约束，不能只靠渲染后兜底。
- 死板问题的根因是当前 `cards/process/comparison` 直接承接模型产出的“结构化模板话术”，缺少语义槽位和占位词检测。
- 在进入 `html2ppt` 之前必须新增一层“校验门”，只有合格内容才能继续渲染。

---

## 1. 背景与问题

本轮调试已经证明，当前 PPT 流程的主问题不再是流程不通或任务超时，而是内容中间表示不够 PPT 友好。

现状体现为：

1. `preparation` 里只有 3 个核心 key points，但目录页却被扩成了 12 条目录项。
2. `slide_plan` 的内容比之前充实，但缺少版式容量控制，导致多页正文超出可视边界。
3. `cards`、`process`、`comparison` 等页面虽然结构完整，但出现了明显的“结构有了，语义没填满”的情况。
4. 很多真正能讲的具体内容进入了 `presenter_notes`，而页面可视区域只剩模板话术。

这说明当前问题不是简单的 prompt 不够强，而是：

- 目录层级不稳定
- 中间表示没有显式容量模型
- 页面内容没有语义层和可视层分离
- 缺少进入渲染前的质量闸门

---

## 2. 已确认需求

以下内容视为本次设计的硬约束：

1. 目录页正常应保持 3-4 个一级章节，不应列出所有内容页。
2. 内容进入 `html2ppt` 之前必须先通过一层检查，检查合格后才能继续。
3. 整体改造必须分阶段推进，避免一次性大改导致调试成本失控。
4. 第一阶段优先解决结构和稳定性问题，不追求一次性把所有内容风格问题彻底做完。

---

## 3. 设计原则

### 3.1 章节层和页面层必须解耦

目录来源必须是稳定的章节层，而不是内容页标题列表。

目录页只能读取：

- `chapters`

不能再读取：

- `slides`
- `slide titles`
- `expanded content points`

### 3.2 中间表示必须面向排版，而不是面向自由生成

模型可以负责生成内容候选，但最终进入 `content_markdown` 的内容必须受控于：

- 版式容量预算
- 内容类型规则
- 占位词检测
- 失败回退策略

### 3.3 可视内容与讲解内容分离

页面可视区域需要短、稳、信息密度清晰。

讲解补充内容可以更长，但应进入：

- `presenter_notes`

而不是直接塞进：

- `lead`
- `bullets`
- `cards.text`
- `process.step.text`

### 3.4 先加校验门，再考虑进一步增强

当前最需要的是“阻止坏内容继续进入 html2ppt”，而不是继续把更多自由度开放给模型。

---

## 4. 目标架构

改造后的链路建议拆成四层：

1. `outline` 生成章节树
2. `slide_plan` 生成每页语义槽位与版式候选
3. `content_gate` 做容量校验、占位词校验、必要压缩与降级
4. `content_markdown_assembler` 仅负责把已通过校验的内容拼成协议稿

目标流程：

```text
preparation
  -> outline(chapters + slides)
  -> slide_plan(semantic payload + layout intent)
  -> pre-html2ppt validation gate
      -> pass: assemble content_markdown
      -> fail: compress / downgrade / regenerate / reject
  -> html2ppt
```

---

## 5. 核心改造方案

### 5.1 引入稳定的 chapter 层

当前 `PptOutline` 虽然已有 `chapters`，但实际目录仍由 `slide_plan.slides` 的 content title 组成，说明 `chapter` 层还没有成为真正的数据源。

建议补强以下字段语义：

#### `PptOutlineChapter`

- `chapter_id`
- `chapter_order`
- `chapter_title`
- `toc_label`
- `chapter_goal`
- `chapter_summary`
- `slides`

#### `PptOutlineSlide`

- `chapter_id`
- `slide_topic`
- `show_in_toc`

关键规则：

- `chapter_title` 代表一级章节
- `toc_label` 只负责目录短标签
- `chapter_goal` / `chapter_summary` 负责给同章页面扩写提供统一上下文
- `slide title` 代表具体页面
- 目录页永远只读 `chapters`
- 非目录级页面必须 `show_in_toc = false`
- `slides` 只能挂载到现有 chapter 下，不能反向生成 chapter

以当前 Agent 案例为例，目录应固定为：

1. Agent 的核心工作循环
2. 工具调用的决策与执行
3. 技能系统的模块化设计

而这些页面不进入目录：

- 核心概念
- 工作机制
- 实现细节
- 案例
- 小结

### 5.2 将 slide_plan 从“版式内容”改为“语义槽位 + 版式映射”

当前 `slide_plan` 直接生成：

- `bullets`
- `cards`
- `process_steps`
- `comparison`

这导致模型经常直接生成模板化文案。

建议逐步引入语义槽位：

- `definition`
- `mechanism`
- `example`
- `value`
- `pitfall`
- `takeaway`

然后由版式模板决定哪些语义槽位进入可视区域，哪些进入 notes。

MVP 阶段不要求一次性替换所有字段，可以先在 `slide_plan_builder` 内部引入一个过渡层：

- 先生成简化 `semantic_payload`
- 再映射到当前已有的 `bullets/cards/process/comparison`

这样既能复用现有域模型，又能减少直接输出模板话术。

### 5.3 为每种 layout 增加硬性内容预算

建议在进入 `content_markdown` 前增加版式预算规则：

#### `lead`

- 仅 1 句
- 目标上限：36-48 个中文字符

#### `bullets`

- 3-4 条优先，最多 5 条
- 每条目标上限：28-36 个中文字符

#### `cards`

- 3-4 张卡
- 标题目标上限：8-12 个中文字符
- 正文目标上限：24-32 个中文字符

#### `process`

- 3-4 步
- 步骤标题目标上限：6-10 个中文字符
- 步骤正文目标上限：22-30 个中文字符

#### `comparison`

- 左右各 2-3 条
- 每条目标上限：20-30 个中文字符

规则目标不是“语义最完整”，而是“进入当前主题模板后大概率放得下”。

### 5.4 新增 pre-html2ppt 校验门

在 `content_markdown` 真正送往 `html2ppt` 之前新增一层内容校验：

- `structure_validator`
- `fit_validator`
- `placeholder_detector`
- `content_gate`

但 `content_gate` 不应成为一个巨型对象，而应拆成三层职责：

#### `inspectors`

职责：

- 只发现问题
- 不修改内容
- 输出统一 issue 列表

建议包含：

- `structure_validator`
- `fit_validator`
- `placeholder_detector`

#### `transformers`

职责：

- 只做确定性修复
- 不创造新语义
- 只能做删减、压缩、合并、降级

建议包含：

- `text_shortener`
- `item_trimmer`
- `layout_downgrader`

#### `gate adjudicator`

职责：

- 汇总 issue
- 执行允许的 transformer
- 决定 `pass / pass_with_transformations / fail`

约束：

- `builder` 负责生成候选内容
- `gate` 负责让候选内容可渲染
- `gate` 不能变成第二个 `builder`

### 5.5 issue model 与 transformation log

为了让日志、测试和回退行为稳定可读，`inspectors` 必须输出统一的 issue model。

建议字段：

- `code`
- `severity`
- `slide_index`
- `field_path`
- `message`
- `suggested_action`

同时，每次确定性修复都要记录 transformation log。

建议字段：

- `strategy`
- `slide_index`
- `field_path`
- `reason`
- `before`
- `after`

示例：

- `trim_cards_count: 4 -> 3`
- `shorten_card_text[slide=8][card=2]: 41 -> 28 chars`
- `downgrade_layout: process -> bullets`

#### `structure_validator`

检查：

- deck header 是否完整
- slide role / title / blocks 是否齐全
- 目录项数量是否超上限
- layout 与内容字段是否匹配

#### `fit_validator`

检查：

- lead 是否超预算
- bullets/cards/process/comparison 是否超项数
- 单项文本是否超字数
- 当前页面是否为高风险密度组合

`fit_validator` 必须同时包含两类规则：

##### 单项规则

- `lead > N chars`
- `bullet > N chars`
- `card title/body > N chars`
- `process step title/body > N chars`

##### 组合规则

- `lead + 5 bullets`
- `lead + 4 cards + long titles`
- `lead + 4 process steps + long step bodies`
- `lead + 3x3 comparison`

高风险示例：

- `lead + 5 bullets`
- `lead + 4 cards + 长标题`
- `lead + 4 process steps + 长正文`

#### `placeholder_detector`

Phase 1 只抓最硬的三类问题，避免误杀过多正常页面。

检查：

- `Text == Title`
- 正文只是标题复述
- 出现“为什么重要 / 课堂结论 / 最值得强调 / 关键作用”等空泛模板词，且缺少具体名词、动作或例子

以下更主观的规则延后到 Phase 2：

- sibling items 近似同义改写
- 卡片之间信息分工不清

### 5.6 校验失败后的回退策略

校验失败后不能直接继续进入 `html2ppt`。

建议回退顺序如下：

1. 压缩文本
2. 减少项数
3. 降级版式
4. 重新生成该页
5. 若仍失败，则中止并记录 debug 信息

压缩时要遵循一个硬原则：

- 优先删修饰语、过渡语、课堂化包装语
- 不优先删主体、动作、对象、差异点

也就是说，压缩器要尽量保留“谁做什么、对什么做、为什么不同”，避免把内容压成模板话。

示例：

- `cards x4` 超预算 -> 改为 `cards x3`
- `bullets x5` 超预算 -> 合并为 4 条
- `comparison` 左右过长 -> 裁成 2x2
- `process x4` 单步过长 -> 压缩文本，必要时降为 `bullets`

---

## 6. 分阶段落地方案

### 阶段 1A：目录层与最小校验门

目标：

- 目录只显示 3-4 个一级章节
- gate 先接管流转控制权
- 第一版只拦结构错误和 TOC 错误

不做：

- 不在这一阶段接预算压缩
- 不在这一阶段接 placeholder 判定

### 阶段 1B：容量控制与基础内容质检

目标：

- 对现有 `slide_plan` 做容量限制和自动压缩
- 接入单项预算和整页密度预算
- 接入最小 placeholder 检测

不做：

- 不重写全部 `slide_plan` 域模型
- 不一次性引入完整 semantic payload 体系

### 阶段 2：页面内容模板重做

目标：

- 重写 `cards/process/comparison` 的扩写规则
- 降低“课堂模板话术”比例
- 提高页面的信息密度和差异化表达

### 阶段 3：语义层与可视层解耦

目标：

- 引入 `semantic_payload`
- 将语义内容映射到 visible blocks / notes
- 让 notes 中的高价值具体内容优先进入可视区域

### 阶段 4：主题感知与容量调优

目标：

- 让不同 theme 拥有不同的容量预算
- 让 `fit_validator` 具备 theme-aware 配置

---

## 7. 受影响模块

本次改造主要涉及：

- `Edu_AI/api/Edu_AI/app/chat/domain/ppt_outline.py`
- `Edu_AI/api/Edu_AI/app/chat/domain/ppt_slide_plan.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/outline_builder.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/slide_plan_builder.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_markdown_assembler.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_validator.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/runtime.py`
- `Edu_AI/api/Edu_AI/tests/chat/` 下对应测试文件

建议新增：

- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/content_gate.py`

可选新增：

- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/layout_budget.py`
- `Edu_AI/api/Edu_AI/app/chat/workflows/ppt/placeholder_detector.py`

---

## 8. 风险与控制

### 风险 1：一次性改太多层，调试困难

控制方式：

- 严格分阶段
- 先做 chapter + gate，不同时做 semantic payload 全量替换

### 风险 2：容量限制过严，内容被压得太空

控制方式：

- 预算先按保守值落地
- 每次压缩都记录 debug log
- 后续再基于真实样例微调

### 风险 3：validator 太死，导致大量重试或回退

控制方式：

- 先做“结构检查 + 超长检查 + 占位词检查”三类核心规则
- 不在第一阶段引入复杂评分模型

---

## 9. 验收标准

阶段 1A 完成后，至少应满足：

1. 当前 Agent 样例的目录页只显示 3 个一级章节。
2. `content_markdown` 在送入 `html2ppt` 前必须经过 gate。
3. gate 能拦住结构错误和 TOC 错误。
4. 日志中能看到统一 issue model。

阶段 1B 完成后，至少应满足：

1. 当前 Agent 样例的目录页只显示 3 个一级章节。
2. `content_markdown` 在送入 `html2ppt` 前必须经过校验门。
3. 校验失败的内容不会直接进入 `html2ppt`。
4. 高风险页面会被压缩或降级，而不是直接溢出。
5. 日志中能看到校验结果、失败原因、issue model 和 transformation log。

阶段 2 完成后，至少应满足：

1. `cards` 页不再出现“标题和正文同义复读”。
2. `process` 页每步有明确动作语义，而不是流程占位语。
3. `comparison` 页左右两列语义差异清晰，不再只是平行改写。

---

## 10. 推荐实施顺序

推荐顺序如下：

1. 先补测试，把当前问题锁死
2. 再修 `chapter` 层和目录逻辑
3. 再落一个最小 gate，只做 `structure + TOC count`
4. 再加 layout 容量预算和自动压缩
5. 再加 placeholder detector
6. 最后重做 `cards/process/comparison` 的语义生成方式

这个顺序的好处是：

- 先解决结构问题
- 让 gate 尽早接管流转，但第一轮不要过重
- 再解决稳定性问题
- 最后解决表达质量问题

这样可以避免一开始就进入“大重构 + 大量不可控回归”的状态。

---

## 11. 固定样例回归测试

除规则级单元测试外，必须增加一类样例级回归测试。

第一份样例直接使用当前的 Agent 案例，固定以下输入和中间产物：

- `preparation`
- `outline`
- `slide_plan`
- `final content_markdown`

至少验证：

1. `TOC item count == 3`
2. 没有页面超过预算
3. placeholder-only 页面不会通过 gate
4. markdown 能成功进入 runtime 下游

这类样例测试的价值在于：

- 单元测试保证规则正确
- 样例回归测试保证整条链路真的变好了
