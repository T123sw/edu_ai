# 2026-09-21 多窗口任务执行核查

结论：模块成果已有较大进展，但 07-integration 的全链路交付目标尚未完成。主要阻塞为 B 未形成可集成提交及完整接线、D 最新修复漏合、E 的真实媒体能力缺口，以及 G 尚未实现/执行的验收场景。不能把模块测试通过解释为整课可交付。

本次核对了各 worktree、Git 提交/补丁等价关系、模块交接、实际生成入口和验收账本，并复跑针对性测试。未修改业务代码、合并分支、部署服务或访问业务数据库；本次只新增这份记录。历史真实服务成绩均明确沿用原证据，本次没有重跑付费模型或生产浏览器。

## 代码位置

- 用户当前目录 `/home/zxqs_ep/Edu_AI`：`feat/self-learning-frontend-20260914`，HEAD `67fc18b85ffbd82406c5ab33703eff8ea627c222`。仍有上一轮及 B 的未提交/未跟踪源文件，不能清理或当作已发布模块。
- 共同基线：`18080783b7aa9b50f23e688a57a7944df90e258a`。
- 集成 worktree：`.worktrees/preparation-integration-20260919`，HEAD `9689c97614752eeade5f62210600c4fb0f097943`；本次核查前后干净。
- A/C/D/E/F 各 worktree 均干净。集成成果尚未合回上述用户当前分支。

## 各窗口状态

| 窗口 | 可引用成果 | 集成及剩余情况 |
| --- | --- | --- |
| A 参数 | `e3d3ce6b`、`d7d26fc8`；分支 HEAD `c264070f` | 参数上下文、v2 规格及 v1 兼容已集成。主 handler 尚未使用 A builder，真实参数效果仍待最终链路验证。 |
| B Harness | 当前工作区代码、`b0-changes.patch`、SDK 模拟 provider 证据；无模块提交 | 协议骨架已有实现；A/F 接线、分类失败、恢复队列及全链路 phase 仍未完成。仅把现有 patch 合入也不足以完成任务。 |
| C 来源 | `868320bb`、`f115f629`、`8864ee7c`、`73d6eed3`；HEAD `1ad95410` | 领域提交已集成；解析控制、正文快照和上下文限制有模块证据。真实来源路径验证只到 produce 交接，不是最终课程生成。 |
| D 内容 | `ee818810`、`3157cb4f`、`3e4d613c`；HEAD `1a5e57e9` | 前两项已集成；最新代码 `3e4d613c` 和交接/证据 `1a5e57e9` 漏合。D 有资源级真实 Harness 产物，但使用固定 B 源码快照，不能替代最终 handler 集成。 |
| E 课堂 | `cc234811`、`21195202`；HEAD `21cdfea0` | 已集成分镜、受控图形和题目反馈。浏览器证据来自组件夹具；真实图片/TTS 工具未接入，必需媒体明确失败；窄屏流程图文字可读性仍待处理。 |
| F 质量恢复 | `debc7960`；HEAD `7da7b9b8` | 候选端口、失败分类、质量/交付和隔离 PostgreSQL 模块证据已集成。B 尚未传 checkpoint、持久化 FailureDetail 或实现恢复队列接口，功能未形成主入口闭环。 |
| G 集成 | HEAD `9689c976` | G0 基线及账本已建立；G1 部分集成，G2 部分驱动，G3 有测试代码无生产闭环结果，G4 未验收。 |

## 阻塞发现

### 1. 集成分支仍使用旧生成入口

集成 worktree 的 `backend/src/app/course_preparation/adapters/generation.py`：

- 第 57 行的 `automatic_payload` 仍为旧实现，保留固定“概念与机制 / 案例与面试表达 / 学习检查”大纲，未调用 A 的规范化 builder。
- 第 86 行仍创建 `GenerationGateway`，没有 B 的 `harness_generation.py`。
- 第 90/94/97 行未将 F 的 checkpoint 传给报告、课堂和习题生成器。
- 第 103 行只保存错误 code，未保存结构化 FailureDetail；GenerationAdapter 无 `resume_review` 队列装配。
- D 的 `preparation_content.phase_gateway` 在准备生成路径动态导入缺失的 B 模块。

`test_full_pipeline_contract.py:144` 用 importorskip 明确跳过 B 缺失时的 handler 测试，因此该套件的绿色结果不能证明生成链路已可执行。主工作区 B 增量虽已替换网关及 wrapper，仍未补齐 checkpoint、分类失败及恢复队列。

### 2. D 最新修复漏合，且存在可复现影响

