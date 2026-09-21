# 课程准备链路优化与多窗口交接 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement the assigned module task-by-task. 用户已选择将各模块交给不同窗口；无需另开子 Agent。步骤用复选框记录实际完成状态。

**Goal:** 让现有课程准备全链路可靠执行，使每个阶段的输入参数有真实来源、明确语义、下游用途和可验证效果。

**Architecture:** 保留现有阶段状态机、耐久队列、权限、预算、版本与事务提交；补齐阶段契约，并将备课中的智能生成/审阅纳入原生 DeepSeek Harness 与 Skills。按模块独立提交，最后由集成窗口合并并验收。

**Tech Stack:** Python、Pydantic、SQLAlchemy/PostgreSQL、DeepSeek Harness、MinerU、Tavily/Bocha、现有报告/习题/OpenMAIC 课堂组件、TypeScript/Playwright。

**Spec:** [实际代码审查及证据](../../acceptance/2026-09-19-preparation-agent-code-audit.md)、[课程准备主设计](../../architecture/2026-09-17-course-preparation-agent-design-cn.md)、[学习 Agent 主设计](../../architecture/2026-09-17-learning-agent-design-cn.md)。本计划按用户 2026-09-19 最新要求收缩本轮范围。

## Global Constraints

- **本轮不新增独立资源清单规划阶段，不实现按节点智能选择资源组合，不扩展资源类型。**创建课程仍沿用报告、习题以及已要求的课堂；局部补充/修订沿用既有范围。此约束优先于审查报告中的后续资源规划建议。
- 必须修复现有参数的含义和使用：节点时间不能冒充每份资源的独立用时；学习活动、基础、明确要求与有效偏好不能在中间丢失。
- “全部接入 Harness”要求备课中的智能写作、审阅、内容修复可追踪到实际 SDK/Skill 调用；不要求跨整课使用一个无限增长的会话，不把事务提交交给模型。
- 不增加正常流程中的人工确认，不重新在首页添加显式风格输入项。用户自然语言要求和授权记忆继续生效。
- 当前请求优先于历史偏好；材料缺口不是用户排除项；一次性要求不写入长期记忆。
- 保留取消、预算、租约、幂等、来源权限、摘要校验及确切资源版本。不能用静默降级、删检查或伪造回执获得成功。
- 旧工作台的显式确认和审阅策略不能因新备课流程被全局关闭。
- 本计划状态为**待实施**。历史测试成绩不是这些改动的验收结果。

## 1. 分配给窗口的文档

每个窗口只需收到“本总计划＋自己的模块文档”。模块文档会引用统一契约，包含自身代码范围、步骤和测试。

| 窗口 | 模块计划 | 主要交付 | 前置条件 |
| --- | --- | --- | --- |
| A | [01 参数与上下文贯通](2026-09-19-preparation-chain-optimization/01-parameters.md) | 有来源的教学上下文、版本化生成规格、真实时间语义 | 可立即开始；先发布契约与样例 |
| B | [02 Harness 与 Skills 接入](2026-09-19-preparation-chain-optimization/02-harness.md) | 所有备课智能调用的统一 SDK 入口及加载证据 | 接口骨架可并行；集成依赖 A |
| C | [03 文件、检索与证据](2026-09-19-preparation-chain-optimization/03-sources.md) | 可取消解析、正文快照分页、明确服务能力、长资料衔接 | 可立即开始；与 B 协调上下文预算接口 |
| D | [04 报告、习题与资源审阅](2026-09-19-preparation-chain-optimization/04-content.md) | 去模板污染、教学要求落实、逐选项核验、共享报告回归 | 样例与测试可先做；依赖 A/B 接口 |
| E | [05 AI 课堂生成与播放](2026-09-19-preparation-chain-optimization/05-classroom.md) | 参数驱动课堂、必要视觉与反馈、实际播放验证 | 样例/渲染可先做；依赖 A/B，复用 D 审阅接口 |
| F | [06 课程验收、恢复与交付](2026-09-19-preparation-chain-optimization/06-quality-recovery.md) | 正确失败分类、最小范围修复、目标检查与版本衔接 | 故障测试可先做；依赖 A/B/D/E 输出 |
| G | [07 集成与端到端验收](2026-09-19-preparation-chain-optimization/07-integration.md) | 共同基线、合并、真实后端与浏览器闭环、验收报告 | 从基线整理开始，最后集成各模块 |

