# 学习 Agent P5：准备交接与版本连续性

本阶段接通真实准备任务，原始资料保持可读。准备服务当前交付 report 和 quiz；未实现的类型明确返回 unavailable，不转成其他类型或伪报成功。旧课程采用准备侧个人补充 manifest，`course_ready=false`，不把旧课程伪装为通过完整质量门的课程。

## 实现

- 当前持久化用户轮次授权交接，冻结 origin、目标版本和来源内容；解释、否定保存、含糊的修订目标不创建任务。稳定 operation ID 与请求 UUID 保证响应丢失后复用任务。
- 准备 intake 与队列同事务保存；独立 worker 生成、检查、最多两次修复，检查点、租约和取消围栏控制恢复。生产资料保留私有草稿身份，只有检查通过且版本 CAS 成功才写入个人 manifest 与成功事件。
- 共享或个人资料的修订均产生新的私有资料 ID，保留 source_ref；旧引用、完成标记、阅读位置不复制到新身份。
- 学习端只读取已提交个人 manifest；事件消费者按 event ID 去重并排除旧 attempt/revision。通知独立于聊天，不自动切换节点或资料，用户主动打开。
- 模型传输抽取为共享 `app/chat/bounded_completion.py`，保留直接异步调用、截止时间和严格 JSON 语义。学习侧继续提供兼容导出。

## 验证记录

所有 PostgreSQL 测试使用本机隔离数据库的独立 schema，资料保存到临时目录，没有迁移业务数据库。

- 首轮基础适配测试：3 passed，3 skipped（当时未设置隔离 PostgreSQL URL）；跳过不计通过。
- 首轮完整生产/传输测试：28 passed，2 failed。失败揭示新资料排序改变默认选中项，已调整原资料与交付资料排序。
- 第二轮适配/生产测试：SQLite 与 PostgreSQL 合计 24 passed，包括响应重放、取消重试、租约回收、质量失败、版本冲突、个人修订、通知去重与任务提交后的答疑失败。
- 浏览器首轮因后台生成及轮询超过默认 5 秒断言窗口而失败，现场任务仍处于准备中；改用明确的 20 秒异步交付等待窗口。第二轮 1 passed，实际生成与修订均完成，跨节点继续提问且通知不切页面。
- 前端限定范围 TypeScript、ESLint 通过。
- 真实模型 `deepseek-v4-pro`：从自然语言答疑工具提交到真实资料生成、检查、持久化、交付；生成 24.24 秒、修订 21.14 秒，均 succeeded。产物包含变量追踪表、常见误区和新增的变量交换例子；完整回答、交付收据、资料正文见 [real-model.json](artifacts/learning-agent-p5/real-model.json)。此处验证运行与交付路径，不把单次模型质量检查视为事实正确性的保证。

日志目录：[learning-agent-p5](artifacts/learning-agent-p5/)。最终变更后的生产、迁移与传输回归：39 passed（SQLite/PostgreSQL、迁移上下行、唯一 Alembic head），日志 production-final.log。P5 阶段验收完成。完整迁移和总体验收属于 P6。
