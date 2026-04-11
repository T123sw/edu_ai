# PPT Content 直出重构设计（中文协议驱动）

**状态：** 已完成初版设计，待评审  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\workflows\ppt`、`D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat\application`、`D:\Edu_AI_1\Edu_AI\api\Edu_AI\tests\chat`

## 1. 背景与问题

当前 PPT content 生成链路为：

`PptOutline`
-> `PptSlidePlanBuilder`
-> `PptContentMarkdownAssembler`
-> `PptContentGate`
-> `PptContentReviewer`
-> `html2ppt`

这条链路存在四个问题：

1. LLM 先生成中间态 `slide_plan`，再由代码翻译成最终 `content_markdown`，链路过长，约束重复。
2. Prompt 同时要求模型思考内容、版式意图、协议映射、JSON 结构，注意力被格式约束分散，内容质量不稳定。
3. `slide_plan_builder.py` 内已混入较多 fallback、章节拆分、layout 引导、review 回灌逻辑，职责膨胀，维护成本高。
4. 当前系统目标是中文教学场景，但 content prompt 仍以英文指令为主，且协议约束被人工拆散为规则列表，不利于模型整体理解协议。

用户期望的新方向是：

1. 删除中间态 content 扩写逻辑，不再让模型先生成 `slide_plan` 再转 markdown。
2. 直接让模型生成完整最终版 `content_markdown`。
3. 将 `content-protocol.md` 原文作为参考文档直接交给模型，而不是由代码手工拆解后再喂给模型。
4. 提示词改为中文，贴近系统实际使用场景。
5. 对页数给出软约束，引导模型生成 15 页以上的完整教学内容，但不写成代码硬规则。
6. 暂时关闭 content reviewer，将其作为后续优化项，而不是当前主链路的一部分。

## 2. 设计目标

本次重构目标如下：

1. 将 PPT content 生成主链路简化为：
   `已确认大纲 -> 直接生成 content_markdown -> 协议校验 -> html2ppt`
2. 完全删除 `slide_plan_builder.py`，避免复用旧逻辑和旧抽象。
3. 停止在 PPT 主流程中使用 `PptContentMarkdownAssembler`。
4. 使用中文 prompt，并保留最少但足够的软约束，让模型自行扩写和拆页。
5. 让 `content-protocol.md` 以“参考协议文档原文”的形式进入 prompt。
6. 保持对外工作流接口、artifact 类型、html2ppt 提交协议总体兼容。

## 3. 非目标

本次不做以下事项：

1. 不改造 `html2ppt` 服务的 API 协议，仍然提交 `content_markdown`。
2. 不引入真正的多文件上传或 LLM 附件接口；当前运行时仍通过文本 prompt 调用模型。
3. 不把“最终页数 >= 15”做成程序硬校验。
4. 不在本次引入新的媒体检索、自动配图或联网扩充。
5. 不在本次保留 `slide_plan` 作为运行时中间产物。
6. 不在本次继续启用 `PptContentReviewer` 的自动审查与再生闭环。

## 4. 新链路设计

### 4.1 新的主流程

在用户确认大纲后，PPT runtime 的 content 生成阶段改为：

1. 读取已确认 `PptOutline`
2. 读取 `preparation` 中必要上下文
3. 读取 `html2ppt/content-protocol.md` 原文
4. 构造中文 prompt
5. 调用 LLM，直接生成完整 `content_markdown`
6. 使用 `PptContentValidator` 校验协议结构
7. 校验通过后提交给 `Html2PptClient`

链路变为：

`PptOutline`
-> `PptContentMarkdownGenerator`
-> `PptContentValidator`
-> `Html2PptClient`

### 4.2 彻底删除旧中间层

以下旧中间层不再继续存在于主流程中：

1. `PptSlidePlanBuilder`
2. `PptContentMarkdownAssembler`
3. `slide_plan` 相关调试结构
4. 基于 `review_feedback` 的多轮内容再生成机制
5. one-shot / chapter fallback 内容扩写策略

其中：

- `slide_plan_builder.py` 直接删除，不保留兼容壳。
- `PptSlidePlan` 领域模型若仅被这条链路使用，也应在后续实现中评估是否一并下线；若还有其他引用，则先停止在 PPT 主流程中使用，再分步清理。

## 5. 新组件设计

### 5.1 新增 `PptContentMarkdownGenerator`

新增文件建议：

- `app/chat/workflows/ppt/content_markdown_generator.py`

职责仅有一项：

> 基于已确认大纲、必要上下文和 `content-protocol.md` 原文，直接生成完整 `content_markdown`。

建议接口：

```python
class PptContentMarkdownGenerator:
    def __init__(self, llm=None, protocol_path: str | None = None):
        ...

    def generate(self, *, outline, preparation) -> tuple[str, dict]:
        """
        返回:
        - content_markdown: str
        - debug: dict
        """
