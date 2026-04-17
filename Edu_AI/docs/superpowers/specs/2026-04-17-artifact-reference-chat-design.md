# Artifact Reference Chat Design

## Goal

实现“生成物预览 -> 添加到当前对话”后的统一引用语义：

- 默认把生成物当作当前对话的引用文件，而不是直接进入编辑模式。
- 用户可以直接围绕这个文件提问。
- 当用户表达明确修改意图时，系统进入修改链路，并尽可能精准定位修改目标。

本期范围：

- 完整支持 `report` / `report_outline` 的“问答 + 精准修改”。
- 支持 `ppt_deck` 的“问答 + 按页修改”。
- 不在本期实现 PPT 页内元素级精准修改。

## Current State

当前链路已经具备以下基础：

- `StudioPanel.tsx` 可将预览中的生成物写入前端 store 的 `artifactReference`。
- `ChatPanel.tsx` 发送消息时会把 `artifact_reference` 一并带到 `/api/chat/v2/reply`。
- 后端 `reply_service_v2.py` 在检测到 `artifact_reference` 后，会直接进入 `report_edit_runtime` 或 `ppt_edit_runtime`。

这带来两个问题：

1. “引用文件提问”和“修改文件”没有被分开，引用行为被等价成编辑行为。
2. 报告修改的定位逻辑较粗糙，PPT 修改仅支持页码定位，且用户提问无法直接利用引用文件内容。

## Product Behavior

### Entry Behavior

用户点击“添加到当前对话”后：

- 当前对话绑定该生成物引用。
- 输入框上方继续显示引用卡片。
- 用户后续输入默认被视为“围绕该文件继续提问”。

辅助提示文案保持轻量：

- 可直接提问。
- 如需修改，可说“修改第 3 页”“重写结论”“把‘课堂纪律现状’这一节压缩一点”等。

### Default Mode

默认模式为“围绕文件提问”。

只有当系统识别到明确修改意图时，才切换到修改链路。

### Scope Rules

- `report` / `report_outline`
  - 支持问答。
  - 支持基于结构节点的精准修改。
- `ppt_deck`
  - 支持问答。
  - 支持按页修改。
  - 如果未明确到页码，则返回澄清，不自动猜测。

## Architecture

### 1. Artifact Reference Means Context, Not Edit

`artifact_reference` 的语义从“强制编辑目标”升级为“当前对话绑定的引用文件”。

后端收到 `artifact_reference` 后，先判断本轮用户输入属于：

- `ask_about_artifact`
- `edit_artifact`

再决定进入普通问答路径还是编辑路径。

### 2. Reply Service Becomes the Split Point

在 `reply_service_v2.py` 中增加引用文件意图分流：

- 若是 `ask_about_artifact`：
  - 解析引用内容。
  - 将引用文件内容整理为模型上下文。
  - 走 `FastChatRuntime`。
- 若是 `edit_artifact`：
  - 继续走 `report_edit_runtime` 或 `ppt_edit_runtime`。

这样不需要新建第二套问答系统，直接复用现有快路径聊天能力。

### 3. Artifact Context Injection

新增一个轻量的 artifact context 解析层，负责把不同类型的生成物转成模型可消费的文本上下文。

建议新增职责：

- `artifact_context_loader`
  - 依据 `artifact_reference` 找到源 artifact。
  - 优先从课程材料读取；找不到时回退到当前会话 snapshot。
- `artifact_context_formatter`
  - 将 artifact 内容格式化成统一上下文块。

格式规则：

- `report`
  - 注入全文 Markdown。
- `report_outline`
  - 注入完整大纲结构。
- `ppt_deck`
  - 注入标题、页数、每页标题/章节摘要、可用的 outline 信息。
  - 不向模型注入二进制文件内容。

`FastChatRuntime` 在构造 `user_text` 时追加一段 artifact context block，例如：

- 当前引用文件类型
- 文件标题
- 文件结构摘要
- 文件正文/大纲/页摘要
- 用户问题

## Intent Routing

### Ask vs Edit

本期优先采用“规则优先”的意图分流，不引入额外模型分类器。

判定为 `edit_artifact` 的信号包括：

- 显式修改动词：修改、重写、润色、压缩、扩写、重排、调整、删掉、补充。
- 目标表达明显指向文件内容：第 3 页、结论、摘要、这一节、这一段、这句。