`git cherry integration/preparation-chain-20260919 feat/preparation-content-20260919` 显示 `3e4d613c` 和 `1a5e57e9` 尚无等价集成补丁。最新修复包括逐分句解析理由、v2 输出封装说明及 review-only 恢复边界。

本次将 D 最新 `test_review_counterexamples.py` 复制到临时目录，用集成分支的生产代码和数据库夹具运行 `test_review_only_retry_escalates_semantic_error_before_writing`：

| 代码 | 结果 | 实际观察 |
| --- | --- | --- |
| 集成 `9689c976` | 2 failed / 2 skipped | report 的 writer/review 为 3/4，quiz 为 3/2；预期均为 1/2。仅重审恢复仍额外调用写作器。 |
| D `1a5e57e9` | 2 passed / 2 skipped | 同名报告/习题用例通过，恢复不额外调用 writer。 |

两次跳过均为未配置隔离 PostgreSQL；实际运行的是 SQLite 持久化分支。模型为脚本化测试网关。这个结果证明恢复控制流缺陷及 D 修复有效，不代表真实模型恢复已验收。没有把 D 生产代码或测试覆盖到集成工作树。

### 3. G 有自身未完成实现，并非只等待 B

`backend/src/scripts/preparation_cases/scenarios.json` 的 E04–E09 均只有 `requires_driver`；验证脚本在该条件下返回 `SCENARIO_DRIVER_PENDING` / `not_run`。参数对照、偏好删除、长资料、故障恢复、取消/重启和局部变更六类驱动仍待实现。

集成 `ledger.json`：E01/E02/E04–E10 共九项 not_run；E03 为 failed；`final_acceptance=false`。按场景状态为 0 passed / 1 failed / 9 not_run，不能把未运行场景算作产品失败率。E03 原运行正确得到 RESEARCH_INSUFFICIENT 且未交付课程，但严格验收因 COMPLETION_PHASE_MISSING 失败，原代码 SHA 为 `d2d912a5`，不是当前集成最终 SHA。

E01 连续三轮、E02/E10 完整交付、真实参数效果、桌面/窄屏从输入到学习、音频解码及人工抽听、同一最终 SHA 的综合回归均未完成。G 的 Playwright 用例可加载和前端构建通过不等于这些验证通过。

## 本次复跑

在集成 HEAD `9689c976`，使用约定 Python、`COURSE_PREPARATION_ENABLED=false`、`PYTHONPATH=backend/src`；禁用 dotenv，移除进程内 DATABASE_URL / PREPARATION_TEST_DATABASE_URL / LEARNING_TEST_DATABASE_URL 后调用 pytest：

```text
backend/src/tests/course_preparation/test_full_pipeline_contract.py
backend/src/tests/course_preparation/test_generation_context.py
backend/src/tests/course_preparation/test_spec_compatibility.py
backend/src/tests/chat/test_reviewed_report.py
backend/src/tests/chat/test_report_review_policy.py
backend/src/tests/course_preparation/test_generated_content_constraints.py
backend/src/tests/course_preparation/test_review_counterexamples.py
pytest arguments: -q -ra --tb=short
```

结果：**127 passed / 20 skipped，11.23 秒**。跳过：3 项 B 模块缺失、11 项隔离 PostgreSQL 未配置、6 项 opt-in 真实模型。上述 D 新增恢复反例是单独执行的补充验证，不混入此组结果；没有运行全套或真实浏览器。

## 后续交接顺序

1. B 基于现有 A/C/D/E/F 明确接口完成主 handler、生命周期、候选及恢复队列，提交可引用 SHA；现有“等待 F/C 接口”说明已过时，应按已交付代码接线。
2. G 合入 D `3e4d613c` / `1a5e57e9`，再集成 B；确认 A 参数和 F 恢复经三类真实 handler 消费。
3. E/G 补齐约定媒体能力和窄屏可读性；G 实现 E04–E09 六类驱动。
4. 在同一最终 SHA 上执行隔离 PostgreSQL 回归、E01 三轮及其他真实场景、生产浏览器学习闭环，更新账本后再判定可交付。独立资源清单规划仍按原计划暂缓。

历史依据：集成 worktree 的 `docs/acceptance/2026-09-19-preparation-chain-integration/{README.md,ledger.json}`，A/C/E/F 模块交接，以及 D worktree 的 `docs/acceptance/2026-09-19-preparation-content-handoff.md`。模块文档、主目录计划和集成记录存在更新时间差异，应以具体 SHA、消费路径和实跑证据判断，不能只按复选框估算完成率。
