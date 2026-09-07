# B 实际接口交接（2026-09-07）

已实施并完成分层组合验证；详细通过范围与限制见 B 验收文档。

- URL 保留 `scopeType/scopeId/scopeLabel` 及旧别名。
- `app.chat.application.knowledge_context.KnowledgeContextService.prepare(request: ChatRequestV2) -> dict | None`：校验认证主体与会话，解析真实图谱，写 `request.workspace_context`；dict 表示澄清/取消/切换已处理，None 继续调度。
- `ResolvedWorkspaceContext`：`course_id/course_title/scope_type/scope_id/scope_title/scope_path/resolution/explicit_course/update_workspace`。
- JSON 响应与 SSE `result.payload` 均增量带 `workspace_context` 和可选 `clarification`。澄清结构：`status='needs_clarification', operation_id, question, candidates[{scope_id,scope_title,scope_path}]`。回答仍走 question + conversation_id，服务端恢复原来源和生成意图。
- 一个待操作槽：`conversation_storage.state.pending_operation`。通用字段 `id/kind/owner/course_id/scope_id`。B 的 `kind='workspace_scope'` 用 request 保存原请求；C 的 `kind='artifact_revision'` 由 B 用 `revision_pending` 包装 C 返回的 pending 原样数据。B 不消费 revision 回答。
- 已读 C 的 artifact-revision-integration-cn.md；B 将消费其中 ArtifactRevisionService.run 签名并在共享 reply/reply_stream 调度接入。C 不需修改共享入口。
- StudioPanel 已接收 workspaceScope；请 C 核对其 GenerationFactory 各直接提交 scope_type/scope_id 透传与缺范围处理；来源选择不可改变主题。B 已修复 Agent AI 课堂 handler 的 scope 透传。
- 工具执行前校验入口：`validate_generation_scope(request)`，通用 executor 调用；v2 请求必有可信 context。

## B 接入更新

已接入 C ArtifactRevisionService、EditReference、RevisionResult 和 subscribeRevisionIntent。注意 C components.tsx 当前使用 `user?.id`，但 AuthUser 实际字段是 `username`；请 C 改为 `user?.username`，否则按钮不会出现。B 的订阅使用 username 校验。B 使用 `artifact_revision` 增量字段承载 C outcome；旧成果保存分支对 revision 跳过，避免新版被再次覆盖。

直接生成 API 已统一调用 `resolve_direct_workspace(payload, course_storage)`：有效知识点/唯一匹配主题/显式整课才能提交；不明确返回 HTTP 422 `detail.code=needs_clarification` 和可读 message，未创建 job。请 C 在工厂错误区显示此 message，并提示使用 B 范围栏选择知识点。共享聊天请求新增可选 request_id 用于同请求重试复用 C operation_id。

真实模型审计发现主 planner 的任务主题仍从原始“当前课程”字符串提取，已改为消费可信 context；draft_outline 也受同一执行前校验保护。顺带修复自检重试在 assistant/tool 调用之间插 system 提示造成模型 HTTP 400 的问题，追加了协议序列行为测试。AI 课堂独立路由的范围校验由 B 在 app/api/courses.py 完成。

C 报告的 undefined→真实课程初始化竞态已由 B 修复：pendingRevisionIntent 只在其 source_course_id 与当前课程匹配、且当前 workspace 初始化 epoch 完成后消费；finally 先验当前 workspace/epoch 再引用和 focus。关闭引用、新建对话和账号变化清除暂存，不定时重放。C 的两 viewport 浏览器用例已通过。

C 的 f73cd1ca 交付后，B 真实组合验收发现“增加一句‘验收标记’”中的引号文本被当作竞争资料标题，导致已明确引用仍追问。B 在最终集成中做了窄修复：目标标题识别限定为书名号或紧跟修改/编辑动词的引号；普通替换文本不覆盖已选引用。保留资料标题冲突澄清行为，补共享行为测试。

历史/恢复接入已新增：POST `/api/chat/v2/artifacts/revisions/read`、`/restore`，请求 `{reference,version,operation_id?}`；恢复必须携当前 reference.version_id 和 operation_id。服务端同时查课程权限和 C 资料所有权。共享结果的“恢复旧版”打开 RevisionHistoryDialog，先读指定历史版并预览，再恢复为新版本。新增取消接口 POST `/operations/{operation_id}/cancel?conversation_id=...`，切换范围/关闭引用只取消对应主体、会话和 operation_id 的待操作。

## 资料修改 Skill（2026-09-07 后续）

应用运行时已接入 [edu-artifact-revision](../../../../backend/skills/edu-artifact-revision/SKILL.md)。ArtifactRevisionService 从 backend/skills 明确路径加载 SYSTEM_PROMPT，缺失时失败且不写资料；不依赖旧报告工作流或全局技能选择。

模型动作互斥为 answer／question／edits。服务新增 status=answered，共享 reply／SSE 映射 action=artifact.read，返回消息和原版本引用、空 artifacts，不生成修改成功卡。澄清期间插入只读问答保留原 pending，返回 awaiting_clarification=true 供前端保留取消操作绑定；不会将阅读问题写入原修改意见。仍由服务执行原文匹配、结构校验、冲突和幂等保存，校验错误仅允许一次模型修正。

真实隔离样本已验证先读后改，详见 [Skill 接入验证](../acceptance/2026-09-07-artifact-revision-skill-acceptance-cn.md)。这不替代 C 各类型使用及发布链剩余验收。
