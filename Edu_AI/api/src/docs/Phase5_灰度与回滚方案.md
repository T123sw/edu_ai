# Phase 5 灰度与回滚方案

## 1. 目标

将 Universal Report Engine 由“可用”推进到“可灰度上线、可监控、可回滚”。

本阶段不要求立刻删除旧链路，要求先完成：
1. 可控灰度（百分比 + 白名单）
2. 基础指标可观测
3. 一键回滚能力

---

## 2. 灰度配置

通过环境变量控制：

- `ENABLE_UNIVERSAL_REPORT_ENGINE`
  - `1/true/yes` 开启新引擎能力
  - 关闭则始终走旧链路

- `UNIVERSAL_REPORT_ROLLOUT_PERCENT`
  - `0-100`，按会话/用户稳定分桶
  - 例：`10` 表示约 10% 报告请求进入新引擎

- `UNIVERSAL_REPORT_ALLOWLIST`
  - 逗号分隔用户ID，白名单用户强制走新引擎
  - 例：`teacher_001,teacher_002`

路由策略：
1. 若是报告恢复场景（`report_state.awaiting=true`）=> 强制继续新引擎
2. owner 在 allowlist => 走新引擎
3. 否则按分桶 <= rollout_percent 决定

---

## 3. 指标与观测

`ChatService` 维护轻量计数器：

- `selected`：新引擎被选中次数
- `skipped`：报告请求中被旧链路接管次数
- `awaiting_human`：挂起次数
- `replanning`：重规划次数
- `finished`：完成次数
- `tool_failure`：工具失败次数（有 error 即计）

指标会在响应 `meta` 中透出：
- `meta.rollout`
- `meta.universal_report_metrics`

---

## 4. 发布步骤（建议）

### Step 1：内测
- `ENABLE_UNIVERSAL_REPORT_ENGINE=1`
- `UNIVERSAL_REPORT_ROLLOUT_PERCENT=0`
- 配置 `UNIVERSAL_REPORT_ALLOWLIST` 为内测用户

验收：
- 白名单用户报告链路完整可跑
- 非白名单不受影响

### Step 2：小流量
- `UNIVERSAL_REPORT_ROLLOUT_PERCENT=5~10`

验收：
- `finished/(selected)` 达到可接受阈值
- `tool_failure` 与 `replanning` 在可控范围

### Step 3：逐步放量
- 20% -> 50% -> 100%
- 每一档至少观察一个稳定周期

验收：
- 挂起恢复稳定
- 回归无明显退化

---

## 5. 回滚方案

### 快速回滚（秒级）
设置：
- `ENABLE_UNIVERSAL_REPORT_ENGINE=0`

效果：
- 新请求全部回到旧链路
- 已持久化状态不丢失

### 温和回滚（保留内测）
设置：
- `UNIVERSAL_REPORT_ROLLOUT_PERCENT=0`
- 清空或保留极小 allowlist

效果：
- 仅白名单继续验证
- 大盘恢复旧链路

---

## 6. 旧链路下线条件

仅在以下条件都满足时考虑下线旧 report 固定链路：
1. 灰度 100% 稳定运行一段周期
2. 完成率稳定，失败率低
3. 挂起恢复未出现数据丢失
4. 关键场景回归通过

下线前仍需保留可恢复分支。