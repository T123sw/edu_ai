# Task 8 报告：全量回归、迁移演练与发布签字

## 结论

最终发布验收为 **不通过**。这不是学习闭环自动化失败：真实双账号闭环、确定性 Agent、前端全量门禁和旧库副本迁移均已通过。阻断来自真实外部模型人工验收缺失、课程/聊天完整回归的 3 个 LLM 配置相关失败，以及重名资源与单课程摘要局部降级页面证据缺失。

## 实测结果

- 后端学习与 Agent 目标集：97 passed，5 个既有 FastAPI deprecation warnings。
- 课程、权限与聊天完整集：1,013 passed，3 failed。失败为 `test_blog_generation_adapter_v2.py` 两项和 `test_route_chat_service_report_wiring.py` 一项；当前无模型凭据时 `get_fallback_llm()` 返回 `None`。用假密钥会触发其他用例的真实网络路径，因此没有用该方式掩盖结果。
- 前端全量：289 passed，0 failed。
- lint：0 errors；存在既有 warnings。
- build：成功；存在既有 dynamic-import/chunk-size warnings。
- Playwright：1 passed，retries=0；用例主体 46.8s。
- 旧库迁移：独立临时旧 schema 的任务数 1→1、事件数 1→1，旧 `completed` 映射 `self_reported`，连续打开两次结果一致；`test_learning_store.py` 5 passed。
- 本轮额外修正学习上下文提示字段名：`completed_basis` → `completion_basis`，目标测试 10 passed。

## 发布边界

- 确定性网关证明页面、学习工具、结构化事实、角色投影和 trace 可用，不证明真实外部模型的自然语言稳定性或供应商链路可用。
- Task 7 早期隔离失误产生的外部 8001 测试任务 `lt_9dbeb1159aec4bc0ad0ee435f8d04af4` 保持未删除；正式 API 无删除能力，未直接修改真实学习库。
- 最终验收证据和阻断复现记录见 `Edu_AI/docs/acceptance/2026-08-10-teacher-student-interaction-loop-phase2-acceptance.md`。
