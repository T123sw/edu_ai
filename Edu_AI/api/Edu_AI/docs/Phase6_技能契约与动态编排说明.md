# Phase 6：技能契约化、动态工具编排、去硬编码兜底（实施说明）

## 1. 实施目标

本阶段完成三件事：
1. **去硬编码兜底**：兜底计划不再固定写死字段顺序，改为读取 Skill 中的 `REPORT_SLOT_SCHEMA.required_slots`。
2. **动态工具编排**：引擎不再内嵌工具函数映射，改为注入 `tool_registry`（工具名 -> callable + metadata）。
3. **Skill 契约化校验**：从 Skill 文本中解析契约核心（当前实现：`REPORT_SLOT_SCHEMA`），用于规划与兜底逻辑一致性。

---

## 2. 代码变更点

## 2.1 `app/chat/tools/agent_tools.py`
新增：
- `ToolCallable`
- `ToolRegistry`
- `get_default_tool_registry()`

作用：
- 统一输出默认工具注册表
- 每个工具包含：
  - `callable`
  - `signature`
  - `requires_human`

---

## 2.2 `app/chat/agents/universal_report_engine.py`

### A) 契约提取
新增 `_extract_required_slots_from_skill(skill_prompt)`：
- 从 Skill 的 `### REPORT_SLOT_SCHEMA` 代码块提取 JSON
- 获取 `required_slots`
- 解析失败时回退到 `['core_topic','focus_area']`

### B) 通用兜底
`_fallback_plan(...)` 改为：
- 基于 `required_slots` 动态决定缺失追问
- 基于工具注册表判断可用能力（如没有 `submit_outline_for_review` 就不规划该步）

### C) 动态工具路由
`executor_node(...)` 改为读取 `tool_registry`：
- `tool_name` -> `tool_meta.callable`
- 不可调用/不存在时统一返回 `unknown_tool/tool_not_callable`

### D) 图构建注入
`build_universal_report_graph(...)` 支持 `tool_registry` 参数：
- planner/executor 均使用同一个注册表

---

## 2.3 `app/chat/service.py`

在构建新引擎时注入：
- `tool_registry=get_default_tool_registry()`

实现了“入口层动态注入工具能力，运行层按 registry 编排”。

---

## 3. 当前契约能力边界

已实现：
- `REPORT_SLOT_SCHEMA.required_slots` 解析与生效
- 工具注册表化与动态执行

尚可继续增强（后续可选）：
- 校验 Skill 必备 section 完整度（EXTRACTOR/OUTLINE/PATCH/CHAPTER）
- schema 字段类型校验并输出告警
- Skill 版本/能力矩阵校验（如要求工具在 registry 中必须存在）

---

## 4. 对报告生成能力的意义

1. Skill 可以直接控制“必填槽位”策略，不再需要改代码。
2. 工具能力可以按环境替换（如切换 web_search 实现），无需改引擎逻辑。
3. 报告主流程从“固定逻辑”进一步走向“契约驱动”。

---

## 5. 验收建议

1. 修改 Skill 的 `required_slots`（例如增加 `depth_level`），确认 Planner/Fallback 会追问该字段。
2. 从 registry 临时移除某工具，确认 Planner/Fallback 不再规划该工具，Executor 对未知工具能安全失败。
3. 主链路仍可完成：追问 -> 提纲挂起 -> 恢复 -> 正文生成。