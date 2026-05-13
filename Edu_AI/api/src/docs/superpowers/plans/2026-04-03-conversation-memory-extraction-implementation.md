# 对话记忆抽取实施计划

**状态：** 执行中  
**日期：** 2026-04-03  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`  
**依赖文档：**
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-generation-context-design-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-conversation-memory-merge-spec-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-02-state-writeback-event-flow-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-03-status-card-builder-rules-cn.md`

## 1. 目标

为普通 `reply` 对话补齐最小可用的自动抽取链路，使每轮成功返回后都能增量维护：

- `conversation_summary.summary_text`
- `conversation_memory.current_topics`
- `conversation_memory.user_goals`
- `conversation_memory.confirmed_facts`
- `conversation_memory.teaching_issues`
- `conversation_memory.constraints`

本次目标不是做高质量语义摘要器，而是做一个稳定、可测试、可持续演进的 MVP 提取链。

## 2. 实施原则

- 优先保证卡片和 workflow 有结构化状态可读，而不是追求“完美理解”
- 抽取逻辑集中在一处，不散落到 `reply/report/route` 多条路径
- 先做确定性、低风险的启发式抽取
- merge 规则以“增量覆盖 + 去重 + 保守写入”为主
- 每一步先有测试，再接入持久化

## 3. 范围

### 3.1 本次要做

- 新增对话摘要与记忆抽取器
- 在 `write_v2_result` 流程中自动写回 summary / memory
- 保持 `reply` 与 `report` 路径统一受益
- 让状态卡片在普通多轮对话中不再长期为空

### 3.2 本次不做

- LLM 驱动的复杂抽取
- 高置信度知识图谱
- 完整 relevance ranking
- 所有字段的一次性铺满

## 4. 设计落点

建议新增：

- `app/chat/orchestrator/conversation_memory_extractor.py`

建议修改：

- `app/chat/persistence/conversation_store_adapter.py`
- `app/chat/application/route_chat_service.py`

## 5. MVP 抽取字段

### 5.1 `conversation_summary.summary_text`

来源：

- 当前轮 user question
- 当前轮 assistant answer
- 最近窗口消息

目标：

- 生成 1 句短摘要，优先描述“当前在讨论什么 / 正在做什么”

### 5.2 `conversation_memory.current_topics`

来源：

- user question 主体
- assistant answer 的高频主题线索

策略：

- 保留最近且高价值的 1 到 5 条

### 5.3 `conversation_memory.user_goals`

来源：

- question 中的动作意图
- workflow type

策略：

- 普通对话可抽“解释/分析/总结/生成报告”等目标

### 5.4 `conversation_memory.confirmed_facts`

来源：

- assistant answer 中明确陈述句
- 只保留短句，避免整段复制

### 5.5 `conversation_memory.teaching_issues`

来源：

- question / answer 中带有“问题/不足/困难/分心/参与度低”等问题信号

### 5.6 `conversation_memory.constraints`

来源：

- question 中出现的 audience / tone / length / grade / subject 显式约束
- workflow request 中的 course/doc 相关上下文

## 6. 执行步骤

### 步骤 1. 补抽取器测试

新增：

- 抽取器单元测试
- 持久化写回测试

验收：

- 普通对话能抽出 topic / goal / summary
- 教学问题类对话能抽出 issue / constraints

### 步骤 2. 实现抽取器

实现：

- 轻量摘要构建
- topic / goal / issue / fact / constraint 提取
- merge 与去重

验收：

- 新增测试通过

### 步骤 3. 接入持久化链路

实现：

- `ConversationStoreAdapter.write_v2_result` 自动写回
- `RouteChatService._persist_new_result` 保持一致

验收：

- `reply` 多轮对话后状态不为空
- 状态卡片能读到 summary / memory

### 步骤 4. 回归验证

运行：

- focused persistence / context / status-card suite
- broader chat v2 regression

## 7. 风险与控制

### 7.1 抽取质量一般

控制：

- 先保证“有稳定结构化输出”
- 保持抽取器可替换，后续再升级到更强策略

### 7.2 状态污染

控制：

- 采用保守 merge
- 只写入短句、可解释字段
- 不把整段 assistant 内容直接存入 memory

### 7.3 多路径分叉

控制：

- 尽量以 `ConversationStoreAdapter` 为主入口
- `RouteChatService` 只做兼容补齐

## 8. 验收标准

本次完成后，应满足：

1. 普通多轮对话后，`conversation_summary` 不为空
2. 普通多轮对话后，`conversation_memory.current_topics` 与 `user_goals` 至少能形成最小值
3. 状态卡片在普通 chat 场景不再长期停留在“尚未形成明确主题”
4. report-first 既有链路测试不回退
