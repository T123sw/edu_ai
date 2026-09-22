# 窗口 G：共同基线、集成与端到端验收 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 A–F 的改动集成到同一真实入口，用最终提交验证参数、工具、恢复、交付与浏览器学习体验。

**Architecture:** 固定共同基线、维护接口和合并顺序；使用隔离 PostgreSQL、文件与任务目录、测试身份及真实外部服务。最终验收走 HTTP 与实际 worker，不能只直接调用 runner。

**Tech Stack:** pytest、PostgreSQL、现有应用/耐久 worker、MinerU/Tavily/DeepSeek、Playwright。

**Spec:** [总计划](../2026-09-19-preparation-chain-optimization.md)、[共享契约](00-shared-contracts.md)、[历史审查证据](../../../acceptance/artifacts/2026-09-19-preparation-agent-audit/)。

## Global Constraints

- 当前工作区包含未提交健壮性代码、审查文档及无关备份/构建目录。不得 `git add -A`、reset 或 stash 他人未完成改动来制造干净基线。
- 不把模拟模型、SQLite、直接 runner、按钮可见各自的通过冒充真实全链路和播放验收。
- 不访问或迁移业务数据库；真实测试只在专用库、合成身份和私有课程中运行。
- 不宣称绝对稳定；报告实际次数、失败原因、重试成本和未覆盖范围。

## 文件范围

- 负责 `backend/src/app/course_preparation/pipeline.py` / 启动装配的跨模块接线、迁移编号与公共 conftest；领域实现仍回交 A–F。
- 新建 `backend/src/scripts/verify_preparation_full_e2e.py`、参数/失败样例集、`tests/course_preparation/test_full_pipeline_contract.py`。
- 复用 `verify_preparation_intake_e2e.py`、`smoke_preparation_stages.py`、`validate_preparation_live.py`，保留它们原测试范围，不悄悄改历史脚本的通过含义。
- 新建 `frontend/tests/live-learning/preparation-chain-real.spec.ts` 和专用 Playwright config；前端生产接线确有问题时做最小修复，不重做样式或增加新输入字段。
- 最终证据保存于新的 `docs/acceptance/` 日期目录；原审查记录不可覆盖。

## Task G0：发布共同基线和样例账本

- [x] 逐项记录 git status、HEAD、相关未提交 diff 与未跟踪源文件，确认上轮研究覆盖/blocker/重试/回执精简等必需改动已纳入基线；不要漏掉新建 Python 模块。
- [x] 仅提交/打包本轮相关源文件、测试、审查证据及计划，列出被排除的无关文件类别；凭据、任务库和上传原件不进入 Git。
- [ ] 给各窗口发布基线 SHA，使用各自分支/worktree；后续不能仅说“基于最新代码”，必须标出 SHA。A0/B0 的公共接口提交作为其他分支依赖。
- [x] 在证据目录建立 ledger：case_id、代码 SHA、配置版本、测试身份、输入摘要、预期结果、真实/模拟范围、状态、耗时、调用/token、错误和证据路径。
- [x] 原审查真实成绩只作为比较基线：完整课程 295.36 秒/34 次模型调用；联网路径 229.86 秒/27 次。不能将场景变小后宣布同等条件性能提升。

## Task G1：同一最终提交的契约集成

- [x] 按总计划文件负责人核对改动；优先合 A0/B0，再集成 C/D/E/F。检查跨模块 import、签名、schema 和兼容 wrapper 一致。
- [x] 接通实际 build_pipeline、generation handler、phase/Skill 注册、候选 checkpoint、失败恢复和最终交付。仅存在新文件而入口未调用的模块判未完成。
- [ ] 对新 schema/持久化字段做向前迁移和旧版本读取测试；迁移编号唯一，现有运行中任务不会因字段默认值改变而重生成。
- [ ] 如 F 扩展 manifest 的课堂检查定位，同步接通学习端授权读取、定位和旧版本兼容；没有消费路径的字段不能纳入正式已支持能力。
- [ ] 将共享契约的六个参数生效场景做成接口/集成测试；测试需读取实际 payload 和产物，不只断言字符串进入 prompt。
- [x] 执行准备套件、报告/资源共享回归、文件/搜索适配器、课堂渲染及学习端版本测试；PostgreSQL 和学习域 test URL 显式提供。
- [x] 单列失败、跳过及其原因。既有共享报告三个失败应有 D 的修复证据；不因“不是备课入口”忽略。

