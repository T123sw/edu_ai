# G 集成验收工作记录

状态：实施中，不能作为完整课程交付验收通过证明。共同基线见 [BASELINE.md](BASELINE.md)。

新增 `verify_preparation_full_e2e.py` 使用真实 HTTP 提交、轮询实际后台任务，并只读指定 PostgreSQL 采集检查点、动作/模型回执、规格、正文、预算和 manifest，最后从学习端读取确切版本。脚本不会调用 runner、切 mock、迁移数据库或修改业务配置。业务预期失败与测试通过分别记录。所有输出目录必须是新目录。

## 隔离应用

专用数据库名必须符合 `edu_ai_preparation_test_[a-z0-9_]+`。由测试负责人预建并迁移，禁止提供业务库。私有测试配置必须显式提供：

- `PREPARATION_TEST_DATABASE_URL`、`DATABASE_URL`、`LEARNING_TEST_DATABASE_URL`：完全相同的专用 PostgreSQL 地址。
- `PREPARATION_VALIDATION_ROOT`：绝对路径，末级目录名以 `preparation-validation-` 开头。
- `STORAGE_ROOT`、`COURSE_STORAGE_ROOT`、`RUNTIME_CONFIG_ROOT`、`TASKS_DB_PATH`：该目录下的绝对路径。
- `PREPARATION_TEST_CREDENTIALS_FILE`：私有 JSON，含预建测试用户的 `username`、`password`；用户名以 `prep-test-` 开头。
- 真实服务配置、持久化模式及学习端开关按测试应用配置显式提供。不要把私有配置、认证信息、上传原件或 trace 提交 Git。

在已提交、干净的集成 worktree 启动（不得自动从业务 `.env` 重新加载）：

```bash
PREPARATION_VALIDATION_ENV_FILE=/private/test.env PYTHONPATH=backend/src \
  /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python -m uvicorn \
  scripts.preparation_validation_server:create_app --factory --host 127.0.0.1 --port 8027
```

factory 使用实际 `create_app()` 和耐久 worker，启动校验库与存储身份。仅该测试入口提供认证后的 `/api/preparation-validation/identity`；生产路由未新增调试端点。脚本核对 server/client SHA、数据库身份、认证身份与 worker 状态。

```bash
PYTHONPATH=backend/src /home/zxqs_ep/miniforge3/envs/edu-ai/bin/python \
  backend/src/scripts/verify_preparation_full_e2e.py --env-file /private/test.env \
  --base-url http://127.0.0.1:8027 --database-url-env PREPARATION_TEST_DATABASE_URL \
  --scenario uploaded-course --repeat 3 --output-dir /private/new-e01-result
```

退出码：0 自动化检查通过；1 失败或 E01 未满足三轮；2 preflight/scenario `not_run`。即使自动化通过，语义评估和浏览器也独立标记，不等于整项 G 验收。

E01/E02/E03/E10 已有真实请求驱动；E04–E09 需要对应领域接口与场景驱动，目前明确 `not_run`。场景定义见 `backend/src/scripts/preparation_cases/scenarios.json`，不得将缺驱动记录成 passed。

## 浏览器

使用同一 SHA 的正式前端构建与专用代理后端，设置 `PREPARATION_FRONTEND_URL`、`PREPARATION_TEST_CREDENTIALS_FILE`、`PREPARATION_TEST_UPLOAD`（真实 DOCX），运行：

```bash
PATH=/home/zxqs_ep/miniforge3/envs/edu-ai/bin:$PATH \
  frontend/node_modules/.bin/playwright test --config frontend/playwright.preparation-chain-real.config.ts
```

每个视口从页面生成独立新任务；不复用历史课程。保存截图、trace、浏览器/网络错误；需要音频时设置 `PREPARATION_REQUIRE_AUDIO=1`，自动检查媒体解码与时钟推进。人工抽听、题目先于答案和语义效果仍需单独记录，不能从点击或截图推断通过。

## 当前验证边界

- 基线研究测试：40 passed / 2 skipped（当时未提供测试库）。
- 新增验收工具契约测试：20 passed，无真实模型。
- Playwright `--list`：桌面/窄屏两项加载成功，非浏览器执行。
- 完整 PostgreSQL 回归、A–F 最终集成与真实服务/浏览器结果后续填写。
- 独立资源组合规划继续暂缓。

前端专用构建完成后，在构建目录写入 `preparation-build.json`，内容为 `{"code_sha":"实际构建SHA"}`；浏览器会与当前 Git 和后端同时核对，缺失时失败。已定位工具链：Node v22.23.2、pnpm 10.28.2（`/home/zxqs_ep/miniforge3/envs/edu-ai/bin`）。

## 2026-09-19 首批集成结果

| 模块原 SHA | 集成 SHA | 范围 |
| --- | --- | --- |
| A e3d3ce6b / d7d26fc8 / c264070f | b2f61307 / c7705989 / 89a97e27 | 参数上下文、v1/v2 兼容及交接 |
| D ee818810 | 75b9ee49 | 独立的历史共享报告策略修复，D 其余生成改动未交付 |
| C 868320bb / f115f629 / 8864ee7c | d2d912a5 / 591d14d6 / ff3522d9 | 文档取消、持久正文分页、上下文有界 |

A 的计划文档发生 add/add 冲突：保留 A 自己交付的复选框与验收记录，其他模块计划未改。C 的快照基线 `1c1b9fd0` 与 G0 内容重复，未重复挑入；仅集成其领域实现提交。

