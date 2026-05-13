# Phase 5.5 收官清单

## 0) 主路策略更新（已完成）

已执行“强制主路化代码收口”：
- 当 `ENABLE_UNIVERSAL_REPORT_ENGINE=1` 且引擎可用时，所有报告请求统一走 Universal Report Engine。
- `UNIVERSAL_REPORT_ROLLOUT_PERCENT` 与 `UNIVERSAL_REPORT_ALLOWLIST` 不再参与报告路由决策（仅保留兼容字段与观测展示）。

---

## 1) 运行态观测入口（已完成）

已在 `ChatService` 增加运行态统计方法：

- `get_universal_report_runtime_stats()`

返回结构：
- `enabled`：是否启用新引擎
- `rollout_percent`：灰度百分比
- `allowlist_size`：白名单数量
- `metrics`：运行计数（selected/skipped/awaiting_human/replanning/finished/tool_failure）

用途：
- 供内部调试接口或管理面板读取
- 发布阶段用于快速判断灰度健康度

---

## 2) 旧 report 固定链路可删除清单（先列后删）

> 当前先做清单，不立即删除。待新链路 100% 稳定后再执行清理。

### A. 旧节点实现（已迁移但仍可能有残余依赖）

- `service.py` 中所有 legacy report 路由判定分支（如 `response_type == outline/generate/ask` 的旧更新逻辑）
- 与旧 report 子图强耦合的状态字段写入逻辑：
  - `report_missing`
  - `report_ask_counts`
  - `report_outline_pending`
  - `soft_params_confirmed`
  - `report_auto_fill`

### B. 旧 report 状态持久化路径

- `conversation_storage.update_state(... report_state=...)` 中仅服务旧流水线的字段
- 旧链路专用 `last_clarification_reason/same_reason_clarify_count` 对 report 的复用部分

### C. 旧图装配与节点挂载

- `service._build_graph()` 中旧 `report_agent` 固定节点链装配路径
- 与 old report flow 绑定的 `SupervisorAgent` report 路由分支（可保留统一节点名，但底层切新引擎）

---

## 3) 删除前硬门槛（必须全满足）

1. 新引擎灰度 100% 连续稳定
2. `finished/selected` 达到目标阈值（由业务设定）
3. `tool_failure` 和 `replanning` 在可控阈值内
4. 挂起恢复无状态丢失
5. 完整回归通过（报告主路径 + chat/research 不回退）

---

## 4) 推荐下线顺序

1. **第一批**：删除旧 report 的冗余状态写入（保留字段兼容）
2. **第二批**：删除旧 report 子图节点实现与挂载
3. **第三批**：收敛 `service.py` 到“路由 + 流式 + 会话状态”
4. **第四批**：清理无用常量、prompt、helper、文档

---

## 5) 回滚保护

在旧链路真正删除前，保持：
- `ENABLE_UNIVERSAL_REPORT_ENGINE` 开关可立即回退
- `UNIVERSAL_REPORT_ROLLOUT_PERCENT` 可快速降到 0
- 白名单机制可用于紧急隔离验证