共同必读：[00 共享参数与交接契约](2026-09-19-preparation-chain-optimization/00-shared-contracts.md)。表中的新接口和 Skill 名称都是本轮拟实现约定，不是已存在能力。

## 2. 并行顺序与阶段门槛

1. **G0：固定共同基线。**当前工作区存在上一轮未提交改动及无关备份，不能直接让各窗口从旧 HEAD 各自开工。G 记录并打包本轮必需的已验证改动；排除密钥、数据库、构建产物及无关 `.bak`。建立包含本计划和审查证据的可引用基线提交，各窗口记录相同 SHA。
2. **A0/B0：先交付接口。**A 实现共享类型、兼容读取、上下文样例；B 实现有明确 phase 的 SDK 调用入口和协议测试。接口提交优先集成，后续窗口不自行创造另一套字段。
3. **并行实施。**C 修资料工具；D/E 根据 A/B 接口修正文与课堂；F 修验收与恢复；G 建评测和真实验收脚本。尚未合入依赖时可写基于约定的测试，但不能把模拟网关通过当作真实集成完成。
4. **逐模块集成。**建议顺序 A → B → C → D → E → F。一个模块只能改自己负责的文件；跨文件修改由所属窗口接受交接或由 G 在合并时实施。
5. **G1：闭环验收。**以同一最终提交执行数据库、真实服务、故障和浏览器场景；问题退给所属窗口后重测受影响部分及完整主路径。

A/B 接口发布后若需要变化，更新共享契约的版本与调用点清单；未迁移所有消费者前不得删除旧入口。不能将“等待依赖”改成向用户反复询问实现细节。

## 3. 共享文件唯一负责人

| 文件或区域 | 唯一负责人 | 其他窗口如何使用 |
| --- | --- | --- |
| `generation_contracts.py`、新 `teaching_context.py` / `generation_context.py`、`production_stages.py` | A | B 调用 payload builder；D/E/F 使用规范化上下文 |
| `adapters/generation.py`、`generation_gateway.py`、Harness adapter/provider/context、`workflow_skills.py` | B | A 交付 builder；F 交付恢复策略；B 负责把它们接到 handler |
| `intake.py`、`research_contracts.py`、研究/来源/文件适配器、研究 Skills | C | A 不修改 brief schema；确需补字段交给 C |
| `chat/harness/reviewed_report.py`、`reviewed_resource.py`、`services/generation_task_handlers.py` | D | E 调用 D 提供的课堂审阅接口，不能同时编辑该共享文件 |
| `adapters/classroom.py`、新课堂分镜/渲染模块、课堂视觉/TTS 专用服务 | E | 对全局服务保持旧调用兼容；需要前端功能修复先交接 G |
| `quality.py`、`artifact_store.py`、`delivery.py`、`manifest.py`、runner/lifecycle/预算与生成失败契约 | F | B 通过 F 的既有或明确新增接口写草稿/失败回执 |
| pipeline 装配、迁移编号、公共测试夹具、端到端脚本、浏览器测试及前端接入修复 | G | 各窗口提供装配 patch/迁移需求；不自行抢占同一迁移编号 |
| 新 Skill 的内容 | 业务模块 D/E/F | B 只注册名称和路由；相同 Skill 文件不多人编辑 |
| 既有模块测试 | 按被测生产代码归属；`test_generation_adapter.py` 归 B | A 新建自己的参数测试；G 独占跨模块测试与最终证据 |

文件名缩写均相对于 `backend/src/app/course_preparation/`，带 `chat/` 或 `services/` 的相对于 `backend/src/app/`。未列文件按所属模块目录处理；遇到共享文件先列出需要的改动并交给唯一负责人。

## 4. 问题覆盖与本轮边界

