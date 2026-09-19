# 连续 Harness：需求理解后到学习路径生成

已实现总控 [build-learning-path Skill](../../backend/src/app/course_preparation/skills/build-learning-path/SKILL.md)。正常执行在同一个原生 Harness 会话内完成附件读取、Web 搜索、正文读取、证据整合、汇总和路径提交；MCP 返回真实业务结果，校验错误也在本会话内修正。实现边界及恢复机制见[架构说明](../architecture/2026-09-19-continuous-learning-path-harness.md)。

## 真实测试

沿用上一版的 DOCX、用户原话、空全局记忆和模型配置。独立身份、SQLite 与文件目录，通过真实上传/任务 HTTP API、MinerU Cloud、DeepSeek、网络搜索与正文读取、SQL runner 执行到 produce 入口。不是生产登录页面测试，也未生成最终课程。

```bash
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python \
  backend/src/scripts/verify_preparation_intake_e2e.py --env-file .env \
  --output-dir /tmp/preparation-continuous-path-20260919 --through path --network-research
```

| 指标 | 上一版逐动作会话 | 本版连续会话 |
| --- | --- | --- |
| 资料研究到路径提交 | 216.25 秒 | 75.92 秒 |
| 该环节模型 API 调用 | 28 | 8 |
| 该环节 tokens | 400,223 | 155,474 |
| 含需求理解与独立检查的总耗时 | 348.11 秒 | 193.89 秒 |
| 全程模型 API 调用 | 45 | 29 |
| 全程 tokens | 534,445 | 307,448 |
| 学习节点 / 总分钟数 | 5 / 120 | 6 / 120 |

本版研究至路径仅一次 `run_learning_path`，所有模型调用都记录原生 Harness runtime、正确 Skill 名称/摘要与 loaded=true。多个独立结论可在一轮模型响应中批量提交，工具逐项真实执行与保存；没有使用旧的“其余动作延后”行为。

最终路径包含 SDK 环境准备、官方小例子、循环原理、add 工具定义、失败处理、日志验收六个节点，总计 120 分钟；每个节点有目标、先修、活动、自测及需求/证据关联。独立路径审阅通过，六个节点依据检查全部通过。全局记忆前后仍为空。

本版研究与规划没有可恢复校验错误；需求理解阶段有一次“用户原话引用不匹配”错误，随后恢复。上一版存在一次重复正文读取和一次需求 ID 覆盖遗漏。模型和外部服务存在波动，来源选择、节点数量和检查输出长度也不同，因此该对比只说明样例实测效果，不证明一般性能上界或所有学习任务的质量。

路径仍披露限制：官方 get_weather 例子需改写成 add，完整错误回传需结合不同来源组织；这一步检查学习路径依据，没有实际运行最终生成的计算器程序。

## 行为验证

针对性测试覆盖：原生 SDK 连续读取真实 MCP 结果、批量结论均被执行、路径校验失败后修正、从已保存证据/汇总恢复而不重复搜索、规划回到研究使旧汇总失效、uploaded_only 禁止搜索、未挂载审阅不可执行、伪造引用拒绝、权限撤销后阻止后续操作、预算耗尽前阻止外部请求。新总控 Skill 格式校验通过。

全量回归和针对性结果见同目录 artifacts 的 validation.json。

## 证据

- [指标对比](artifacts/2026-09-19-continuous-learning-path/metrics.json)
- [原始执行报告](artifacts/2026-09-19-continuous-learning-path/report.json)
- [最终学习路径](artifacts/2026-09-19-continuous-learning-path/plan.json)
- [研究汇总](artifacts/2026-09-19-continuous-learning-path/research_summary.json)
- [节点依据检查](artifacts/2026-09-19-continuous-learning-path/node_research_checks.json)

## 部署

无需数据库迁移或前端更新。已尝试 `sudo -n systemctl restart edu-ai-backend`，当前 sudo 要求密码，后端尚未重启；执行 `sudo systemctl restart edu-ai-backend` 后新流程生效。
