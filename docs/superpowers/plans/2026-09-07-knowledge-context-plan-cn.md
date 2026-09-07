# 知识点上下文与澄清：实施计划（Agent B）

状态：B1–B8 已实施，B9 已分层组合验证，完整发布／学生链待验。设计：[B 设计](../specs/2026-09-07-knowledge-context-design-cn.md)；验收：[B 验收](../acceptance/2026-09-07-knowledge-context-acceptance-cn.md)；[并行约定](2026-09-07-frontend-experience-parallel-handoff-cn.md)。

## 文件所有权

B 拥有范围 UI／解析及共享聊天入口：`AIWorkspace.tsx`、`services/teacher/workspaceScope.ts`、`components/teacher/ChatPanel.tsx`、`services/teacher/chatV2.ts`、`store/teacher/useStore.ts`，以及后端 `chat/api/schemas_v2.py`、`application/request_normalizer.py`、`application/reply_service_v2.py`、`application/route_chat_service.py`、`orchestrator/context_builder.py`、`runtime/react_agent.py` 和必要主调度／工具注册入口。完整前缀按仓库现有结构。

新增独立 context／clarification 模块以减少入口改动。C 提交组件和服务接口，B 负责接入共享文件。不要整体重写这些文件。

## 执行步骤

- [x] B1 调用链审计：找到当前流式、非流式、直接生成入口真实运行路径，列出 scope 在哪里丢失；检查已有工作区、课程权限和 memory 工具测试。
- [x] B2 尽早交付契约：将可信 context、澄清输入输出、共享事件映射及 C 接入函数签名写入独立契约模块／交接说明，先做可兼容的小提交。通知 A 现有 hash 参数仍保持稳定。
- [x] B3 先验证语义：为“当前课程＝当前知识点”、无知识点追问、同名节点、非法归属、学生权限编写确定性后端行为测试；让 fake model／spy tool 验证未明确时生成调用次数为零。
- [x] B4 服务端贯通：规范化请求并查可信名称／路径；将范围注入主 Agent 和生成工具，保存结果归属；加入澄清续接和执行前校验。不止修改历史 report workflow 而漏掉当前 runtime。
- [x] B5 前端：实现范围栏和知识点选择，绑定现有 URL 参数；请求冻结上下文，切换清理引用及迟到响应隔离；显示并提交澄清回答。
- [x] B6 工厂透传：将 scope props／payload 的最小补丁交给 C，由 C 写入其拥有的 StudioPanel／GenerationFactory；直接生成和聊天生成使用一致的范围。
- [x] B7 接入 C：在共享协议、ChatPanel 引用区和调度入口接入 C 的修改能力。明确目标资料的修改不重复触发“选择知识点”。统一单一待处理操作与 SSE 完成结果。
- [x] B8 分项测试：运行已有相关测试、新范围行为测试与浏览器用例、构建；真实模型专用数据冒烟，记录输入、识别范围和结果归属。
- [ ] B9 组合验收：合入 A／C 后覆盖“继续 → 当前知识点生成 → 修改 → 追问续接”，回填集成记录。共享集成完成前 B／C 不能宣称整体交付。

## 验证命令

在 `backend/src/` 使用项目既有 Python 环境：

```sh
python -m pytest tests/chat/test_workspace_scope.py tests/chat/test_course_scope_routes.py tests/chat/test_conversation_scope_routes.py
python -m pytest tests/chat/runtime/test_react_agent.py
python -m pytest tests/chat/test_knowledge_context_clarification.py
```

最后一个为计划新增。根据真实主链增加工具参数与结果归属测试。

在 `frontend/`：

```sh
node --import tsx --test "src/services/teacher/workspaceScope*.test.ts"
pnpm exec playwright test tests/e2e/knowledge-context.spec.ts --project=desktop1366
pnpm build
```

计划新增相应测试后再运行。前端默认 `pnpm test` 不覆盖 `tests/frontend`，若修改该目录测试须显式执行；不将构建成功等同于类型检查或全量测试通过。

## 交付与回退

提交应包含契约、实现、行为测试、验收证据。范围校验失败不能为了兼容静默回退整门课程。若新增协议无法兼容，按增量字段和旧响应兼容方式修正；回退 UI 不等于放松服务端归属校验。

## 执行回填

B9 的 A 继续→B 请求范围、B 真实生成→C 真实修改已验证；完整跨课程／账号／发布快照到学生继续学习的端到端组合仍待验证。详见 B 验收表。契约已写入 [实际接口交接](2026-09-07-knowledge-context-contract-cn.md)。共享工作区含其他会话并发变更，B 尚未单独提交，未改写 A/C 分项验收结论。验证应使用证据目录的隔离 runner，避免本地 .env 覆盖测试持久化模式。
