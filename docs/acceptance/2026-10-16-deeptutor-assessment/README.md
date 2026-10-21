# DeepTutor 迁移评估验证记录

日期：2026-10-16。对应[迁移评估](../../architecture/2026-10-16-deeptutor-exam-migration-assessment-cn.md)。验证对象固定为 `HKUDS/DeepTutor@6cf793bd868ba5ecbe64722936d4be8fab5a01df`（v1.6.14）。上游业务代码未修改。

最终三个分组全部运行结束：217 项通过、1 项失败。另有 3 个离线行为探针完成，不并入上游测试数量。

## 结果与文件

- [verification.json](verification.json)：最终分组结果与范围，测试数量按互不重叠的最终分组统计。
- [core-tests.log](core-tests.log)：207 项通过，含最初的 68 项出题相关用例。
- [recovery-tests.log](recovery-tests.log)：4 项任务等待/恢复用例通过。
- [application-tests.log](application-tests.log)：应用任务服务独立运行，6 项通过、1 项失败，耗时 50.10 秒。
- [behavior-probes.json](behavior-probes.json)：三个离线行为复现；[运行脚本](behavior_probes.py)替换模型调用边界，不修改被验证的提示构建与管线分支。
- [environment-packages.json](environment-packages.json)：补装依赖后的包版本清单，仅用于描述本次测试环境，不是可部署的依赖锁。
- [initial-question-tests.log](initial-question-tests.log)：初次 68 项通过记录，已被最终 core 分组覆盖。
- [application-mixed-run.log](application-mixed-run.log)：早期混合测试运行，135 项通过、1 项失败后人工中断；后续按分组独立运行，不以该记录宣称全套完成。任务订阅在 DONE 之后等待租约结束，设有 30 秒尾部等待上限；不能把这段等待单独判为死锁。

应用测试失败位置：`tests/app/test_turn_application_service.py:130`，用例 `test_failed_first_submission_resends_in_its_original_conversation_without_a_duplicate_user`。失败断言读取完成事件的 `metadata.user_message_id`，抛出 KeyError。该用例先前的同会话、重试 turn 不同、用户消息不重复等断言已通过。日志中的 `controlled upstream failure` 是上游测试主动模拟的模型故障，不是本次真实模型调用失败。

## 环境与操作边界

源码位于临时研究目录 `/tmp/exam-mimic-research-20261015/DeepTutor`。使用 Python 3.12.14 创建 `/tmp/deeptutor-assessment-venv-20261016`，启用了 `--system-site-packages`，只在该临时 venv 补装缺失包，没有向 Edu_AI 正在使用的 Python 环境安装依赖。

主数据目录为 `/tmp/deeptutor-assessment-data-20261016`；单独应用与恢复测试分别使用 `...-app-...` 和 `...-recovery-...` 目录。通过上游 `DEEPTUTOR_HOME` 配置指定；未改写 HOME/CODEX_HOME，未读取或提供真实模型密钥。旧 router 导入要求 `data/user/settings/main.yaml` 存在，因此在各临时数据目录提供内容为 `{}` 的配置文件。此文件是测试准备，不代表完整服务初始化已完成。

初次收集曾因缺少 `loguru` 失败，应用执行也曾因缺少 `defusedxml` 失败；补装真实依赖后重测。最终应用服务的消息 ID 失败仍存在，与这两项缺包错误分开记录。未修改上游测试断言，也没有为绕过失败而替换其业务模块。

本次不覆盖真实模型质量、真实 PDF/OCR、真实检索与执行工具、Redis、前端构建或端到端考试。上游单元测试使用其自带 mock；额外探针用固定模型响应，仅验证控制流、提示与输出字段。

## 复现方式

在固定提交的上游仓库根目录运行。先准备独立 Python 3.12 环境及该版本的依赖，并创建独立运行目录的 `data/user/settings/main.yaml`。以下路径为本次评估路径，可替换为新的测试目录。

```bash
DEEPTUTOR_HOME=/tmp/deeptutor-assessment-data-20261016 \
  /tmp/deeptutor-assessment-venv-20261016/bin/python -m pytest \
  tests/agents/question tests/tools/test_question_extractor.py \
  tests/core/test_stream_bus.py tests/core/agentic \
  tests/core/test_agentic_labels.py tests/core/test_agentic_messages.py \
  tests/api/routers/test_quiz_judge_unit.py \
  tests/runtime/coordination/test_memory_coordinator.py \
  tests/runtime/coordination/test_journal_recovery.py -q --disable-warnings

DEEPTUTOR_HOME=/tmp/deeptutor-assessment-recovery-20261016 \
  /tmp/deeptutor-assessment-venv-20261016/bin/python -m pytest \
  tests/app/test_waiting_turn_recovery.py -vv --disable-warnings

DEEPTUTOR_HOME=/tmp/deeptutor-assessment-app-20261016 \
  /tmp/deeptutor-assessment-venv-20261016/bin/python -m pytest \
  tests/app/test_turn_application_service.py -vv --disable-warnings

DEEPTUTOR_HOME=/tmp/deeptutor-assessment-data-20261016 PYTHONPATH=. \
  /tmp/deeptutor-assessment-venv-20261016/bin/python \
  /home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-16-deeptutor-assessment/behavior_probes.py
```