其余情况默认进入 `ask_about_artifact`。

这样可以尽量避免把普通提问误判成修改。

### Route Outcomes

- `ask_about_artifact`
  - 返回正常聊天回答。
  - 不要求用户移除引用。
- `edit_artifact`
  - 进入编辑 runtime。
  - 若定位失败，返回澄清问题而不是直接修改。

## Report Editing Design

### Targeting Strategy

报告修改采用“先定位，再改写”的流程。

定位优先级：

1. 显式编号
   - 例：第 2 部分、第 3 节。
2. 显式标题
   - 例：把“课堂纪律现状”这一节改短。
3. 引号片段
   - 例：把“学生参与度明显下降”这句改得更正式。
4. 常见别名
   - 摘要、引言、结论、总结。
5. 无法唯一命中时，进入澄清。

### Parser Output

升级 `report_edit_intent_parser.py`，返回更完整的结构：

- `intent_type`
- `action_type`
- `target_locator_type`
- `target_node_id`
- `target_node_label`
- `matched_snippet`
- `needs_disambiguation`
- `candidate_labels`
- `instruction`

### Structure Parsing

继续复用 `report_structure_parser.py` 提供的结构节点，但扩展匹配能力：

- 支持标题精确匹配和归一化匹配。
- 支持按正文内容片段匹配到节点。
- 命中多个节点时返回候选列表。

### Disambiguation

当修改目标不明确时，系统返回自然语言澄清，例如：

- 你要修改的是：摘要 / 问题界定 / 课堂观察 / 结论？

禁止：

- 默认落到第一个章节。
- 在多候选情况下静默猜测。

## PPT Design

### Q&A

PPT 被引用后，用户可以直接围绕该 PPT 内容提问。

问答时使用：

- 标题
- 页数
- outline
- slide 摘要信息

### Editing

PPT 修改仍保持现有按页 revision 机制。

本期只接受明确页码目标：

- 第 3 页
- slide 5

如果用户说“把讲牛顿第二定律那页改成流程图风格”但没有明确页码：

- 本期不做语义猜页。
- 返回澄清，请用户指定页码。

这样可以避免把高风险的定位问题引入 HTML2PPT 修订链路。

## State and UI Impact

前端交互不新增重型模式切换。

保留现有：

- `StudioPanel` 添加引用
- `ChatPanel` 引用卡片展示

小幅增强：

- 引用卡片附近增加轻提示，说明可直接提问或发出修改指令。

会话状态继续保存：

- `artifact_reference`
- `active_artifact`
- `referenced_artifact_ids`

不新增新的前端主状态模式字段。

## Error Handling

- 引用文件不存在：
  - 返回“引用文件未找到，请重新添加到当前对话”。
- 问答路径无法解析内容：
  - 返回“当前文件暂不支持直接问答”。
- 修改路径定位失败：
  - 返回澄清提示。
- 修改路径命中多个节点：
  - 返回候选列表。
- PPT 修改未给出页码：
  - 返回指定页码提示。

## Testing

### Frontend

- `StudioPanel` 添加到当前对话后，仍写入 `artifactReference`。
- `ChatPanel` 在引用卡片区域展示轻提示文案。
- `buildChatReplyPayload` 继续正确发送 `artifact_reference`。

### Backend

- `artifact_reference + 普通问题` 走问答路径。
- `artifact_reference + 明确修改意图` 走编辑路径。
- `report` 正文问答时会注入全文上下文。
- `report_outline` 问答时会注入大纲上下文。
- 报告修改支持：
  - 编号定位
  - 标题定位
  - 引号片段定位
  - 歧义澄清
- `ppt_deck` 问答时会注入页摘要上下文。
- `ppt_deck` 修改未指定页码时返回澄清。

## Non-Goals

本期不做以下内容：

- PPT 页内元素级定位修改。
- 用 LLM 做通用修改意图分类。
- 为引用文件新增独立的前端模式切换器。
- 对所有 artifact 类型统一开放问答与编辑能力。

## Rollout Notes

推荐按以下顺序实现：

1. 后端 artifact 问答/编辑分流。
2. artifact context 注入快路径。
3. 报告编辑定位增强。
4. PPT 引用问答支持。
5. 前端轻提示与回归测试。

这样可以先打通主价值链路，再补精准定位与体验细节。
