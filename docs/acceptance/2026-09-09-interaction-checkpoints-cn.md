# 会话任务检查点与恢复隔离（2026-09-09）

## 问题与设计依据

旧报告修改稿被挂起后，仅因请求携带相同文档引用就恢复为当前修改任务，使新教案确认可能落入旧报告保存流程。前一轮清理预览和补充模型上下文并不足以消除这个入口。

参考官方实践：
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)：持久检查点、线程标识、指定中断恢复，以及恢复执行中的副作用幂等。
- [OpenAI Agents SDK RunState](https://openai.github.io/openai-agents-python/ref/run_state/) 与 [Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)：保存实际运行状态，围绕原有中断恢复。

本项目沿用现有 Harness 和业务持久层，实现这些机制，不新增框架依赖。用户意图、新建/修改/恢复等语义仍由模型判断，不增加关键词规则。

## 实现

- `interaction_state` 持久记录 foreground、各任务 ID、revision、状态和检查点版本；从结构化工具结果投影，不从聊天文本猜测状态。
- 新方案或新修改预览切换前台任务，原等待确认任务挂起。后台任务状态更新不夺取前台任务。
- 文档引用只表示可读取的材料，不具备恢复任务的权限。
- 挂起稿按 draft_id 保存集合。模型恢复必须明确给出 draft_id 和 revision；程序验证用户、会话、来源及源版本/哈希。恢复只重新展示修改稿并递增 revision，不能同时保存，旧按钮版本失效。
- 未激活修改稿即使模型输出 save 也不能保存；生成方案若不是前台任务也不能提交，须重新展示并等待后续确认。
- 已有方案提交版本检查与幂等键继续生效。同一用户会话的交互在服务入口串行执行，覆盖读取到提交状态的完整区间。
- 新资源交接后重新配置 Harness 的检索能力，避免带文档引用的请求与普通后续请求使用不同策略，导致确认时错误要求重新制作方案。

## 验证与边界

自动化覆盖挂起稿误保存、旧保存按钮、错误草稿 ID、陈旧版本、其他用户/会话检查点、任务切换、后台迟到通知、重复结果投影和挂起生成方案误提交。

同会话串行锁当前使用共享存储目录的文件锁，适用于本部署同一主机的多进程；跨主机部署需共享且支持锁的文件系统，或迁移到数据库/分布式锁。此修复约束任务执行边界，不声称模型永远不会产生语义误判。用户原有资源与挂起草稿未擅自删除或改写。

回归结果：271 项通过，3 条已有运行环境警告；包括 JSON 与 PostgreSQL 修改存储测试。证据见 [backend-tests.txt](evidence/2026-09-09-interaction-checkpoints/backend-tests.txt)。

端到端首次运行发现：引用交接后未配置 Harness 检索能力，第一次方案 policy 为 false/false，后续普通请求为 true/true，再携带引用确认时发生 `source_scope_changed_redraft_required`。修复共享能力配置后重新执行全流程，不将这次失败计为通过。

部署：确认当前主服务没有活跃任务后，重启 `edu-ai-backend-session.service`；`GET /health` 返回 `status=ok`、`knowledge_base_ready=true`。前端本轮无新增修改。


## 真实端到端结果

隔离测试账户与课程，使用实际 HTTP/SSE、Harness、模型服务、持久后台任务、资源读取 API 和 Chromium：

1. 预置一份尚未保存的旧报告修改稿（测试数据）。
2. 携带旧报告引用要求新建教案，模型交接到教案流程。
3. 暂停生成并询问教学评价，再要求改为 12 分钟，保持同一方案并提升版本。
4. 再次携带旧报告引用发送“可以”：约 18.2 秒收到后台任务事件，未保存旧稿、未重复制作方案。
5. 后台约 471 秒完成正文、两次修改和三轮质量审核，真实资源 `lesson_plan-c6855ff3967fc8b1` 类型为 `lesson_plan`，审核 pass。
6. Agent 查询完成状态并读取实际内容；源报告内容不变；Chromium 成功打开教案预览。

证据：[完整结果](evidence/2026-09-09-interaction-checkpoints/lesson_plan.json)、[页面截图](evidence/2026-09-09-interaction-checkpoints/lesson_plan-preview.png)。首轮含旧引用的大纲请求本次耗时约 97 秒，说明模型调用延迟仍会波动；本次状态修复不等于消除了所有生成延迟。

完整生成测试运行期间新增的挂起方案提交守卫与提交后方案/任务关联，由最终 271 项回归覆盖；未将较早启动的模型测试声称为覆盖这些随后新增的守卫。
