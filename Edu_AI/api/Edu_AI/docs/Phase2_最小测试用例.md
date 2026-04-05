# Phase 2 最小测试用例

## 用例 1：缺少 core_topic -> ask_human 挂起

输入：
- `report_slots = {}`
- `report_outline = []`
- `report_content = ""`

预期：
1. Planner 生成 `ask_human_for_clarification` step
2. Executor 返回 `need_human=true`
3. Analyzer 状态为 `awaiting_human`
4. 子图结束等待用户反馈

---

## 用例 2：有 topic/focus，无 outline -> 提纲挂起

输入：
- `report_slots.core_topic` 非空
- `report_slots.focus_area` 非空
- `report_outline = []`

预期：
1. Planner 生成 `submit_outline_for_review` step
2. Executor 写入 `report_outline`
3. Analyzer 返回 `awaiting_human`

---

## 用例 3：有 outline，无 content -> 正文生成完成

输入：
- `report_slots` 完整
- `report_outline` 非空
- `report_content = ""`

预期：
1. Planner 生成 `generate_long_report_content` step
2. Executor 写入 `report_content`
3. Analyzer 返回 `finished`

---

## 用例 4：未知工具 -> 重规划

输入：
- 手动注入计划 step：`tool_name=unknown_tool`

预期：
1. Executor 返回 `ok=false`
2. 状态置为 `replanning`
3. controller_edge 路由回 planner