## Task G2：真实后端主链路与参数效果矩阵

新脚本提供下列显式接口，使用真实 API/worker；缺服务时明确失败或 not_run，不能自动切 mock：

```bash
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python \
  backend/src/scripts/verify_preparation_full_e2e.py \
  --env-file .env \
  --base-url http://127.0.0.1:8027 \
  --database-url-env PREPARATION_TEST_DATABASE_URL \
  --scenario uploaded-course \
  --repeat 3 \
  --output-dir artifacts/preparation-chain-validation/uploaded-course
```

该命令是本模块拟实现入口。测试应用必须使用传入隔离库，启动时校验库身份；认证凭据从本地测试配置读取，不通过命令行参数或日志公开。浏览器与该后端/最终构建使用同一数据库与课程版本。

| case_id / scenario | 实际输入/操作 | 必须得到的结果 |
| --- | --- | --- |
| E01 / uploaded-course | DOCX＋明确用户需求＋空记忆，2 节点、报告/习题/课堂 | 连续 3 次独立任务完整交付，无需人工推动；记录所有内部重试和内容评估 |
| E02 / network-course | 附件缺一部分知识，允许搜索官方正文 | 真搜索/提取/证据/生成/交付，不能到 produce 就停止 |
| E03 / blocked-course | 缺真实 API 资料且禁止联网 | RESEARCH_INSUFFICIENT，指出真实缺口，没有最终课程 |
| E04 / parameter-pairs | 同主题分别先例后理/先理后例；基础和语言也做有控制的变化 | 产物对应改变、映射可定位；不要求随机输出逐字一致 |
| E05 / memory-priority | 空记忆、有关全局偏好、本次相反要求、运行中删除偏好 | 当前要求优先；删除使旧上下文失效；不自动写永久偏好 |
| E06 / long-sources | 长 PDF＋第二附件，核心内容位于后部，网页分页 | 真实覆盖相关后文；同一快照只提取一次；上下文有界 |
| E07 / recovery | 模型超时/429、正文写完后进程退出、审阅漏选项、内容真错误 | 有限恢复；格式重试正文不变，内容修复后重新审阅；成本结清 |
| E08 / control | 重复提交、刷新、重启 worker、取消与交付竞争 | 不重复课程/资源、状态可恢复、取消结果准确 |
| E09 / scoped-changes | 补充节点、修订资料、只调整路线、基准版本冲突 | 范围正确、保留旧资源/进度，冲突不覆盖 |
| E10 / other-subject | 非 Agent/非面试主题，如分数加法 | 无面试模板污染，教学参数与来源仍正确 |

- [ ] E01/E02/E03/E04/E05/E10 使用真实模型；E07 的确定性故障可注入真实 handler 的模型/工具边界，明确标记注入点，不把返回固定最终产物的 mock 算恢复验收。
- [ ] E01 必须记录 normalize 到 commit 的全部阶段；缺口测试 expected business failed 与 test passed 分开存储。
- [ ] 新脚本输出 public state、各阶段摘要、动作回执、resource_specs、资源版本与哈希、质量/失败详情、manifest、学习端回读、计量。不要把密钥和全量私有配置写入记录。
- [ ] 对所有真实备课 completion 执行 B 的 Harness 回执断言；media 工具如含模型调用，同样纳入检查，不能只统计主 provider。
- [ ] 比较耗时、调用数、token 与每阶段失败/修复次数；单轮快不代表稳定，三轮成功也不能宣称统计可靠性已证明。任何场景触及既有硬预算即记录真实失败，不临时无限加预算求通过。

## Task G3：真实浏览器从输入到学习的闭环

