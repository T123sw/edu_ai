# Task 8 报告：全量回归、迁移演练与发布签字

## 结论

最终发布验收为 **通过**。真实双账号闭环、确定性 Agent、真实千问双端 Agent、前后端全量门禁、旧库副本迁移、重名资源选择和单课程摘要局部降级均有可复验证据。

## 实测结果

- 后端学习与 Agent 目标集：97 passed，5 个既有 FastAPI deprecation warnings。
- 初次课程、权限与聊天完整集因隔离 worktree 未包含被 Git 忽略的 `.env`，得到 1,013 passed、3 failed。确认主工作区千问配置存在后，仅在测试进程内只读加载该 `.env`，`get_fallback_llm()` 成功构造 `qwen3.5-plus`；4 个相关目标测试通过，完整集合最终为 1,016 passed、2 warnings。密钥未复制、未打印、未写入证据。
- 前端全量：289 passed，0 failed。
- lint：0 errors；存在既有 warnings。
- build：成功；存在既有 dynamic-import/chunk-size warnings。
- Playwright：1 passed，retries=0；用例主体 46.8s。
- 最终 HEAD `e09e7a4` 再次执行 Playwright：1 passed，总命令 1.7m、用例约 1.2m、workers=1、retries=0；证据 worker 为 `worker-0-1786386355084`，15173/18001 均无监听残留。
- 最终学习/Agent 目标集：131 passed；完整课程/聊天集：1,022 passed；前端：289 passed；lint 0 errors；build 成功。
- 真实千问：`qwen3.5-plus` 双端 1 passed（41.7s），教师和学生分别使用课程汇总与本人学习工具；证据 worker `worker-0-1786419331685`。
- 页面边界：重名资源与单课程摘要局部降级 1 passed；最终与主闭环合并复跑 2 passed（1.1m），证据 worker `worker-0-1786419732274`。
- 真实模型 RED→GREEN 修复：否定的“不要查询后台生成任务”不再制造跨领域歧义；默认 reply service 接入持久化学习上下文；终端 report_result 保留经验证的角色隔离学习事实并生成可读回答。
- 旧库迁移：独立临时旧 schema 的任务数 1→1、事件数 1→1，旧 `completed` 映射 `self_reported`，连续打开两次结果一致；`test_learning_store.py` 5 passed。
- 本轮额外修正学习上下文提示字段名：`completed_basis` → `completion_basis`，目标测试 10 passed。

## 发布边界

- 确定性网关提供稳定回归，真实千问门禁证明当前供应商链路和自然语言结果可用；外部服务未来仍需常规可用性监控。
- Task 7 早期隔离失误产生的外部 8001 测试任务 `lt_9dbeb1159aec4bc0ad0ee435f8d04af4` 保持未删除；正式 API 无删除能力，未直接修改真实学习库。
- 最终验收证据和阻断复现记录见 `Edu_AI/docs/acceptance/2026-08-10-teacher-student-interaction-loop-phase2-acceptance.md`。
