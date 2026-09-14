# 知识点标准资源安全重生成与 Agent Skills 设计

日期：2026-09-10  
状态：已确认，进入实施

## 1. 背景

课程知识页按叶子知识点维护 AI 课堂、学习指南和练习三个标准资源槽位。现有实现使用稳定 `material_id` 和材料版本保存新内容，旧批准版在新版待审期间仍可供学生使用；但批次提交会无差别重做三个槽位，审核请求没有绑定教师实际预览的版本，批次也没有记录最终材料版本。并发生成时，较晚完成的旧任务可能覆盖更新请求的候选状态。

标准资源生成同时仍由固定参数驱动。`entrypoint=agent` 只选择生成适配器，不代表 Agent 已读取资源 Skill、形成跨资源教学蓝图或执行统一独立审阅。

## 2. 目标

1. 已有资源默认保留，只补齐缺失槽位；教师可明确选择修订退回项或重新生成全部选中类型。
2. 审核必须绑定 `material_id + version + content_hash`，不得批准未预览版本。
3. 同一课程、知识点和标准类型同一时刻最多有一个活跃生成项；重复请求幂等返回同一批次。
4. 批次保存知识图快照标识、生成模式、最终材料版本和内容哈希，可恢复、可审计。
5. 三类资源共享一个教学蓝图，并使用版本化 Skill 约束生成和独立质量审阅。
6. 学生始终只读取已批准版本，不暴露任务 ID、错误详情或待审内容。

## 3. 非目标

- Agent 不决定权限、材料 ID、版本号、幂等、审核或发布。
- 不自动批准 AI 生成内容。
- 不改变一个叶子知识点固定拥有三个标准资源槽位的产品模型。
- 不删除历史材料版本和已发布学习任务快照。

## 4. 重生成语义

批次请求增加 `mode` 和 `standard_kinds`：

- `fill_missing`：默认。只生成不存在的槽位。
- `repair_rejected`：生成缺失槽位，并基于最近退回原因修订已退回槽位。
- `regenerate_all`：为选中的类型创建候选新版；已批准版继续对学生可见。

待审核或生成中的槽位不会被任何模式静默覆盖。服务端预检返回每个槽位的 `generate / repair / regenerate / keep / blocked` 动作及原因。前端先展示权威预检摘要，再由教师确认创建批次。

## 5. 数据与并发模型

### 5.1 批次

`standard_resource_batches` 增加：

- `idempotency_key`：课程内唯一；客户端一次确认操作使用稳定请求 ID。
- `graph_version`：优先使用知识图显式版本，否则使用规范化内容哈希。
- `generation_mode`：本批次的已有资源策略。

### 5.2 批次项

`standard_resource_batch_items` 增加：

- `base_version`：提交时观察到的材料版本。
- `material_version`、`content_hash`：任务成功后绑定的真实结果。
- `active_slot_key`：活跃状态下为 `course:leaf:kind`，数据库唯一；终态后清空。
- `action`：`generate / repair / regenerate`。
- `generation_context`：知识点路径、共享教学蓝图、旧版本摘要和退回意见。

任务完成必须返回材料版本和内容哈希。批次项只在结果材料 ID、批次 ID和来源 Job 全部匹配时成功。被替代的旧任务不得更新当前待审候选。

## 6. 精确审核

审核请求必须携带：

```json
{
  "decision": "approved",
  "expected_version": 3,
  "expected_content_hash": "sha256...",
  "reason": ""
}
```

事务内再次核对当前候选版本和哈希。任一不一致返回 `409 VERSION_CHANGED`。批量审核使用批次项绑定的 `material_version/content_hash`，不按 `material_id` 猜测当前版本。

## 7. Agent 与 Skills 边界

新增 `edu-standard-resource-bundle` Skill。每个叶子知识点形成共享 `LearningResourceBundleSpec`：

- 课程与知识点路径；
- 受众、先修和可观察目标；
- 核心概念、适用边界、例子和常见误区；
- 课堂—指南—练习的覆盖映射；
- 来源范围、旧版本和退回反馈。

三个生成器读取同一蓝图及各自的资源契约。标准资源统一设置 `review_policy=required`，成品必须经过独立审阅并与最终内容哈希绑定。Skill 可以决定内容组织、题量、场景和表达，但不能调用发布或审核事务。

首版蓝图由可信课程元数据、知识点路径和明确的教学覆盖规则构建；模型在生成—审阅—修订循环中完成具体内容决策。后续可把蓝图构建本身迁入独立耐久 Agent 任务，而不改变本设计的数据和工具契约。

## 8. API

- `POST /api/courses/{course_id}/standard-resource-batches/preview`
  - 输入：`leaf_ids`、`standard_kinds`、`mode`
  - 输出：知识图版本、动作明细和计数，不创建任务。
- `POST /api/courses/{course_id}/standard-resource-batches`
  - 增加上述字段、`idempotency_key` 和预检返回的 `graph_version`。
- `GET /api/courses/{course_id}/standard-resource-batches?limit=...`
  - 仅课程管理者读取最近批次，用于刷新恢复。
- 审核请求增加期望版本和内容哈希。

旧客户端只传 `leaf_ids` 时按 `fill_missing + 全部三类` 处理，但审核接口不保留不安全的无版本兼容行为。

## 9. 前端交互

生成面板增加：

1. 全局资源类型复选框；
2. 已有资源策略单选项；
3. “检查生成内容”按钮；
4. 服务端预检摘要与明确确认按钮；
5. 最近批次恢复；
6. 审核提交精确版本与哈希，版本变化时重新加载。

`fill_missing` 下没有可执行项时不创建空批次，并提示资源已齐全。

## 10. 完成标准

只有精确审核、批次幂等、活跃槽位互斥、已有资源预检、批次版本绑定、Skill 质量门、刷新恢复和权限投影均有自动化证据，才可标记完成。