- 从 `33681583` 启动的基线回归对准备套件与 `chat/test_reviewed_report.py`：324 passed / 3 failed / 5 skipped，351.79 秒；运行期间另行提交了 G 工具改动 `cdff0ef8`，因此该组不作为同一最终 SHA 的验收证明；5 项跳过是 SQLite 参数下仅 PostgreSQL 适用的竞争用例，PostgreSQL 对应项已运行。
- `75b9ee49` 对 `test_reviewed_report.py`、`test_report_review_policy.py`、`test_generation_context.py`、`test_spec_compatibility.py`：76 passed，10.33 秒；历史三个报告失败全部修复。
- `d2d912a5` 对文档适配、解析取消、MinerU 格式和 G 验收工具：73 passed，7.14 秒。
- 已在专用端口 55447 的专用数据库执行 Alembic 正向迁移。此为测试库，不涉及业务迁移。
- E03 第一次使用错误的测试模型绑定，1/1 失败（BUDGET_EXHAUSTED，4 次失败模型尝试）。修正私有配置中 `ANSWER_LLM_API_BASE` / `ANSWER_LLM_API_KEY` / `ANSWER_LLM_MODEL` 后，第二次实际业务结果符合预期，但 B 回执契约尚缺 phase，所以严格验收仍 0/1 通过。两种原因分别记录，不合并成产品稳定性失败率。
- 第二次 E03：58.22 秒，8 次计费动作（其中包括来源动作，不能等同模型调用数）、45692 tokens，未交付课程。不能与历史完整课性能比较。
- 原始运行数据位于本机 `/tmp/preparation-validation-g-20260919`；提交的 [账本](ledger.json) 与 `evidence/` 仅含脱敏概要。浏览器完整执行及最终 SHA 回归尚未完成。

## 当前交接点：G 尚未完成

已集成 A/C/D/E/F 的可引用代码提交；B 原工作区仍是未提交状态，未复制、提交或覆盖其在途实现。因此未启动已知缺生成网关的 E01/E02/E10，以免浪费真实调用并制造必然失败。B 主入口、统一阶段回执及 F 检查点接线必须以 B 交付的提交继续集成。

后续已合入：

| 模块原 SHA | 集成 SHA | 范围 |
| --- | --- | --- |
| C 73d6eed3 / 1ad95410 | 64c55814 / 689ebeff | 来源耗时回执及独立真实格式/来源证据 |
| D 3157cb4f | edd7b031 | 结构化教学参数、逐项审阅、候选恢复 |
| E cc234811 / 21195202 / 21cdfea0 | 2e256de0 / c4a3bad1 / 8b4248b6 | 分镜、真实题目反馈、v1 恢复、组件证据 |
| F debc7960 / 7da7b9b8 | 7b0afe9d / 4144bddb | 授权候选检查点、恢复分类、精确交付与交接 |

追加验证（各组有重叠，不能相加）：

- C 快照/研究上下文/研究流程/Harness/健壮性：85 passed，14.64 秒。
- D/F 生成约束、审阅反例、恢复、定位、质量、交付、局部 manifest、学习回读及共享报告/资源：176 passed / 10 skipped，221.02 秒。6 项跳过是 opt-in 真实模型场景，4 项是 SQLite 参数下的 PostgreSQL 行锁用例。测试期间后续提交仅涉及 G 工具/证据，不作为最终全链路 SHA 证明。
- E 兼容补丁、渲染、C 来源和 G 工具：102 passed，4.40 秒。
- G 最新契约：24 passed / 6 skipped，11.38 秒。6 项是 report/quiz/classroom × SQLite/PostgreSQL 的真实 handler 参数/检查点接线测试，明确因 B 未集成跳过；拦截的是最终生成器，并非真实内容质量验收。
- Node v22.23.2 / pnpm 10.28.2 正式前端构建通过，19.99 秒；现存大 bundle 警告保留。Playwright 两个视口用例可加载；没有完整真实浏览器通过记录。

三个层次的结论：

| 代码已接线 | 自动化已验证 | 真实服务/浏览器已验证 |
| --- | --- | --- |
| A 参数/规格、C 文件/来源、D 内容与审阅、E 分镜、F 验收/恢复已挑入；B 主 handler 接线仍缺 | 上述模块套件和 G 工具测试通过；B 相关接线跳过 | HTTP→实际 worker→真实模型/MinerU 的 E03 基线诊断已运行；业务不足正确阻断，但回执缺 phase，严格验收失败；完整课程和生产浏览器未验证 |

仍需执行：B 合入与三类生成器的 checkpoint、phase/Skill、实际 payload 检查；E01 连续三次完整交付；E02/E10；E04–E09 的专项驱动实现和实跑；真实语义参数对照；桌面/窄屏全部资源与播放；同一最终源码 SHA 的综合回归。不能把这些待办全部归因于 B，G 的六个专项驱动本身也还未实现。

E 的窄屏流程图文字可读性、真实图片/TTS、音频实测和人工抽听仍是明确边界。其已提交浏览器证据使用确定性组件夹具，不能冒充 G 的真实课程验收。F 没有扩展 manifest locator schema，也没有新增数据库字段；本轮 A–F 当前提交无新迁移编号需求，旧规格/候选兼容由各模块测试覆盖。

开发工作区、文档和提交均保留，未部署业务服务。测试数据库和私有证据目录保留供后续恢复；端口服务会在交接时停止。

最后一次仅 G 工具的快速重跑：24 passed / 6 skipped，3.28 秒；该次没有提供 PostgreSQL URL，所以 3 项在数据库夹具处跳过，另 3 项为 SQLite 下 B 尚缺。先前显式 PostgreSQL 的 G 门禁运行仍为 24 passed / 6 skipped，全部 6 项都明确停在 B 缺失检查。两次边界分别列明，不替换原结果。
