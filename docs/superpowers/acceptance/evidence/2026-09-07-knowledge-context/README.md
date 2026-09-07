# B 验证证据（2026-09-07）

详细结论见上级 B 验收表。live-context.json 与 live-bc-revision.json 是最终真实模型结果；initial 文件为失败排错历史。所有模型资料属于合成课程及账号。未验证外部 worker、真实生产数据库、完整师生发布链。

后端从 backend/src 运行（使用 edu-ai 环境）：

```sh
python ../../docs/superpowers/acceptance/evidence/2026-09-07-knowledge-context/run_isolated_tests.py tests/chat/test_knowledge_context_clarification.py tests/chat/test_reply_service_v2.py tests/chat/test_reply_service_v2_stream.py tests/chat/test_workspace_scope.py tests/chat/test_course_scope_routes.py tests/chat/test_conversation_scope_routes.py tests/chat/runtime/test_react_agent.py tests/chat/runtime/test_phase3_guided.py tests/chat/test_artifact_revision.py tests/chat/test_generation_context_builder.py tests/chat/test_schemas_v2.py tests/chat/test_request_normalizer.py tests/chat/test_report_generation_fallback.py tests/test_generation_task_handlers.py -q
```

隔离 runner 禁止 .env 覆盖，使用临时 JSON 目录和 SQLite agent 状态。不要直接在生产持久化配置上运行该回归。

前端从 frontend 运行：

```sh
node --import tsx --test src/services/teacher/workspaceScope.test.ts src/components/teacher/chatHistoryRecovery.test.ts
PLAYWRIGHT_PORT=5182 pnpm exec playwright test tests/e2e/knowledge-context.spec.ts tests/e2e/artifact-revision.spec.ts tests/e2e/home-resume.spec.ts --project=desktop1366 --output=/tmp/edu-b-e2e
pnpm build
pnpm exec tsc --noEmit
```

浏览器使用模拟 API。最后 UI 修正后单独重跑 B 五项并留存 final-e2e.log 和 1366／390 截图。真实模型脚本位于 backend/src/tests/chat/knowledge_context_live_smoke.py 及 knowledge_context_revision_live_smoke.py；后者读取前者临时落库产物，需保留运行目录。模型配置来自本机配置，证据不包含凭据。
