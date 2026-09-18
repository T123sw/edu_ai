# 资料研究与学习路径：Harness Skills 验收

资料检索、证据整合、学习路径编排及既有审阅已接入 DeepSeek Harness 原生 Skill 插件。实现和阶段映射见[架构说明](../architecture/2026-09-18-preparation-research-harness-skills.md)。不增加用户确认大纲步骤，不增加审阅层。

## 验证范围

使用独立 SQLite、测试身份与文件目录，通过上传和任务 HTTP API 执行真实 DOCX 导入、MinerU Cloud 解析、DeepSeek 模型、Tavily 检索/正文读取、SQL runner 和全局记忆读取。全局记忆前后为空；不代表已验证非空记忆冲突。不是生产登录页的浏览器测试。

用户目标：会 Python 的初学者在两小时内，用上传材料与 DeepSeek 官方文档实现计算器命令行 Agent，并解释工具调用失败处理；中文、先例子后原理，排除训练、多 Agent 和 Web 部署。附件包含故意干扰指令，以及明确缺少真实 SDK/鉴权/可运行示例的说明。

命令：

```bash
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python \
  backend/src/scripts/verify_preparation_intake_e2e.py \
  --env-file .env --output-dir /tmp/preparation-path-harness-fixed-20260918 \
  --through path --network-research
```

去掉最后两个选项可验证仅上传资料的研究交接；输出目录须为不存在的新目录。

## 结果

| 样例 | 边界 | 耗时 | 模型 API 调用 | tokens |
| --- | --- | --- | --- | --- |
| 上传＋联网 | 路径与全部节点依据检查通过，到 produce 入口 | 348.11 秒 | 45 | 534,445 |
| 仅上传 | 带引用研究汇总，到 plan 入口 | 127.81 秒 | 15 | 107,309 |

两次执行的全部已完成模型调用均记录 `runtime=deepseek-harness`、正确 Skill 名称/摘要和 `loaded=true`。需求理解 Skill 沿用已有实现；新增资料研究、路径编排、路径审阅三个 Skill，按阶段挂载工具。

联网样例执行两次搜索、三次网络正文读取，实际引用上传材料和 DeepSeek 官方正文，得到三条整合结论。路径共五个节点，合计 120 分钟：环境准备 20、运行小例子 30、解释循环原理 20、失败处理 30、日志验收 20。每个节点均有目标、先修关系、活动、自测和需求/结论/来源关联，独立路径审阅与五个节点依据检查通过。

存在两次可恢复业务错误：重复读取已读正文、路径遗漏 REQ-005 的关联；均由原有校验拒绝并根据错误修正。不能将结果描述为全程零重试。仅上传对照没有网络调用，保留 SDK/鉴权/可运行示例等限制；其 overview 仍出现“覆盖全部预期能力”后又声明无法完整达成目标的措辞矛盾。该对照只验收来源权限、引用和缺口交接，未验收完整路径；不能据此宣称资料已充分。联网样例也保留 API key 申请等前置条件。

初次真实试跑暴露模型一次返回多条工具调用，旧单调用解析把整批拒绝，导致 SDK 重试耗尽单步预算。修复为先校验整批，再由原生 SDK 调度：MCP 接受一个动作，其余返回明确的未执行状态；接收后强制结束本轮。没有放宽来源/引用校验或增大调用预算。原生 SDK 测试覆盖批量延后，另验证未挂载工具、重复调用 ID、损坏 JSON 整批拒绝。

回归 **205 passed、78 skipped**，Harness 针对性测试 **25 passed**，三个新增 Skill 格式校验通过。跳过项不计作通过。

本次止于材料生成入口，没有验收最终课程内容。耗时和 tokens 为单次样例，不能视为普遍性能保证；原生工具回执后的模型收尾、重复上下文以及逐节点检查仍有优化空间。

## 证据

- [指标及恢复错误](artifacts/2026-09-18-research-harness-skills/metrics.json)
- [联网原始执行报告](artifacts/2026-09-18-research-harness-skills/path-report.json)
- [仅上传原始执行报告](artifacts/2026-09-18-research-harness-skills/upload-report.json)
- [最终学习路径](artifacts/2026-09-18-research-harness-skills/plan.json)
- [研究汇总](artifacts/2026-09-18-research-harness-skills/research_summary.json)
- [节点依据检查](artifacts/2026-09-18-research-harness-skills/node_research_checks.json)

## 部署

仅后端更新，无需数据库迁移或前端构建。尝试 `sudo -n systemctl restart edu-ai-backend` 返回需要密码，服务尚未重启。执行 `sudo systemctl restart edu-ai-backend` 后新代码生效；不要运行会覆盖新版前端的旧激活脚本。