- [ ] 定位可用 Node/pnpm 工具链并记录版本；使用专用 config、端口、测试用户和最终构建，不复用旧审查课程假装新生成。
- [ ] 从页面填写要求、上传真实文件并启动准备；离开/刷新后查看同一任务，最终从页面进入刚交付课程。
- [ ] 打开每个节点的全部必需资源，检查确切版本；报告要求能定位，习题作答可保存并刷新回读，课堂每页可显示、图示/媒体可加载。
- [ ] 课堂验证播放动作确实推进，图片无坏链、文字不溢出、题目先于答案；需要配音时检查实际音频响应、解码及播放进度，人工抽听记录与自动化结果分开。
- [ ] 覆盖桌面与窄屏，保存 screenshots、trace、console/network 错误。旧 `agent-full.spec.ts` 只点击播放按钮的断言不足以替代本次播放验证。
- [ ] 如果交互功能原生未支持，报告能力缺口并回交 E；不能添加静态“答对了”文本伪装用户作答结果。

## Task G4：验收与最终交接

- [ ] 在同一最终 SHA 上重跑受影响检查与完整主路径；所有阻塞失败修复后才标可交付。
- [ ] 参数账本必须覆盖用户要求、语言/深度/基础、活动/先修/目标、来源/版本、偏好/删除、节点时间/资源估算、规格/正文摘要、取消/预算。
- [ ] 输出结论分三栏：代码已接线、自动化已验证、真实服务/浏览器已验证；未完成项给具体场景和原因。
- [ ] 逐项对照总计划问题表，独立资源清单规划仍标暂缓，不因接口存在宣布该能力完成。
- [ ] 提供所有模块 SHA、最终 SHA、测试命令/数量、真实案例结果、失败率分母、恢复情况、性能数据、部署所需配置和迁移说明。验收完成不自动部署业务服务。


## G 实施记录（持续更新）

- G0 基线 `18080783`，集成分支 `integration/preparation-chain-20260919`；各窗口既有起点 SHA 保留，未重置他人分支。
- 已新增真实 HTTP/worker 脚本、隔离启动校验、E01–E10 账本和桌面/窄屏 Playwright 用例；E04–E09 驱动仍未完成。
- 基线 PostgreSQL 回归 324 passed / 3 failed / 5 skipped；3 个历史共享报告失败在合入 D `ee818810` 后，相关 A/D 套件 76 passed。C 首批与 G 工具测试 73 passed。
- E03 真实请求已得到 `RESEARCH_INSUFFICIENT` 且无课程，58.22 秒、总动作计费 calls=8、tokens=45692；B 尚未合入，严格回执检查 `COMPLETION_PHASE_MISSING`，因此**测试仍失败**，不能标整链路通过。
- 详见 [G 验收记录](../../../acceptance/2026-09-19-preparation-chain-integration/README.md) 与 [场景账本](../../../acceptance/2026-09-19-preparation-chain-integration/ledger.json)。

- 首批 A/C/D/E/F 全部可引用代码已集成；B 无提交，未擅自快照其在途代码。D/F 相关 176 passed / 10 skipped；E/C/G 追加 102 passed；G 接线门禁 24 passed / 6 skipped（B 未集成）。正式前端构建通过。
- G1–G4 保持未完成：E04–E09 专项驱动尚待实现，完整模型、真实浏览器及同一最终 SHA 验收未进行；当前不是可交付结论。

## 2026-09-21 合并后验收补记

- 已保存原目录相关改动，并将 A–F/B 原补丁、D 漏合修复及实际接线合回用户分支；合并提交 `48bbf51d`、`e8122048`，被测运行代码 `885aaf5a`。此前“B 尚未集成”的状态由本记录更新。
- 最终备课/共享回归 706 passed / 15 skipped；学习端首轮 206 passed / 2 failed / 3 skipped，两个多进程启动方式问题修正后重跑 2 passed；前端播放器 23 passed，正式构建通过。
- 真实 E03 通过；E01 和桌面浏览器新任务均在有限修复后以 QUALITY_GATE_FAILED 结束，未交付课程。取消任务仍有在途模型预留未结清。E01 连续三轮和浏览器学习/播放没有通过。
- G2–G4 继续保持未完成；E04–E09 驱动、外部媒体及其他未覆盖项没有补记为通过。详见 [本次验收记录](../../../acceptance/2026-09-21-preparation-chain-integration/README.md)、场景账本及具体错误证据。


## 2026-09-21 故障修复与 Flash 复验

