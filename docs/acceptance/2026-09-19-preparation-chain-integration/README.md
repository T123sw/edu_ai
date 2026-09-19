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
