# DeepTutor 迁移 M1 验收

2026-10-16：M1 已完成本地验证，未上线。五阶段任务见[迁移计划](../../architecture/2026-10-16-deeptutor-migration-plan-cn.md)，安装与内部协议见[服务说明](../../../services/deeptutor/README.md)。当前交付是保留完整上游的内部运行服务与业务客户端，还不是可供用户使用的模拟考试。

## 已交付

- 固定 DeepTutor 1.6.14 / `6cf793bd868ba5ecbe64722936d4be8fab5a01df`，完整检出源码，保留许可证与第三方通知；准备脚本可重跑，拒绝覆盖未知修改。
- 独立 Python 3.12.14 环境，不继承系统 site-packages；安装完整上游默认依赖，锁定实际版本。GraphRAG、Manim 等可选扩展尚未安装验证。
- 四个上游文件的可追踪补丁：空模板明确失败；用户要求传入逐题生成及格式修复；仿卷默认处理全部已抽出题目；完成事件等待真实运行层发布，保留事件关联字段。
- 基于真实 DeepTutor SDK 的内部启动、状态、事件与取消接口；受信服务 token 和 owner 工作区隔离；展示事件仅含白名单进度字段，内部事件保留完整内容。
- Edu_AI 异步 HTTP 客户端，支持身份传递、事件游标、取消及错误脱敏；尚未注册到业务路由和持久任务执行器。

## 验证结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 上游专项回归 | 218 passed，78.71 秒 | [日志](upstream-tests.txt) |
| 服务、补丁、源码准备及真实 SDK 隔离 | 18 passed，8.77 秒 | [日志](bridge-tests.txt) |
| Edu_AI 客户端 | 6 passed，0.12 秒 | [日志](client-tests.txt) |
| 安装脚本重跑与依赖检查 | 安装成功，pip check 无冲突 | [日志末尾](bootstrap-tail.txt) |
| 真实 uvicorn / HTTP 冷启动 | 健康 200、无鉴权 401、owner 下不存在任务 404，已停止服务 | [结果](smoke.json) |

合计 242 项测试通过。生成路径的模型边界使用替身；SDK 隔离测试使用真实工作区和数据库；HTTP 启动检查使用真实 SDK，不调用模型。没有真实 PDF 解析、真实出题质量或前端端到端验收。

初次 HTTP 检查采用 2 秒读超时，在用户数据库首次初始化时超时；改为覆盖冷启动的 30 秒后通过，最终首次 owner 读取耗时 2.928 秒。该结果只说明服务启动和基础边界可运行，不代表生成耗时或容量表现。

## 复现

在仓库根目录运行客户端测试：

```bash
PYTHONPATH=backend/src services/deeptutor/.venv/bin/python -m pytest backend/src/tests/integrations/test_deeptutor_client.py -q
```

在 `services/deeptutor` 运行服务测试和独立 HTTP 检查：

```bash
DEEPTUTOR_HOME=/tmp/deeptutor-migration-final-tests .venv/bin/python -m pytest tests -q --disable-warnings
.venv/bin/python scripts/smoke_service.py
```

在 `services/deeptutor/.upstream/DeepTutor` 运行上游专项：

```bash
DEEPTUTOR_HOME=/tmp/deeptutor-migration-tests ../../.venv/bin/python -m pytest \
  tests/agents/question tests/tools/test_question_extractor.py tests/core/test_stream_bus.py \
  tests/core/agentic tests/core/test_agentic_labels.py tests/core/test_agentic_messages.py \
  tests/api/routers/test_quiz_judge_unit.py \
  tests/runtime/coordination/test_memory_coordinator.py tests/runtime/coordination/test_journal_recovery.py \
  tests/app/test_waiting_turn_recovery.py tests/app/test_turn_application_service.py -q --disable-warnings
```

## 未完成项

M2 尚需绑定 Edu_AI 实际模型配置与授权、持久任务映射、资料读取及解析，然后运行真实模型样本和并发恢复验收。显式工具白名单不替代上游自动工具挂载策略，完整资料来源与执行范围仍需在该阶段接入。

M3 尚需完整试卷蓝图、文件角色识别、长卷分段抽取、多选/多空/复合题和逐题检查点。当前上游抽题输入仍有 15,000 字符限制，解除默认 10 题限制不保证长卷完整性；mimic 暂时要求明确提供一份 PDF。

M4/M5 尚需考试版本、作答与评分、页面、联调和部署。`/health` 明确返回 `exam_ready=false`。未修改生产用户数据，未重启或部署线上业务服务。

版本、补丁与依赖锁摘要见[机器可读记录](verification.json)。
