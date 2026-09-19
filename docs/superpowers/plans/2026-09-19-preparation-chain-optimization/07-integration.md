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

- [ ] 逐项记录 git status、HEAD、相关未提交 diff 与未跟踪源文件，确认上轮研究覆盖/blocker/重试/回执精简等必需改动已纳入基线；不要漏掉新建 Python 模块。
- [ ] 仅提交/打包本轮相关源文件、测试、审查证据及计划，列出被排除的无关文件类别；凭据、任务库和上传原件不进入 Git。
- [ ] 给各窗口发布基线 SHA，使用各自分支/worktree；后续不能仅说“基于最新代码”，必须标出 SHA。A0/B0 的公共接口提交作为其他分支依赖。
- [ ] 在证据目录建立 ledger：case_id、代码 SHA、配置版本、测试身份、输入摘要、预期结果、真实/模拟范围、状态、耗时、调用/token、错误和证据路径。
- [ ] 原审查真实成绩只作为比较基线：完整课程 295.36 秒/34 次模型调用；联网路径 229.86 秒/27 次。不能将场景变小后宣布同等条件性能提升。

## Task G1：同一最终提交的契约集成

- [ ] 按总计划文件负责人核对改动；优先合 A0/B0，再集成 C/D/E/F。检查跨模块 import、签名、schema 和兼容 wrapper 一致。
- [ ] 接通实际 build_pipeline、generation handler、phase/Skill 注册、候选 checkpoint、失败恢复和最终交付。仅存在新文件而入口未调用的模块判未完成。
- [ ] 对新 schema/持久化字段做向前迁移和旧版本读取测试；迁移编号唯一，现有运行中任务不会因字段默认值改变而重生成。
- [ ] 如 F 扩展 manifest 的课堂检查定位，同步接通学习端授权读取、定位和旧版本兼容；没有消费路径的字段不能纳入正式已支持能力。
- [ ] 将共享契约的六个参数生效场景做成接口/集成测试；测试需读取实际 payload 和产物，不只断言字符串进入 prompt。
- [ ] 执行准备套件、报告/资源共享回归、文件/搜索适配器、课堂渲染及学习端版本测试；PostgreSQL 和学习域 test URL 显式提供。
- [ ] 单列失败、跳过及其原因。既有共享报告三个失败应有 D 的修复证据；不因“不是备课入口”忽略。

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