- 本次累计 34 个源码/测试提交已合回用户分支，被测源码 `4c4ea1972e5408abb19687895caa311f4a1af120`。修复涵盖取消结算、有限格式/内容恢复、原生工具提交与 schema 校验、时长修订、学习端多选/作答回读及私有课堂版本读取。原有未跟踪备份/构建未纳入提交。
- 同一源码准备/共享回归 **846 passed / 15 skipped，494.98 秒**；正式构建 **20.12 秒**。学习域此前 `13d9eeaf` 为 **256 passed / 3 skipped**，其后相关学习后端文件未变；不记作最终 SHA 全域重跑。
- 当前真实 Flash E03 和 R01 均通过，所有在途模型预留已结清。E01 首轮 **531.69 秒、76 计量 calls、895432 token**，以 `BUDGET_EXHAUSTED` 结束；第 2/3 轮未启动。
- 当前桌面新课程 **601.82 秒、77 计量 calls、918809 token**，两轮内容修订后节点仍 **11.41 / 11.34 分钟 > 各 10 分钟**，以 `QUALITY_GATE_FAILED` 结束。未交付；窄屏未启动。Flash 正常课程完整闭环仍未通过。
- 历史 `3461e4a8` 的 Pro 桌面新课程曾完整交付并通过报告、习题保存回读和课堂页面/旁白推进，窄屏失败。该成绩不移记到 Flash 或当前源码；真实 TTS 未验收。
- 新整课智能阶段已验证实际原生 DeepSeekHarness + Skill/MCP → `deepseek-v4-flash`，供应商响应名 `deepseek-flash`。旧学习对话及其部分补充/修订入口仍有 BoundedModelAdapter，不能称全应用已迁移。
- G2–G4 仍未完成。完整账本保存 **105 个已启动任务**，含失败/取消，未启动轮次另列；历史报告未覆盖。见 [故障修复与 Flash 复验报告](../../../acceptance/2026-09-21-preparation-chain-recovery/README.md)、[逐轮账本](../../../acceptance/2026-09-21-preparation-chain-recovery/runs.md) 和 [未覆盖矩阵](../../../acceptance/2026-09-21-preparation-chain-recovery/not-run.json)。本次合并没有自动部署或重启业务服务。

- 清理前全库补查：本轮账本 105 个任务的预留均为零，但更早验收留下的 5 个取消任务仍有旧预留，未纳入本轮分母，也未手工清零或伪造实际用量。历史迁移/对账仍有缺口，详见报告的旧预留记录。


## 2026-09-22 学习时长语义修正后的复验

- 用户明确学习时长仅用于控制内容量，不能作为交付硬门槛。本轮移除对应规划/生成/质量/交付拦截，保留估算与内容正确性要求；这个新语义覆盖旧共享契约中的学习时长硬门槛。
- 同时修复节点审阅重复传入教学上下文导致窗口溢出，以及整课摘要审阅误要求重新提供全部正文、进而触发全资源返工的问题。被测源码 `3d9d2e33525a22d2aa2be91d4d56fcc4fde9ecbe`；最终回归 **842 passed / 15 skipped**，正式构建通过。
- 最终 E01 第一轮交付成功 **300.41 秒 / 544330 token**；第二轮因习题审阅工具参数 JSON 非法，在有限恢复后 **QUALITY_GATE_FAILED，469.46 秒 / 642283 token**；第三轮未启动。不是学习时长或父预算阻塞。
- 最终桌面新课程浏览器闭环通过；窄屏课程交付并完成资源交互，但首次节点学习会话读取 GET 404 导致零错误断言失败。人工发现字幕遮挡步骤图底部说明、报告定位锚点直接显示为正文。两项视觉问题未被现有横向溢出断言覆盖。
- E03 资料不足和 R01 在途取消均通过。本次三个提交批次共 17 个真实任务，含失败与主动取消，预留均已结清；先前历史预留欠账不在本轮清理范围。
- G2–G4 继续保持未完成，不能用首批两个视口通过代替最终结果。完整专项矩阵和 TTS 仍未验收。代码合并未自动重启业务服务。见 [本轮报告](../../../acceptance/2026-09-22-preparation-advisory-e2e/README.md)、账本与截图。
