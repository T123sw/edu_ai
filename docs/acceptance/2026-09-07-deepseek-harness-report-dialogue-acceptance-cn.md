# DeepSeek Harness 普通对话与报告首版验收

日期：2026-09-07。结论：首版代码接入与隔离验证通过；未切换运行中的服务，不代表全系统迁移或生产验收完成。

实现与启用方式见[接入说明](../architecture/deepseek-harness-pilot-integration-cn.md)。

## 真实五轮验证

使用 Python SDK `0.1.2rc1`、真实 dsh 运行时和模型；正文使用现有 GenerationCommandService、durable executor、GenerationTaskHandler 及课程资料存储。用户和课程均为验证专用标识，最终有效验证的数据仅保存在指定临时目录。

| 轮次 | 请求 | 实际结果 |
| --- | --- | --- |
| 1 | 一句话解释递归终止条件，不生成资料 | 普通回答，无业务工具调用；2.44 秒 |
| 2 | 回忆上一条问题 | 正确提及递归；新建 runtime 后从持久化上下文恢复；3.46 秒 |
| 3 | 只生成三章报告大纲 | 原生加载 edu-report；首次模型 JSON 无效，未保存无效大纲，第二次成功；19.86 秒 |
| 4 | 确认大纲并继续 | 调用 submit_report，创建一个规范 job，返回 submitted；6.99 秒 |
| 后台 | 执行已有报告任务服务 | 真实正文生成约 33.74 秒；任务 succeeded，报告保存成功 |
| 5 | 读取并检查报告 | query_report_job 返回已保存产物，基础结构检查通过；6.55 秒 |

最终报告 1,685 个字符；读取内容与保存内容完全一致。证据：[机器可读验证结果](evidence/2026-09-07-deepseek-harness/live-verification.json)、[生成的报告样例](evidence/2026-09-07-deepseek-harness/report.md)。耗时来自单次验证，不能当作性能基准。

原生事件中出现 `skill`、`mcp__edu__draft_report_outline`、`mcp__edu__submit_report`、`mcp__edu__query_report_job`，证明实际由 dsh 选择 Skill 并调用工具，而非脚本直接代替模型执行预设流程。脚本只发送五轮用户请求，并在提交后驱动已有后台 worker。

## 自动化验证

运行 `python scripts/test-deepseek-harness.py`。覆盖范围包括：

- 未确认拒绝提交、模型伪造 approved 被拒绝、修改版本后重新确认。
- 用户／课程／知识点隔离，同会话并发锁。
- 检索开关、失败结果、显式证据引用与来源范围变化。
- 无效模型大纲不保存，同参数可重新执行；入队失败不虚报提交成功。
- 只能读取本会话且归属正确的任务，产物结构验证失败不作为完成交付。
- 上下文恢复、成功响应重放、reasoning delta 过滤、超时关闭 SDK。
- 同步／流式总入口和报告 action_hint 路由，HTTP 响应字段与报告入口适配。
- 现有 V2 回复、schema、SSE 和课程范围相关回归。

最终结果：**71 passed，2 warnings，16.39 秒**。两个 warning 为 pytest 插件导入提示和现有 FastAPI on_event 弃用提示。测试使用隔离文件存储并阻止 dotenv 被导入模块覆盖。

## 发现并纠正的验证环境问题

首次扩展测试及第一次 live smoke 中，旧 RAG 模块的 `load_dotenv(override=True)` 覆盖了临时存储模式。五项课程样例测试出现数据混用／路径断言失败；第一次 smoke 的专用 job 和报告进入了当前配置数据库，因此该次运行不能作为“隔离存储通过”的证据。

已经按准确 job_id、material_id、专用 owner/course 及 source_job_id 核对并删除了第一次 smoke 的 job、报告及关联数据库记录，随后验证其不存在。未批量删除无法确定归属的其他课程测试样例；首次扩展测试对这些共享样例的写入不作为用户业务数据迁移的一部分。

验证脚本现已禁止进程内重复加载 dotenv，固定存储模式，并检查实际文件。上述最终 live 结果来自修正后的隔离重跑，证据中的独立 job 文件和报告文件均为 1。

另有两个旧 RouteChatService 测试失败：`test_route_chat_service_uses_new_path_for_fast_chat`、`test_route_chat_service_uses_report_workflow_when_engine_available`。已在独立进程中加载 HEAD 原版 MainOrchestrator 和 RouteChatService 重跑，两者同样失败；未将其改成通过来掩盖既有行为差异。这两个旧入口断言不计入本次已通过的专用回归套件。

## 验收边界

- 真实验证没有使用产品用户登录，也未做浏览器端到端操作；HTTP schema、SSE 和权限边界通过自动化用例验证。
- RAG/Web 的权限与错误契约经过自动化验证，本次五轮样例明确关闭检索，没有验证真实网络搜索或真实课程文档检索质量。
- 真实验证覆盖重新创建运行时后的上下文恢复；没有做宿主机掉电、进程强杀或跨机器恢复测试。
- 基础结构检查不能证明报告事实准确或完整满足所有语义要求。
- 长期记忆服务沿用现有实现；完整记忆生命周期、原生压缩、分布式会话和其他资源 Skills 尚未迁移。
- 当前运行服务未重启，配置开关未启用。灰度启用前需要按接入说明配置持久卷并确认本版功能范围。
