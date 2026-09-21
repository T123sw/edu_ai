# 复验命令与证据边界

使用专用环境文件（权限 0600，含测试身份及隔离数据库配置，不提交仓库）启动：

```sh
PREPARATION_VALIDATION_ENV_FILE=/path/to/private/test.env PYTHONPATH=src python -m uvicorn scripts.preparation_validation_server:create_app --factory --host 127.0.0.1 --port 8027
```

在仓库根目录运行真实接口测试；三次独立任务以首轮失败停止，未启动轮次不算通过：

```sh
PYTHONPATH=backend/src python backend/src/scripts/verify_preparation_full_e2e.py --env-file /path/to/private/test.env --base-url http://127.0.0.1:8027 --scenario uploaded-course --repeat 3 --stop-on-failure --output-dir /path/to/private/e01
```

负向场景分别将 scenario 换为 `blocked-course`、`cancel-inflight-model`，repeat 为 1。预期业务失败/取消与测试是否通过分开记录。

浏览器在 frontend 目录运行，专用 5199 前端代理指向 8027，提供本次正式构建：

```sh
PREPARATION_FRONTEND_URL=http://127.0.0.1:5199 PREPARATION_TEST_CREDENTIALS_FILE=/path/to/private/credentials.json PREPARATION_TEST_UPLOAD=/path/to/private/tool-calling.docx pnpm exec playwright test -c playwright.preparation-chain-real.config.ts --max-failures=1
```

每个视口创建新课程；桌面失败时窄屏不启动。这里未设置 `PREPARATION_REQUIRE_AUDIO=1`，不能据播放断言宣称 TTS 已验收。

准备与共享回归：

```sh
PYTHONPATH=backend/src python /path/to/private/main-guard-pytest-launcher.py -q backend/src/tests/course_preparation backend/src/tests/chat/test_reviewed_report.py backend/src/tests/chat/test_report_review_policy.py backend/src/tests/chat/test_harness_resources.py backend/src/tests/test_generation_task_handlers.py backend/src/tests/test_mineru_cloud_formats.py backend/src/tests/test_classroom_validation.py
```

启动器在 `if __name__ == '__main__'` 内调用 pytest，禁用默认 dotenv 并移除业务 `DATABASE_URL`，显式提供专用 `PREPARATION_TEST_DATABASE_URL` 和 `LEARNING_TEST_DATABASE_URL`。不可把测试指向业务库。

学习域回归覆盖 `backend/src/tests/learning`、`backend/src/tests/self_learning`、`backend/src/tests/test_self_learning.py`。报告中保留其实际被测提交，未将跨提交的回归成绩写成同一最终 SHA 全部重跑。

原始 provider 回执、认证信息及浏览器 trace 留在本机 `/tmp/preparation-validation-recovery-20260921`。公开账本只含合成任务标识、状态、哈希、模型名和计量。历史 `559d1dda` 浏览器 trace 未完整归档，仍保留其业务失败/取消数据，不宣称存在完整截图录像。