| 审查问题 | 本轮负责模块 | 验收证据 |
| --- | --- | --- |
| 活动/偏好/原始要求丢失、面试模板污染 | A/D/E/F | 参数变化使最终正文和课堂按约束改变，审阅能指出具体位置 |
| 后半程绕过原生 Harness | B/D/E/F | 每次智能调用带实际 runtime、phase、Skill 摘要与真实 usage |
| 节点时间误作资源时长 | A/D/E/F | 节点上限、资源估算/实测分别记录，整课检查使用正确口径 |
| 习题解析与选项不对应却通过 | D/F/G | 审查中的失败样本被阻断或修正，答案位置可回读 |
| 静态文字课堂、检查直接播答案 | E/G | 分镜落实、显示/讲解匹配、先题后反馈、真实播放器证据 |
| 审阅格式错导致重生成全文 | D/F/B | 故障注入时正文 digest 不变，只补审阅，保留真实原因 |
| 共享报告 3 项回归失败 | D | 明确新旧策略兼容，原失败用例及新策略测试通过 |
| 网页分页重复拉整页、长上下文、工具能力不完整 | C/B/G | 单快照分页、恢复可复用、预算有界且不静默丢要求 |
| MinerU 格式、取消、时间与定位 | C/G | 格式/质量分层验收，超时取消不会误交付或长期占用 |
| 课程交付到学习端、局部变更与恢复 | F/G | 确切版本、权限、幂等、取消竞争及浏览器闭环 |
| 智能资源组合、独立资源规划 Skill/阶段 | **暂缓** | 仅记录现状，不作为本轮交付依赖 |

## 5. 所有窗口统一交付格式

- [ ] 提供基线 SHA、模块提交 SHA、只涉及自身范围的文件清单。
- [ ] 提供“参数来源 → 变换 → 消费者 → 产物证据”清单；字段只有进 prompt 没有产物效果，不算验收。
- [ ] 说明旧任务/旧资源读取与恢复策略，是否有迁移及复用失效变化。
- [ ] 给出实际执行的命令、通过/失败/跳过数量、真实服务/模拟边界、证据路径。
- [ ] 列出交给其他窗口的明确接口与装配变更；没有挂到主流程的新模块不得声明完成。
- [ ] 更新自己的模块复选框和结果记录，不修改其他窗口的状态，不改写历史审查结论。

## 6. 测试运行约定

仓库根目录使用 `/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python`，`PYTHONPATH=backend/src`。测试库通过 `PREPARATION_TEST_DATABASE_URL` / `LEARNING_TEST_DATABASE_URL` 显式提供，仅指向隔离库；测试不读取业务 `.env`。模块文档中的 `pytest` 路径均从仓库根解析。

示例（运行现有备课契约测试）：

```bash
COURSE_PREPARATION_ENABLED=false PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python - <<'PY'
import dotenv, pytest
dotenv.load_dotenv = lambda *args, **kwargs: False
raise SystemExit(pytest.main(['backend/src/tests/course_preparation/test_contracts.py', '-q', '-ra']))
PY
```

每个模块用自己的测试文件替换上述列表。真实服务脚本显式读取运行配置，凭据不得进入 prompt、文档和提交。当前 shell 的 `npx` 不在 PATH；G 在运行浏览器前定位项目现有 Node/pnpm 工具链，不将命令不存在记录为产品失败。

## 7. 可直接发给工作窗口的启动语

```text
执行 docs/superpowers/plans/2026-09-19-preparation-chain-optimization.md 分配的模块。
先读总计划、00-shared-contracts.md，以及本窗口对应的模块文档；以 G 固定的共同基线为准。
目标是现有备课链路完整运行、参数有真实语义且最终落实。本轮不新增独立资源清单规划阶段。
只修改本模块拥有的文件，遇到共享文件向其负责人提供接口/patch，不覆盖其他窗口工作。
按模块任务实施、验证、提交，并按总计划的统一格式交付，明确哪些结果使用了真实服务。
```

分发时在上述文字后加对应文档路径即可；七份模块文档都包含独立的入口说明。
