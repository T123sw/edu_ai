# P6 验证命令

2026-09-17；工作目录仓库根，除标明 frontend 的命令外。Python 为 `/home/zxqs_ep/miniforge3/envs/edu-ai/bin/python`，PATH 同环境。隔离 PostgreSQL URL 通过 `LEARNING_TEST_DATABASE_URL` 传入；每次测试使用独立 schema，禁止指向业务库。真实模型脚本读取已有运行配置，不把密钥写入日志。

```bash
PYTHONPATH=backend/src python -m pytest backend/src/tests/self_learning backend/src/tests/database/test_alembic_revision_chain.py -q
PYTHONPATH=backend/src python -m pytest backend/src/tests/self_learning/test_model_adapter.py backend/src/tests/self_learning/test_agent_runtime.py backend/src/tests/self_learning/test_preparation_adapter.py -q
PYTHONPATH=backend/src python -m pytest backend/src/tests/test_self_learning.py -q
PYTHONPATH=backend/src LEARNING_LIVE_ACCEPTANCE=1 python -m pytest backend/src/tests/self_learning/test_live_agent.py -q
PYTHONPATH=backend/src python backend/src/scripts/verify_learning_backup.py
PYTHONPATH=backend/src python backend/src/scripts/verify_learning_performance.py
```

在 frontend 中，以下 Playwright 配置按顺序运行（共享 8016/5196 端口，不能并发）：

```bash
pnpm exec playwright test -c playwright.learning-session.config.ts
pnpm exec playwright test -c playwright.learning-progress.config.ts
pnpm exec playwright test -c playwright.learning-agent.config.ts
pnpm exec playwright test -c playwright.learning-enrichment.config.ts
pnpm exec playwright test -c playwright.learning-preparation.config.ts
pnpm exec playwright test -c playwright.learning-acceptance.config.ts
pnpm exec playwright test -c playwright.learning-real.config.ts
pnpm exec tsc -p tsconfig.self-learning.json
pnpm exec eslint src/liveLearning src/selfLearning
pnpm exec tsx --test src/liveLearning/learningClient.test.ts src/liveLearning/readingContext.test.ts src/liveLearning/learningState.test.ts
```

独立检出验证：在 P5 提交 `2e81a8c2` 的 worktree 应用 P6 暂存区完整补丁，使用该目录的 PYTHONPATH 运行 test_rollout_migration.py、test_migration.py，共 16 项通过；不带入主工作区其他未提交文件。此前 fresh-p5-checkout.log 是纯 P5 提交的生成/修订验证。

`*-first`、`*-second` 等为历史尝试。最终依据 backend-full-final、protocol-final、fresh-p6-index、browser-*-final、real-browser-final、real-boundaries-repaired、performance 与 backup-cli。失败日志为修复依据保留，不代表最终结果。