```

输出的 `debug` 用于 runtime trace，建议包含：

```python
{
    "prompt_preview": "...",
    "response_preview": "...",
    "protocol_path": "...",
    "protocol_loaded": True,
    "generation_mode": "direct_content_markdown"
}
```

### 5.2 Prompt 构成原则

Prompt 使用中文，结构建议如下：

1. 角色说明
2. 任务目标
3. 输入上下文
4. 协议参考文档原文
5. 输出要求
6. 软约束

其中最关键的变化是：

- 不再把 `content-protocol.md` 人工拆成几十条规则。
- 直接将其原文放入 prompt 的“参考协议文档”部分。
- 指示模型“必须严格遵守参考文档协议”，但由模型自己理解该协议。

### 5.3 Prompt 内容要求

Prompt 中必须显式写明：

1. 你现在要生成的是完整的 `content_markdown`，不是 JSON、不是 slide plan。
2. 需要覆盖封面、目录、内容页、结束页。
3. 需要严格依据“已确认大纲”生成，不得偏题。
4. 可以为了课堂讲解效果主动扩页、拆页、加入过渡页、总结页、举例页、对比页。
5. 页数 15 页以上是推荐目标，不是硬性指标。
6. 输出只能是最终 markdown，不要解释、不要代码块围栏、不要额外说明。

Prompt 中建议保留的软约束：

1. 面向中文教学场景，内容表达自然、清晰、可讲授。
2. 优先生成“能讲课”的内容，而不是“摘要式”的内容。
3. 如果大纲点数较少，可通过定义、机制、例子、误区、应用、总结等方式自然扩展。
4. 每页内容应适合 PPT 阅读，不要段落过长。
5. 应尽量让整套课件达到 15 页以上，但不要为了凑页数机械重复。

### 5.4 协议文档注入方式

当前系统不具备“文件附件上传给 LLM”的统一接口，因此实现上采用：

1. 运行时从磁盘读取 `D:\Edu_AI_1\Edu_AI\api\Edu_AI\html2ppt\content-protocol.md`
2. 将全文原样注入 prompt
3. 在 prompt 中标记其身份为“参考协议文档”

这是一种“文本形式的文档注入”，语义上等价于把文档交给模型参考，但不再由 Python 代码手工拆解文档规则。

## 6. Runtime 改造方案

### 6.1 `PptWorkflowRuntime` 的注入对象调整

当前默认装配位于：

- `app/chat/application/reply_service_v2.py`

需调整为：

1. 移除 `slide_plan_builder=PptSlidePlanBuilder(...)`
2. 移除 `content_markdown_assembler=PptContentMarkdownAssembler()`
3. 暂时移除 `content_reviewer=PptContentReviewer(...)`
4. 新增 `content_markdown_generator=PptContentMarkdownGenerator(...)`

### 6.2 `_submit_outline()` 简化

当前 `_submit_outline()` 包含多轮尝试、slide plan 汇总、review 闭环、assembler 组装等逻辑。

重构后应简化为：

1. 调用 generator 直接获取 `content_markdown`
2. 调用 validator 进行结构校验
3. 若失败，返回 workflow failed，并附带生成稿 artifact
4. 若成功，直接提交 html2ppt

删除的运行时行为包括：

1. `generation_attempts` 多轮再生
2. `review_feedback`
3. `slide_plan_summary`
4. `slide_plan_debug`
5. `content_reviewer.review(...)`

保留的运行时行为包括：

1. `ppt_outline` artifact
2. `ppt_content_markdown` artifact
3. html2ppt 请求元数据
4. trace/debug 日志

### 6.3 新调试字段

trace 中建议从：

- `ppt_slide_plan_debug`

迁移为：

- `ppt_content_generation_debug`

并保留：

1. `content_markdown_preview`
2. `content_markdown_length`
3. `validation`
4. `html2ppt request metadata`

这样可以避免新流程继续沿用旧字段名造成误导。

## 7. 校验策略

### 7.1 保留结构校验

`PptContentValidator` 应继续保留，作为主系统向 html2ppt 提交前的最后一道结构闸门。

### 7.2 校验器需要升级

当前 validator 仍带有 phase-1 限制，例如：

1. 只接受 `Lead/Toc/Bullets`
2. 禁止 `Media`
3. 将 block 类型限制为旧阶段的子集

这与新的“模型直接参考完整 `content-protocol.md` 输出内容”目标不一致。

因此 validator 需要升级为：

1. 支持 `content-protocol.md` 中定义的完整 block 集合
2. 允许封面、目录、内容页、结束页使用协议允许的组合
3. 重点校验结构合法性，而非内容风格

### 7.3 页数不做硬校验

代码层明确不增加如下硬性规则：

1. `slide_count >= 15`
2. 内容页最少多少页
3. 每章最少多少页

这些要求只体现在 prompt 的软引导中，避免系统因“页数未达标”机械拒绝一份本来结构正确、内容也可用的输出。

## 8. Reviewer 策略

### 8.1 当前阶段关闭 reviewer

`PptContentReviewer` 暂时退出主链路，原因如下：

1. 当前核心目标是先把生成链路从“复杂中间态”降到“直接生成协议稿”。
2. reviewer 会再次引入一层内容判断和多轮再生，让链路重新变复杂。
3. 在新 prompt 和新 validator 尚未稳定前，先保证“能稳定生成合格协议稿”优先。

### 8.2 reviewer 的后续定位

后续若恢复 reviewer，应作为“第二阶段优化”，并满足以下原则：

1. 不重新引入 `slide_plan`
2. reviewer 面向最终 `content_markdown` 工作
3. reviewer 的反馈是可选增强，而不是主链路强依赖

## 9. 失败处理

### 9.1 生成失败

若 LLM 不可用或返回空结果：

1. runtime 返回 workflow failed
2. message 明确提示“PPT 协议稿生成失败”
3. 不提交到 html2ppt

### 9.2 协议不合法

若模型返回结果未通过 validator：

1. runtime 返回 workflow failed
2. 将原始生成结果作为 `ppt_content_markdown` artifact 返回，便于调试
3. 不再自动进行多轮再生成

### 9.3 协议文档加载失败

若 `content-protocol.md` 读取失败：

1. 视为不可继续的系统错误
2. runtime 直接失败
3. trace 记录协议路径与异常信息

这里不建议在协议文档读取失败时退回旧逻辑，因为本次目标就是“彻底替换”，不是双轨并存。

## 10. 对现有代码文件的影响

### 10.1 删除

建议直接删除：

- `app/chat/workflows/ppt/slide_plan_builder.py`

### 10.2 停止在主流程中使用

建议从 PPT 主流程中移除：

- `app/chat/workflows/ppt/content_markdown_assembler.py`
- `app/chat/workflows/ppt/content_reviewer.py`

### 10.3 新增

建议新增：

- `app/chat/workflows/ppt/content_markdown_generator.py`

### 10.4 需要修改

建议修改：

- `app/chat/application/reply_service_v2.py`
- `app/chat/workflows/ppt/runtime.py`
- `app/chat/workflows/ppt/content_gate.py`
- `app/chat/workflows/ppt/content_validator.py`
- `tests/chat/test_reply_service_v2.py`
- `tests/chat/test_ppt_workflow_runtime.py`
- `tests/chat/test_ppt_workflow_runtime_debug.py`

### 10.5 需要删除或重写的测试

建议删除或改写：

- `tests/chat/test_ppt_slide_plan_builder.py`
- `tests/chat/test_ppt_slide_plan_builder_debug.py`
- `tests/chat/test_ppt_content_markdown_assembler.py`
- `tests/chat/test_ppt_content_reviewer.py`

并新增：

- `tests/chat/test_ppt_content_markdown_generator.py`

## 11. 测试策略

### 11.1 Generator 单测

需要覆盖：

1. prompt 使用中文主指令
2. prompt 中包含 outline 核心信息
3. prompt 中包含 `content-protocol.md` 原文
4. prompt 中包含“15 页以上”为软约束描述
5. 能从模型响应中提取最终 markdown
6. 能处理带代码块围栏的返回

### 11.2 Runtime 单测

需要覆盖：

1. 确认大纲后直接调用 generator，而非 slide plan builder
2. 生成的 markdown 通过 validator 后正常提交 html2ppt
3. markdown 校验失败时不提交 html2ppt
4. trace 中输出新的 `ppt_content_generation_debug`

### 11.3 装配单测

需要覆盖：

1. `reply_service_v2` 默认装配的是新的 generator
2. 不再注入 `slide_plan_builder`
3. 不再在主流程强依赖 `content_reviewer`

## 12. 风险与取舍

### 12.1 风险

1. 取消中间态后，模型输出自由度更高，初期可能出现更多协议格式波动。
2. 不再自动 review，意味着第一版质量控制主要依赖 prompt 与 validator。
3. validator 若升级不完整，可能误判模型输出。

### 12.2 取舍

本次明确优先选择：

1. 更短、更直接、更符合直觉的生成链路
2. 更少的代码中间态
3. 更符合中文教学场景的 prompt

而不是优先追求：

1. 复杂的中间结构控制
2. 自动再生与多轮审查
3. 高耦合的内容计划抽象

## 13. 最终方案结论

本次重构采用以下结论：

1. 完全删除 `slide_plan_builder.py`，不复用旧逻辑。
2. 用新的 `PptContentMarkdownGenerator` 直接生成最终 `content_markdown`。
3. Prompt 全部使用中文。
4. 将 `content-protocol.md` 原文直接注入 prompt，作为模型参考协议文档。
5. 以“自然扩页、目标 15 页以上”作为软约束，而非代码硬规则。
6. 暂时关闭 `PptContentReviewer`，将其留待后续优化阶段。
7. `PptContentValidator` 升级为完整协议校验器，作为主系统提交前唯一强结构闸门。

该方案的核心是：

> 不再让代码代替模型做 content 结构规划，而是让模型直接在完整协议约束下生成最终 content，再由代码负责校验与提交流程稳定性。
