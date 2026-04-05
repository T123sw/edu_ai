# 状态卡片 MVP 实施计划

**状态：** 执行中  
**日期：** 2026-04-03  
**范围：** `D:\Edu_AI_1\Edu_AI\api\Edu_AI\app\chat`  
**依赖文档：**
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-03-status-card-field-mapping-mvp-cn.md`
- `D:\Edu_AI_1\Edu_AI\api\Edu_AI\docs\superpowers\specs\2026-04-03-status-card-builder-rules-cn.md`

## 1. 目标

在现有 chat v2 链路中增加一个可选的 `status_card` 响应字段，使对话页能够在每次 `reply/report` 成功返回时，同步拿到当前会话状态卡片。

MVP 本次只做后端派生与响应接入，不做独立只读接口，不做前端组件实现。

## 2. 实施原则

- 不新增 `status_card` 持久化实体
- 状态卡片由现有 `snapshot + workflow + capability` 运行时派生
- `StatusCardBuilder` 保持轻量、可测试
- 文案映射单独抽出，不散落在 workflow/runtime/service 中
- 每个实现步骤都先补测试，再通过局部回归推进

## 3. 范围

### 3.1 本次要做

- 定义 `StatusCardVM` 契约
- 新增 `StatusCardLabelMapper`
- 新增 `StatusCardBuilder`
- 在 `ChatResponseV2` 中增加 `status_card`
- 在 `build_v2_success_response` 中支持 `status_card`
- 在 `ReportServiceV2` / `ReplyServiceV2` 返回结果中带上 `status_card`
- 增加对应单元测试与服务层集成测试

### 3.2 本次不做

- `GET /conversations/{id}/status-card`
- artifact / course / doc title 的完整元数据解析
- 前端展示实现
- conversation summary / memory 自动刷新链路

## 4. 设计落点

建议新增以下文件：

- `app/chat/domain/status_card.py`
- `app/chat/orchestrator/status_card_label_mapper.py`
- `app/chat/orchestrator/status_card_builder.py`

建议修改以下文件：

- `app/chat/api/schemas_v2.py`
- `app/chat/application/response_builder_v2.py`
- `app/chat/application/report_service_v2.py`
- `app/chat/application/reply_service_v2.py`

## 5. 字段策略

MVP 先返回以下字段：

- `mode`
- `status_label`
- `workflow_label`
- `topics`
- `goal`
- `issues`
- `confirmed_facts`
- `source_labels`
- `active_artifact_label`
- `waiting_label`
- `suggested_actions`
- `audience`
- `tone`
- `length`
- `grade_level`
- `subject`
- `allow_rag`
- `allow_web`
- `summary_hint`

## 6. 构建规则

### 6.1 主要输入

- `ConversationSnapshot`
- `workflow` 响应对象
- `request.capability`

### 6.2 主要规则

- `mode` 由 workflow/active context 推断
- `status_label` / `workflow_label` / `waiting_label` / `suggested_actions` 走统一 mapper
- `topics / goal / issues / confirmed_facts` 主要来自 `conversation_memory`
- `source_labels` 至少保留 `当前会话`
- `summary_hint` 只在结构化信息不足时返回

## 7. 执行步骤

### 步骤 1. 定义契约与 builder 测试

新增：

- `StatusCardVM` 模型
- `StatusCardBuilder` 单元测试
- `StatusCardLabelMapper` 单元测试

验收：

- builder 能处理 workflow 场景
- builder 能处理低信息 chat 场景

### 步骤 2. 实现 builder 与 mapper

实现：

- workflow / active context 到卡片字段的派生
- 文案映射与空状态回退

验收：

- 新增 builder 测试通过
- 相关 domain/schema 测试不回退

### 步骤 3. 接入响应契约

实现：

- `ChatResponseV2` 增加 `status_card`
- `build_v2_success_response` 支持透传

验收：

- schema / response builder 测试通过

### 步骤 4. 接入服务返回链路

实现：

- `ReportServiceV2` 在 runtime 结果上补 `status_card`
- `ReplyServiceV2` 在 orchestrator 结果上补 `status_card`

验收：

- `report` 与 `reply` 服务测试通过
- 状态卡片能随回复一起返回

### 步骤 5. 回归验证

运行：

- focused suite
- broader chat v2 regression

## 8. 风险与控制

### 8.1 workflow 文案分叉风险

控制：

- 所有卡片文案统一进 `StatusCardLabelMapper`

### 8.2 状态来源不全导致卡片过空

控制：

- 提供低信息回退
- `source_labels` 至少显示 `当前会话`

### 8.3 builder 变重

控制：

- MVP 不做外部 store 查询
- 仅使用 snapshot / workflow / capability

## 9. 验收标准

本次实施完成后，应满足：

1. `reply/report` 成功响应可选返回 `status_card`
2. workflow 场景下卡片能显示当前状态、主题、来源、等待事项
3. 冷启动 chat 场景下卡片不会空崩，而是优雅回退
4. 现有 report-first 上下文链路测试不回退
