# LLM Enhancement Provider 第一阶段实施计划

日期：2026-04-03

## 目标

在不替换当前规则抽取主链的前提下，引入第一版真实可用的 `LLM enhancement provider`，仅增强以下字段：

- `summary_text`
- `teaching_issues`
- `student_signals`
- `evidence_points`

增强结果必须继续经过 `LLMEnhancementRouter -> ExtractionGuard`，不能直接写入会话状态。

## 范围

### 包含

1. 新增 `LLMEnhancementProvider`
2. 为 provider 增加 prompt 构建与 JSON 解析
3. 为 `LLMEnhancementRouter` 增加异常回退
4. 增加 feature flag，默认关闭 LLM enhancement
5. 在默认 route service factory 中接入可开关的真实 provider
6. 增加 focused tests 与相关回归

### 不包含

1. 不增强 `confirmed_facts`
2. 不增强 `active_context / workflow_state / capability_policy`
3. 不做全量每轮触发
4. 不引入新的前端显示改动

## 实施步骤

### Task 1. 固定 provider 行为测试

新增 focused tests：

- `tests/chat/test_llm_enhancement_provider.py`
- 扩充 `tests/chat/test_llm_enhancement_router.py`
- 更新 `tests/chat/test_route_feature_flags.py`
- 更新 `tests/chat/test_route_service_factory.py`

重点覆盖：

- provider 能把模型 JSON 输出转成 candidates
- provider 只产出允许增强的字段
- provider 遇到无效 JSON 时返回空候选
- router 遇到 enhancer 异常时回退到 rule patch
- feature flag 默认关闭，显式开启可注入 provider

### Task 2. 实现 provider

新增：

- `app/chat/orchestrator/llm_enhancement_provider.py`

实现要点：

- 复用现有 `ChatModelGateway`
- 输入为 `trigger / existing_state / rule_patch / context`
- 输出为 `list[ExtractionCandidate]`
- 使用严格 JSON 响应格式
- 仅生成 `summary_text / teaching_issues / student_signals / evidence_points`

### Task 3. 接入默认工厂

修改：

- `app/chat/application/route_feature_flags.py`
- `app/chat/application/route_service_factory.py`
- `app/chat/application/route_chat_service.py`

实现要点：

- 新增 `CHAT_USE_LLM_ENHANCEMENT`
- 默认关闭
- 开启时由 service factory 构造真实 provider，并挂入 `ConversationStoreAdapter`
- 保持未开启时行为完全不变

### Task 4. 验证

先跑 focused tests，再跑相关 regression：

- `test_llm_enhancement_provider.py`
- `test_llm_enhancement_router.py`
- `test_route_feature_flags.py`
- `test_route_service_factory.py`
- `test_conversation_memory_phase2*.py`
- `test_route_chat_service.py`

最后跑一轮更宽的 `tests/chat` 回归。

## 验收标准

1. 默认配置下，现有规则抽取路径无行为变化
2. 开启 flag 后，provider 能生成候选增强并通过 guard 合并
3. provider 失败不会中断回复主链
4. 所有 focused tests 与 chat regression 通过
