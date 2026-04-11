# 后端驱动 Generated Files 恢复实施记录

## 目标

- 右侧生成物列表不再以前端 localStorage 为真源。
- 每次登录或刷新后，由后端会话详情和课程资源接口重建列表。
- 课程资源同步改成“后端快照替换”，避免前端残留旧条目。

## 实施项

1. 移除 `generatedFiles` 的前端持久化，仅保留 `currentConversationId`。
2. 为持久化 hydration 增加 `merge` 兜底，忽略旧 localStorage 中残留的 `generatedFiles`。
3. 新增 `replaceCourseMaterialGeneratedFiles`，按后端课程资源快照替换课程资源来源的生成物。
4. `StudioPanel` 中的课程资源刷新逻辑改为调用课程资源快照替换，而不是逐条 `addGeneratedFile`。
5. 保持会话生成物恢复链继续走后端 `conversation detail -> artifacts -> replaceConversationGeneratedFiles`。

## 验证

- `materials.helpers.test.ts`
- `studioPanel.course-material-sync.test.ts`
- `useStore.persistence.test.ts`
- `chatPanel.restore-preview.test.ts`
- `npm run build`
