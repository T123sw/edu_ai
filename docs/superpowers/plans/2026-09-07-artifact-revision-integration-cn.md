# C → B 实际接入契约与交付

日期：2026-09-07。C 模块可交付；整体验收未完成。最终测试与剩余项见 [C 验收](../acceptance/2026-09-07-artifact-revision-acceptance-cn.md)。本文件所在 C 提交可用 `git log -1 -- 本文件路径` 定位。

## 文件所有权与存储

C 新增 `backend/src/app/artifact_revision/{__init__,service,adapters,storage}.py`、`frontend/src/stitch/artifactRevision/{intent.ts,components.tsx}` 及分项测试。修改 generation 工厂、StudioPanel、CourseResources 和 artifact_reference 领域类型。不修改 ChatPanel、chatV2、useStore、共享 schema/route/runtime。

版本复用 Material/MaterialVersion 和 JSON manifest，无 DDL 迁移或新数据库。JSON 增量字段为 revision_history/revision_operations/revision；SQL 在同一事务内条件 UPDATE 当前版本并插入 MaterialVersion。原资料 ID 稳定，原发布副本/发布指针不更新，旧文件不覆盖。C 的 JSON 修改加线程＋进程间锁；旧手动写入器未共享新增进程锁，混合多进程并发仍未完整保证。

## 后端实际签名

```python
ArtifactRevisionService(manager, llm).run(
    *, owner_user_id: str, conversation_id: str,
    course_id: str | None, question: str, operation_id: str,
    artifact_reference: ArtifactReferencePayload | dict | None = None,
    pending: dict | None = None, scope_id: str | None = None,
    session_artifacts: list[dict] | None = None,
) -> dict
```

- owner 必须来自认证；course_id 必须是 B 已授权的当前课程。引用可使用 source_course_id，C 再校验 owner_user_id 与认证主体相等、visibility=private；拒绝直接改发布副本。新页面 scope 不覆盖引用原归属。
- status：`not_applicable / needs_clarification / completed / conflict / failed`，均含 message。只有 not_applicable 可继续原生成/聊天链。
- 追问返回 pending、candidates；B 将 pending 放入唯一 `pending_operation(kind=artifact_revision, revision_pending=...)`，不能信任客户端传入 pending。C 校验其中 owner_user_id/conversation_id。
- candidates 含稳定 artifact_id/artifact_type/version_id/source_course_id/title；自然语言歧义候选另含 created_at/scope_id，供 UI 区分。数字序号续接已有候选。
- 完成返回 artifact_reference、artifact、summary、changes、base_version_id。artifact 为聊天产物：`version` 是 `{version_id,version_number,root_artifact_id,parent_artifact_id}`，整数存储版本为 `material_version`；数据库 version 仍为整数。B 当前的 `{...artifact,...reference}` 可直接消费。
- changes：`{path:(str|int)[],before:str,after:str}[]`，取实际应用的改动，不使用模型口头摘要。相同操作重试返回同一版本。
- operation_id 首次提交创建，网络重试必须复用，下一轮修改必须新建。B 已增加 request_id；完整 HTTP 重试尚未验收。
- conflict/failed 保留意见；以最新版重试需刷新 pending.reference.version_id，同时更新 pending.operation_id，不应一直沿用旧基准版本。重试同一失败操作可复用原编号。

其他公开方法：

```python
read_version(*, owner_user_id, course_id, artifact_type, artifact_id, version)
restore(*, owner_user_id, course_id, artifact_type, artifact_id,
        version, base_version, operation_id)
```

恢复创建新当前版本，不抹去历史。B 尚需提供历史/恢复 HTTP 路由及 UI 调用。不要将新版结果送旧生成保存分支再次落库；B 已跳过该分支。

## 前端实际接口

`intent.ts` 导出 `ArtifactRevisionReference`、`RevisionIntent{reference,ownerUserId}`、`createRevisionIntent(material,ownerUserId)`、`dispatchRevisionIntent(intent)`、`subscribeRevisionIntent(listener): unsubscribe`、`clearRevisionIntent()`。ownerUserId 对应当前 AuthUser.username。意图暂存只在模块内，支持资源页跳转，不用 localStorage/URL 存引用。

`components.tsx`：

- `RevisionButton({material,disabled?})`：校验用户、资料类型、服务端版本；只选择引用并导航 AI 页。
- `GenerationRevisionButton({courseId,materialType,materialId})`：读取真实资料详情后展示按钮，不猜测 v1。
- `EditReference({reference,onClose})`。
- `RevisionResult({reference,summary,changes,onView,onContinue,onRestore?})`。

B 已挂载服务和这些组件。C 已传递 `StudioPanel.workspaceScope → GenerationFactory → buildGenerationRequest`，scope_type/scope_id 最后覆盖 serializer 的旧课程默认值。共享 ApiError 会显示 B 返回的范围澄清 message；工厂保留表单且捕获提交异常。

## B 必须完成的初始化修复

最终双尺寸 Playwright 测试仍失败：1366px 引用曾显示但发送 payload 缺 artifact_reference；390px 引用消失。单次 1366px 曾通过不能视作竞态解决。C 的 microtask 暂存交付仅降低复现率。

根因：AIWorkspace 首次以 selectedCourse undefined 挂载 ChatPanel，真实 courseId 到达后再次初始化并清空引用；ChatPanel 的 `!historyLoading` 初始值不能证明课程初始化结束。

请在 B 所有的 ChatPanel 中：

1. 保存 pendingRevisionIntent，直到 `courseId === intent.reference.source_course_id` 且该课程历史初始化真正结束。
2. 在对应初始化 finally/完成状态提交处应用引用及 focus；不要在初始 historyLoading=false 的 effect 中立即清空 pending。
3. 用户关闭引用、新会话、切换账号时清空暂存。不要定时重放用户已经关闭的引用。

复现命令：`PLAYWRIGHT_PORT=5183 pnpm exec playwright test tests/e2e/artifact-revision.spec.ts --project=desktop1366`。测试用真实 React 页面＋mock SSE；资源按钮不提交任务，发送时断言正确 ID/版本/课程。

## 验证与剩余边界

- 后端最终记录：78 passed（新增模块、JSON 多进程、SQL repository、旧报告回归、共享 reply/SSE 按钮/自然语言四组合）。SQL 使用隔离 SQLite，真实 PostgreSQL 待验证。
- 前端 intent 与八类工厂 scope：10 passed；Vite build passed；全项目 tsc 未通过，C 业务文件无诊断。
- 专用临时资料真实模型：报告/习题均自动保存 v2，报告独特段落不变。
- 各类型都实现原文读取、精确改动和结构校验；游戏生成新版独立 HTML；课堂讲解变化清除该 Action 的旧音频指针，保留旧版音频。
- 其余类型完整预览/评分/交互/课堂播放及指定版本导出、学生任务快照整链路、历史恢复 UI 尚未验收。
- 原文完整读取，不静默截断；超出模型上下文时失败保留原文，章节分段加载尚未实现。

回退：关闭新增入口/停用共享 ArtifactRevisionService，保留已保存版本、revision_history、MaterialVersion 和旧导出。不需要回滚数据库 schema。
